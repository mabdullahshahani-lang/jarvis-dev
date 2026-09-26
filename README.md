# JARVIS Dev

### Local AI Developer Assistant for Understanding Existing Codebases

JARVIS Dev is a locally running AI developer assistant designed to help developers understand and maintain existing software projects.

Instead of manually searching through files and trying to understand an unfamiliar codebase, developers can interact with their project conversationally through JARVIS.

## The Problem

Understanding an existing codebase can take significant time, especially when:

* Joining an unfamiliar project
* Maintaining an older application
* Trying to understand how different files work together
* Looking for specific functionality inside a large project

JARVIS Dev addresses this by loading project context and allowing developers to ask questions about the project and its code.

## Core Workflow

```text
Existing Project
       ↓
Project Context Loader
       ↓
JARVIS Dev
       ↓
Project Analysis
       ↓
Code Q&A
       ↓
Faster Codebase Understanding
```

## Key Features

### Project Analysis

JARVIS can analyze the loaded project and provide a structured overview of its codebase, including its main components and organization.

This is particularly useful when onboarding onto an unfamiliar project.

### Code Q&A

Developers can ask questions about specific code within the loaded project.

JARVIS uses the indexed project context to answer questions about files, functions, and implementation details.

### Project Context

JARVIS can load a project recursively and build a usable context from its source files while avoiding sensitive files and unnecessary data.

### Voice Interaction

JARVIS supports voice-based interaction, allowing developers to communicate with the assistant without relying entirely on a traditional text interface.

### Custom HUD

JARVIS includes a custom HTML/CSS/JavaScript HUD rendered through pywebview.

The interface provides visual feedback while JARVIS is listening, processing, and responding.

### Local AI

The core AI functionality runs locally through Ollama using Llama 3.1 8B.

This allows the developer-assistant workflow to operate without requiring a paid per-request cloud AI API.

## Technology Stack

* **Python** — core application and orchestration
* **Ollama** — local AI inference
* **Llama 3.1 8B** — local language model
* **openWakeWord** — wake-word detection
* **SpeechRecognition / PyAudio** — voice input
* **pyttsx3** — text-to-speech
* **pywebview** — native HUD interface
* **HTML / CSS / JavaScript** — HUD frontend
* **Selenium** — browser automation for existing assistant functionality
* **Google Calendar API** — calendar integration for existing assistant functionality

## How It Works

1. JARVIS starts and initializes the voice interface.
2. A project can be loaded into the developer context system.
3. Relevant project files are indexed and prepared as context.
4. The developer can request a project analysis.
5. The developer can ask questions about specific code.
6. JARVIS sends the relevant context to the locally running LLM.
7. The response is presented through the voice interface and HUD.

## Project Structure

```text
JARVIS/
│
├── Jarvis.py
├── jarvis_ui.py
├── dev_control.py
├── vision_control.py
├── calendar_control.py
├── whatsapp_control.py
├── devlog_control.py
├── system_control.py
├── hud.html
├── start_jarvis.bat
├── requirements.txt
└── README.md
```

## Running JARVIS Dev

### Requirements

* Windows
* Python 3.13+
* Ollama
* Llama 3.1 8B
* Required Python packages from `requirements.txt`

### Setup

1. Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

2. Install Ollama.

3. Pull the local model:

```bash
ollama pull llama3.1:8b
```

4. Start JARVIS:

```bash
python Jarvis.py
```

The project may also be launched using the included:

```text
start_jarvis.bat
```

## Security

Sensitive files are excluded from project context and version control.

The project uses `.gitignore` and `.bobignore` to prevent files such as credentials, authentication tokens, WhatsApp sessions, and private development logs from being included.

Never commit personal credentials or API tokens to the repository.

## Demo

The demo demonstrates the core developer workflow:

**Project Analysis → Code Understanding → Code Q&A**

The demonstration focuses on how JARVIS can help a developer understand an existing project without manually inspecting every file.

## Challenge Connection

JARVIS Dev was created for the developer-workflow challenge by focusing on:

**Developer onboarding and application maintenance.**

The workflow is designed to reduce the time developers spend understanding an unfamiliar codebase by providing project-level analysis and conversational access to its code.

## Project Status

JARVIS Dev is a working prototype developed during the hackathon.

The project is actively evolving, with the current prototype focused on project context, project analysis, code Q&A, voice interaction, and the custom HUD.

## Author

Built by Abdullah

A developer exploring local AI, game development, voice interfaces, and software systems.
