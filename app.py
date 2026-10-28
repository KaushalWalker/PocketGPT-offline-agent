"""PocketAgent Windows MVP: a private Streamlit interface for local Ollama."""

from __future__ import annotations

import html
import hashlib
import json

import streamlit as st

from pocketagent.ollama_client import (
    LocalModel,
    ModelUnavailableError,
    OllamaClient,
    OllamaError,
    OllamaUnavailableError,
    model_supports_capability,
)
from pocketagent.prompts import MAX_CONTEXT_MESSAGES, build_messages
from pocketagent.reading_cards import (
    constrain_vocabulary_messages,
    extract_vocabulary_term,
    stream_vocabulary_card,
    vocabulary_card_schema,
)
from pocketagent.storage import Conversation, ConversationStore, default_database_path
from pocketagent.ui import render_local_model_controls
from pocketagent.voice import VoiceUnavailableError, synthesize_wav, transcribe_wav

st.set_page_config(
    page_title="PocketAgent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { max-width: 980px; padding-top: 2.1rem; padding-bottom: 5rem; }
      [data-testid="stChatMessage"] { border: 1px solid rgba(150, 165, 205, .12); }
      .pocketagent-subtitle { color: #a7b0c4; margin-top: -.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_store() -> ConversationStore:
    store = ConversationStore(default_database_path())
    store.initialize()
    return store


def format_conversation(conversation: Conversation) -> str:
    return conversation.title or "New conversation"


def select_saved_conversation() -> None:
    st.session_state["pending_conversation_id"] = st.session_state[
        "saved_conversation_selector"
    ]
    st.session_state.pop("clear_confirmation_for", None)


def copy_response_button(text: str, key: str) -> None:
    """Render a clipboard button; fall back to the browser's local copy command."""
    safe_text = json.dumps(text, ensure_ascii=False)
    safe_text = safe_text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    safe_key = html.escape(key, quote=True)
    st.html(
        f"""
        <button id="copy-{safe_key}" style="border:1px solid #454c5d;border-radius:8px;
          background:#1c2230;color:#dce2ef;padding:6px 11px;cursor:pointer;font:13px sans-serif;">
          Copy response
        </button>
        <span id="status-{safe_key}" style="margin-left:8px;color:#9aa5ba;font:12px sans-serif;"></span>
        <script>
          const copyText = {safe_text};
          const button = document.getElementById("copy-{safe_key}");
          const status = document.getElementById("status-{safe_key}");
          button.addEventListener("click", async () => {{
            try {{
              await navigator.clipboard.writeText(copyText);
              status.textContent = "Copied";
            }} catch (error) {{
              const area = document.createElement("textarea");
              area.value = copyText;
              area.style.position = "fixed";
              area.style.opacity = "0";
              document.body.appendChild(area);
              area.select();
              const copied = document.execCommand("copy");
              area.remove();
              status.textContent = copied ? "Copied" : "Copy unavailable in this browser";
            }}
          }});
        </script>
        """,
        unsafe_allow_javascript=True,
    )


store = get_store()
client = OllamaClient(timeout=600)
conversations = store.list_conversations()
if not conversations:
    conversations = [store.create_conversation()]
conversation_ids = {conversation.id for conversation in conversations}
selected_id = st.session_state.get("selected_conversation_id")
if selected_id not in conversation_ids:
    selected_id = conversations[0].id
st.session_state["selected_conversation_id"] = selected_id
st.session_state["saved_conversation_selector"] = selected_id
conversation = store.get_conversation(selected_id)

models: list[LocalModel] = []
runtime_error: str | None = None
try:
    models = client.list_models(timeout=1.5)
except OllamaUnavailableError as exc:
    runtime_error = str(exc)
except OllamaError as exc:
    runtime_error = str(exc)

with st.sidebar:
    st.markdown("## 📚 PocketAgent")
    st.caption("Your local reading and thinking companion")
    if st.button("＋ New conversation", use_container_width=True, type="primary"):
        new_conversation = store.create_conversation()
        st.session_state["selected_conversation_id"] = new_conversation.id
        st.session_state.pop("clear_confirmation_for", None)
        st.rerun()

    refreshed_conversations = store.list_conversations()
    st.selectbox(
        "Saved conversations",
        options=[item.id for item in refreshed_conversations],
        format_func=lambda item_id: format_conversation(
            next(item for item in refreshed_conversations if item.id == item_id)
        ),
        key="saved_conversation_selector",
        on_change=select_saved_conversation,
    )

    conversation = store.get_conversation(selected_id)
    mode_options = ["chat", "reading"]
    mode_index = mode_options.index(conversation.mode) if conversation.mode in mode_options else 0
    selected_mode = st.selectbox(
        "Assistant mode",
        options=mode_options,
        index=mode_index,
        format_func=lambda mode: "General chat" if mode == "chat" else "Reading companion",
        key=f"assistant_mode_{selected_id}",
    )

    model_names = [model.name for model in models]
    selected_model, selected_model_info, reasoning_enabled = render_local_model_controls(
        models,
        conversation.model,
        key=selected_id,
    )
    if selected_mode != conversation.mode or selected_model != conversation.model:
        store.update_settings(selected_id, mode=selected_mode, model=selected_model)
        conversation = store.get_conversation(selected_id)

    st.divider()
    if runtime_error:
        st.error("Local Ollama is not ready.")
        st.caption(runtime_error)
    elif not model_names:
        st.warning("Ollama is running, but no local model is installed.")
    else:
        st.success(f"Local runtime ready · {len(model_names)} model(s)")

    if runtime_error or not model_names:
        st.markdown("**Setup needed**")
        st.caption(
            "PocketAgent never downloads models. Ollama needs to be installed and running. "
            "The default model is llama3.2:3b; check whether Ollama recognizes it."
        )
        with st.expander("Check the existing local model"):
            st.code("ollama list", language="powershell")
            st.caption("If llama3.2:3b is not listed, ask before downloading another model.")

    clear_for = st.session_state.get("clear_confirmation_for")
    if clear_for == selected_id:
        st.warning("Clear all messages in this conversation?")
        confirm_col, cancel_col = st.columns(2)
        if confirm_col.button("Clear messages", key="confirm_clear", type="primary"):
            store.clear_conversation(selected_id)
            st.session_state.pop("clear_confirmation_for", None)
            st.rerun()
        if cancel_col.button("Cancel", key="cancel_clear"):
            st.session_state.pop("clear_confirmation_for", None)
            st.rerun()
    elif st.button("Clear current conversation", use_container_width=True):
        st.session_state["clear_confirmation_for"] = selected_id
        st.rerun()

    st.divider()
    st.caption("Inference stays on this PC at 127.0.0.1. No cloud models or telemetry are used.")

st.title("What would you like to explore?")
st.markdown(
    '<p class="pocketagent-subtitle">Read, learn a word, discuss an idea, or ask a coding question.</p>',
    unsafe_allow_html=True,
)

messages = store.get_messages(selected_id)
for message in messages:
    with st.chat_message(message.role):
        st.markdown(message.content)
        if message.role == "assistant":
            copy_response_button(message.content, f"saved-{message.id}")

can_chat = not runtime_error and selected_model is not None
voice_transcript_key = f"voice_transcript_{selected_id}"
voice_clear_key = f"voice_clear_transcript_{selected_id}"
if st.session_state.pop(voice_clear_key, False):
    st.session_state[voice_transcript_key] = ""

try:
    recorded_audio = st.audio_input(
        "Record a voice message",
        sample_rate=16000,
        key=f"voice_input_{selected_id}",
        disabled=not can_chat,
        help=(
            "Record English speech. Audio is captured by this browser and transcribed "
            "locally on this PC."
        ),
    )
    st.caption(
        "If recording fails, allow microphone access in your browser and Windows privacy settings."
    )
except Exception as exc:
    recorded_audio = None
    st.warning(
        "Microphone unavailable. Check browser microphone permission and the Windows "
        f"input device, then try again. ({exc})"
    )

if recorded_audio is not None:
    audio_bytes = recorded_audio.getvalue()
    audio_fingerprint = hashlib.sha256(audio_bytes).hexdigest()
    fingerprint_key = f"voice_fingerprint_{selected_id}"
    if st.session_state.get(fingerprint_key) != audio_fingerprint:
        st.session_state[fingerprint_key] = audio_fingerprint
        try:
            with st.spinner("Transcribing locally…"):
                st.session_state[voice_transcript_key] = transcribe_wav(audio_bytes)
            st.session_state.pop(f"voice_transcription_error_{selected_id}", None)
        except VoiceUnavailableError as exc:
            st.session_state[f"voice_transcription_error_{selected_id}"] = str(exc)

transcription_error = st.session_state.get(f"voice_transcription_error_{selected_id}")
if transcription_error:
    st.warning(transcription_error)

voice_send = False
if recorded_audio is not None or st.session_state.get(voice_transcript_key):
    st.text_area(
        "Recognized text (edit before sending)",
        key=voice_transcript_key,
        disabled=not can_chat,
    )
    voice_send = st.button(
        "Send recognized text",
        key=f"send_voice_{selected_id}",
        type="primary",
        disabled=not can_chat or not st.session_state.get(voice_transcript_key, "").strip(),
    )

playback_key = f"voice_playback_{selected_id}"
pending_audio_key = f"pending_voice_audio_{selected_id}"
pending_audio = st.session_state.pop(pending_audio_key, None)
if pending_audio:
    st.audio(pending_audio, format="audio/wav", autoplay=True)
    st.session_state[playback_key] = True
if st.session_state.get(playback_key):
    if st.button("Stop speaking", key=f"stop_voice_{selected_id}"):
        st.session_state[playback_key] = False
        st.rerun()
tts_error_key = f"voice_tts_error_{selected_id}"
if st.session_state.get(tts_error_key):
    st.warning(st.session_state.pop(tts_error_key))

prompt = st.chat_input(
    "Ask PocketAgent…",
    disabled=not can_chat,
    max_chars=20_000,
)

voice_submission = bool(voice_send and not prompt)
if voice_submission:
    prompt = st.session_state.get(voice_transcript_key, "").strip()
    st.session_state[voice_clear_key] = True

pending_conversation_id = st.session_state.pop("pending_conversation_id", None)
if not prompt and pending_conversation_id in conversation_ids:
    st.session_state["selected_conversation_id"] = pending_conversation_id
    st.rerun()

if prompt and selected_model:
    vocabulary_term = (
        extract_vocabulary_term(prompt) if conversation.mode == "reading" else None
    )
    store.add_message(selected_id, role="user", content=prompt)
    current_history = store.get_messages(selected_id)
    ollama_messages = build_messages(
        [{"role": message.role, "content": message.content} for message in current_history],
        mode=conversation.mode,
        limit=MAX_CONTEXT_MESSAGES,
        vocabulary_request=vocabulary_term is not None,
    )
    if vocabulary_term:
        ollama_messages = constrain_vocabulary_messages(ollama_messages, vocabulary_term)
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner(f"Generating locally with {selected_model}…"):
                options: dict[str, object] = {
                    "num_ctx": 8192,
                    "num_predict": 256 if vocabulary_term else 1024,
                    "temperature": 0.7,
                }
                if vocabulary_term:
                    options.update({"top_p": 0.8, "top_k": 20})
                    raw_stream = client.stream_chat(
                        selected_model,
                        ollama_messages,
                        options=options,
                        think=(
                            False
                            if model_supports_capability(selected_model_info, "thinking")
                            else None
                        ),
                        format=vocabulary_card_schema(vocabulary_term),
                    )
                    display_stream = stream_vocabulary_card(raw_stream, vocabulary_term)
                else:
                    display_stream = client.stream_chat(
                        selected_model,
                        ollama_messages,
                        options=options,
                        think=reasoning_enabled,
                    )
                answer = st.write_stream(display_stream)
            if isinstance(answer, str) and answer.strip():
                store.add_message(selected_id, role="assistant", content=answer)
                if voice_submission:
                    try:
                        st.session_state[pending_audio_key] = synthesize_wav(answer)
                    except VoiceUnavailableError as exc:
                        st.session_state[tts_error_key] = str(exc)
                st.rerun()
            st.warning("The local model returned an empty response. Please try again.")
        except ModelUnavailableError as exc:
            st.error(str(exc))
        except OllamaUnavailableError as exc:
            st.error(str(exc))
        except OllamaError as exc:
            st.error(f"Local inference failed: {exc}")

