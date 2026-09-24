# J.A.R.V.I.S — Personal Voice-Controlled AI Assistant

A locally-run, voice-activated AI assistant for Windows, built from scratch — inspired by Iron Man's JARVIS.

## What it does

- **Wake word activation** — always listening for "Hey Jarvis" (via openWakeWord), zero cloud dependency for wake detection
- **Natural conversation** — understands casual, messy speech (not just fixed commands) via a locally-run LLM (Llama 3.1 8B through Ollama)
- **Follow-up conversations** — no need to repeat the wake word for follow-up questions within a session
- **Real calendar access** — reads your actual Google Calendar via OAuth, tells you your schedule by voice
- **WhatsApp messaging** — finds a contact, drafts a message, confirms with you, and sends it (via Selenium browser automation)
- **Screen vision** — takes a screenshot and describes/analyzes what's on your screen using a local vision model (Llava)
- **System control** — adjusts volume and brightness by voice
- **Dev progress log** — a simple voice-powered journal for tracking project progress over time
- **Custom HUD** — a fullscreen animated overlay (HTML/CSS/JS via pywebview) with a live clock, weather, CPU/RAM stats, calendar preview, and an activity log — pops up on wake word, hides when idle
- **Runs fully locally** — no per-message API costs, no cloud dependency for the core assistant loop (calendar/WhatsApp are the only pieces that talk to external services, and only when asked)

## Tech stack

- **Python** — core orchestration
- **openWakeWord** — offline wake-word detection
- **SpeechRecognition + PyAudio** — voice input
- **pyttsx3** — text-to-speech output
- **Ollama (Llama 3.1 8B / Llava)** — local LLM for conversation + vision
- **pywebview** — renders the custom HTML/CSS/JS HUD as a native overlay window
- **Selenium** — WhatsApp Web automation
- **Google Calendar API (OAuth)** — real calendar access
- **pycaw / screen-brightness-control** — system-level volume & brightness control

## Setup

1. Install Python 3.13+ and the dependencies (see `requirements.txt`)
2. Install [Ollama](https://ollama.com) and pull `llama3.1:8b` and `llava`
3. Set up your own Google Cloud project + OAuth credentials for Calendar API access, save as `credentials.json` in the project folder (never commit this file)
4. Run `Jarvis.py`

## Project status

Actively in development. Built as a learning project to explore voice interfaces, local AI, browser automation, and building a genuinely useful personal assistant end-to-end — from ears, to brain, to hands, to a face.

## Author

Built by Abdullah — first-time game developer (see also: [Aagnee Chronicles]) and hobbyist AI/systems builder.
