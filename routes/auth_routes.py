from flask import Blueprint, redirect, request, session, render_template
from googleapiclient.discovery import build
from config import SECRET_KEY
from utils.auth import get_flow, save_credentials

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@auth_bp.route('/oauth/callback')
def callback():
    if 'state' not in session or session['state'] != request.args.get('state'):
        return 'State mismatch', 400
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    user_info_service = build('oauth2', 'v2', credentials=creds)
    user_info = user_info_service.userinfo().get().execute()
    user_id = user_info['id']
    save_credentials(user_id, creds)
    session['user_id'] = user_id
    return redirect('/')

@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')
