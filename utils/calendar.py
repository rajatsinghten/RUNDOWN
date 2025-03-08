# backend/utils/calendar.py
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import traceback

def create_calendar_event(creds, subject, sender, date_str, iso_date, end_date=None):
    """Creates a calendar event based on email details."""
    calendar_service = build('calendar', 'v3', credentials=creds)
    
    # If no specific end date is provided, set it to 1 hour after start time
    if not end_date:
        # Parse the iso_date to datetime
        try:
            start_dt = datetime.fromisoformat(iso_date.rstrip('Z'))
            end_dt = start_dt + timedelta(hours=1)
            end_iso_date = end_dt.isoformat() + 'Z'
        except:
            # Fallback if parsing fails
            end_iso_date = iso_date
    else:
        end_iso_date = end_date
    
    event_body = {
        'summary': f'{subject}',
        'description': f'From: {sender}\nDate: {date_str}\nSubject: {subject}',
        'start': {'dateTime': iso_date, 'timeZone': 'UTC'},
        'end': {'dateTime': end_iso_date, 'timeZone': 'UTC'},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 30}
            ]
        }
    }
    event = calendar_service.events().insert(
        calendarId='primary',
        body=event_body
    ).execute()
    print(f"Created event: {event.get('htmlLink')}")
    return event

def delete_calendar_event(creds, event_id):
    """Deletes a calendar event by ID."""
    try:
        print(f"Attempting to delete calendar event with ID: {event_id}")
        calendar_service = build('calendar', 'v3', credentials=creds)
        
        # First, try to get the event to confirm it exists
        try:
            event = calendar_service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            print(f"Found event to delete: {event.get('summary', 'No title')} ({event_id})")
        except HttpError as e:
            if e.resp.status == 404:
                print(f"Event {event_id} not found - it may have been already deleted")
                return {"status": "not_found", "message": "Event already deleted"}
            else:
                print(f"Error checking event existence: {str(e)}")
                raise
        
        # If we got here, the event exists, so delete it
        result = calendar_service.events().delete(
            calendarId='primary',
            eventId=event_id
        ).execute()
        print(f"Successfully deleted event with ID: {event_id}")
        return {"status": "deleted", "message": "Event deleted successfully"}
    except HttpError as e:
        print(f"Google API error during deletion: {str(e)}")
        print(traceback.format_exc())
        raise
    except Exception as e:
        print(f"Unexpected error during event deletion: {str(e)}")
        print(traceback.format_exc())
        raise

def fetch_calendar_events(creds):
    """Fetch upcoming calendar events."""
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary',
        timeMin=now, 
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    items = events_result.get('items', [])
    formatted_events = []
    for event in items:
        formatted_event = {
            "id": event.get("id", ""),
            "summary": event.get("summary", "No Title"),
            "description": event.get("description", ""),
            "start": event.get("start"),
            "end": event.get("end"),
            "htmlLink": event.get("htmlLink", "")
        }
        formatted_events.append(formatted_event)
    return formatted_events
