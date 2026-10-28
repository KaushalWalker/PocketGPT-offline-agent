"""Minimal Ollama API client restricted to the local Windows machine."""

from __future__ import annotations

import http.client
import json
import re
import socket
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Mapping

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 11434


class OllamaError(RuntimeError):
    """Base exception for local inference errors."""


class OllamaUnavailableError(OllamaError):
    """Raised when the local Ollama service cannot be reached."""


class ModelUnavailableError(OllamaError):
    """Raised when a requested model is missing or is a cloud-only model."""


class OllamaAPIError(OllamaError):
    """Raised for malformed responses or other Ollama API errors."""


@dataclass(frozen=True)
class LocalModel:
    name: str
    size_bytes: int | None = None
    capabilities: tuple[str, ...] = ()


def model_supports_capability(model: LocalModel | None, capability: str) -> bool:
    """Check a capability against the canonical capability list from `/api/tags`."""
    return model is not None and capability.casefold() in {
        item.casefold() for item in model.capabilities
    }


def is_cloud_model(name: str) -> bool:
    """Ollama cloud-tagged models must never be used by this application."""
    return name.strip().lower().endswith(":cloud")


def local_models_from_payload(payload: Mapping[str, object]) -> list[LocalModel]:
    models = payload.get("models", [])
    if not isinstance(models, list):
        raise OllamaAPIError("Ollama returned an invalid model list")
    result: list[LocalModel] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name or is_cloud_model(name):
            continue
        size = item.get("size")
        raw_capabilities = item.get("capabilities", [])
        capabilities = (
            tuple(value for value in raw_capabilities if isinstance(value, str))
            if isinstance(raw_capabilities, list)
            else ()
        )
        result.append(
            LocalModel(
                name=name,
                size_bytes=size if isinstance(size, int) else None,
                capabilities=capabilities,
            )
        )
    return result


_THINK_TAG = re.compile(r"</?\s*think\b[^<>]*>", re.IGNORECASE)


class _ThinkingContentFilter:
    """Stream message.content while withholding tagged internal reasoning."""

    def __init__(self) -> None:
        self.buffer = ""
        self.inside_thinking = False

    @staticmethod
    def _partial_tag_start(text: str) -> int | None:
        start = text.rfind("<")
        if start < 0:
            return None
        suffix = text[start:].casefold()
        if suffix.startswith(("<think", "</think")):
            return start
        if "<think>".startswith(suffix) or "</think>".startswith(suffix):
            return start
        return None

    def feed(self, text: str, *, final: bool = False) -> Iterator[str]:
        self.buffer += text
        while True:
            match = _THINK_TAG.search(self.buffer)
            if match:
                before_tag = self.buffer[: match.start()]
                is_closing_tag = match.group().lstrip().startswith("</")
                if not self.inside_thinking:
                    malformed_open = (
                        re.search(r"<\s*think\b[^>]*$", before_tag, re.IGNORECASE)
                        if is_closing_tag
                        else None
                    )
                    safe_text = (
                        before_tag[: malformed_open.start()]
                        if malformed_open
                        else before_tag
                    )
                    if safe_text:
                        yield safe_text
                self.inside_thinking = not is_closing_tag
                self.buffer = self.buffer[match.end() :]
                continue

            partial_start = self._partial_tag_start(self.buffer)
            if self.inside_thinking:
                self.buffer = self.buffer[partial_start:] if partial_start is not None else ""
            elif final:
                safe_text = self.buffer if partial_start is None else self.buffer[:partial_start]
                self.buffer = ""
                if safe_text:
                    yield safe_text
            elif partial_start is None:
                safe_text, self.buffer = self.buffer, ""
                if safe_text:
                    yield safe_text
            else:
                safe_text, self.buffer = self.buffer[:partial_start], self.buffer[partial_start:]
                if safe_text:
                    yield safe_text
            return


def _read_stream_content(
    lines: Iterable[bytes], *, on_done: Callable[[dict[str, object]], None] | None = None
) -> Iterator[str]:
    content_filter = _ThinkingContentFilter()
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise OllamaAPIError("Ollama returned malformed streaming data") from exc
        if not isinstance(event, dict):
            raise OllamaAPIError("Ollama returned an invalid streaming event")
        error = event.get("error")
        if error:
            message = str(error)
            if "not found" in message.lower() and "model" in message.lower():
                raise ModelUnavailableError(message)
            raise OllamaAPIError(message)
        message = event.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content:
                yield from content_filter.feed(content)
        if event.get("done"):
            yield from content_filter.feed("", final=True)
            if on_done is not None:
                on_done(event)
            return
    yield from content_filter.feed("", final=True)


class OllamaClient:
    """Calls only 127.0.0.1:11434; proxy environment settings are ignored."""

    def __init__(self, *, timeout: float = 300):
        self.timeout = timeout
        self.last_metrics: dict[str, int | str] = {}

    @staticmethod
    def _new_connection(timeout: float) -> http.client.HTTPConnection:
        return http.client.HTTPConnection(LOCAL_HOST, LOCAL_PORT, timeout=timeout)

    @staticmethod
    def _encode_payload(payload: Mapping[str, object] | None) -> bytes | None:
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")

    @staticmethod
    def _raise_http_error(status: int, body: bytes) -> None:
        text = body.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("error"):
                text = str(parsed["error"])
        except json.JSONDecodeError:
            pass
        if status == 404 and "model" in text.lower():
            raise ModelUnavailableError(text or "The selected model is not installed.")
        raise OllamaAPIError(f"Ollama returned HTTP {status}: {text[:500]}")

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, object]:
        connection = self._new_connection(self.timeout if timeout is None else timeout)
        try:
            body = self._encode_payload(payload)
            headers = {"Content-Type": "application/json"} if body is not None else {}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read()
            if not 200 <= response.status < 300:
                self._raise_http_error(response.status, response_body)
            try:
                parsed = json.loads(response_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise OllamaAPIError("Ollama returned invalid JSON") from exc
            if not isinstance(parsed, dict):
                raise OllamaAPIError("Ollama returned an invalid JSON response")
            return parsed
        except (OSError, http.client.HTTPException, socket.timeout) as exc:
            raise OllamaUnavailableError(
                "Cannot reach local Ollama at 127.0.0.1:11434. Start Ollama and try again."
            ) from exc
        finally:
            connection.close()

    def list_models(self, *, timeout: float = 2) -> list[LocalModel]:
        payload = self._request_json("GET", "/api/tags", timeout=timeout)
        return local_models_from_payload(payload)

    @staticmethod
    def _validate_model(model: str) -> None:
        if not model.strip():
            raise ModelUnavailableError("Choose an installed local model first.")
        if is_cloud_model(model):
            raise ModelUnavailableError(
                "Cloud models are disabled. Choose a model installed on this computer."
            )

    def chat_once(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: Mapping[str, object] | None = None,
        think: bool | None = None,
        format: str | Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        self._validate_model(model)
        payload: dict[str, object] = {"model": model, "messages": messages, "stream": False}
        if options:
            payload["options"] = dict(options)
        if think is not None:
            payload["think"] = think
        if format is not None:
            payload["format"] = dict(format) if isinstance(format, Mapping) else format
        result = self._request_json("POST", "/api/chat", payload)
        error = result.get("error")
        if error:
            text = str(error)
            if "not found" in text.lower() and "model" in text.lower():
                raise ModelUnavailableError(text)
            raise OllamaAPIError(text)
        return result

    def stream_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        options: Mapping[str, object] | None = None,
        think: bool | None = None,
        format: str | Mapping[str, object] | None = None,
    ) -> Iterator[str]:
        self._validate_model(model)
        payload: dict[str, object] = {"model": model, "messages": messages, "stream": True}
        if options:
            payload["options"] = dict(options)
        if think is not None:
            payload["think"] = think
        if format is not None:
            payload["format"] = dict(format) if isinstance(format, Mapping) else format
        self.last_metrics = {}

        def capture_metrics(event: dict[str, object]) -> None:
            metric_names = (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
                "done_reason",
            )
            self.last_metrics = {
                name: event[name]
                for name in metric_names
                if isinstance(event.get(name), (int, str))
            }

        connection = self._new_connection(self.timeout)
        try:
            connection.request(
                "POST",
                "/api/chat",
                body=self._encode_payload(payload),
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                body = response.read()
                self._raise_http_error(response.status, body)
            yield from _read_stream_content(response, on_done=capture_metrics)
        except OllamaError:
            raise
        except (OSError, http.client.HTTPException, socket.timeout) as exc:
            raise OllamaUnavailableError(
                "The local Ollama response was interrupted. Check Ollama and retry."
            ) from exc
        finally:
            connection.close()

