from __future__ import annotations

import wave
from io import BytesIO
from types import SimpleNamespace

import pytest

from pocketagent import voice


def test_transcribe_wav_uses_local_asr_and_returns_text(monkeypatch):
    calls = {}

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            calls["audio"] = audio.read()
            calls["kwargs"] = kwargs
            return iter([SimpleNamespace(text="  hello "), SimpleNamespace(text="world")]), None

    monkeypatch.setattr(voice, "_load_asr_model", lambda: FakeModel())

    assert voice.transcribe_wav(b"wav-data") == "hello world"
    assert calls["audio"] == b"wav-data"
    assert calls["kwargs"] == {
        "language": "en",
        "beam_size": 3,
        "vad_filter": True,
    }


def test_transcribe_wav_reports_empty_recording():
    with pytest.raises(voice.VoiceUnavailableError, match="recording was empty"):
        voice.transcribe_wav(b"")


def test_synthesize_wav_returns_local_piper_audio(monkeypatch):
    class FakeVoice:
        def synthesize_wav(self, text, wav_file):
            assert text == "Hello there."
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(b"\x00\x00")

    monkeypatch.setattr(voice, "_load_tts_voice", lambda: FakeVoice())

    result = voice.synthesize_wav("Hello there.")
    with wave.open(BytesIO(result), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getframerate() == 16000
        assert wav_file.readframes(1) == b"\x00\x00"


def test_synthesize_wav_rejects_blank_text():
    with pytest.raises(voice.VoiceUnavailableError, match="no response text"):
        voice.synthesize_wav("  ")
