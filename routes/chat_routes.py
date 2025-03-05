from flask import current_app
from flask import Blueprint, request, jsonify, session
import google.generativeai as genai
from config import GOOGLE_API_KEY
from utils.calendar import fetch_calendar_events
from utils.gmail import fetch_emails
from utils.auth import load_credentials

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
        responses = []
        for email in emails:
            prompt = f"""
            {f'**Emails:**\n{email}' if email else ''}
            Above is one email in my inbox. Extract and return the subject of the email.
            """
            response = model.generate_content(prompt)
            responses.append(response.text.strip() if response and response.text.strip() else "No subject found")
        current_app.logger.info(f"AI Responses: {responses}")
        return jsonify({"responses": responses})
    except Exception as e:
        chat_bp.logger.error(f"Add suggestion error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@chat_bp.route('/addtask', methods=['POST'])
@require_auth
def add_task():
    user_id = session.get('user_id')
    user_message = request.data.decode('utf-8').strip()
    if not user_message:
        return ("Empty message"), 400
    try:
        prompt = f"""
        Generate a todo to be added to the todo list with time and date from the task provided by the user.
        User Query: {user_message}
        """
        response = model.generate_content(prompt)
        if not response or not response.text.strip():
            return jsonify({"error": "Empty response from AI model"}), 500
        return jsonify({"response": response.text.strip()})
    except Exception as e:
        chat_bp.logger.error(f"Add task error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
