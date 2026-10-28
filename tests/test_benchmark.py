import pytest

from benchmark import choose_model, run_benchmark
from pocketagent.ollama_client import LocalModel, ModelUnavailableError


class FakeClient:
    def __init__(self):
        self.call = None
        self.last_metrics = {
            "eval_count": 20,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 100,
            "prompt_eval_duration": 5_000_000_000,
            "load_duration": 3_000_000_000,
            "done_reason": "stop",
        }

    def stream_chat(self, model, messages, *, options, think, format):
        self.call = {
            "model": model,
            "messages": messages,
            "options": options,
            "think": think,
            "format": format,
        }
        yield '{"definition":"A word lasting briefly.","synonyms":["temporary","brief","short-lived"],"examples":["An ephemeral cloud passed.","The ephemeral glow faded."]}'


def test_choose_model_requires_an_installed_non_cloud_model():
    local = [LocalModel("qwen3:4b", 2_500_000_000)]

    assert choose_model(None, local) == "qwen3:4b"
    with pytest.raises(ModelUnavailableError, match="not installed locally"):
        choose_model("missing:3b", local)
    with pytest.raises(ModelUnavailableError, match="Cloud models"):
        choose_model("model:cloud", [LocalModel("model:cloud")])


def test_benchmark_reports_performance_and_sends_fixed_local_prompt():
    client = FakeClient()

    result = run_benchmark(
        "qwen3:4b",
        client,
        term="ephemeral",
        question="What does ephemeral mean?",
    )

    assert "**Definition:** A word lasting briefly." in result["answer"]
    assert result["think"] is False
    assert result["done_reason"] == "stop"
    assert result["first_visible_text_seconds"] >= 0
    assert result["generation_tokens_per_second"] == 10
    assert result["prompt_tokens_per_second"] == 20
    assert result["load_seconds"] == 3
    assert client.call["model"] == "qwen3:4b"
    assert client.call["options"] == {
        "num_ctx": 8192,
        "num_predict": 256,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
    }
    assert client.call["think"] is False
    assert "ephemeral" in client.call["messages"][1]["content"]
    assert "exactly three" in client.call["messages"][0]["content"]
    assert "exactly two" in client.call["messages"][0]["content"]
    assert client.call["format"]["properties"]["synonyms"]["maxItems"] == 3

