"""Small Streamlit controls shared by PocketAgent and UI smoke tests."""

from __future__ import annotations

import streamlit as st

from pocketagent.ollama_client import LocalModel, model_supports_capability

DEFAULT_MODEL = "llama3.2:3b"


def render_local_model_controls(
    models: list[LocalModel],
    current_model: str | None,
    *,
    key: str,
) -> tuple[str | None, LocalModel | None, bool | None]:
    """Render the model picker and show reasoning only for capable models."""
    names = [model.name for model in models]
    options = ["", *names]
    if current_model in names:
        index = options.index(current_model)
    elif DEFAULT_MODEL in names:
        index = options.index(DEFAULT_MODEL)
    elif len(names) == 1:
        index = 1
    else:
        index = 0

    selected_model = st.selectbox(
        "Local model",
        options=options,
        index=index,
        format_func=lambda model: "Choose an installed model" if not model else model,
        help="Only locally installed, non-cloud Ollama models are listed.",
        key=f"local_model_{key}",
    ) or None
    selected_info = next((model for model in models if model.name == selected_model), None)

    reasoning_enabled: bool | None = None
    if model_supports_capability(selected_info, "thinking"):
        reasoning_enabled = st.toggle(
            "Reasoning",
            value=False,
            key=f"reasoning_enabled_{key}",
            help=(
                "Use reasoning for complex questions. Short vocabulary cards use "
                "constrained output to keep the answer concise and hide self-review."
            ),
        )

    return selected_model, selected_info, reasoning_enabled
