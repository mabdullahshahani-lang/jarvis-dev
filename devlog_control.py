import os
import json
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "devlog.json")


def _load_log():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_log(entries):
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


def add_entry(text):
    """Adds a new progress entry with today's date."""
    entries = _load_log()
    entries.append({
        "date": datetime.date.today().isoformat(),
        "text": text
    })
    _save_log(entries)


def get_entries_for_date(target_date):
    """target_date: a datetime.date object"""
    entries = _load_log()
    return [e["text"] for e in entries if e["date"] == target_date.isoformat()]


def get_recent_summary(days=3, max_entries=5):
    """Returns a natural sentence summarizing the most recent entries."""
    entries = _load_log()
    if not entries:
        return "You haven't logged any game dev progress yet."

    recent = entries[-max_entries:]
    lines = [f"On {e['date']}: {e['text']}" for e in recent]
    return "Here's your recent progress: " + " ".join(lines)


def get_yesterday_summary():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    entries = get_entries_for_date(yesterday)
    if not entries:
        return "You didn't log anything yesterday."
    return "Yesterday you worked on: " + "; ".join(entries)
