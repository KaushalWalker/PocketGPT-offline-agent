PocketGPT — Your AI Companion, Even Without the Internet

A privacy-first, open-source AI companion that runs locally on your computer. Chat, learn, think, and speak with AI without relying on cloud services.

""License: MIT" (https://img.shields.io/badge/License-MIT-green.svg)" (LICENSE)
"Python" (https://img.shields.io/badge/Python-3.11%2B-blue)
"Platform" (https://img.shields.io/badge/Platform-Windows-blue)
"Offline" (https://img.shields.io/badge/AI-Offline-brightgreen)
"Contributions" (https://img.shields.io/badge/Contributions-Welcome-orange)

«Status: Windows MVP working and manually tested with the internet disconnected. Android development is planned.»

Why PocketGPT?

Most AI assistants depend on an internet connection and remote servers.

PocketGPT explores a different approach: What if your everyday AI companion lived entirely on your own device?

The goal is to make local AI useful for everyday conversations, reading, learning English, understanding difficult ideas, and asking technical questions.

No cloud LLM API keys. No mandatory account. No internet connection required after the initial setup.

Features

Feature| Status
Local AI chat using Ollama| ✅ Working
Multi-turn conversations| ✅ Working
Persistent conversation history| ✅ Working
Reopen previous conversations| ✅ Working
Reading and vocabulary companion| ✅ Working
Definitions, synonyms, and examples| ✅ Working
Offline speech-to-text| ✅ Working
Offline text-to-speech| ✅ Working
Editable voice transcripts| ✅ Working
Fully offline Windows operation| ✅ Manually verified
Native Android app| 🚧 Planned
Document import and analysis| 💡 Future improvement

Local AI chat

Ask questions, discuss ideas, learn programming concepts, or explore new topics using a language model running on your own computer.

PocketGPT uses Ollama for local inference and supports selecting already-installed local models. The current tested configuration uses "llama3.2:3b".

Reading companion

Built for readers and curious learners.

Use PocketGPT to:

- Understand unfamiliar English words.
- Find synonyms and usage examples.
- Explain difficult concepts and passages.
- Explore ideas from books.
- Practice asking questions in English.

Vocabulary responses use structured output and validation to improve consistency, although model answers can still contain mistakes.

Offline voice conversations

Talk to PocketGPT using your microphone and receive spoken responses.

The voice workflow uses:

- Faster Whisper for local speech recognition.
- Piper for local speech synthesis.
- Ollama for generating responses.

You can review and edit recognized text before submitting it.

Speech recognition, language-model inference, and speech synthesis all run locally.

Conversation history

Conversations are stored in a local SQLite database so you can return to previous discussions without relying on a cloud account.

Demo

Screenshots and a short demonstration video are coming soon.

The planned demo will show PocketGPT answering questions, recognizing speech, and speaking responses while the computer is disconnected from the internet.

Tech stack

Component| Technology
Language| Python
Interface| Streamlit
Local LLM runtime| Ollama
Tested language model| Llama 3.2 3B
Speech recognition| Faster Whisper
Text-to-speech| Piper
Conversation storage| SQLite
Testing| pytest

Architecture

                  User
                   |
          Streamlit Interface
                   |
        +----------+----------+
        |                     |
     Text Input           Microphone
        |                     |
        |              Faster Whisper
        |              (Offline STT)
        |                     |
        +----------+----------+
                   |
          Conversation Manager
                   |
            Ollama Local API
            127.0.0.1:11434
                   |
             Local LLM
             llama3.2:3b
                   |
             AI Response
                   |
        +----------+----------+
        |                     |
     Text Output          Piper TTS
        |                     |
        |                Spoken Reply
        |
    SQLite History

All AI processing takes place on the user's computer.

Getting started

Requirements

- Windows PC
- Python 3.11 or newer with compatible package wheels
- Ollama installed and running locally
- A locally installed Ollama language model
- Microphone and speakers for voice features
- Internet connection for initial package and model downloads

The tested development laptop has 16 GB RAM. Actual performance will depend on your hardware and selected models.

1. Clone the repository

Open PowerShell:

git clone https://github.com/KaushalWalker/PocketGPT-offline-agent.git
cd PocketGPT-offline-agent

2. Create a Python virtual environment

python -m venv .venv

Install the dependencies:

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

The project pins "av==18.1.0" because the tested speech-recognition configuration encountered a compatibility error with PyAV 19.0.2.

3. Install and configure Ollama

Download Ollama from:

https://ollama.com/download

For the tested configuration, download the local language model:

ollama pull llama3.2:3b

This step requires internet access and downloads model weights to your computer.

Check the installed models:

ollama list

Ensure Ollama is running locally. PocketGPT does not automatically download language models.

4. Download the offline voice models

PocketGPT uses two separate speech models:

Model| Purpose| Approximate size
"Systran/faster-whisper-base.en"| English speech recognition| 148 MB
"en_US-lessac-medium"| English text-to-speech| 63 MB

Run the following PowerShell commands from the repository directory:

$voiceDir = Join-Path $env:LOCALAPPDATA "PocketAgent\voice"
$whisperDir = Join-Path $voiceDir "faster-whisper-base.en"

New-Item -ItemType Directory -Force -Path $voiceDir | Out-Null

@"
from huggingface_hub import snapshot_download
snapshot_download(repo_id="Systran/faster-whisper-base.en", local_dir=r"$whisperDir")
"@ | .\.venv\Scripts\python.exe -

.\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium --download-dir $voiceDir

Verify the downloaded files:

Test-Path (Join-Path $whisperDir "model.bin")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx")
Test-Path (Join-Path $voiceDir "en_US-lessac-medium.onnx.json")

All three commands should return "True".

These models are stored under the current Windows user's local application data directory, not inside the Git repository.

5. Launch PocketGPT

.\.venv\Scripts\python.exe -m streamlit run app.py

Open the local URL shown in the terminal, typically:

http://localhost:8501

The exact port may differ if another Streamlit app is already running.

Allow microphone access in your browser and Windows privacy settings if you want to use voice features.

Stop the application using "Ctrl+C" in the terminal.

Verify offline operation

After installing the dependencies and downloading all required models:

1. Confirm PocketGPT works normally while connected.
2. Disconnect Wi-Fi and any other internet connection.
3. Keep Ollama running locally.
4. Ask a text question.
5. Record and transcribe a spoken question.
6. Generate a response and play it using local text-to-speech.
7. Reopen a saved conversation.

Verification status: The maintainer has successfully completed a manual offline test of the Windows application, including chat, voice input, and spoken responses.

This is a manual functional test, not a formal security or network audit. Users should verify their own installations.

Privacy by design

PocketGPT is designed around local processing.

- LLM inference uses the local Ollama API.
- The Streamlit server is configured to bind to the local loopback interface.
- Cloud-tagged Ollama models are excluded from selection.
- Chat history is stored in a local SQLite database.
- Speech recognition and synthesis use downloaded local models.
- Streamlit usage telemetry is disabled in the project configuration.
- The application does not require cloud AI API keys.

Conversation history is stored at:

%LOCALAPPDATA%\PocketAgent\conversations.sqlite3

Models and packages must initially be downloaded from external sources. Browser, operating-system, and third-party software behavior is outside the scope of the application's privacy guarantees.

Performance and testing

PocketGPT includes "benchmark.py" for measuring local vocabulary response performance.

Run:

.\.venv\Scripts\python.exe benchmark.py llama3.2:3b

Example results from a local test on October 27, 2026:

Vocabulary prompt| First visible field| Total time
Ephemeral| 2.92 s| 10.85 s
Meticulous| 5.44 s| 14.94 s
Reluctant| 4.50 s| 13.90 s

These are measurements from one development machine, not guaranteed performance across devices. Response quality and timing depend on the hardware, model, and prompt.

Run tests

.\.venv\Scripts\python.exe -m pytest -q

The automated tests use mocked model and speech-engine components where appropriate. Real microphone and offline-operation tests must be performed separately.

Roadmap

Windows

- [x] Local language-model integration
- [x] Multi-turn chat
- [x] Persistent conversation history
- [x] Reading companion
- [x] Offline speech recognition
- [x] Offline spoken responses
- [x] Manual offline verification
- [ ] Improved interface and accessibility
- [ ] Document import and analysis
- [ ] Additional language support

Android

- [ ] Native Android interface
- [ ] On-device quantized LLM
- [ ] Local conversation history
- [ ] Offline speech recognition
- [ ] Offline text-to-speech
- [ ] Airplane-mode testing
- [ ] Performance optimization for mobile hardware

The Android application is a future development milestone. It is not currently included as a working release.

Contributing

PocketGPT is open to contributors, whether you're a beginner or an experienced developer.

Contributions involving bug fixes, documentation, accessibility, model optimization, reading features, and offline voice improvements are welcome.

To contribute:

1. Fork the repository.
2. Create a feature branch.
3. Make and test your changes.
4. Open a pull request explaining your changes.

Please read "CONTRIBUTING.md" (CONTRIBUTING.md) before submitting contributions.

For larger changes, open an Issue first to discuss the approach.

License

The original PocketGPT project code is released under the "MIT License" (LICENSE).

Third-party packages, models, and voices retain their respective licenses. In particular, "piper-tts" is GPL-3.0-or-later, while the selected Piper voice is MIT-licensed. Redistributors are responsible for satisfying applicable license obligations.

Author

Kaushal Jambhale

AI/ML Engineer | Building practical AI systems

- GitHub: https://github.com/KaushalWalker
- LinkedIn: https://www.linkedin.com/in/kaushaljambhle/

---

PocketGPT is an experiment in making AI more personal, private, and accessible—one device at a time.

If you find the project useful, consider starring the repository, opening an Issue, or contributing an improvement.