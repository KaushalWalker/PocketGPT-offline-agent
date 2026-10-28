# PocketAgent — Windows MVP

PocketAgent is a local-first reading and chat companion. The Windows MVP uses a
Streamlit interface, SQLite conversation history, and Ollama's local chat API.
Inference requests are sent only to `127.0.0.1:11434`; cloud-tagged models are
excluded and rejected. The Streamlit server binds to loopback, and usage telemetry
is disabled in its local configuration.

## Current status

- General multi-turn chat and a reading companion mode are implemented.
- Conversation history is stored in the current Windows user's local app data:
  `%LOCALAPPDATA%\PocketAgent\conversations.sqlite3`.
- The app streams tokens through Ollama, lists installed local models, and handles
  an unavailable runtime or model with a setup message.
- The model selector never pulls or downloads a model.
- Reading Companion vocabulary requests use Ollama's JSON schema output, then
  stream validated definition, synonym, and example fields as readable text.
- Reasoning remains enabled by default for complex questions and can be toggled.
  Short vocabulary cards use constrained `think=false` output to suppress the
  installed model's self-review.
- `benchmark.py` runs three fresh vocabulary prompts and reports time to first
  visible field, total response time, generated tokens, token rate, and answers.
- Windows voice input and spoken replies use local Whisper and Piper models.
- Android, document import, and fully offline verification are not part of this
  milestone.

## Setup on Windows PowerShell

Ollama 0.40.11 is already installed on this PC, and `llama3.2:3b` is the
selected default model. Check the existing installation with
`ollama list`; PocketAgent does not reinstall Ollama or pull models.

Create a project-local Python environment and install the Python dependencies.
This downloads packages from PyPI, including the CPU speech recognition runtime
and Piper voice engine; review the package licenses before installing:

```powershell
Set-Location "$env:USERPROFILE\OneDrive\Desktop\PocketGPT"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Download voice models once

Voice recognition and speech synthesis run on the PC. The browser captures audio
through Streamlit's microphone control; neither audio nor transcripts are sent to
an external service. The default assets below require about **211 MB** total:

- `Systran/faster-whisper-base.en`: about 148 MB, English transcription model.
- Piper `en_US-lessac-medium`: about 63 MB, English speech model, plus a small
  JSON configuration file.

`faster-whisper` is MIT-licensed. `piper-tts` is GPL-3.0-or-later; the selected
Piper voice is MIT-licensed. These are downloads for the current Windows user,
not system-wide installations. Do this setup step only after approving the
package and model downloads:

```powershell
$voiceDir = Join-Path $env:LOCALAPPDATA "PocketAgent\voice"
$whisperDir = Join-Path $voiceDir "faster-whisper-base.en"
New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null
Set-Location "$env:USERPROFILE\OneDrive\Desktop\PocketGPT"
@"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Systran/faster-whisper-base.en", local_dir=r"$whisperDir")
"@ | .\.venv\Scripts\python.exe -
.\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium --download-dir $voiceDir
```

Check that these files exist before starting the app:

```powershell
Test-Path (Join-Path $whisperDir "model.bin")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx.json")
```

The model paths are resolved under `%LOCALAPPDATA%\PocketAgent\voice`. If a
package or asset is missing, text chat remains available and the voice control
shows a local setup error. Allow microphone access in the browser and in Windows
Settings > Privacy & security > Microphone. Use the transcript editor to review
or correct recognized words before sending.

Confirm Ollama can see `llama3.2:3b` before running the
benchmark. `ollama run` and `ollama pull` can fetch a model if it is missing, so do
not run either command unless you first approve that download.

```powershell
ollama list
```

Start the app in the same folder:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The app opens in a browser on the same PC. Stop it with `Ctrl+C`. Ollama must be
running locally and the selected model must already be installed. The app itself
does not download models. The response audio has a **Stop speaking** control;
browser autoplay policies may require clicking its audio play button instead.

### Verify offline operation

After the package and model setup is complete, disconnect networking (for example,
turn off Wi-Fi and unplug Ethernet), then launch PocketGPT and test a text prompt,
a microphone recording, and a spoken reply. This project has not yet been tested
with network access disabled, so offline operation is not yet verified.

## Qwen3 response diagnosis and benchmark

The installed `qwen3:4b` artifact is a 4B Q4_K_M Qwen3-4B-Thinking-2507 checkpoint.
Its `/api/show` data advertises only `think=true`, and the installed Ollama 0.40.11
template appends `<think>` after every final user turn. In unconstrained requests,
`think=true` put long reasoning in the separate `message.thinking` field; PocketGPT
did not display that field, but 1,024 generated tokens were consumed without a
visible answer. With `think=false`, the model's self-review appeared in
`message.content`. The same behavior reproduced through direct Ollama calls with
no system prompt and with a minimal system prompt, so conversation history and the
PocketGPT stream parser were not the cause.

For short vocabulary requests, PocketGPT now sends a JSON schema with exact field
counts and target-word constraints, uses `think=false`, and incrementally renders
only validated fields. Complex requests still use the optional reasoning setting.
The mode is local and does not pull a model. Repeat the three-question check with:

After `ollama list` confirms the existing model, measure it with:

```powershell
.\.venv\Scripts\python.exe benchmark.py llama3.2:3b
```

The benchmark warms the existing model locally, then sends three fresh requests
with an 8,192-token context, a 256-token cap, temperature 0.7, and `think=false`.
On 2026-10-27, all three responses stopped normally and returned the requested
shape:

| Word | First visible field | Total time | Generated tokens | Quality review |
|---|---:|---:|---:|---|
| ephemeral | 2.92 s | 10.85 s | 69 | Definition, synonyms, and examples were good |
| meticulous | 5.44 s | 14.94 s | 75 | Definition, synonyms, and examples were good |
| reluctant | 4.50 s | 13.90 s | 78 | Correct structure and examples; “doubtful” was a weak synonym |

An exact seeded request sent directly to Ollama and through PocketGPT's client
returned the same definition and synonyms; example wording varied. The wrapper
formats the model's JSON and validates field counts, non-duplicate synonyms, and
that both examples contain the whole target word. The 4B model can still choose a
related but imperfect synonym, as the “reluctant” result shows.

## Tests

Run the local unit suite with the installed Python interpreter:

```powershell
python -m pytest -q
```

Tests use temporary SQLite databases, mocked Ollama streams, and mocked speech
engines. They do not need Ollama, downloaded speech assets, or internet access.

## Data and privacy notes

- Chat messages are sent to the local Ollama service only. The client uses a direct
  loopback TCP connection and ignores proxy environment variables.
- Cloud-tagged Ollama models are excluded from the picker and rejected by the API
  client.
- Conversation history remains in the local SQLite database until cleared by the
  user. Clearing requires confirmation in the UI.
- Streamlit usage statistics are disabled and the web server binds to `127.0.0.1`.
- The code has not yet been exercised with networking disabled. Do not treat the
  app as verified offline until it has been installed and tested in that state.

