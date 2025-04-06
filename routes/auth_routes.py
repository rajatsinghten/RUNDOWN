from flask import Blueprint, redirect, request, session, render_template, jsonify, make_response
from googleapiclient.discovery import build
from config import SECRET_KEY
from utils.auth import get_flow, save_credentials
import traceback
from oauthlib.oauth2.rfc6749.errors import InvalidScopeError

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    try:
        flow = get_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true'
        )
        session['state'] = state
        # Set a cookie to help debug session issues
        resp = make_response(redirect(authorization_url))
        resp.set_cookie('session_started', 'true', max_age=3600, httponly=True, samesite='Lax')
        return resp
    except Exception as e:
        print(f"Error in login route: {str(e)}")
        print(traceback.format_exc())
        return render_template('error.html', error=str(e))

@auth_bp.route('/oauth/callback')
def callback():
    try:
        if 'state' not in session:
            print("State not in session")
            return 'State mismatch or session issue', 400
            
        if session['state'] != request.args.get('state'):
            print(f"State mismatch: {session['state']} vs {request.args.get('state')}")
            return 'State mismatch', 400
            
        flow = get_flow()
        try:
            flow.fetch_token(authorization_response=request.url)
        except InvalidScopeError as scope_error:
            # Log the scope error but continue the authentication process
            print(f"Scope warning (proceeding anyway): {str(scope_error)}")
        except Exception as token_error:
            print(f"Token fetch error: {str(token_error)}")
            return render_template('error.html', error=str(token_error))
            
        creds = flow.credentials
        
        # Get user information
        user_info_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_info_service.userinfo().get().execute()
        user_id = user_info['id']
        
        # Save credentials and set session
        save_credentials(user_id, creds)
        session['user_id'] = user_id
        session['user_email'] = user_info.get('email', '')
        session['user_name'] = user_info.get('name', '')
        session.permanent = True
        
        print(f"User authenticated: {user_id} ({session['user_email']})")
        
        # Set a cookie to track successful authentication
        resp = make_response(redirect('/'))
        resp.set_cookie('auth_status', 'authenticated', max_age=3600)
        return resp
    except Exception as e:
        print(f"Error in OAuth callback: {str(e)}")
        print(traceback.format_exc())
        return render_template('error.html', error=str(e))

@auth_bp.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status and return user info if authenticated."""
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user_id": session['user_id'],
            "user_email": session.get('user_email', ''),
            "user_name": session.get('user_name', '')
        })
    return jsonify({
        "authenticated": False
    }), 401

@auth_bp.route('/logout')
def logout():
    # Clear all session data
    session.clear()
    resp = make_response(redirect('/'))
    # Clear cookies
    resp.set_cookie('auth_status', '', expires=0)
    resp.set_cookie('session_started', '', expires=0)
    return resp
