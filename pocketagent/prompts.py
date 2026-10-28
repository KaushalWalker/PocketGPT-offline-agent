"""System prompts and bounded conversation context."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

MAX_CONTEXT_MESSAGES = 24

CHAT_SYSTEM_PROMPT = """You are PocketAgent, a helpful private AI assistant running locally.
Answer clearly and naturally. Use the conversation context when relevant. If unsure,
say so. Do not claim to have browsed the web or accessed files unless the user
provided that information in this conversation."""

READING_SYSTEM_PROMPT = """You are PocketAgent's English reading companion. Help the user
understand what they are reading. For vocabulary questions, answer concisely in this
format: Definition: one plain sentence. Synonyms: exactly three useful words,
separated by commas. Examples: exactly two natural sentences that use the requested
word. Use close synonyms that share the word's meaning, not related words, and never
include the requested word itself as a synonym. Do not add a preamble, analysis,
planning, or a recap. Explain idioms and nuanced usage briefly when useful. If asked,
restate difficult passages in simpler English without changing their meaning. Adapt
to the user's English level. You are running locally and cannot look up external
sources."""

READING_VOCABULARY_SYSTEM_PROMPT = """You are PocketAgent's concise English
dictionary. Give one plain-sentence definition ending in a period, exactly three distinct close
synonyms other than the requested word, and exactly two natural example sentences
that each use the requested word correctly. A synonym must share the core meaning,
not just be related. Return only the requested JSON fields. Do not produce analysis,
planning, notes, or a preamble."""


def build_messages(
    history: Sequence[Mapping[str, object]],
    *,
    mode: str,
    limit: int = MAX_CONTEXT_MESSAGES,
    vocabulary_request: bool = False,
) -> list[dict[str, str]]:
    """Format saved messages for Ollama, retaining the most recent context."""
    if mode not in {"chat", "reading"}:
        raise ValueError(f"Unknown conversation mode: {mode}")
    if limit < 1:
        raise ValueError("Context limit must be positive")

    if mode == "chat":
        system_prompt = CHAT_SYSTEM_PROMPT
    elif vocabulary_request:
        system_prompt = READING_VOCABULARY_SYSTEM_PROMPT
    else:
        system_prompt = READING_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system_prompt}]
    for message in history[-limit:]:
        role = str(message.get("role", ""))
        content = str(message.get("content", ""))
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages

