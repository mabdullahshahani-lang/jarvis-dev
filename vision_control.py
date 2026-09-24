import base64
import io
import requests
from PIL import ImageGrab

OLLAMA_URL = "http://localhost:11434/api/generate"
VISION_MODEL = "llava"


def take_screenshot_base64():
    """Captures the screen and returns it as a base64 string (what Ollama's vision API expects)."""
    screenshot = ImageGrab.grab()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8")


def analyze_screen(question="What's on my screen right now? Describe it briefly."):
    """Takes a screenshot and asks Llava to describe/answer about it."""
    try:
        img_b64 = take_screenshot_base64()
        response = requests.post(OLLAMA_URL, json={
            "model": VISION_MODEL,
            "prompt": question,
            "images": [img_b64],
            "stream": False
        }, timeout=180)
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        print("Vision error:", e)
        return "Sorry, I couldn't analyze your screen right now."