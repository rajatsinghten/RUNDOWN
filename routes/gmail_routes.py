from flask import Blueprint, jsonify, session, redirect
from utils.gmail import fetch_emails
from utils.auth import load_credentials

gmail_bp = Blueprint('gmail', __name__)

def require_auth(view):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

@gmail_bp.route('/gmail')
@require_auth
def get_emails():
    user_id = session['user_id']
    try:
        email_details = fetch_emails(user_id)
        if email_details is None:
            return redirect('/login')
        return jsonify({'emails': email_details})
    except Exception as e:
        gmail_bp.logger.error(f"Failed to fetch emails: {str(e)}")
        return jsonify({"error": "Failed to fetch emails"}), 500
