# backend/utils/calendar.py
from googleapiclient.discovery import build
from datetime import datetime

def create_calendar_event(creds, subject, sender, date_str, iso_date):
    """Creates a calendar event based on email details."""
    calendar_service = build('calendar', 'v3', credentials=creds)
    event_body = {
        'summary': f'Email Event: {subject}',
        'description': f'From: {sender}\nDate: {date_str}\nSubject: {subject}',
        'start': {'dateTime': iso_date, 'timeZone': 'UTC'},
        'end': {'dateTime': iso_date, 'timeZone': 'UTC'},
    }
    event = calendar_service.events().insert(
        calendarId='primary',
        body=event_body
    ).execute()
    print(f"Created event: {event.get('htmlLink')}")
    return event

def fetch_calendar_events(creds):
    """Fetch upcoming calendar events."""
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary',
        timeMin=now, 
        maxResults=5,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    items = events_result.get('items', [])
    formatted_events = []
    for event in items:
        formatted_event = {
            "summary": event.get("summary", "No Title"),
            "start": event.get("start"),
            "end": event.get("end"),
        }
        formatted_events.append(formatted_event)
    return formatted_events
