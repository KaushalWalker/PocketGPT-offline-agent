"""Constrained local vocabulary-card requests and incremental rendering."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from json import JSONDecoder, JSONDecodeError

from pocketagent.ollama_client import OllamaAPIError

_TERM_CORE = r"[\w][\w'’\-]*(?:\s+[\w][\w'’\-]*){0,3}"
_TERM = rf"(?P<term>[\"'“‘]?{_TERM_CORE}[\"'”’]?)"
_VOCABULARY_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"^\s*what does\s+(?:the word\s+)?{_TERM}\s+mean\s*[?.!]*\s*$",
        rf"^\s*what is the meaning of\s+{_TERM}\s*[?.!]*\s*$",
        rf"^\s*define\s+{_TERM}\s*[?.!]*\s*$",
        rf"^\s*meaning of\s+{_TERM}\s*[?.!]*\s*$",
        rf"^\s*synonyms?\s+(?:for|of)\s+{_TERM}\s*[?.!]*\s*$",
        rf"^\s*explain the word\s+{_TERM}\s*[?.!]*\s*$",
    )
)
_CARD_KEYS = ("definition", "synonyms", "examples")
_DECODER = JSONDecoder()


def extract_vocabulary_term(prompt: str) -> str | None:
    """Return a target word or short phrase for a simple vocabulary request."""
    for pattern in _VOCABULARY_PATTERNS:
        match = pattern.match(prompt)
        if not match:
            continue
        term = match.group("term").strip(" \t\r\n\"'“”‘’.,!?;:")
        if term and term.casefold() not in {"this", "that", "it", "something"}:
            return term
    return None


def _case_insensitive_pattern(term: str) -> str:
    parts: list[str] = []
    for character in term:
        if character.isspace():
            parts.append(r"\s+")
        elif character.isalpha() and len(character.upper()) == 1:
            parts.append(f"[{character.lower()}{character.upper()}]")
        else:
            parts.append(re.escape(character))
    return r".*\b" + "".join(parts) + r"\b.*"


def vocabulary_card_schema(term: str) -> dict[str, object]:
    """Build an Ollama JSON schema for one concise vocabulary answer."""
    variants = list({term.casefold(), term.lower(), term.title(), term.upper()})
    return {
        "type": "object",
        "properties": {
            "definition": {
                "type": "string",
                "minLength": 12,
            },
            "synonyms": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": 2,
                    "not": {"enum": variants},
                },
                "minItems": 3,
                "maxItems": 3,
                "uniqueItems": True,
            },
            "examples": {
                "type": "array",
                "items": {
                    "type": "string",
                    "minLength": max(16, len(term) + 8),
                    "pattern": _case_insensitive_pattern(term),
                },
                "minItems": 2,
                "maxItems": 2,
                "uniqueItems": True,
            },
        },
        "required": list(_CARD_KEYS),
        "additionalProperties": False,
    }


def constrain_vocabulary_messages(
    messages: list[dict[str, str]], term: str
) -> list[dict[str, str]]:
    """Add target-specific requirements to the newest user turn only."""
    if not messages or messages[-1].get("role") != "user":
        raise ValueError("A vocabulary card requires a final user message")
    constrained = [dict(message) for message in messages]
    constrained[-1]["content"] += (
        f"\nFor the word {term}, return one plain-sentence definition, exactly three "
        "close synonyms that are different from each other and from the target word, "
        f"and exactly two natural example sentences. Each example must use {term} "
        "correctly."
    )
    return constrained


def _validate_card_field(key: str, value: object, term: str) -> None:
    if key == "definition":
        if not isinstance(value, str) or len(value.strip()) < 12:
            raise OllamaAPIError("The local model returned an incomplete definition.")
        return

    if key == "synonyms":
        if (
            not isinstance(value, list)
            or len(value) != 3
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            raise OllamaAPIError("The local model did not return exactly three synonyms.")
        normalized = [item.strip().strip(".,;:!?").casefold() for item in value]
        if len(set(normalized)) != 3 or term.casefold() in normalized:
            raise OllamaAPIError("The local model returned repeated or invalid synonyms.")
        return

    if key == "examples":
        if (
            not isinstance(value, list)
            or len(value) != 2
            or any(not isinstance(item, str) or not item.strip() for item in value)
        ):
            raise OllamaAPIError("The local model did not return exactly two examples.")
        if any(
            re.search(rf"(?<!\w){re.escape(term)}(?!\w)", item, re.IGNORECASE) is None
            for item in value
        ):
            raise OllamaAPIError("A local example did not use the requested word.")
        return

    raise OllamaAPIError("The local model returned an unexpected vocabulary field.")


def _render_field(key: str, value: object) -> str:
    if key == "definition":
        definition = str(value).strip()
        if not definition.endswith((".", "!", "?")):
            definition += "."
        return f"**Definition:** {definition}\n\n"
    if key == "synonyms":
        words = ", ".join(str(item).strip() for item in value)  # type: ignore[arg-type]
        return f"**Synonyms:** {words}\n\n"
    examples = "\n".join(f"- {str(item).strip()}" for item in value)  # type: ignore[arg-type]
    return f"**Examples:**\n\n{examples}"


def stream_vocabulary_card(chunks: Iterable[str], term: str) -> Iterator[str]:
    """Parse Ollama's streamed JSON and emit validated answer fields as they finish."""
    buffer = ""
    cursor = 0
    opened = False
    seen: dict[str, object] = {}
    emitted: set[str] = set()

    def skip_space(index: int) -> int:
        while index < len(buffer) and buffer[index].isspace():
            index += 1
        return index

    for chunk in chunks:
        buffer += chunk
        while True:
            cursor = skip_space(cursor)
            if cursor >= len(buffer):
                break
            if not opened:
                if buffer[cursor] != "{":
                    raise OllamaAPIError("The local model returned malformed vocabulary JSON.")
                opened = True
                cursor += 1
                continue
            if buffer[cursor] == ",":
                cursor += 1
                continue
            if buffer[cursor] == "}":
                cursor += 1
                break

            try:
                key, after_key = _DECODER.raw_decode(buffer, cursor)
            except JSONDecodeError:
                break
            if not isinstance(key, str) or key not in _CARD_KEYS or key in seen:
                raise OllamaAPIError("The local model returned an invalid vocabulary card.")
            value_start = skip_space(after_key)
            if value_start >= len(buffer):
                break
            if buffer[value_start] != ":":
                raise OllamaAPIError("The local model returned malformed vocabulary JSON.")
            value_start = skip_space(value_start + 1)
            try:
                value, after_value = _DECODER.raw_decode(buffer, value_start)
            except JSONDecodeError:
                break
            _validate_card_field(key, value, term)
            seen[key] = value
            cursor = after_value

            for ready_key in _CARD_KEYS:
                if ready_key in emitted:
                    continue
                if ready_key not in seen:
                    break
                emitted.add(ready_key)
                yield _render_field(ready_key, seen[ready_key])

    try:
        final_payload = json.loads(buffer)
    except json.JSONDecodeError as exc:
        raise OllamaAPIError("The local model returned incomplete vocabulary JSON.") from exc
    if not isinstance(final_payload, dict) or set(final_payload) != set(_CARD_KEYS):
        raise OllamaAPIError("The local model returned an incomplete vocabulary card.")
    for key in _CARD_KEYS:
        if key not in emitted:
            _validate_card_field(key, final_payload[key], term)
            yield _render_field(key, final_payload[key])

