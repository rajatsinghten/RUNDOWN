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
        calendar_events = fetch_calendar_events(creds)
        emails = fetch_emails(user_id)
        relevant_data = emails if "@email" in user_message.lower() else calendar_events

        prompt = f"""
        {f'**Relevant Data:**\n{relevant_data}' if relevant_data else ''}
        Refer to the above details and answer the upcoming questions. Prefer a concise answer.
        User Query: {user_message}
        """

        response = model.generate_content(prompt)
        if not response or not response.text.strip():
            return jsonify({"error": "Empty response from AI model"}), 500
        return jsonify({"response": response.text.strip()})
    except Exception as e:
        chat_bp.logger.error(f"Chat error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route('/addsuggestion', methods=['POST'])
@require_auth
def add_suggestion():
    user_id = session.get('user_id')
    try:
        creds = load_credentials(user_id)
        emails = fetch_emails(user_id)
        
        # Fetch existing calendar events to check for duplicates
        calendar_events = fetch_calendar_events(creds)
        existing_event_titles = [event.get('summary', '').lower() for event in calendar_events]
        existing_subjects = {}
        
        # Build a map of subjects that already have events to avoid duplicates
        for event in calendar_events:
            # Extract subject from event description if available
            description = event.get('description', '')
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
        chat_bp.logger.error(f"Add suggestion error: {str(e)}")
        chat_bp.logger.error(traceback.format_exc())
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
            
            # Debug all date information received
            print(f"RECEIVED DATE INFO:")
            print(f"  event_date: {data.get('event_date')}")
            print(f"  raw_deadline: {data.get('raw_deadline')}")
            print(f"  display_date: {data.get('display_date')}")
            if data.get('debug_info'):
                print(f"  debug_info: {data.get('debug_info')}")
            
            # Try all possible date sources in order of reliability
            date_sources = [
                ('event_date', data.get('event_date')),
                ('raw_deadline', data.get('raw_deadline')),
                ('display_date', data.get('display_date'))
            ]
            
            parsed_date = None
            used_source = None
            
            # Try each source until we get a valid date
            for source_name, source_value in date_sources:
                if source_value and source_value.lower() not in ('none', ''):
                    print(f"Attempting to parse date from {source_name}: {source_value}")
                    try:
                        from dateutil import parser
                        parsed_date = parser.parse(source_value)
                        used_source = source_name
                        print(f"Successfully parsed date from {source_name}: {source_value} -> {parsed_date}")
                        break
                    except Exception as e:
                        print(f"Failed to parse date from {source_name}: {source_value}, error: {e}")
            
            # If we couldn't parse any date, we'll fall back to AI extraction
            if parsed_date:
                print(f"Using parsed date from {used_source}: {parsed_date}")
                
                # Build a title and description
                title = task_desc
                description = f"Task: {task_desc}"
                
                # Create the calendar event - no Z suffix to avoid UTC designation
                iso_date = parsed_date.isoformat()
                print(f"Creating event with ISO date: {iso_date}")
                
                event = create_calendar_event(
                    creds, 
                    title, 
                    "Added from RunDown", 
                    parsed_date.strftime("%Y-%m-%d %H:%M:%S"), 
                    iso_date,
                    description=description,
                    set_reminder=True
                )
                
                # Format deadline for display
                formatted_deadline = parsed_date.strftime("%b %d, %Y at %I:%M %p")
                
                return jsonify({
                    "response": title, 
                    "event": event.get("htmlLink"),
                    "deadline": formatted_deadline,
                    "debug": {
                        "source": used_source,
                        "original": date_sources[0][1] if date_sources[0][1] else None
                    }
                })
            else:
                print("No usable date found in request data, falling back to AI extraction")
        else:
            # Handle plain text request from manual entry
            task_desc = request.data.decode('utf-8')
            print(f"Received plain text task: {task_desc}")
        
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
        
        If no date is specifically mentioned, use tomorrow at 9am.
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
            chat_bp.logger.error(f"Error parsing AI response: {parse_error}")
            chat_bp.logger.error(traceback.format_exc())
            return jsonify({"response": task_desc})
                
    except Exception as e:
        chat_bp.logger.error(f"Add task error: {str(e)}")
        chat_bp.logger.error(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500
