import webview
import os
import json

window = None

def start_ui_blocking():
    """Call this from the MAIN thread. Opens the HUD window and blocks until closed."""
    global window
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hud.html")
    window = webview.create_window(
        "JARVIS HUD",
        html_path,
        fullscreen=True,
        frameless=True,
        on_top=True,
        transparent=True,
        hidden=True,
    )
    webview.start()

# ---- Helper functions the voice/brain code calls to update the HUD ----
def ui_show():
    if window:
        try:
            window.show()
        except Exception:
            pass

def ui_hide():
    if window:
        try:
            window.hide()
        except Exception:
            pass

def ui_set_state(state):
    if window:
        try:
            window.evaluate_js(f"setState('{state}')")
        except Exception:
            pass

def ui_set_status(text):
    if window:
        safe_text = text.replace("'", "\\'").replace("\n", " ")
        try:
            window.evaluate_js(f"setStatusText('{safe_text}')")
        except Exception:
            pass

def ui_set_schedule(lines):
    if window:
        try:
            window.evaluate_js(f"setSchedule({json.dumps(lines)})")
        except Exception:
            pass

def ui_set_stats(cpu_pct, ram_pct):
    if window:
        try:
            window.evaluate_js(f"setStats({cpu_pct}, {ram_pct})")
        except Exception:
            pass

def ui_set_weather(text):
    if window:
        try:
            safe_text = text.replace("'", "\\'")
            window.evaluate_js(f"setWeather('{safe_text}')")
        except Exception:
            pass

def ui_add_log(text):
    if window:
        try:
            safe_text = text.replace("'", "\\'").replace("\n", " ")
            window.evaluate_js(f"addLogEntry('{safe_text}')")
        except Exception:
            pass