from flask import current_app
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
from config import GOOGLE_API_KEY
from utils.calendar import fetch_calendar_events, create_calendar_event, delete_calendar_event
from utils.gmail import fetch_emails
from utils.auth import load_credentials, require_auth
from utils.models import UserPreferences
import json
from datetime import datetime, timedelta, time
import traceback
import re
import os
import pytz
from google.generativeai import GenerativeModel
from functools import wraps

chat_bp = Blueprint('chat', __name__)

# Configure the Generative AI model
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

@chat_bp.route('/chat', methods=['POST'])
@require_auth
def chat():
    """Process chat messages and commands"""
    user_id = session.get('user_id')
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        # Handle follow-up requests
        if data.get('follow_up') and data.get('action') == 'add_event':
            # Create an event from the stored suggestion
            suggested_event = session.get('suggested_event')
            if suggested_event:
                # Clear session data
                session.pop('suggested_event', None)
                
                # Get credentials
                creds = load_credentials(user_id)
                
                # Create event
                title = suggested_event.get('title')
                start_time = suggested_event.get('start')
                end_time = suggested_event.get('end')
                
                if not all([title, start_time, end_time]):
                    return jsonify({
                        "response": "I couldn't find the details of the event you want to add. Could you please provide the event details again?",
                        "command_detected": True
                    })
                
                # Convert to datetime objects
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
                
                # Format dates for calendar API
                iso_start = start_dt.isoformat()
                iso_end = end_dt.isoformat()
                
                # Create the calendar event
                description = f"Created via RunDown Chatbot\n\nScheduled on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                try:
                    event = create_calendar_event(
                        creds,
                        title,
                        "RunDown Chatbot",
                        start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        iso_start,
                        end_date=iso_end,
                        description=description,
                        set_reminder=True
                    )
                    
                    # Format response
                    formatted_datetime = start_dt.strftime("%A, %B %d, %Y at %I:%M %p")
                    response_message = f"✅ Added to calendar: **{title}**\n📅 {formatted_datetime}\n🔗 [View in Calendar]({event.get('htmlLink')})"
                    
                    return jsonify({
                        "response": response_message,
                        "command_detected": True,
                        "markdown": True,
                        "event_data": {
                            "title": title,
                            "datetime": formatted_datetime,
                            "event_id": event.get("id"),
                            "link": event.get("htmlLink")
                        }
                    })
                except Exception as e:
                    current_app.logger.error(f"Error creating event from suggestion: {str(e)}")
                    return jsonify({
                        "response": f"I encountered an error adding the event to your calendar: {str(e)}",
                        "command_detected": True
                    })
        
        # Get credentials for API access
        creds = load_credentials(user_id)
        model = GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash'))
        
        # Check for commands
        is_command = False
        command_type = None
        command_content = user_message
        
        # Define command prefixes and their handlers
        commands = {
            "@add": "add_event",
            "@remove": "remove_event",
            "@list": "list_events",
            "@help": "show_help",
            "@check": "check_availability",
            "@when": "check_availability",
            "@suggest": "suggest_time"
        }
        
        # Check if message starts with any command prefix
        for prefix, command in commands.items():
            if user_message.lower().startswith(prefix.lower()):
                is_command = True
                command_type = command
                command_content = user_message[len(prefix):].strip()
                current_app.logger.info(f"Detected command: {command_type}, content: {command_content}")
                break
        
        # Process commands
        if is_command:
            return process_command(command_type, command_content, creds, user_id)
        
        # Handle normal chat (not a command)
        calendar_events = fetch_calendar_events(creds)
        emails = fetch_emails(user_id)
        relevant_data = emails if "@email" in user_message.lower() else calendar_events

        prompt = f"""
        You are an AI assistant for RunDown, a task management application. You have access to the following information:
        
        {f'**Relevant Data:**{relevant_data}' if relevant_data else ''}
        
        The user can use the following commands:
        - @add [event details] - Add an event to calendar (e.g., "@add Meeting with John tomorrow at 3pm")
        - @remove [event ID or description] - Remove an event from calendar
        - @list - List upcoming events
        - @help - Show available commands
        
        Refer to the above details and answer the upcoming questions. Prefer a concise answer.
        If the user is asking about adding or removing events, suggest using the appropriate command.
        
        User Query: {user_message}
        """

        response = model.generate_content(prompt)
        if not response or not response.text.strip():
            return jsonify({"error": "Empty response from AI model"}), 500
        return jsonify({"response": response.text.strip(), "command_detected": False})
    except Exception as e:
        current_app.logger.error(f"Chat error: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

def process_command(command_type, command_content, creds, user_id):
    """Process a command from the chatbot"""
    try:
        if command_type == "add_event":
            return add_event_command(command_content, creds)
        elif command_type == "remove_event":
            return remove_event_command(command_content, creds)
        elif command_type == "list_events":
            return list_events_command(creds)
        elif command_type == "show_help":
            return show_help_command()
        elif command_type == "check_availability":
            return check_availability_command(command_content, creds)
        elif command_type == "suggest_time":
            return suggest_time_command(command_content, creds)
        else:
            return jsonify({
                "response": "I don't understand that command. Try @help to see available commands.",
                "command_detected": True
            })
    except Exception as e:
        current_app.logger.error(f"Command processing error: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I encountered an error processing your command: {str(e)}",
            "command_detected": True
        })

def add_event_command(command_content, creds):
    """Process the @add command to add an event to calendar"""
    if not command_content:
        return jsonify({
            "response": "Please provide event details. Example: @add Meeting with John tomorrow at 3pm",
            "command_detected": True
        })
    
    # Use AI to extract event details
    prompt = f"""
    Extract event details from the following text: "{command_content}"
    
    Provide a JSON response with:
    1. A concise event title
    2. The date and time of the event (YYYY-MM-DD HH:MM format)
    3. Location (if mentioned)
    4. Any other important details
    
    Format:
    {{
        "title": "Event title",
        "date": "YYYY-MM-DD HH:MM",
        "location": "Location or null",
        "details": "Additional details or null"
    }}
    
    For dates:
    - If no date is specified, use tomorrow at 9am
    - If a date is specified without a year, use the current year {datetime.now().year}
    - If a date mentions a month after the current month with no year, assume the current year
    - If a date mentions a month before the current month with no year, assume next year
    - Always provide the full date in YYYY-MM-DD HH:MM format
    """
    
    try:
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        current_app.logger.info(f"AI response for date extraction: {response_text}")
        
        # Extract JSON from response if needed
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].strip()
        else:
            json_str = response_text
            
        event_data = json.loads(json_str)
        
        title = event_data.get("title", "New Event")
        date_str = event_data.get("date")
        location = event_data.get("location")
        details = event_data.get("details")
        
        # Parse the date
        try:
            from dateutil import parser
            event_dt = parser.parse(date_str)
            
            # Ensure the event is not defaulting to a future year if not explicitly specified
            current_year = datetime.now().year
            
            # Check if the parsed date is in the future with a different year
            if event_dt.year != current_year:
                # If the date was specified without a year, dateutil may have chosen a different year
                # Let's check if this might be the case by comparing the input string
                if str(event_dt.year) not in date_str:
                    # Year wasn't explicitly mentioned, so default to current year
                    event_dt = event_dt.replace(year=current_year)
                    current_app.logger.info(f"Adjusted year to current year: {event_dt}")
                    
                    # If this makes the date in the past, and it's not today, assume it's for next year
                    now = datetime.now()
                    if event_dt < now and event_dt.date() != now.date():
                        event_dt = event_dt.replace(year=current_year + 1)
                        current_app.logger.info(f"Date was in the past, adjusted to next year: {event_dt}")
            
            current_app.logger.info(f"Parsed date: {date_str} -> {event_dt}")
            
        except Exception as date_error:
            current_app.logger.error(f"Error parsing date: {date_error}, using default date")
            # Default to tomorrow 9am
            event_dt = datetime.now() + timedelta(days=1)
            event_dt = event_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            current_app.logger.info(f"Using default date: {event_dt}")
        
        # Check for email ID in the command
        email_id = None
        if 'https://mail.google.com/mail/' in command_content:
            # Extract email ID from the URL
            try:
                email_match = re.search(r'mail/u/\d+/#inbox/([a-zA-Z0-9]+)', command_content)
                if email_match:
                    email_id = email_match.group(1)
            except Exception as e:
                current_app.logger.error(f"Error extracting email ID: {str(e)}")
        
        # Create description
        description = f"Created via RunDown Chatbot\n\n"
        if details:
            description += f"Details: {details}\n\n"
        if location:
            description += f"Location: {location}\n\n"
        if email_id:
            description += f"Email ID: {email_id}\n\n"
            
        # Create calendar event
        iso_date = event_dt.isoformat()
        current_app.logger.info(f"Creating event with ISO date: {iso_date}")
        event = create_calendar_event(
            creds, 
            title, 
            "RunDown Chatbot", 
            event_dt.strftime("%Y-%m-%d %H:%M:%S"), 
            iso_date,
            description=description,
            set_reminder=True
        )
        
        # Format response
        formatted_datetime = event_dt.strftime("%A, %B %d, %Y at %I:%M %p")
        response_message = f"Added to calendar: **{title}**\n{formatted_datetime}"
        if location:
            response_message += f"\nLocation: {location}"
        response_message += f"\n[View in Calendar]({event.get('htmlLink')})"
        
        return jsonify({
            "response": response_message,
            "command_detected": True,
            "markdown": True,
            "event_data": {
                "title": title,
                "datetime": formatted_datetime,
                "event_id": event.get("id"),
                "link": event.get("htmlLink"),
                "location": location if location else None,
                "details": details if details else None,
                "raw_date": date_str,
                "email_id": email_id
            }
        })
    except Exception as e:
        current_app.logger.error(f"Error adding event: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I had trouble adding that event. Please try again with a clearer date and time.",
            "command_detected": True
        })

def remove_event_command(command_content, creds):
    """Process the @remove command to remove an event from calendar"""
    if not command_content:
        return jsonify({
            "response": "Please provide the event to remove. You can specify a title or an exact event ID.",
            "command_detected": True
        })
    
    try:
        # First check if it's an event ID
        try:
            from utils.calendar import delete_calendar_event
            result = delete_calendar_event(creds, command_content)
            if result.get("status") == "deleted":
                return jsonify({
                    "response": "✅ Event has been deleted from your calendar.",
                    "command_detected": True
                })
            elif result.get("status") == "not_found":
                # Not an ID, so let's search by title
                pass
            else:
                return jsonify({
                    "response": f"Something went wrong: {result.get('message')}",
                    "command_detected": True
                })
        except:
            # Not an ID, so search by title
            pass
        
        # Search for events by title
        events = fetch_calendar_events(creds)
        matching_events = []
        
        for event in events:
            if command_content.lower() in event.get("summary", "").lower():
                matching_events.append(event)
        
        if not matching_events:
            return jsonify({
                "response": f"I couldn't find any events matching '{command_content}'. Please try a different search or use @list to see your upcoming events.",
                "command_detected": True
            })
        
        if len(matching_events) == 1:
            # Only one match, delete it
            event = matching_events[0]
            event_id = event.get("id")
            from utils.calendar import delete_calendar_event
            delete_calendar_event(creds, event_id)
            
            return jsonify({
                "response": f"✅ Deleted event: **{event.get('summary')}**",
                "command_detected": True,
                "markdown": True
            })
        else:
            # Multiple matches, ask user to be more specific
            response = "I found multiple matching events. Please be more specific or use the event ID:\n\n"
            for i, event in enumerate(matching_events[:5], 1):
                summary = event.get("summary")
                start = event.get("start", {}).get("dateTime", "Unknown time")
                
                try:
                    from dateutil import parser
                    dt = parser.parse(start)
                    formatted_date = dt.strftime("%A, %B %d at %I:%M %p")
                except:
                    formatted_date = start
                
                response += f"{i}. **{summary}** - {formatted_date} (ID: `{event.get('id')}`)\n"
            
            if len(matching_events) > 5:
                response += f"\n... and {len(matching_events) - 5} more events."
                
            response += "\n\nTo delete a specific event, use:\n`@remove EVENT_ID`"
            
            return jsonify({
                "response": response,
                "command_detected": True,
                "markdown": True,
                "event_matches": [
                    {
                        "id": e.get("id"),
                        "title": e.get("summary"),
                        "start": e.get("start", {}).get("dateTime")
                    } for e in matching_events[:5]
                ]
            })
    except Exception as e:
        current_app.logger.error(f"Error removing event: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I encountered an error trying to remove that event: {str(e)}",
            "command_detected": True
        })

def list_events_command(creds):
    """Process the @list command to list upcoming events"""
    try:
        events = fetch_calendar_events(creds)
        
        if not events:
            return jsonify({
                "response": "You don't have any upcoming events in your calendar.",
                "command_detected": True
            })
        
        response = "📅 **Upcoming Events**\n\n"
        
        for i, event in enumerate(events[:8], 1):
            summary = event.get("summary", "Untitled Event")
            start = event.get("start", {}).get("dateTime", "Unknown time")
            
            try:
                from dateutil import parser
                dt = parser.parse(start)
                formatted_date = dt.strftime("%A, %B %d at %I:%M %p")
            except:
                formatted_date = start
            
            response += f"{i}. **{summary}** - {formatted_date}\n"
        
        if len(events) > 8:
            response += f"\n... and {len(events) - 8} more events."
            
        return jsonify({
            "response": response,
            "command_detected": True,
            "markdown": True,
            "events": events[:8]
        })
    except Exception as e:
        current_app.logger.error(f"Error listing events: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I encountered an error trying to list your events: {str(e)}",
            "command_detected": True
        })

def show_help_command():
    """Show available commands and help information"""
    help_message = """
### Available Commands:

- **@add [event details]** - Add a new event to your calendar
  Example: @add Team meeting tomorrow at 3pm
  
- **@remove [event name]** - Remove an event from your calendar
  Example: @remove Team meeting
  
- **@list** - Show your upcoming calendar events
  
- **@check [date]** - Check your availability on a specific date
  Example: @check tomorrow
  Example: @check Friday
  
- **@when [event description]** - Find a suitable time for an event
  Example: @when can I schedule a team meeting on Wednesday?
  
- **@suggest [event description]** - Suggest a free time for an event
  Example: @suggest time for a coffee break tomorrow

- **@help** - Show this help message
    """
    
    return jsonify({
        "response": help_message,
        "command_detected": True,
        "markdown": True
    })

@chat_bp.route('/addsuggestion', methods=['POST'])
@require_auth
def add_suggestion():
    user_id = session.get('user_id')
    try:
        data = request.get_json() or {}
        # Get the time period from the request (default to 7 days)
        time_period = int(data.get('time_period', 7))
        
        creds = load_credentials(user_id)
        # Pass the time period to fetch_emails
        emails = fetch_emails(user_id, days=time_period)
        
        # Fetch existing calendar events to check for duplicates
        calendar_events = fetch_calendar_events(creds)
        existing_event_titles = [event.get('summary', '').lower() for event in calendar_events]
        existing_subjects = {}
        existing_email_ids = set()
        
        # Build a map of subjects that already have events to avoid duplicates
        for event in calendar_events:
            # Extract subject from event description if available
            description = event.get('description', '')
            # Extract email ID if it exists in the description
            if 'Email ID:' in description:
                email_id_line = [line for line in description.split('\n') if 'Email ID:' in line]
                if email_id_line:
                    email_id = email_id_line[0].replace('Email ID:', '').strip()
                    existing_email_ids.add(email_id)
            
            if 'Subject:' in description:
                subject_line = [line for line in description.split('\n') if 'Subject:' in line]
                if subject_line:
                    subject = subject_line[0].replace('Subject:', '').strip()
                    existing_subjects[subject.lower()] = True
        
        # Get user preferences for filtering
        user_preferences = UserPreferences.load_preferences(user_id)
        user_interests = user_preferences.get('interests', [])
        filtering_enabled = user_preferences.get('enabled', True)
        
        filtered_emails = []
        suggestions = []
        
        # Only apply filtering if user has preferences and filtering is enabled
        if filtering_enabled and user_interests:
            current_app.logger.info(f"Filtering emails based on user interests: {user_interests}")
            
            # Filter emails based on user interests
            for email in emails:
                email_content = f"{email.get('subject', '')} {email.get('content', '')}".lower()
                for interest in user_interests:
                    if interest.lower() in email_content:
                        filtered_emails.append(email)
                        break
            
            current_app.logger.info(f"Filtered {len(filtered_emails)} emails from {len(emails)} total")
        else:
            # No filtering needed
            filtered_emails = emails
        
        # Process emails (filtered or all)
        for email in filtered_emails:
            email_id = email.get('id', '')
            email_subject = email.get('subject', 'No Subject')
            email_content = email.get('content', '')
            
            # Skip if the email subject is already in calendar events or already processed
            if email_subject.lower() in existing_subjects:
                current_app.logger.info(f"Skipping already processed email: {email_subject}")
                continue
                
            # Skip if the email title exactly matches an existing event
            if any(email_subject.lower() == title for title in existing_event_titles):
                current_app.logger.info(f"Skipping email with title already in calendar: {email_subject}")
                continue
            
            prompt = f"""
            **Email Subject:** {email_subject}
            **Email Content:** {email_content}
            
            Extract the following information from this email:
            1. A task description (what needs to be done or attended)
            2. When this task/event is happening (date and time in YYYY-MM-DD HH:MM format)
            3. Where it's happening (location)
            4. Is this time-sensitive? (yes/no)
            
            Format your response as JSON:
            {{
                "task": "task description",
                "event_date": "YYYY-MM-DD HH:MM or none if not found",
                "location": "location if mentioned or none",
                "is_time_sensitive": true/false
            }}
            
            If there is no clear task or this is just an informational email, respond with:
            {{
                "task": "FYI: brief summary of what this email is about",
                "event_date": "none",
                "location": "none",
                "is_time_sensitive": false
            }}
            """
            
            response = model.generate_content(prompt)
            
            if response and response.text.strip():
                try:
                    # Extract JSON from response
                    response_text = response.text.strip()
                    if "```json" in response_text:
                        json_str = response_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in response_text:
                        json_str = response_text.split("```")[1].strip()
                    else:
                        json_str = response_text
                    
                    suggestion_data = json.loads(json_str)
                    
                    # Prepare formatted response
                    task_text = suggestion_data.get('task', '')
                    
                    # Skip if the task is "FYI" or doesn't seem like an actionable task
                    if task_text.startswith("FYI:") or not task_text:
                        current_app.logger.info(f"Skipping non-actionable task: {task_text}")
                        continue
                        
                    # Skip if the task exactly matches an existing event title
                    if any(task_text.lower() == title for title in existing_event_titles):
                        current_app.logger.info(f"Skipping task already in calendar: {task_text}")
                        continue
                    
                    # Get the event date - look for event_date first (new format) then deadline (old format)
                    event_date = suggestion_data.get('event_date', suggestion_data.get('deadline', 'none'))
                    location = suggestion_data.get('location', 'none')
                    
                    formatted_deadline = None
                    if event_date and event_date.lower() != 'none':
                        try:
                            # First try strict format
                            dt = datetime.strptime(event_date, "%Y-%m-%d %H:%M")
                            formatted_deadline = dt.strftime("%b %d, %Y at %I:%M %p")
                        except ValueError:
                            try:
                                # Try with dateutil parser as fallback
                                from dateutil import parser
                                dt = parser.parse(event_date)
                                formatted_deadline = dt.strftime("%b %d, %Y at %I:%M %p")
                            except:
                                # Just use as is if parsing fails
                                formatted_deadline = event_date
                    
                    # Add to suggestions
                    suggestions.append({
                        "text": task_text,
                        "deadline": formatted_deadline,
                        "email_id": email_id,
                        "email_subject": email_subject,
                        "location": location if location and location.lower() != 'none' else None,
                        "event_date": event_date if event_date and event_date.lower() != 'none' else None,
                        "is_time_sensitive": suggestion_data.get('is_time_sensitive', False)
                    })
                    
                except Exception as json_error:
                    # Fallback if JSON parsing fails
                    current_app.logger.error(f"Error parsing AI response: {json_error}")
                    current_app.logger.error(traceback.format_exc())
                    suggestions.append({
                        "text": response.text.strip(),
                        "email_id": email_id,
                        "email_subject": email_subject
                    })
        
        # Sort suggestions by time sensitivity
        suggestions.sort(key=lambda x: x.get('is_time_sensitive', False), reverse=True)
        
        current_app.logger.info(f"Generated {len(suggestions)} suggestions")
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        current_app.logger.error(f"Add suggestion error: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route('/addtask', methods=['POST'])
@require_auth
def add_task():
    """Add a task from natural language to calendar"""
    user_id = session.get('user_id')
    try:
        creds = load_credentials(user_id)
        
        # Check if the content type is JSON
        is_json = request.headers.get('Content-Type') == 'application/json'
        
        if is_json:
            # Handle JSON request from suggestion
            data = request.json
            task_desc = data.get('task_text', '')
            # Get the original event_date if available
            original_event_date = data.get('event_date')
            display_date = data.get('display_date')
            
            print(f"Received task with original_event_date: {original_event_date}, display_date: {display_date}")
        else:
            # Handle plain text request from manual entry
            task_desc = request.data.decode('utf-8')
            original_event_date = None
            display_date = None
        
        # Use the original event date if available, otherwise ask AI to extract
        if original_event_date and original_event_date.lower() != 'none':
            print(f"Using original event date from suggestion: {original_event_date}")
            # Parse the original date
            try:
                from dateutil import parser
                dt = parser.parse(original_event_date)
                print(f"Successfully parsed original event date: {original_event_date} -> {dt}")
                
                # Check if the year wasn't explicitly specified
                current_year = datetime.now().year
                if dt.year != current_year and str(dt.year) not in original_event_date:
                    dt = dt.replace(year=current_year)
                    # If this makes the date in the past (and it's not today), use next year
                    now = datetime.now()
                    if dt < now and dt.date() != now.date():
                        dt = dt.replace(year=current_year + 1)
                        print(f"Adjusted to next year: {dt}")
                    else:
                        print(f"Adjusted to current year: {dt}")
                
                # Build a title and description
                title = task_desc
                description = f"Task: {task_desc}"
                
                # Create the calendar event - no Z suffix to avoid UTC designation
                iso_date = dt.isoformat()
                print(f"Creating event with ISO date from original event date: {iso_date}")
                
                event = create_calendar_event(
                    creds, 
                    title, 
                    "Added from RunDown", 
                    dt.strftime("%Y-%m-%d %H:%M:%S"), 
                    iso_date,
                    description=description,
                    set_reminder=True
                )
                
                # Format deadline for display
                formatted_deadline = dt.strftime("%b %d, %Y at %I:%M %p")
                
                return jsonify({
                    "response": title, 
                    "event": event.get("htmlLink"),
                    "deadline": formatted_deadline
                })
            except Exception as e:
                print(f"Error parsing original event date: {e}, falling back to AI extraction")
                # Fall back to AI extraction
                original_event_date = None
        
        # If we get here, we need to use AI to extract information
        print(f"Using AI to extract date from task: {task_desc}")
        
        # Use AI to parse the task and get information
        prompt = f"""
        User wants to add a task: "{task_desc}"
        
        Extract the following information:
        1. Task title (a concise version of the task, 5-10 words)
        2. Date and time when this task is due or scheduled to happen (EXACT DATE AND TIME)
        3. Location of the task/event (if mentioned)
        4. Any other important details
        
        Format your response as JSON with:
        {{
            "title": "concise task title",
            "date": "YYYY-MM-DD HH:MM" or null if not specified,
            "location": "location string or null if not mentioned",
            "details": "other important details or null"
        }}
        
        For dates:
        - If no date is specifically mentioned, use tomorrow at 9am
        - If a date is specified without a year, use the current year {datetime.now().year}
        - If a date mentions a month after the current month with no year, assume the current year
        - If a date mentions a month before the current month with no year, assume next year
        - Always provide the full date in YYYY-MM-DD HH:MM format
        """
        
        response = model.generate_content(prompt)
        
        # Parse the response
        try:
            response_text = response.text.strip()
            print(f"AI response: {response_text}")
            
            # Extract JSON from response if needed
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text
                
            task_data = json.loads(json_str)
            title = task_data.get("title", task_desc)
            location = task_data.get("location")
            details = task_data.get("details")
            
            # Parse the date or use tomorrow
            try:
                date_str = task_data.get("date")
                if date_str:
                    # Try to parse the date
                    from dateutil import parser
                    dt = parser.parse(date_str)
                    
                    # Check if the year wasn't explicitly specified
                    current_year = datetime.now().year
                    if dt.year != current_year and str(dt.year) not in date_str:
                        dt = dt.replace(year=current_year)
                        # If this makes the date in the past (and it's not today), use next year
                        now = datetime.now()
                        if dt < now and dt.date() != now.date():
                            dt = dt.replace(year=current_year + 1)
                            print(f"Adjusted to next year: {dt}")
                        else:
                            print(f"Adjusted to current year: {dt}")
                    
                    print(f"Parsed date from AI: {date_str} -> {dt}")
                else:
                    # Use tomorrow at 9am
                    dt = datetime.now() + timedelta(days=1)
                    dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
                    print(f"Using default tomorrow at 9am: {dt}")
            except Exception as e:
                print(f"Error parsing date from AI: {e}")
                # Fallback to tomorrow at 9am
                dt = datetime.now() + timedelta(days=1)
                dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
                print(f"Using fallback tomorrow at 9am: {dt}")
            
            # Build a rich description
            description = f"Task: {task_desc}"
            if details:
                description += f"\n\nDetails: {details}"
            if location:
                description += f"\n\nLocation: {location}"
                
            # Create the calendar event - note: no Z suffix to avoid UTC designation
            iso_date = dt.isoformat()
            print(f"Creating event with ISO date: {iso_date}")
            event = create_calendar_event(
                creds, 
                title, 
                "Added from RunDown", 
                dt.strftime("%Y-%m-%d %H:%M:%S"), 
                iso_date,
                description=description,
                set_reminder=True
            )
            
            # Format deadline for display
            formatted_deadline = dt.strftime("%b %d, %Y at %I:%M %p")
            
            return jsonify({
                "response": title, 
                "event": event.get("htmlLink"),
                "deadline": formatted_deadline,
                "location": location
            })
        except Exception as parse_error:
            current_app.logger.error(f"Error parsing AI response: {parse_error}")
            current_app.logger.error(traceback.format_exc())
            return jsonify({"response": task_desc})
                
    except Exception as e:
        current_app.logger.error(f"Add task error: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500

def find_free_slots(events, date_to_check, timezone="America/New_York"):
    """
    Find free time slots on a given day
    
    Args:
        events: List of calendar events
        date_to_check: Date to check for free time slots (datetime.date object)
        timezone: Timezone to use for calculations
    
    Returns:
        List of free time slots as (start, end) tuples
    """
    # Set up the time zone
    tz = pytz.timezone(timezone)
    
    # Define the start and end of the working day (9 AM to 8 PM)
    work_start_time = time(9, 0)  # 9 AM
    work_end_time = time(20, 0)   # 8 PM
    
    # Create datetime objects for the start and end of the working day
    day_start = datetime.combine(date_to_check, work_start_time)
    day_start = tz.localize(day_start)
    day_end = datetime.combine(date_to_check, work_end_time)
    day_end = tz.localize(day_end)
    
    # Filter events that fall on the specified date
    day_events = []
    for event in events:
        # Parse event start and end times
        event_start = event.get('start', {}).get('dateTime')
        event_end = event.get('end', {}).get('dateTime')
        
        if not event_start or not event_end:
            continue
            
        # Convert to datetime objects
        try:
            event_start_dt = datetime.fromisoformat(event_start.replace('Z', '+00:00'))
            event_end_dt = datetime.fromisoformat(event_end.replace('Z', '+00:00'))
            
            # Convert to target timezone
            event_start_dt = event_start_dt.astimezone(tz)
            event_end_dt = event_end_dt.astimezone(tz)
            
            # Check if the event falls on the target date
            if event_start_dt.date() == date_to_check or event_end_dt.date() == date_to_check:
                # Clip events to the working day if needed
                if event_start_dt.date() < date_to_check:
                    event_start_dt = day_start
                if event_end_dt.date() > date_to_check:
                    event_end_dt = day_end
                    
                day_events.append((event_start_dt, event_end_dt, event.get('summary', 'No Title')))
        except Exception as e:
            current_app.logger.error(f"Error parsing event date: {e}")
            continue
    
    # Sort events by start time
    day_events.sort(key=lambda x: x[0])
    
    # Find free time slots
    free_slots = []
    current_time = day_start
    
    for start, end, _ in day_events:
        # If there's a gap between current_time and the next event's start
        if current_time < start:
            # Only add slots that are at least 30 minutes
            if (start - current_time).total_seconds() >= 30 * 60:
                free_slots.append((current_time, start))
                
        # Update current time to the end of this event
        current_time = max(current_time, end)
    
    # Check for free time after the last event until end of day
    if current_time < day_end:
        free_slots.append((current_time, day_end))
    
    return free_slots, day_events

def format_time_slot(slot):
    """Format a time slot for display"""
    start, end = slot
    # Format as "10:00 AM - 11:30 AM"
    return f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"

def parse_date_with_ai(date_text, model):
    """Use AI to parse a date string into a datetime object"""
    prompt = f"""
    Parse the following date/time reference into a specific date: "{date_text}"
    
    Today is {datetime.now().strftime('%A, %B %d, %Y')}.
    If no specific date is mentioned, assume today.
    If a day of week is mentioned (e.g., "Monday"), use the upcoming one.
    
    Respond with ONLY a date in YYYY-MM-DD format.
    """
    
    try:
        response = model.generate_content(prompt)
        date_str = response.text.strip()
        
        # Extract just the date if there's additional text
        import re
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
        if date_match:
            date_str = date_match.group(0)
            
        # Convert to date object
        parsed_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        return parsed_date
    except Exception as e:
        current_app.logger.error(f"Error parsing date with AI: {e}")
        # Return today's date as fallback
        return datetime.now().date()

def check_availability_command(command_content, creds):
    """Process availability check command and return free time slots"""
    if not command_content:
        return jsonify({
            "response": "Please specify a date to check. For example: @check tomorrow",
            "command_detected": True
        })
    
    try:
        # Initialize the model for date parsing
        model = GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash'))
        
        # Parse the date using AI
        date_to_check = parse_date_with_ai(command_content, model)
        
        # Fetch calendar events
        events = fetch_calendar_events(creds)
        
        # Get free time slots and booked events
        free_slots, booked_events = find_free_slots(events, date_to_check)
        
        # Format the response
        formatted_date = date_to_check.strftime("%A, %B %d, %Y")
        
        # Format the response message
        if not booked_events:
            response = f"### Availability for {formatted_date}\n\nYou have no events scheduled for this day. You're completely free from 9:00 AM to 8:00 PM."
        else:
            response = f"### Availability for {formatted_date}\n\n"
            
            # Add booked events
            response += "**Booked Events:**\n"
            for start, end, summary in booked_events:
                response += f"- {summary}: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}\n"
            
            # Add free slots
            response += "\n**Free Time Slots:**\n"
            if free_slots:
                for i, slot in enumerate(free_slots, 1):
                    response += f"{i}. {format_time_slot(slot)}\n"
            else:
                response += "You have no free time slots available on this day."
        
        # Store the free slots in session for possible follow-up
        session['free_slots'] = [
            {
                'start': slot[0].isoformat(),
                'end': slot[1].isoformat()
            } for slot in free_slots
        ]
        session['availability_date'] = date_to_check.isoformat()
        
        return jsonify({
            "response": response,
            "command_detected": True,
            "markdown": True,
            "free_slots": len(free_slots) > 0
        })
    except Exception as e:
        current_app.logger.error(f"Error checking availability: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I encountered an error checking your availability: {str(e)}",
            "command_detected": True
        })

def suggest_time_command(command_content, creds):
    """Suggest a free time slot for an event based on calendar availability"""
    if not command_content:
        return jsonify({
            "response": "Please describe the event you want to schedule. For example: @suggest time for a coffee break tomorrow",
            "command_detected": True
        })
    
    try:
        # Initialize the model
        model = GenerativeModel(os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash'))
        
        # Extract event details and target date
        prompt = f"""
        Extract event information from this request: "{command_content}"
        
        Provide a JSON response with:
        1. Event title (a concise description of the activity)
        2. The target date for this event
        3. Estimated duration in minutes
        4. Any mentioned preferences (morning, afternoon, etc)
        
        Format:
        {{
            "title": "Event title",
            "target_date": "specific date or day reference like 'tomorrow', 'next Friday'",
            "duration": duration in minutes (default to 60 if not specified),
            "preference": "time preference (morning, afternoon, evening, etc) or null"
        }}
        """
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # Extract JSON from response if needed
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].strip()
        else:
            json_str = response_text
            
        event_data = json.loads(json_str)
        
        # Parse the date
        target_date = parse_date_with_ai(event_data.get("target_date", "today"), model)
        
        # Get event title and duration
        title = event_data.get("title", "New Event")
        duration = int(event_data.get("duration", 60))  # in minutes
        preference = event_data.get("preference")
        
        # Fetch calendar events
        events = fetch_calendar_events(creds)
        
        # Find free slots
        free_slots, _ = find_free_slots(events, target_date)
        
        # Filter slots based on duration and preference
        suitable_slots = []
        for start, end in free_slots:
            slot_duration = (end - start).total_seconds() / 60
            
            # Check if the slot is long enough
            if slot_duration >= duration:
                # Create potential slots within this free period
                potential_starts = []
                current = start
                while (current + timedelta(minutes=duration)) <= end:
                    potential_starts.append(current)
                    current += timedelta(minutes=30)  # 30-minute increments
                
                # Add all potential start times to suitable slots
                for potential_start in potential_starts:
                    slot_end = potential_start + timedelta(minutes=duration)
                    suitable_slots.append((potential_start, slot_end))
        
        # Apply time preference if specified
        if preference and suitable_slots:
            filtered_slots = []
            
            if preference.lower() in ["morning", "am", "early"]:
                # Morning: 9 AM - 12 PM
                filtered_slots = [s for s in suitable_slots if s[0].hour < 12]
            elif preference.lower() in ["afternoon", "noon", "lunch"]:
                # Afternoon: 12 PM - 5 PM
                filtered_slots = [s for s in suitable_slots if 12 <= s[0].hour < 17]
            elif preference.lower() in ["evening", "night", "pm", "late"]:
                # Evening: 5 PM - 8 PM
                filtered_slots = [s for s in suitable_slots if s[0].hour >= 17]
                
            if filtered_slots:
                suitable_slots = filtered_slots
        
        # No suitable slots found
        if not suitable_slots:
            formatted_date = target_date.strftime("%A, %B %d, %Y")
            return jsonify({
                "response": f"I couldn't find a suitable time for a {duration}-minute '{title}' on {formatted_date}. Would you like to check a different day?",
                "command_detected": True,
                "ask_followup": False
            })
            
        # Select the best slot (first available, or based on preference)
        best_slot = suitable_slots[0]
        
        # Format the suggestion
        start_time = best_slot[0].strftime("%I:%M %p")
        end_time = best_slot[1].strftime("%I:%M %p")
        formatted_date = target_date.strftime("%A, %B %d, %Y")
        
        # Store event info for follow-up
        session['suggested_event'] = {
            'title': title,
            'start': best_slot[0].isoformat(),
            'end': best_slot[1].isoformat(),
            'date': target_date.isoformat()
        }
        
        response = f"### Time Suggestion\n\nI suggest scheduling **{title}** on **{formatted_date}** from **{start_time}** to **{end_time}**.\n\nWould you like me to add this to your calendar?"
        
        return jsonify({
            "response": response,
            "command_detected": True,
            "markdown": True,
            "ask_followup": True,
            "event_suggestion": {
                "title": title,
                "date": formatted_date,
                "start_time": start_time,
                "end_time": end_time
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error suggesting time: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            "response": f"I encountered an error suggesting a time for your event: {str(e)}",
            "command_detected": True
        })
