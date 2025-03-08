# backend/utils/calendar.py
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
import traceback
import pytz
from tzlocal import get_localzone

def create_calendar_event(creds, subject, sender, date_str, iso_date, end_date=None, description=None, set_reminder=False):
    """Creates a calendar event based on email details.
    
    Args:
        creds: Google API credentials
        subject: Event subject/title
        sender: Email sender
        date_str: Original date string
        iso_date: ISO formatted date for the event start time
        end_date: Optional end time (if None, will be set to start + 1 hour)
        description: Optional detailed description for the event
        set_reminder: Whether to set a reminder 24 hours before the event
    """
    calendar_service = build('calendar', 'v3', credentials=creds)
    
    # Debug incoming date information
    print(f"\n==== CALENDAR EVENT CREATION ====")
    print(f"Subject: {subject}")
    print(f"ISO Date: {iso_date}")
    print(f"End Date: {end_date}")
    
    # Get user's local timezone
    try:
        local_tz = get_localzone()
        timezone_str = str(local_tz)
        print(f"Using timezone: {timezone_str}")
    except:
        # Fallback to a common timezone if detection fails
        timezone_str = 'America/New_York'
        print(f"Timezone detection failed, using fallback: {timezone_str}")
    
    # Remove the Z from ISO date which indicates UTC
    if iso_date.endswith('Z'):
        iso_date = iso_date[:-1]
        print(f"Removed Z suffix, new ISO date: {iso_date}")
    
    # If no specific end date is provided, set it to 1 hour after start time
    if not end_date:
        # Parse the iso_date to datetime
        try:
            start_dt = datetime.fromisoformat(iso_date)
            print(f"Parsed start date: {start_dt}")
            end_dt = start_dt + timedelta(hours=1)
            end_iso_date = end_dt.isoformat()
            print(f"Calculated end date: {end_dt} -> {end_iso_date}")
        except Exception as e:
            # Fallback if parsing fails
            end_iso_date = iso_date
            print(f"Failed to calculate end date: {e}")
            print(f"Using same time for end date: {iso_date}")
    else:
        if end_date.endswith('Z'):
            end_iso_date = end_date[:-1]
            print(f"Removed Z suffix from end date: {end_iso_date}")
        else:
            end_iso_date = end_date
            print(f"Using provided end date: {end_iso_date}")
    
    # Use provided description or create default one
    event_description = description if description else f"From: {sender}\nDate: {date_str}\nSubject: {subject}"
    
    # Verbose check to make sure we're not using default values
    if iso_date.endswith('T09:00:00'):
        print(f"WARNING: Date appears to be default 9am time: {iso_date}")
    
    event_body = {
        'summary': f'{subject}',
        'description': event_description,
        'start': {'dateTime': iso_date, 'timeZone': timezone_str},
        'end': {'dateTime': end_iso_date, 'timeZone': timezone_str},
        'reminders': {
            'useDefault': False,
            'overrides': []
        }
    }
    
    print(f"Event start datetime: {iso_date}")
    print(f"Event end datetime: {end_iso_date}")
    print(f"Event timezone: {timezone_str}")
    
    # Add reminders
    reminders = []
    
    # Always add 30 min popup reminder
    reminders.append({'method': 'popup', 'minutes': 30})
    
    # Add day-before reminder if requested
    if set_reminder:
        reminders.append({'method': 'email', 'minutes': 24 * 60})  # 24 hours before
        reminders.append({'method': 'popup', 'minutes': 24 * 60})  # 24 hours before
    
    event_body['reminders']['overrides'] = reminders
    
    try:
        event = calendar_service.events().insert(
            calendarId='primary',
            body=event_body
        ).execute()
        print(f"Created event: {event.get('htmlLink')} with {len(reminders)} reminder(s)")
        print(f"==== END CALENDAR EVENT CREATION ====\n")
        return event
    except Exception as e:
        print(f"Error creating calendar event: {e}")
        print(traceback.format_exc())
        raise

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
