import json

import pytest

from pocketagent.ollama_client import (
    ModelUnavailableError,
    OllamaAPIError,
    OllamaClient,
    model_supports_capability,
    _read_stream_content,
    is_cloud_model,
    local_models_from_payload,
)


def test_cloud_tags_are_filtered_from_local_model_list():
    models = local_models_from_payload(
        {
            "models": [
                {
                    "name": "qwen3:4b",
                    "size": 2_500_000_000,
                    "capabilities": ["completion", "tools", "thinking"],
                },
                {"name": "gemma4:cloud", "size": 1},
            ]
        }
    )

    assert [model.name for model in models] == ["qwen3:4b"]
    assert models[0].size_bytes == 2_500_000_000
    assert "thinking" in models[0].capabilities
    assert model_supports_capability(models[0], "thinking")
    assert is_cloud_model("gemma4:cloud")
    assert not is_cloud_model("qwen3:4b")


def test_model_supports_capability_uses_the_reported_capability_list():
    thinking_model = local_models_from_payload(
        {"models": [{"name": "thinker", "capabilities": ["completion", "thinking"]}]}
    )[0]
    regular_model = local_models_from_payload(
        {"models": [{"name": "regular", "capabilities": ["completion"]}]}
    )[0]

    assert model_supports_capability(thinking_model, "thinking")
    assert not model_supports_capability(regular_model, "thinking")
    assert not model_supports_capability(None, "thinking")


def test_streaming_parser_yields_text_and_stops_at_done():
    lines = [
        json.dumps({"message": {"content": "Hello"}, "done": False}).encode(),
        json.dumps({"message": {"content": " there"}, "done": False}).encode(),
        json.dumps({"message": {"content": ""}, "done": True}).encode(),
        b"not valid json\n",
    ]

    assert list(_read_stream_content(lines)) == ["Hello", " there"]


def test_streaming_parser_never_yields_the_separate_thinking_field():
    event = {
        "message": {"thinking": "private self-review", "content": "Final answer."},
        "done": True,
    }

    assert list(_read_stream_content([json.dumps(event).encode()])) == ["Final answer."]


def test_streaming_chat_hides_separate_and_tagged_thinking_when_disabled(monkeypatch):
    class FakeResponse:
        status = 200

        def __iter__(self):
            events = [
                {"message": {"thinking": "private reasoning", "content": "<thi"}, "done": False},
                {"message": {"content": "nk>secret</thi"}, "done": False},
                {"message": {"content": "nk>Final answer."}, "done": True},
            ]
            return iter(json.dumps(event).encode() for event in events)

    class FakeConnection:
        def request(self, method, path, *, body, headers):
            self.body = body

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    connection = FakeConnection()
    client = OllamaClient()
    monkeypatch.setattr(client, "_new_connection", lambda timeout: connection)

    assert list(client.stream_chat("qwen3:4b", [], think=False)) == ["Final answer."]
    assert json.loads(connection.body)["think"] is False
    malformed = {
        "message": {"content": "<think unfinished private thought</think>Final answer."},
        "done": True,
    }
    assert list(_read_stream_content([json.dumps(malformed).encode()])) == ["Final answer."]

    unclosed = {"message": {"content": "<think unfinished private thought"}, "done": True}
    assert list(_read_stream_content([json.dumps(unclosed).encode()])) == []


def test_streaming_chat_preserves_ordinary_untagged_content_when_thinking_is_disabled(
    monkeypatch,
):
    self_review = "Okay, the user is asking for a definition. Let me think through the answer."

    class FakeResponse:
        status = 200

        def __iter__(self):
            event = {"message": {"thinking": "", "content": self_review}, "done": True}
            return iter([json.dumps(event).encode()])

    class FakeConnection:
        def request(self, method, path, *, body, headers):
            pass

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    client = OllamaClient()
    monkeypatch.setattr(client, "_new_connection", lambda timeout: FakeConnection())

    assert list(client.stream_chat("qwen3:4b", [], think=False)) == [self_review]


def test_streaming_parser_surfaces_model_errors():
    event = {"error": "model 'missing' not found"}

    with pytest.raises(ModelUnavailableError, match="not found"):
        list(_read_stream_content([json.dumps(event).encode()]))


def test_cloud_model_cannot_be_called_even_if_passed_directly():
    client = OllamaClient()

    with pytest.raises(ModelUnavailableError, match="Cloud models are disabled"):
        list(client.stream_chat("gemma4:cloud", []))


def test_non_streaming_chat_sends_think_parameter_at_top_level(monkeypatch):
    client = OllamaClient()
    captured = {}

    def fake_request(method, path, payload):
        captured.update(payload)
        return {"message": {"content": "answer"}}

    monkeypatch.setattr(client, "_request_json", fake_request)

    client.chat_once("qwen3:4b", [], think=False)

    assert captured["think"] is False
    assert "think" not in captured.get("options", {})


def test_streaming_chat_sends_think_parameter_and_keeps_streaming(monkeypatch):
    class FakeResponse:
        status = 200

        def __iter__(self):
            return iter(
                [
                    json.dumps({"message": {"content": "hello"}, "done": False}).encode(),
                    json.dumps({"message": {"content": ""}, "done": True}).encode(),
                ]
            )

    class FakeConnection:
        def request(self, method, path, *, body, headers):
            self.body = body

        def getresponse(self):
            return FakeResponse()

        def close(self):
            pass

    client = OllamaClient()
    connection = FakeConnection()
    monkeypatch.setattr(client, "_new_connection", lambda timeout: connection)

    schema = {"type": "object", "required": ["definition"]}
    assert list(client.stream_chat("qwen3:4b", [], think=True, format=schema)) == ["hello"]
    payload = json.loads(connection.body)
    assert payload["think"] is True
    assert payload["format"] == schema


def test_think_is_omitted_when_not_requested(monkeypatch):
    client = OllamaClient()
    captured = {}

    def fake_request(method, path, payload):
        captured.update(payload)
        return {"message": {"content": "answer"}}

    monkeypatch.setattr(client, "_request_json", fake_request)

    client.chat_once("qwen3:4b", [])

    assert "think" not in captured


def test_streaming_parser_rejects_malformed_events():
    with pytest.raises(OllamaAPIError, match="malformed streaming data"):
        list(_read_stream_content([b"not valid json\n"]))

