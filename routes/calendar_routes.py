from flask import Blueprint, jsonify, session, redirect, request
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError
from utils.calendar import fetch_calendar_events, delete_calendar_event
from utils.auth import load_credentials, save_credentials
import traceback

calendar_bp = Blueprint('calendar', __name__)

def require_auth(view):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            print(f"Authentication required but no user_id in session. Session keys: {session.keys()}")
            # For AJAX requests, return a JSON response instead of redirecting
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            return redirect('/login')
        return view(*args, **kwargs)
    wrapper.__name__ = view.__name__
    return wrapper

@calendar_bp.route('/calendar', methods=['GET', 'OPTIONS'])
@require_auth
def calendar_events_route():
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        user_id = session.get('user_id')
        if not user_id:
            print("No user_id in session")
            return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            
        creds = load_credentials(user_id)
        if not creds:
            print("No credentials found in storage")
            return jsonify({"error": "No credentials found", "redirect": "/login"}), 401
            
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(user_id, creds)
            except Exception as refresh_error:
                print(f"Refresh failed: {str(refresh_error)}")
                return jsonify({"error": "Failed to refresh credentials", "redirect": "/login"}), 401
                
        events = fetch_calendar_events(creds)
        return jsonify({"events": events})
    except HttpError as error:
        print(f"Google API Error: {error._get_reason()}")
        return jsonify({"error": f"Calendar API Error: {error._get_reason()}"}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        print(traceback.format_exc())
        return jsonify({"error": f"Server Error: {str(e)}"}), 500

@calendar_bp.route('/calendar/delete', methods=['POST', 'OPTIONS'])
@require_auth
def delete_calendar_event_route():
    """Delete a calendar event by ID."""
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        # Print the request details for debugging
        print(f"Delete request received: {request.json}")
        print(f"Request headers: {dict(request.headers)}")
        print(f"Session info: {dict(session)}")
        
        user_id = session.get('user_id')
        if not user_id:
            print("No user_id in session")
            return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            
        event_id = request.json.get('event_id')
        if not event_id:
            print("No event_id provided")
            return jsonify({"error": "Event ID is required"}), 400
            
        print(f"Attempting to delete calendar event {event_id} for user {user_id}")
        
        creds = load_credentials(user_id)
        if not creds:
            print("No credentials found")
            return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            
        if creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired credentials")
                creds.refresh(Request())
                save_credentials(user_id, creds)
            except Exception as refresh_error:
                print(f"Credential refresh failed: {str(refresh_error)}")
                return jsonify({"error": "Failed to refresh credentials", "redirect": "/login"}), 401
                
        print("Calling delete_calendar_event function")
        result = delete_calendar_event(creds, event_id)
        print(f"Delete result: {result}")
        return jsonify({"success": True, "message": "Event deleted successfully"})
    except HttpError as error:
        error_details = {
            "status": error.resp.status,
            "reason": error._get_reason()
        }
        print(f"Google API Error: {error_details}")
        
        if error.resp.status == 404:
            # If the event doesn't exist, consider it a success (already deleted)
            return jsonify({"success": True, "message": "Event already deleted"})
        return jsonify({"error": f"Calendar API Error: {error._get_reason()}"}), error.resp.status
    except Exception as e:
        print(f"Unexpected error in delete_calendar_event_route: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Server Error: {str(e)}"}), 500
