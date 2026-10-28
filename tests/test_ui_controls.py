"""Regression coverage for model selection and reasoning-toggle rendering."""

from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

from pocketagent.ollama_client import LocalModel


MODELS = [
    LocalModel("qwen3:4b", capabilities=("completion", "thinking")),
    LocalModel("llama3.2:3b", capabilities=("completion",)),
    LocalModel("regular:1b", capabilities=("completion",)),
]


def test_model_selector_and_reasoning_toggle_follow_model_capabilities():
    source = f"""
import streamlit as st
from pocketagent.ollama_client import LocalModel
from pocketagent.ui import render_local_model_controls

models = {MODELS!r}
selected_model, selected_info, reasoning_enabled = render_local_model_controls(
    models, "qwen3:4b", key="regression"
)
"""

    app = AppTest.from_string(source).run(timeout=15)
    assert not app.exception
    assert len(app.selectbox) == 1
    assert app.selectbox[0].value == "qwen3:4b"
    assert len(app.toggle) == 1
    assert app.toggle[0].label == "Reasoning"
    assert app.toggle[0].value is False

    app.toggle[0].set_value(True).run(timeout=15)
    assert not app.exception
    assert app.toggle[0].value is True

    app.selectbox[0].set_value("regular:1b").run(timeout=15)
    assert not app.exception
    assert app.selectbox[0].value == "regular:1b"
    assert len(app.toggle) == 0

    app.selectbox[0].set_value("qwen3:4b").run(timeout=15)
    assert not app.exception
    assert len(app.toggle) == 1


def test_model_selector_defaults_to_llama_when_available():
    source = f"""
import streamlit as st
from pocketagent.ollama_client import LocalModel
from pocketagent.ui import render_local_model_controls

models = {MODELS!r}
selected_model, selected_info, reasoning_enabled = render_local_model_controls(
    models, None, key="new-conversation"
)
"""

    app = AppTest.from_string(source).run(timeout=15)
    assert not app.exception
    assert app.selectbox[0].value == "llama3.2:3b"
    assert len(app.toggle) == 0
