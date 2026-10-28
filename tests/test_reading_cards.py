import json

import pytest

from pocketagent.ollama_client import OllamaAPIError
from pocketagent.reading_cards import (
    constrain_vocabulary_messages,
    extract_vocabulary_term,
    stream_vocabulary_card,
    vocabulary_card_schema,
)


@pytest.mark.parametrize(
    ("prompt", "term"),
    [
        ('What does "ephemeral" mean?', "ephemeral"),
        ("Define meticulous.", "meticulous"),
        ("Synonyms for reluctant?", "reluctant"),
        ("What is the meaning of short-lived?", "short-lived"),
    ],
)
def test_extract_vocabulary_term(prompt, term):
    assert extract_vocabulary_term(prompt) == term


@pytest.mark.parametrize(
    "prompt",
    [
        "Explain this paragraph in simpler English.",
        "What does this mean?",
        "Help me discuss the author's main idea.",
    ],
)
def test_non_vocabulary_reading_requests_keep_the_freeform_path(prompt):
    assert extract_vocabulary_term(prompt) is None


def test_vocabulary_schema_requires_exact_counts_and_excludes_the_target():
    schema = vocabulary_card_schema("reluctant")
    properties = schema["properties"]

    assert properties["synonyms"]["minItems"] == 3
    assert properties["synonyms"]["maxItems"] == 3
    assert properties["synonyms"]["items"]["not"]["enum"]
    assert properties["examples"]["minItems"] == 2
    assert properties["examples"]["maxItems"] == 2
    assert "[rR][eE][lL]" in properties["examples"]["items"]["pattern"]
    assert r"\b" in properties["examples"]["items"]["pattern"]


def test_target_constraints_are_appended_without_changing_saved_history():
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "What does reluctant mean?"},
    ]

    constrained = constrain_vocabulary_messages(messages, "reluctant")

    assert messages[-1]["content"] == "What does reluctant mean?"
    assert "from the target word" in constrained[-1]["content"]
    assert "Each example must use reluctant" in constrained[-1]["content"]


def test_streamed_card_is_rendered_incrementally_in_reading_order():
    payload = json.dumps(
        {
            "definition": "Lasting for a very short time.",
            "synonyms": ["temporary", "transient", "short-lived"],
            "examples": [
                "The ephemeral glow faded before dawn.",
                "Online trends are often ephemeral.",
            ],
        }
    )
    chunks = [payload[index : index + 9] for index in range(0, len(payload), 9)]

    rendered = list(stream_vocabulary_card(chunks, "ephemeral"))

    assert len(rendered) == 3
    assert "**Definition:** Lasting for a very short time." == rendered[0].strip()
    assert "temporary, transient, short-lived" in rendered[1]
    assert "- The ephemeral glow faded before dawn." in rendered[2]
    assert "- Online trends are often ephemeral." in rendered[2]


@pytest.mark.parametrize(
    ("term", "payload"),
    [
        (
            "reluctant",
            {
                "definition": "Not willing to do something.",
                "synonyms": ["hesitant", "unwilling", "reluctant"],
                "examples": [
                    "She was reluctant to go.",
                    "He was reluctant to leave.",
                ],
            },
        ),
        (
            "ephemeral",
            {
                "definition": "Lasting for a very short time.",
                "synonyms": ["temporary", "transient", "short-lived"],
                "examples": [
                    "The ephemeral glow faded.",
                    "Online trends often disappear quickly.",
                ],
            },
        ),
    ],
)
def test_invalid_target_synonym_or_example_is_rejected(term, payload):
    with pytest.raises(OllamaAPIError):
        list(stream_vocabulary_card([json.dumps(payload)], term))
