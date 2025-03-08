from flask import current_app
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
from config import GOOGLE_API_KEY
from utils.calendar import fetch_calendar_events
from utils.gmail import fetch_emails
from utils.auth import load_credentials
from utils.models import UserPreferences
import json
from datetime import datetime

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
            
            # Skip if the email subject is already in calendar events or already processed
            if email_subject.lower() in existing_subjects:
                current_app.logger.info(f"Skipping already processed email: {email_subject}")
                continue
                
            # Skip if the email title exactly matches an existing event
            if any(email_subject.lower() == title for title in existing_event_titles):
                current_app.logger.info(f"Skipping email with title already in calendar: {email_subject}")
                continue
            
            prompt = f"""
            {f'**Email Subject:**\n{email.get("subject", "No Subject")}\n**Email Content:**\n{email.get("content", "No Content")}' if email else ''}
            
            Extract the following from this email:
            1. Task or event description (one line)
            2. Deadline or date if mentioned (in YYYY-MM-DD HH:MM format or "none" if not found)
            3. Is this a time-sensitive task? (yes/no)
            
            Format your response as JSON:
            {{
                "task": "task description",
                "deadline": "YYYY-MM-DD HH:MM or none",
                "is_time_sensitive": true/false
            }}
            
            If there is no clear task, return a short summary prefixed with "FYI: ".
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
                    
                    deadline = suggestion_data.get('deadline', 'none')
                    
                    if deadline and deadline.lower() != 'none':
                        try:
                            # Try to parse the deadline
                            dt = datetime.strptime(deadline, "%Y-%m-%d %H:%M")
                            formatted_deadline = dt.strftime("%b %d, %Y at %I:%M %p")
                        except:
                            formatted_deadline = deadline
                    else:
                        formatted_deadline = None
                    
                    # Add to suggestions
                    suggestions.append({
                        "text": task_text,
                        "deadline": formatted_deadline,
                        "email_id": email_id,
                        "email_subject": email_subject,
                        "is_time_sensitive": suggestion_data.get('is_time_sensitive', False)
                    })
                    
                except Exception as json_error:
                    # Fallback if JSON parsing fails
                    current_app.logger.error(f"Error parsing AI response: {json_error}")
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
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route('/addtask', methods=['POST'])
@require_auth
def add_task():
    """Add a task from natural language to calendar"""
    user_id = session.get('user_id')
    try:
        task_desc = request.data.decode('utf-8')
        creds = load_credentials(user_id)
        
        # Use AI to parse the task and get information
        prompt = f"""
        User wants to add a task: "{task_desc}"
        Extract the task title and date from this text.
        Format your response as JSON with "title" and "date" fields.
        If no date is mentioned, use tomorrow at 9am.
        """
        
        response = model.generate_content(prompt)
        from utils.calendar import create_calendar_event
        from datetime import datetime, timedelta
        import json
        
        # Parse the response
        try:
            response_text = response.text.strip()
            # Extract JSON from response if needed
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text
                
            task_data = json.loads(json_str)
            title = task_data.get("title", task_desc)
            
            # Parse the date or use tomorrow
            try:
                date_str = task_data.get("date")
                if date_str:
                    # Try to parse the date
                    from dateutil import parser
                    dt = parser.parse(date_str)
                else:
                    # Use tomorrow at 9am
                    dt = datetime.now() + timedelta(days=1)
                    dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
            except:
                # Fallback to tomorrow at 9am
                dt = datetime.now() + timedelta(days=1)
                dt = dt.replace(hour=9, minute=0, second=0, microsecond=0)
                
            # Create the calendar event
            iso_date = dt.isoformat() + 'Z'
            event = create_calendar_event(creds, title, "Added from RunDown", dt.strftime("%Y-%m-%d %H:%M:%S"), iso_date)
            return jsonify({
                "response": title, 
                "event": event.get("htmlLink"),
                "deadline": dt.strftime("%b %d, %Y at %I:%M %p")
            })
        except Exception as parse_error:
            chat_bp.logger.error(f"Error parsing AI response: {parse_error}")
            return jsonify({"response": task_desc})
            
    except Exception as e:
        chat_bp.logger.error(f"Add task error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
