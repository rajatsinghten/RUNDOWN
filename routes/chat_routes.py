from flask import current_app
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
from config import GOOGLE_API_KEY
from utils.calendar import fetch_calendar_events, create_calendar_event
from utils.gmail import fetch_emails
from utils.auth import load_credentials
from utils.models import UserPreferences
import json
from datetime import datetime, timedelta
import traceback
import re

chat_bp = Blueprint('chat', __name__)

# Configure the Generative AI model
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def require_auth(view):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized"}), 401
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

@chat_bp.route('/chat', methods=['POST'])
@require_auth
def chat():
    user_id = session.get('user_id')
    user_message = request.json.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
    try:
        creds = load_credentials(user_id)
        
        # Check for command prefixes
        is_command = False
        command_type = None
        command_content = user_message
        
        # Define command prefixes
        commands = {
            "@add": "add_event",
            "@remove": "remove_event", 
            "@delete": "remove_event",
            "@list": "list_events",
            "@events": "list_events",
            "@help": "show_help"
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
        
        {f'**Relevant Data:**\n{relevant_data}' if relevant_data else ''}
        
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
    """Process the @help command to show available commands"""
    help_text = """
📋 **RunDown Chatbot Commands**

You can use the following commands:

**Calendar Management**
- `@add [event details]` - Add an event to your calendar
  Example: `@add Team meeting tomorrow at 2pm`

- `@remove [event title or ID]` - Remove an event from your calendar
  Example: `@remove Team meeting`

- `@list` or `@events` - List your upcoming calendar events

**General**
- `@help` - Show this help message

You can also ask me questions about your tasks, calendar, or email!
    """
    
    return jsonify({
        "response": help_text,
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
