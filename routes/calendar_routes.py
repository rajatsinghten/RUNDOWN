from flask import Blueprint, jsonify, session, redirect
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from utils.calendar import fetch_calendar_events
from utils.auth import load_credentials, save_credentials

calendar_bp = Blueprint('calendar', __name__)

def require_auth(view):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

@calendar_bp.route('/calendar')
@require_auth
def calendar_events_route():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return redirect('/login')
        creds = load_credentials(user_id)
        if not creds:
            print("No credentials found in storage")
            return redirect('/login')
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(user_id, creds)
            except Exception as refresh_error:
                print(f"Refresh failed: {str(refresh_error)}")
                return redirect('/login')
        events = fetch_calendar_events(creds)
        return jsonify({"events": events})
    except HttpError as error:
        print(f"Google API Error: {error._get_reason()}")
        return jsonify({"error": "Calendar API Error"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Server Error"}), 500
