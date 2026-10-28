"""App regression for the first message in a newly created conversation."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

import pocketagent.storage as storage_module
from pocketagent.ollama_client import LocalModel, OllamaClient
from pocketagent.storage import ConversationStore


def test_first_message_and_reply_persist_in_new_conversation(tmp_path, monkeypatch):
    database_path = tmp_path / "conversations.sqlite3"
    seed_store = ConversationStore(database_path)
    seed_store.initialize()
    existing_conversation = seed_store.create_conversation()
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            ("9999-01-01T00:00:00+00:00", existing_conversation.id),
        )
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    monkeypatch.setattr(storage_module, "default_database_path", lambda: database_path)
    monkeypatch.setattr(
        OllamaClient,
        "list_models",
        lambda self, timeout=2: [LocalModel("test-model")],
    )
    monkeypatch.setattr(
        OllamaClient,
        "stream_chat",
        lambda self, model, messages, **kwargs: iter(["Simulated reply."]),
    )
    source = f"""
from pathlib import Path
exec(compile(Path({str(app_path)!r}).read_text(encoding="utf-8"), "app.py", "exec"))
"""
    app = AppTest.from_string(source).run(timeout=20)
    assert not app.exception
    first_conversation_id = app.session_state["selected_conversation_id"]
    assert app.session_state["saved_conversation_selector"] == first_conversation_id

    new_button = next(button for button in app.button if "New conversation" in button.label)
    new_button.click().run(timeout=20)
    assert not app.exception
    new_conversation_id = app.session_state["selected_conversation_id"]
    assert new_conversation_id != first_conversation_id
    assert app.session_state["saved_conversation_selector"] == new_conversation_id
    assert app.selectbox[0].value == new_conversation_id
    assert app.chat_input[0].disabled is False

    app.chat_input[0].set_value("Why is the sky blue?").run(timeout=20)
    assert not app.exception
    assert app.session_state["selected_conversation_id"] == new_conversation_id
    messages = ConversationStore(database_path).get_messages(new_conversation_id)
    assert [(message.role, message.content) for message in messages] == [
        ("user", "Why is the sky blue?"),
        ("assistant", "Simulated reply."),
    ]

    app.selectbox[0].set_value(first_conversation_id).run(timeout=20)
    app.selectbox[0].set_value(new_conversation_id).run(timeout=20)
    assert not app.exception
    rendered_text = [element.value for element in app.markdown]
    assert "Why is the sky blue?" in rendered_text
    assert "Simulated reply." in rendered_text
