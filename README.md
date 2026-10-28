# PocketGPT — Your AI Companion, Even Without the Internet

**A privacy-first, open-source AI companion that runs locally on your Windows PC.** Chat, learn, explore ideas, and talk to AI without sending your conversations to a cloud AI service.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Offline AI](https://img.shields.io/badge/AI-Offline-brightgreen)
![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-orange)

> **Status:** Working Windows MVP, manually tested with the internet disconnected. A standalone Android app is planned, not yet released.

## Why PocketGPT?

Most AI assistants rely on remote servers. PocketGPT explores a simpler idea: **what if your everyday AI companion lived on your own device?**

Use it to discuss ideas, understand difficult passages, practice English, learn vocabulary, or ask programming questions—all with locally running models.

- **Private by design:** AI processing and conversation storage stay on your computer.
- **No cloud LLM API key or mandatory account.**
- **Offline after setup:** Download dependencies and models once, then use the app without an internet connection.
- **Open source:** Explore the code, report bugs, and contribute improvements.

## Features

| Feature | Status |
| --- | --- |
| Local AI chat with Ollama | ✅ Working |
| Multi-turn conversations | ✅ Working |
| Persistent SQLite chat history | ✅ Working |
| Reopen previous conversations | ✅ Working |
| Reading and vocabulary companion | ✅ Working |
| Definitions, synonyms, and examples | ✅ Working |
| Offline speech-to-text | ✅ Working |
| Offline spoken replies | ✅ Working |
| Editable voice transcripts | ✅ Working |
| Windows use without internet | ✅ Manually verified |
| Native Android app | 🚧 Planned |
| Document import and analysis | 💡 Future improvement |

### Local AI chat

Ask follow-up questions, explore topics, and select from compatible models already installed in Ollama. The tested default model is **`llama3.2:3b`**.

### Reading companion

Try prompts like:

- “What does *indolence* mean?”
- “Give me two synonyms for *meticulous*.”
- “Explain this paragraph in simple English.”
- “Help me improve this English sentence.”

Vocabulary answers use structured output and validation to improve consistency, but model responses can still be inaccurate.

### Offline voice conversations

Record a question using your microphone, review or edit the transcript, and send it to the local model. PocketGPT can then read the answer aloud.

- **Faster Whisper:** local English speech recognition
- **Ollama:** local language-model inference
- **Piper:** local text-to-speech

### Conversation history

Chats are saved in a local SQLite database, so you can start a new conversation or return to an older one without a cloud account.

## Demo

**Screenshots and a short demo video are coming soon.** The planned demonstration will show text chat, speech recognition, spoken replies, and operation with Wi-Fi disabled.

## Tech stack

| Component | Technology |
| --- | --- |
| Language | Python |
| Interface | Streamlit |
| Local LLM runtime | Ollama |
| Tested LLM | Llama 3.2 3B |
| Speech recognition | Faster Whisper |
| Text-to-speech | Piper |
| Conversation storage | SQLite |
| Tests | pytest |

## Architecture

```text
                          User
                           |
                    Streamlit UI
                     /         \
                Text input   Microphone
                     |           |
                     |     Faster Whisper
                     |     (local STT)
                     \           /
                      Chat request
                           |
                 Conversation manager
                           |
                   Ollama local API
                    127.0.0.1:11434
                           |
                    Local language
                         model
                           |
                       AI response
                      /           \
                Text output     Piper TTS
                      |           |
                SQLite history  Spoken reply
```

All AI inference and speech processing in this workflow run on the user's computer.

## Getting started (Windows)

### Prerequisites

- Windows PC
- Python 3.11 or newer **with compatible package wheels** (the maintainer's working environment used Python 3.11)
- Git
- [Ollama](https://ollama.com/download) installed and running locally
- A locally installed Ollama model
- Microphone and speakers/headphones for voice features
- Internet access for the **initial** downloads

The development laptop used for testing has **16 GB RAM**. Performance depends on your hardware and model choice.

### 1. Clone the repository

Open PowerShell:

```powershell
git clone https://github.com/KaushalWalker/PocketGPT-offline-agent.git
cd PocketGPT-offline-agent
```

### 2. Create an environment and install packages

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`requirements.txt` pins **`av==18.1.0`** because the tested speech-recognition setup encountered a `metadata_errors` compatibility error with PyAV 19.0.2.

### 3. Install Ollama and download a model

Install [Ollama](https://ollama.com/download), then run:

```powershell
ollama pull llama3.2:3b
ollama list
```

The `pull` command downloads model weights and needs an internet connection. Ensure the Ollama service is running. PocketGPT connects to **`http://127.0.0.1:11434`** and does not automatically download language models.

### 4. Download the voice models (one-time setup)

| Model | Purpose | Approx. download |
| --- | --- | ---: |
| `Systran/faster-whisper-base.en` | English speech recognition | 148 MB |
| `en_US-lessac-medium` | English speech synthesis | 63 MB |

Run the following **from the repository directory** in PowerShell:

```powershell
$voiceDir = Join-Path $env:LOCALAPPDATA "PocketAgent\voice"
$whisperDir = Join-Path $voiceDir "faster-whisper-base.en"

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

@"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Systran/faster-whisper-base.en", local_dir=r"$whisperDir")
"@ | .\.venv\Scripts\python.exe -

.\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium --download-dir $voiceDir
```

Check that the model files exist:

```powershell
Test-Path (Join-Path $whisperDir "model.bin")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx.json")
```

All three checks should return `True`. The models are stored under **`%LOCALAPPDATA%\PocketAgent\voice`**, not inside the Git repository. The two voice models require about **211 MB** in total, excluding package dependencies.

### 5. Launch PocketGPT

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL shown in the terminal, typically **http://localhost:8501**. The port may differ if another Streamlit application is running.

For voice input, allow microphone access in your browser and **Windows Settings → Privacy & security → Microphone**. To stop the app, press `Ctrl+C` in the terminal.

## Verify that it works offline

After the one-time downloads:

1. Start Ollama and PocketGPT while connected to the internet.
2. Confirm text and voice features work.
3. Disconnect Wi-Fi and any other internet connection, but keep both local programs running.
4. Ask a question using text chat.
5. Record and transcribe a spoken question.
6. Generate a response and play the spoken answer.
7. Reopen a saved conversation.

**Maintainer verification:** The Windows development machine successfully completed a manual offline test of chat, voice recognition, spoken responses, and conversation history. This is a functional test, **not** a formal security or network audit; results may vary by system.

## Privacy and local data

PocketGPT is designed around local processing:

- Ollama inference uses a local API.
- The Streamlit server is configured to bind to the local loopback interface.
- Cloud-tagged Ollama models are excluded from selection.
- Conversation history is stored in SQLite.
- Voice recognition and synthesis use locally downloaded models.
- Streamlit usage telemetry is disabled in the project configuration.
- No cloud AI API keys are required.

**Chat database:** `%LOCALAPPDATA%\PocketAgent\conversations.sqlite3`
**Voice assets:** `%LOCALAPPDATA%\PocketAgent\voice`

Initial downloads require external services. Browser, operating-system, Ollama, and other third-party software have their own behavior and privacy considerations.

## Performance and testing

The repository includes `benchmark.py` for local vocabulary-response measurements:

```powershell
.\.venv\Scripts\python.exe benchmark.py llama3.2:3b
```

Example measurements from one development laptop on **October 27, 2026**:

| Vocabulary prompt | First visible field | Total time |
| --- | ---: | ---: |
| Ephemeral | 2.92 s | 10.85 s |
| Meticulous | 5.44 s | 14.94 s |
| Reluctant | 4.50 s | 13.90 s |

These are illustrative measurements, not guaranteed timings.

Install the test runner if it is not already available:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```

Some automated tests mock the language model and speech engines. Test real microphones, audio playback, and disconnected operation separately.

## Roadmap

### Windows

- [x] Local language-model integration
- [x] Multi-turn chat and persistent history
- [x] Reading and vocabulary companion
- [x] Offline speech recognition
- [x] Offline spoken replies
- [x] Manual offline verification
- [ ] Improved interface and accessibility
- [ ] Document import and analysis
- [ ] Additional language support

### Android (planned)

- [ ] Native Android interface
- [ ] On-device quantized language model
- [ ] Local conversation history
- [ ] Offline speech recognition
- [ ] Offline text-to-speech
- [ ] Airplane-mode testing
- [ ] Performance optimization for mobile hardware

**Android is not yet available as a working release.**

## Contributing

Contributions are welcome from beginners and experienced developers alike. Bug reports, documentation improvements, accessibility work, tests, reading features, and local-model optimizations are all valuable.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes and test them.
4. Open a pull request explaining what changed and why.

For larger features, please open an Issue first. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

The original PocketGPT project code is licensed under the [MIT License](LICENSE).

**Third-party software and model licenses are separate.** In particular, `piper-tts` is GPL-3.0-or-later, while the selected Piper voice is MIT-licensed. Anyone redistributing bundled applications or dependencies should review and comply with the applicable terms.

## Acknowledgments

Built with open-source projects including [Ollama](https://github.com/ollama/ollama), [Streamlit](https://github.com/streamlit/streamlit), [Faster Whisper](https://github.com/SYSTRAN/faster-whisper), and [Piper](https://github.com/OHF-Voice/piper1-gpl).

## Author

**Kaushal Jambhale** — AI/ML Engineer building practical AI systems

- [GitHub](https://github.com/KaushalWalker)
- [LinkedIn](https://www.linkedin.com/in/kaushaljambhle/)

---

**Your AI. Your device. Your privacy.**

If PocketGPT is useful to you, consider starring the repository, opening an Issue, or contributing an improvement.
