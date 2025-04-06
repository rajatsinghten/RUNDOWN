# backend/utils/auth.py
import os
import json
from pathlib import Path
from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from config import TOKENS_DIR, KEY_FILE, SCOPES

# Ensure the tokens directory exists
Path(TOKENS_DIR).mkdir(exist_ok=True)

# Initialize the encryption cipher
if not os.path.exists(KEY_FILE):
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
else:
    with open(KEY_FILE, 'rb') as f:
        key = f.read()

cipher = Fernet(key)

def get_flow():
    """Create and return a Google OAuth flow instance."""
    return Flow.from_client_secrets_file(
        'credentials.json',
        scopes=SCOPES,
        redirect_uri='https://rundown-sx8n.onrender.com/oauth/callback/'
    )

def save_credentials(user_id, credentials):
    """Encrypt and save credentials to a file."""
    token_path = os.path.join(TOKENS_DIR, f"{user_id}.json")
    creds_json = credentials.to_json()
    encrypted_creds = cipher.encrypt(creds_json.encode())
    with open(token_path, 'wb') as f:
        f.write(encrypted_creds)

def load_credentials(user_id):
    """Load and decrypt credentials from a file."""
    token_path = os.path.join(TOKENS_DIR, f"{user_id}.json")
    if not os.path.exists(token_path):
        return None
    with open(token_path, 'rb') as f:
        encrypted_creds = f.read()
    decrypted_creds = cipher.decrypt(encrypted_creds).decode()
    return Credentials.from_authorized_user_info(json.loads(decrypted_creds))
