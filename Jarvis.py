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
from openwakeword.model import Model

import jarvis_ui  # our HUD module (hud.html must be in the same folder)
import whatsapp_control
import calendar_control
import vision_control
import devlog_control
import system_control
import calendar_control

recognizer = sr.Recognizer()
MIC_INDEX = 1  # your BY-V10 mic
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

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
    prompt = f"""You are JARVIS, a helpful voice assistant running on the user's PC.
Reply in 1-2 short sentences, casual and friendly, since your reply will be spoken out loud.

IMPORTANT: You do NOT have access to the user's real calendar, email, messages, game dev progress log,
or any personal files in this conversation. If the user asks about their schedule, meetings, emails,
messages, or game dev progress, do NOT make up or invent any details (no fake names, times, events,
or progress). Instead, tell them to ask again more clearly, for example: "Try asking me 'what's on my
schedule today'" or "Try asking me 'what's my game dev progress'" so I can check the real data.

User said: "{user_text}"
"""
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        })
        data = response.json()
        return data.get("response", "").strip()
    except Exception:
        return "I'm having trouble thinking right now, sorry."

# ---- Take action based on command (fixed commands first, then AI fallback) ----
def take_action(command):
    jarvis_ui.ui_add_log(f"Heard: {command}")
    if "open notepad" in command:
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
            summary = calendar_control.get_schedule_summary_text()
            events = calendar_control.get_todays_events()
            jarvis_ui.ui_set_schedule(events)
            speak(summary)
        except Exception as e:
            print("Calendar error:", e)
            speak("I couldn't reach your calendar. You may need to reconnect it.")
    elif any(phrase in command for phrase in [
        "schedule", "calendar", "my day", "what's on my plate",
        "what do i have today", "agenda", "any meetings", "any events"
    ]):
        speak("Let me check your calendar.")
        try:
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
                        break
                    if followup:
                        running = take_action(followup)

                owwModel.reset()

if __name__ == "__main__":
    # voice loop and stats loop run in background, HUD runs on the main thread
    threading.Thread(target=voice_loop, daemon=True).start()
    threading.Thread(target=system_stats_loop, daemon=True).start()
    jarvis_ui.start_ui_blocking()