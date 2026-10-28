import pytest

from pocketagent.prompts import MAX_CONTEXT_MESSAGES, build_messages


def test_build_messages_keeps_system_prompt_and_recent_history():
    history = [
        {"role": "user", "content": f"question {index}"}
        for index in range(MAX_CONTEXT_MESSAGES + 3)
    ]

    messages = build_messages(history, mode="chat")

    assert messages[0]["role"] == "system"
    assert len(messages) == MAX_CONTEXT_MESSAGES + 1
    assert messages[1]["content"] == "question 3"
    assert messages[-1]["content"] == f"question {MAX_CONTEXT_MESSAGES + 2}"


def test_reading_mode_has_english_learning_guidance():
    messages = build_messages([], mode="reading")
    prompt = messages[0]["content"].lower()

    assert "synonyms" in prompt
    assert "exactly three" in prompt
    assert "exactly two" in prompt
    assert "simpler english" in prompt


def test_vocabulary_requests_use_a_short_constrained_system_prompt():
    messages = build_messages([], mode="reading", vocabulary_request=True)

    assert "dictionary" in messages[0]["content"]
    assert "core meaning" in messages[0]["content"]
    assert "JSON" in messages[0]["content"]


@pytest.mark.parametrize("mode", ["other", ""])
def test_unknown_modes_are_rejected(mode):
    with pytest.raises(ValueError, match="Unknown conversation mode"):
        build_messages([], mode=mode)

