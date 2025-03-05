from flask import Flask, render_template, session, redirect
from flask_cors import CORS
from flask_session import Session
from apscheduler.schedulers.background import BackgroundScheduler
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import google.generativeai as genai
import os
 
# Configuration and utility imports
from config import SECRET_KEY, TOKENS_DIR, LABEL_NAME, GOOGLE_API_KEY
from utils.auth import load_credentials, save_credentials
from utils.gmail import ensure_label_exists
from utils.calendar import create_calendar_event, fetch_calendar_events

app = Flask(__name__)
CORS(app, supports_credentials=True, resources={
    r"/chat": {"origins": "http://127.0.0.1:5000"},
    r"/gmail": {"origins": "http://127.0.0.1:5000"},
    r"/calendar": {"origins": "http://127.0.0.1:5000"}
})
app.secret_key = SECRET_KEY  
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Configure the Generative AI model (used in blueprints)
genai.configure(api_key=GOOGLE_API_KEY)

# Scheduler for processing emails periodically
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()

def process_emails():
    """Periodic task to process emails and create calendar events."""
    print("Processing emails...")
    for token_file in os.listdir(TOKENS_DIR):
        user_id = token_file.split('.')[0]
        creds = load_credentials(user_id)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    save_credentials(user_id, creds)
                except Exception as e:
                    print(f"Failed to refresh credentials for {user_id}: {e}")
                    continue
            else:
                continue
        try:
            gmail_service = build('gmail', 'v1', credentials=creds)
            label_id = ensure_label_exists(gmail_service, LABEL_NAME)
            if not label_id:
                continue
            query = f"-label:{LABEL_NAME}"
            response = gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=1
            ).execute()
            messages = response.get('messages', [])
            for msg in messages:
                msg_id = msg['id']
                message = gmail_service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['Subject', 'From', 'Date']
                ).execute()
                headers = message.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
                internal_date = int(message.get('internalDate', 0))
                from datetime import datetime
                dt = datetime.utcfromtimestamp(internal_date / 1000)
                iso_date = dt.isoformat() + 'Z'
                create_calendar_event(creds, subject, sender, date_str, iso_date)
                gmail_service.users().messages().modify(
                    userId='me',
                    id=msg_id,
                    body={'addLabelIds': [label_id]}
                ).execute()
        except Exception as e:
            print(f"Error processing emails for {user_id}: {e}")

scheduler.add_job(func=process_emails, trigger='interval', minutes=50)

# Import and register blueprints
from routes.auth_routes import auth_bp
from routes.chat_routes import chat_bp
from routes.gmail_routes import gmail_bp
from routes.calendar_routes import calendar_bp

app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(gmail_bp)
app.register_blueprint(calendar_bp)

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('chat.html')
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)