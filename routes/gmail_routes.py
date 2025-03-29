from flask import Blueprint, jsonify, session, redirect, current_app
from utils.gmail import fetch_emails
from utils.auth import load_credentials, require_auth

gmail_bp = Blueprint('gmail', __name__)

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
        current_app.logger.error(f"Failed to fetch emails: {str(e)}")
        return jsonify({"error": "Failed to fetch emails"}), 500
