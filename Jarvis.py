import speech_recognition as sr
import pyttsx3
import os
import webbrowser
import pyaudio
import numpy as np
import requests
import threading
import psutil
import time
import re
from openwakeword.model import Model

import jarvis_ui  # our HUD module (hud.html must be in the same folder)
import whatsapp_control
import calendar_control
import vision_control
import devlog_control
import system_control
import dev_control

recognizer = sr.Recognizer()

PREFERRED_MIC_NAME = "BY-V10"  # if you have this mic, we'll use it specifically; otherwise auto-detect

def get_default_mic_index():
    """Looks for a preferred mic by name first (useful if your built-in mic is bad).
    Falls back to the system default input device, then to the first available mic."""
    p = pyaudio.PyAudio()
    try:
        # 1) try to find the preferred mic by name
        if PREFERRED_MIC_NAME:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if PREFERRED_MIC_NAME.lower() in info.get("name", "").lower() and info.get("maxInputChannels", 0) > 0:
                    p.terminate()
                    return i

        # 2) fall back to system default input device
        default_info = p.get_default_input_device_info()
        p.terminate()
        return default_info["index"]
    except Exception:
        # 3) last resort: first device with any input channels
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                p.terminate()
                return i
        p.terminate()
        return 0

MIC_INDEX = get_default_mic_index()
print(f"Using microphone index: {MIC_INDEX}")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

conversation_history = []  # keeps recent exchanges so follow-ups have context
MAX_HISTORY_TURNS = 6  # keep last 6 exchanges (user+jarvis pairs)

# ---- Voice output ----
def speak(text):
    print("JARVIS:", text)
    jarvis_ui.ui_set_state("speaking")
    jarvis_ui.ui_set_status(text)
    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
    jarvis_ui.ui_set_state("idle")
    jarvis_ui.ui_clear_response()   # hide long-response panel once speaking ends

# ---- Listen for a command (after wake word, or during a follow-up window) ----
def listen_for_command(timeout=None, phrase_time_limit=None):
    jarvis_ui.ui_set_state("listening")
    jarvis_ui.ui_set_status("Listening...")
    with sr.Microphone(device_index=MIC_INDEX) as source:
        print("Listening for command...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        recognizer.pause_threshold = 1.8  # wait longer before deciding you're done talking
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return None  # nobody spoke in time - different from "" (heard but didn't understand)

    try:
        text = recognizer.recognize_google(audio)
        print("You said:", text)
        jarvis_ui.ui_set_status(f"You said: {text}")
        return text.lower()
    except sr.UnknownValueError:
        speak("Sorry, I didn't catch that.")
        return ""
    except sr.RequestError:
        speak("Speech service is down or no internet.")
        return ""

# ---- Ask the local AI brain (Ollama) ----
def ask_brain(user_text):
    jarvis_ui.ui_set_state("thinking")
    jarvis_ui.ui_set_status("Thinking...")

    # build the recent conversation as context
    history_text = ""
    for turn in conversation_history[-MAX_HISTORY_TURNS:]:
        history_text += f'User: "{turn["user"]}"\nJARVIS: "{turn["jarvis"]}"\n'

    project_ctx = dev_control.get_project_context()

    # Only inject project context when the question clearly relates to code / the project.
    # Uses the shared _code_kw_match() helper (defined below) which applies word-boundary
    # matching for short terms to avoid false positives like "api" inside "capital".
    is_code_question = project_ctx and _code_kw_match(user_text)

    if is_code_question:
        # Developer-assistant mode: question is clearly code/project related
        prompt = f"""You are JARVIS Dev, an expert AI developer assistant running on the user's PC.
You have been given the full source code and file tree of the user's active project below.
Answer questions about the codebase accurately and concisely.
Keep replies to 2-3 sentences when spoken, but you may give longer answers for code review or explanations.
Do NOT invent details that are not in the provided code.

=== ACTIVE PROJECT CONTEXT ===
{project_ctx}
=== END PROJECT CONTEXT ===

Recent conversation:
{history_text}
User said: "{user_text}"
"""
    else:
        # Normal conversation — use the original voice-assistant persona regardless of project state
        prompt = f"""You are JARVIS, a helpful voice assistant running on the user's PC.
Reply in 1-2 short sentences, casual and friendly, since your reply will be spoken out loud.

IMPORTANT: You do NOT have access to the user's real calendar, email, messages, game dev progress log,
or any personal files in this conversation. If the user asks about their schedule, meetings, emails,
messages, or game dev progress, do NOT make up or invent any details (no fake names, times, events,
or progress). Instead, tell them to ask again more clearly, for example: "Try asking me 'what's on my
schedule today'" or "Try asking me 'what's my game dev progress'" so I can check the real data.

Here is the recent conversation so far, use it to understand follow-up questions:
{history_text}
User said: "{user_text}"
"""
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        })
        data = response.json()
        reply = data.get("response", "").strip()
    except Exception:
        reply = "I'm having trouble thinking right now, sorry."

    # save this exchange to history
    conversation_history.append({"user": user_text, "jarvis": reply})
    if len(conversation_history) > MAX_HISTORY_TURNS:
        conversation_history.pop(0)

    return reply

# ---- Take action based on command (fixed commands first, then AI fallback) ----
def take_action(command):
    try:
        return _take_action_inner(command)
    except Exception as e:
        print("take_action crashed:", e)
        speak("Something went wrong there, but I'm still here.")
        return True

# Code-keyword matcher used by both ask_brain() and _take_action_inner().
# Short ambiguous terms (api, file, loop…) use word-boundary regex to avoid
# substring false positives like "api" inside "capital".
# "dot py" is included in _CKW_SUBSTR so spoken filenames ("vision control dot py")
# trigger dev mode before normalization runs.
import re as _re_routing
_CKW_SUBSTR = (
    ".py", "dot py",                          # ".py" in text OR "dot py" spoken
    "function", "module", "import", "class", "method", "variable",
    "codebase", "repository", "stack trace", "wake word", "ollama",
    "architecture", "pipeline", "endpoint",
)
_CKW_WORD = (
    "file", "code", "script", "program", "project", "bug", "error",
    "crash", "exception", "debug", "api", "loop", "thread", "system",
    "library",
)
def _code_kw_match(text: str) -> bool:
    t = text.lower()
    return (
        any(kw in t for kw in _CKW_SUBSTR)
        or any(_re_routing.search(r'\b' + _re_routing.escape(kw) + r'\b', t) for kw in _CKW_WORD)
    )


def _normalize_spoken(command: str) -> str:
    """Normalize common speech-to-text transcriptions before routing and filename resolution.
    - "X dot py" / "X dot P Y" → "X.py"   (spoken filename extension)
    - "underscore" → "_"                    (spoken underscore in filenames)
    Returns the lowercased, normalized command string.
    """
    t = command.lower()
    # Replace " dot py" (with preceding space) so "vision control dot py" → "vision control.py"
    t = _re_routing.sub(r'\s+dot\s+p\s*y\b', '.py', t)   # "X dot P Y" / "X dot py"
    t = t.replace(" underscore ", "_").replace(" underscore", "_")
    return t


def _mentions_project_file(command: str) -> bool:
    """Returns True if any n-gram in the command is a strong match for a real indexed project file.
    Only uses exact/suffix/exact-stem matching (not partial-stem) to avoid false positives like
    'what' matching 'whatsapp_control.py' or 'is' matching 'Jarvis.py'.
    Candidates must be at least 4 characters to filter common words.
    """
    if not dev_control.get_active_project_path():
        return False
    contents = dev_control.get_file_contents()
    if not contents:
        return False

    words = command.split()
    import pathlib as _pl
    for length in range(min(len(words), 5), 0, -1):   # max 5-word n-grams
        for start in range(len(words) - length + 1):
            candidate = " ".join(words[start:start + length]).strip().lower()
            if len(candidate) < 4:          # skip single short words
                continue
            cand_stem = candidate.replace(" ", "_").replace(".py", "").replace(".", "_")
            for rel in contents:
                rel_l = rel.lower()
                rel_stem = _pl.Path(rel).stem.lower()
                # Tier 1: exact
                if rel_l == candidate:
                    return True
                # Tier 2: suffix
                if rel_l.endswith(candidate):
                    return True
                # Tier 3: exact stem (no partial)
                if rel_stem == cand_stem:
                    return True
    return False

def _take_action_inner(command):
    # Normalize speech-to-text quirks (e.g. "dot py" → ".py") before any routing.
    command = _normalize_spoken(command)
    jarvis_ui.ui_add_log(f"Heard: {command}")

    # ---- Time / date — read local system clock directly, never ask Ollama ----
    if any(phrase in command for phrase in [
            "what time is it", "what's the time", "current time",
            "tell me the time", "what time"
          ]) and "schedule" not in command and "calendar" not in command:
        import datetime as _dt
        now = _dt.datetime.now()
        # strftime("%I") gives zero-padded 12-hour; lstrip("0") removes the leading zero
        time_str = now.strftime("%I:%M %p").lstrip("0")
        speak(f"It's {time_str}.")
    elif any(phrase in command for phrase in [
            "what's today's date", "what is today's date", "what day is it",
            "today's date", "what is the date", "what date is it"
          ]):
        import datetime as _dt
        now = _dt.datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        speak(f"Today is {date_str}.")
    elif any(phrase in command for phrase in ["set project", "load project", "switch project"]):
        # extract everything after the trigger phrase as the path; default to current dir
        for phrase in ["set project", "load project", "switch project"]:
            if phrase in command:
                path = command.split(phrase, 1)[1].strip() or "."
                break
        jarvis_ui.ui_set_state("thinking")
        result = dev_control.set_active_project(path)
        speak(result)
    elif any(phrase in command for phrase in ["analyze project", "analyze my project", "analyse project", "analyse my project"]):
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Analyzing project...")
        result = dev_control.analyze_project()
        jarvis_ui.ui_set_long_response(result)
        speak(result)
    elif "review" in command and dev_control.get_active_project_path():
        # extract filename: strip the trigger word and any filler
        filename = (command
                    .replace("review", "")
                    .replace("the file", "")
                    .replace("file", "")
                    .strip())
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Reviewing code...")
        result = dev_control.review_code(filename)
        jarvis_ui.ui_set_long_response(result)
        speak(result)
    elif (any(phrase in command for phrase in [
            "how does", "what does", "where is", "how do",
            "explain the", "explain my", "ask about", "tell me about the",
            "tell me about my", "what is the", "how is the",
            "explain",           # bare "explain X" — fires when code kw OR project file present
          ]) and dev_control.get_active_project_path()
          and (_code_kw_match(command) or _mentions_project_file(command))):
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Looking up code...")
        result = dev_control.ask_about_code(command)
        jarvis_ui.ui_set_long_response(result)
        speak(result)
    elif any(phrase in command for phrase in [
            "check my project for errors", "debug my project",
            "check for errors", "find bugs", "scan for bugs",
            "scan my project"
          ]) and dev_control.get_active_project_path():
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Scanning project for errors...")
        result = dev_control.detect_project_errors()
        jarvis_ui.ui_set_long_response(result)
        speak(result)
    elif any(phrase in command for phrase in [
            "analyze error", "analyze this error", "debug this error",
            "what is this error", "why am i getting", "fix this error",
            "debug this", "what's wrong with this", "explain this error"
          ]):
        # extract error text after common delimiters; prompt if nothing follows
        error_text = ""
        for delim in ["error:", "trace:", "debug this error", "analyze this error",
                      "analyze error", "what is this error", "fix this error",
                      "debug this", "why am i getting", "what's wrong with this",
                      "explain this error"]:
            if delim in command:
                error_text = command.split(delim, 1)[1].strip()
                break
        if not error_text:
            speak("What's the error message?")
            error_text = listen_for_command(timeout=20, phrase_time_limit=30) or ""
        if error_text:
            jarvis_ui.ui_set_state("thinking")
            jarvis_ui.ui_set_status("Analyzing error...")
            result = dev_control.explain_error(error_text)
            jarvis_ui.ui_set_long_response(result)
            speak(result)
        else:
            speak("I didn't catch the error message. Please try again.")
    elif any(phrase in command for phrase in [
            "generate tests", "write tests", "create tests"
          ]):
        # extract filename after the trigger phrase
        filename = command
        for phrase in ["generate tests for", "write tests for", "create tests for",
                       "generate tests", "write tests", "create tests"]:
            if phrase in filename:
                filename = filename.split(phrase, 1)[1].strip()
                break
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Generating tests...")
        result = dev_control.generate_tests(filename)
        jarvis_ui.ui_set_long_response(result)
        speak(result)
    elif "open notepad" in command:
        os.system("notepad")
        speak("Opening Notepad.")
    elif "open calculator" in command:
        os.system("calc")
        speak("Opening Calculator.")
    elif "open chrome" in command:
        os.system("start chrome")
        speak("Opening Chrome.")
    elif "open edge" in command:
        os.system("start msedge")
        speak("Opening Edge.")
    elif "youtube" in command and "open" in command:
        webbrowser.open("https://www.youtube.com")
        speak("Opening YouTube.")
    elif "spotify" in command:
        try:
            os.system("start spotify")
            speak("Opening Spotify.")
        except Exception:
            webbrowser.open("https://open.spotify.com")
            speak("Opening Spotify in your browser.")
    elif "file explorer" in command or "open files" in command:
        os.system("start explorer")
        speak("Opening File Explorer.")
    elif "unreal" in command and "open" in command:
        speak("I don't have Unreal's launch path set up yet, you'll need to tell me where it's installed.")
    elif "search" in command and ("for" in command or "google" in command or len(command.split()) < 8):
        query = command.replace("search", "").replace("google", "").replace("for", "").strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        speak(f"Searching for {query}.")
    elif "log progress" in command or "log my progress" in command:
        # everything after "progress:" or "progress" becomes the log entry
        if "progress:" in command:
            entry_text = command.split("progress:", 1)[1].strip()
        else:
            entry_text = command.split("progress", 1)[1].strip()

        if not entry_text:
            speak("What should I log?")
            entry_text = listen_for_command(timeout=15, phrase_time_limit=25)

        if entry_text:
            devlog_control.add_entry(entry_text)
            speak("Got it, logged.")
            jarvis_ui.ui_set_project("In Dev", "Just now")
        else:
            speak("Didn't catch that, nothing logged.")
    elif "yesterday" in command and ("work" in command or "progress" in command or "did i" in command):
        result = devlog_control.get_yesterday_summary()
        speak(result)
    elif "game dev progress" in command or "how far am i" in command or "project progress" in command:
        result = devlog_control.get_recent_summary()
        speak(result)
    elif "volume" in command:
        if "mute" in command:
            system_control.mute()
            speak("Muted.")
        elif "unmute" in command:
            system_control.unmute()
            speak("Unmuted.")
        elif "up" in command or "increase" in command or "raise" in command:
            new_vol = system_control.change_volume(10)
            speak(f"Volume at {new_vol} percent.")
        elif "down" in command or "decrease" in command or "lower" in command:
            new_vol = system_control.change_volume(-10)
            speak(f"Volume at {new_vol} percent.")
        else:
            # try to catch "set volume to 50"
            digits = "".join(ch for ch in command if ch.isdigit())
            if digits:
                target = int(digits)
                system_control.set_volume(target)
                speak(f"Volume set to {target} percent.")
            else:
                current = system_control.get_volume()
                speak(f"Your volume is at {current} percent.")
    elif "brightness" in command:
        if "up" in command or "increase" in command or "raise" in command:
            new_val = system_control.change_brightness(15)
            speak(f"Brightness at {new_val} percent.")
        elif "down" in command or "decrease" in command or "lower" in command or "dim" in command:
            new_val = system_control.change_brightness(-15)
            speak(f"Brightness at {new_val} percent.")
        else:
            digits = "".join(ch for ch in command if ch.isdigit())
            if digits:
                target = int(digits)
                system_control.set_brightness(target)
                speak(f"Brightness set to {target} percent.")
            else:
                current = system_control.get_brightness()
                speak(f"Your brightness is at {current} percent.")
    elif "screen" in command:
        speak("Let me take a look.")
        jarvis_ui.ui_set_state("thinking")
        jarvis_ui.ui_set_status("Analyzing your screen...")
        result = vision_control.analyze_screen()
        speak(result)
    elif any(phrase in command for phrase in [
        "schedule", "calendar", "my day", "what's on my plate",
        "what do i have today", "agenda", "any meetings", "any events"
    ]):
        speak("Let me check your calendar.")
        try:
            time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', command)
            if time_match and ("at" in command or "pm" in command or "am" in command or "o'clock" in command):
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                meridiem = time_match.group(3)
                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                result = calendar_control.get_event_at_time(hour, minute)
                speak(result)
            else:
                summary = calendar_control.get_schedule_summary_text()
                events = calendar_control.get_todays_events()
                jarvis_ui.ui_set_schedule(events)
                speak(summary)
        except Exception as e:
            print("Calendar error:", e)
            speak("I couldn't reach your calendar. You may need to reconnect it.")
    elif "message" in command or "whatsapp" in command:
        handle_whatsapp_message(command)
    elif "stop" in command or "exit" in command or "goodbye" in command:
        speak("Goodbye!")
        return False
    else:
        reply = ask_brain(command)
        speak(reply)
    return True

# ---- WhatsApp message flow ----
def handle_whatsapp_message(command):
    try:
        _handle_whatsapp_message_inner(command)
    except Exception as e:
        print("WhatsApp flow crashed:", e)
        speak("Something went wrong with WhatsApp, let's try that again later.")

def _handle_whatsapp_message_inner(command):
    # extract contact name: strips filler words, keeps just the name
    filler_words = ["send", "message", "to", "whatsapp", "a"]
    words = command.split()
    words = [w for w in words if w not in filler_words]
    contact_name = " ".join(words).strip().title()

    if not contact_name:
        speak("Who do you want to message?")
        contact_name = listen_for_command(timeout=8, phrase_time_limit=8)
        if not contact_name:
            speak("Didn't catch a name, cancelling.")
            return
        contact_name = contact_name.title()

    speak(f"Opening WhatsApp and searching for {contact_name}.")
    whatsapp_control.open_whatsapp()
    found = whatsapp_control.find_and_open_contact(contact_name)

    if not found:
        speak(f"I couldn't find {contact_name} on WhatsApp.")
        return

    speak("What should I say?")
    message_text = listen_for_command(timeout=15, phrase_time_limit=20)
    if not message_text:
        speak("Didn't catch that, cancelling.")
        return

    whatsapp_control.type_message(message_text)
    speak(f"Ready to send: {message_text}. Say yes to send, or no to cancel.")

    confirmation = listen_for_command(timeout=8, phrase_time_limit=6)
    if confirmation and "yes" in confirmation:
        whatsapp_control.send_message()
        speak("Message sent.")
    else:
        speak("Okay, cancelled. I left it typed in the chat if you want to edit it yourself.")

# ---- Background loop: keep HUD stats live (CPU, RAM, weather) ----
def system_stats_loop():
    last_weather_check = 0
    weather_text = "Loading..."
    while True:
        try:
            cpu = int(psutil.cpu_percent(interval=1))
            ram = int(psutil.virtual_memory().percent)
            jarvis_ui.ui_set_stats(cpu, ram)
        except Exception:
            pass

        # refresh weather every 10 minutes only (free API, no key needed - Islamabad coords)
        if time.time() - last_weather_check > 600:
            try:
                resp = requests.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={"latitude": 33.6844, "longitude": 73.0479,
                            "current": "temperature_2m,weather_code"},
                    timeout=5
                )
                data = resp.json()
                temp = data["current"]["temperature_2m"]
                weather_text = f"{temp}°C"
                jarvis_ui.ui_set_weather(weather_text)
            except Exception:
                pass
            last_weather_check = time.time()

        time.sleep(3)

# ---- Wake word listener loop (runs in a background thread) ----
def voice_loop():
    print("Loading wake word model...")
    owwModel = Model(wakeword_models=["hey_jarvis_v0.1"])

    CHUNK = 1280
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                     input=True, input_device_index=MIC_INDEX,
                     frames_per_buffer=CHUNK)

    speak("JARVIS online. Say Hey Jarvis to wake me up.")
    print("Waiting for wake word 'Hey Jarvis'...")

    running = True
    while running:
        audio_chunk = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
        prediction = owwModel.predict(audio_chunk)

        for mdl, score in prediction.items():
            if score > 0.5:
                print(f"Wake word detected! ({mdl}: {score:.2f})")
                jarvis_ui.ui_show()
                speak("Yes?")
                command = listen_for_command()
                if command:
                    running = take_action(command)

                # ---- follow-up window: keep listening without needing "Hey Jarvis" again ----
                while running:
                    jarvis_ui.ui_set_status("Listening for follow-up...")
                    followup = listen_for_command(timeout=6, phrase_time_limit=15)
                    if followup is None:
                        # silence - go back to sleep, wait for wake word again
                        jarvis_ui.ui_set_state("idle")
                        jarvis_ui.ui_set_status("Awaiting command...")
                        jarvis_ui.ui_hide()
                        conversation_history.clear()
                        break
                    if followup:
                        running = take_action(followup)

                owwModel.reset()

if __name__ == "__main__":
    # restore the last active project so context is available from the first command
    restore_msg = dev_control.restore_last_project()
    if restore_msg:
        print("Dev context:", restore_msg)

    # voice loop and stats loop run in background, HUD runs on the main thread
    threading.Thread(target=voice_loop, daemon=True).start()
    threading.Thread(target=system_stats_loop, daemon=True).start()
    jarvis_ui.start_ui_blocking()