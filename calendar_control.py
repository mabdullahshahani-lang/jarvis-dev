import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CREDS_PATH = os.path.join(BASE_DIR, "credentials.json")


def get_calendar_service():
    """Handles login (first time opens a browser to sign in), returns a usable calendar service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_todays_events():
    """Returns a list of short strings like '9:00 AM - Team standup' for today's events."""
    service = get_calendar_service()

    now = datetime.datetime.utcnow()
    start_of_day = datetime.datetime.combine(now.date(), datetime.time.min).isoformat() + "Z"
    end_of_day = datetime.datetime.combine(now.date(), datetime.time.max).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])

    if not events:
        return ["No events scheduled today"]

    lines = []
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        summary = event.get("summary", "Untitled event")
        # format time nicely if it's a datetime (not an all-day date)
        if "T" in start:
            dt = datetime.datetime.fromisoformat(start)
            time_str = dt.strftime("%I:%M %p").lstrip("0")
            lines.append(f"{time_str} - {summary}")
        else:
            lines.append(f"All day - {summary}")

    return lines


def get_schedule_summary_text():
    """Returns a natural sentence for JARVIS to speak out loud."""
    events = get_todays_events()
    if events == ["No events scheduled today"]:
        return "You have nothing scheduled today."
    return "Here's your schedule: " + "; ".join(events)


def get_event_at_time(target_hour, target_minute=0):
    """Checks if there's an event at/near a specific time today. Returns a natural sentence."""
    service = get_calendar_service()

    now = datetime.datetime.utcnow()
    start_of_day = datetime.datetime.combine(now.date(), datetime.time.min).isoformat() + "Z"
    end_of_day = datetime.datetime.combine(now.date(), datetime.time.max).isoformat() + "Z"

    events_result = service.events().list(
        calendarId="primary",
        timeMin=start_of_day,
        timeMax=end_of_day,
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events = events_result.get("items", [])
    target_total_minutes = target_hour * 60 + target_minute

    matches = []
    for event in events:
        start = event["start"].get("dateTime")
        end = event["end"].get("dateTime") if "end" in event else None
        if not start:
            continue  # skip all-day events for time-specific checks
        start_dt = datetime.datetime.fromisoformat(start)
        end_dt = datetime.datetime.fromisoformat(end) if end else start_dt

        start_minutes = start_dt.hour * 60 + start_dt.minute
        end_minutes = end_dt.hour * 60 + end_dt.minute

        if start_minutes <= target_total_minutes <= end_minutes:
            matches.append(event.get("summary", "Untitled event"))

    time_str = f"{target_hour if target_hour <= 12 else target_hour - 12}:{target_minute:02d} {'AM' if target_hour < 12 else 'PM'}"

    if matches:
        return f"At {time_str}, you have: {', '.join(matches)}."
    return f"You have nothing scheduled at {time_str}."