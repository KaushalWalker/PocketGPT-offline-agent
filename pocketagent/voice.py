"""Local Windows speech recognition and synthesis helpers."""

from __future__ import annotations

import os
import wave
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any


def voice_assets_dir() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "PocketAgent" / "voice"


class VoiceUnavailableError(RuntimeError):
    """Raised when offline speech packages or model assets are unavailable."""


@lru_cache(maxsize=1)
def _load_asr_model() -> Any:
    model_dir = voice_assets_dir() / "faster-whisper-base.en"
    if not (model_dir / "model.bin").is_file():
        raise VoiceUnavailableError(
            f"Speech model is missing. Download it to {model_dir} using the README setup steps."
        )
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VoiceUnavailableError(
            "Speech recognition is not installed. Install the project requirements first."
        ) from exc
    return WhisperModel(str(model_dir), device="cpu", compute_type="int8")


@lru_cache(maxsize=1)
def _load_tts_voice() -> Any:
    voice_path = voice_assets_dir() / "en_US-lessac-medium.onnx"
    if not voice_path.is_file() or not voice_path.with_suffix(".onnx.json").is_file():
        raise VoiceUnavailableError(
            f"Speech voice is missing. Download it to {voice_path.parent} using the README setup steps."
        )
    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise VoiceUnavailableError(
            "Text-to-speech is not installed. Install the project requirements first."
        ) from exc
    return PiperVoice.load(str(voice_path))


def transcribe_wav(audio_bytes: bytes) -> str:
    """Transcribe a browser-recorded WAV locally using CPU int8 inference."""
    if not audio_bytes:
        raise VoiceUnavailableError("The microphone recording was empty.")
    try:
        model = _load_asr_model()
        segments, _ = model.transcribe(
            BytesIO(audio_bytes), language="en", beam_size=3, vad_filter=True
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
    except VoiceUnavailableError:
        raise
    except Exception as exc:
        raise VoiceUnavailableError(f"Local speech recognition failed: {exc}") from exc
    if not transcript:
        raise VoiceUnavailableError("No speech was recognized. Try recording again.")
    return transcript


def synthesize_wav(text: str) -> bytes:
    """Create a WAV response using the locally installed Piper voice."""
    if not text.strip():
        raise VoiceUnavailableError("There is no response text to speak.")
    try:
        voice = _load_tts_voice()
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return output.getvalue()
    except VoiceUnavailableError:
        raise
    except Exception as exc:
        raise VoiceUnavailableError(f"Local speech synthesis failed: {exc}") from exc
