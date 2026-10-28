"""Benchmark concise Reading Companion cards using the installed local model."""

from __future__ import annotations

import argparse
import json
import sys
import time

from pocketagent.ollama_client import (
    LocalModel,
    ModelUnavailableError,
    OllamaClient,
    OllamaError,
    OllamaUnavailableError,
    is_cloud_model,
)
from pocketagent.prompts import build_messages
from pocketagent.reading_cards import (
    constrain_vocabulary_messages,
    stream_vocabulary_card,
    vocabulary_card_schema,
)

BENCHMARK_QUESTIONS = (
    ("ephemeral", 'What does "ephemeral" mean?'),
    ("meticulous", "Define meticulous."),
    ("reluctant", "What does reluctant mean?"),
)
BENCHMARK_OPTIONS = {
    "num_ctx": 8192,
    "num_predict": 256,
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
}


def format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "size unknown"
    return f"{size_bytes / (1024**3):.2f} GiB"


def choose_model(requested: str | None, models: list[LocalModel]) -> str:
    names = [model.name for model in models]
    if requested:
        if is_cloud_model(requested):
            raise ModelUnavailableError("Cloud models are not benchmarked by PocketAgent.")
        if requested not in names:
            available = ", ".join(names) if names else "none"
            raise ModelUnavailableError(
                f"{requested} is not installed locally. Locally available models: {available}."
            )
        return requested
    if len(names) == 1:
        return names[0]
    if not names:
        raise ModelUnavailableError("No local Ollama model is installed yet.")
    raise ModelUnavailableError(
        "Several local models are installed. Pass one explicitly, for example: "
        "python benchmark.py llama3.2:3b"
    )


def run_benchmark(
    model: str,
    client: OllamaClient,
    *,
    term: str,
    question: str,
) -> dict[str, object]:
    """Generate one validated, structured card and return timing metrics."""
    messages = build_messages(
        [{"role": "user", "content": question}],
        mode="reading",
        vocabulary_request=True,
    )
    messages = constrain_vocabulary_messages(messages, term)
    start = time.perf_counter()
    first_visible_text_seconds: float | None = None
    rendered_chunks: list[str] = []
    raw_chunks = client.stream_chat(
        model,
        messages,
        options=BENCHMARK_OPTIONS,
        think=False,
        format=vocabulary_card_schema(term),
    )
    for chunk in stream_vocabulary_card(raw_chunks, term):
        if first_visible_text_seconds is None:
            first_visible_text_seconds = time.perf_counter() - start
        rendered_chunks.append(chunk)
    elapsed_seconds = time.perf_counter() - start
    answer = "".join(rendered_chunks)
    metrics = client.last_metrics
    eval_count = metrics.get("eval_count", 0)
    eval_duration = metrics.get("eval_duration", 0)
    prompt_count = metrics.get("prompt_eval_count", 0)
    prompt_duration = metrics.get("prompt_eval_duration", 0)
    return {
        "model": model,
        "term": term,
        "think": False,
        "answer": answer,
        "wall_seconds": elapsed_seconds,
        "first_visible_text_seconds": first_visible_text_seconds,
        "done_reason": metrics.get("done_reason"),
        "generated_tokens": eval_count if isinstance(eval_count, int) else 0,
        "generation_tokens_per_second": (
            eval_count / (eval_duration / 1_000_000_000)
            if isinstance(eval_count, int)
            and isinstance(eval_duration, int)
            and eval_duration > 0
            else None
        ),
        "prompt_tokens": prompt_count if isinstance(prompt_count, int) else 0,
        "prompt_tokens_per_second": (
            prompt_count / (prompt_duration / 1_000_000_000)
            if isinstance(prompt_count, int)
            and isinstance(prompt_duration, int)
            and prompt_duration > 0
            else None
        ),
        "load_seconds": metrics["load_duration"] / 1_000_000_000
        if "load_duration" in metrics
        else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", nargs="?", help="An already-installed local Ollama model")
    args = parser.parse_args(argv)

    client = OllamaClient(timeout=600)
    try:
        models = client.list_models()
        selected = choose_model(args.model, models)
        model_info = next((item for item in models if item.name == selected), None)
        if model_info is None:
            raise ModelUnavailableError(
                f"{selected} is not available through the local Ollama model list."
            )
        print(f"Model: {selected} ({format_size(model_info.size_bytes if model_info else None)})")
        print("Warming the installed model locally before the three-card check...", flush=True)
        client.chat_once(
            selected,
            [{"role": "user", "content": "Reply with the letter x."}],
            options={"num_ctx": 8192, "num_predict": 1, "temperature": 0},
        )
        results = []
        for term, question in BENCHMARK_QUESTIONS:
            print(f"Benchmarking fresh vocabulary request: {term}...", flush=True)
            results.append(
                run_benchmark(selected, client, term=term, question=question)
            )
    except OllamaUnavailableError as exc:
        print(f"Ollama unavailable: {exc}", file=sys.stderr)
        return 2
    except OllamaError as exc:
        print(f"Benchmark unavailable: {exc}", file=sys.stderr)
        return 2

    for metrics in results:
        answer = str(metrics.pop("answer"))
        print(f"\n--- {metrics['term']}: Reading Companion answer ---\n")
        print(answer)
        print("\n--- Performance ---")
        print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

