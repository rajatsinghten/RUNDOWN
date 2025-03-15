# backend/utils/auth.py
import os
import json
from pathlib import Path
from functools import wraps
from flask import session, jsonify, request, redirect
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
        redirect_uri='http://127.0.0.1:5000/oauth/callback'
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

def require_auth(view):
    """Decorator to require authentication for routes."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            # For AJAX requests, return a JSON response instead of redirecting
            if request and (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
                request.headers.get('Content-Type') == 'application/json'
            ):
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            return redirect('/login')
        return view(*args, **kwargs)
    return wrapper
