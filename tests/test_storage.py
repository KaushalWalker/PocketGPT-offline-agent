from pocketagent.storage import ConversationStore, DEFAULT_TITLE


def make_store(tmp_path):
    store = ConversationStore(tmp_path / "conversations.sqlite3")
    store.initialize()
    return store


def test_conversation_messages_persist_and_title_uses_first_user_message(tmp_path):
    store = make_store(tmp_path)
    conversation = store.create_conversation(mode="reading", model="qwen3:4b")

    store.add_message(
        conversation.id,
        role="user",
        content="  What does   ephemeral mean?  ",
    )
    store.add_message(conversation.id, role="assistant", content="It means short-lived.")

    saved = store.get_conversation(conversation.id)
    messages = store.get_messages(conversation.id)
    assert saved.title == "What does ephemeral mean?"
    assert saved.mode == "reading"
    assert saved.model == "qwen3:4b"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].content == "It means short-lived."
    assert store.list_conversations()[0].id == conversation.id


def test_clear_keeps_conversation_and_settings_but_removes_messages(tmp_path):
    store = make_store(tmp_path)
    conversation = store.create_conversation(mode="reading", model="local-model")
    store.add_message(conversation.id, role="user", content="A question")

    store.clear_conversation(conversation.id)

    cleared = store.get_conversation(conversation.id)
    assert cleared.title == DEFAULT_TITLE
    assert cleared.mode == "reading"
    assert cleared.model == "local-model"
    assert store.get_messages(conversation.id) == []


def test_invalid_roles_and_modes_are_rejected(tmp_path):
    store = make_store(tmp_path)
    conversation = store.create_conversation()

    try:
        store.add_message(conversation.id, role="system", content="not allowed")
    except ValueError as error:
        assert "Unsupported message role" in str(error)
    else:
        raise AssertionError("system messages must not be stored as conversation rows")

    try:
        store.create_conversation(mode="unknown")
    except ValueError as error:
        assert "Unknown conversation mode" in str(error)
    else:
        raise AssertionError("unknown modes must be rejected")

