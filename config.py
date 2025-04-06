# backend/config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Allow OAuthlib to run without HTTPS for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Flask secret key (used for sessions)
SECRET_KEY = os.urandom(24)

# Token storage & encryption configuration
TOKENS_DIR = "tokens"
KEY_FILE = "secret.key"
LABEL_NAME = "AddedToCalendar"

# Google API scopes required by your app
SCOPES = [
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'openid',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email'
]

# Google API key for generative AI (make sure to set it in your .env file)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
