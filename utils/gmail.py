# backend/utils/gmail.py
import os
import base64
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from utils.auth import get_flow, save_credentials, load_credentials
from google.auth.transport.requests import Request


def ensure_label_exists(service, label_name):
    """Create a label if it doesn't exist and return its ID."""
    try:
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        for label in labels:
            if label['name'] == label_name:
                return label['id']
        
        label_body = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        label = service.users().labels().create(userId='me', body=label_body).execute()
        return label['id']
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def get_email_details(service, email_id):
    """Fetch email details including subject, sender, and content."""
    try:
        message = service.users().messages().get(userId='me', id=email_id, format='full').execute()
        headers = message.get('payload', {}).get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
        email_body = extract_email_body(message.get('payload', {}))
        return {
            'id': email_id,
            'subject': subject,
            'sender': sender,
            'content': email_body
        }
    except Exception as e:
        return {'error': str(e)}

def extract_email_body(payload):
    """Extract the email body from the payload."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                return decode_base64(part['body']['data'])
            elif 'parts' in part:
                return extract_email_body(part)
    if 'body' in payload and 'data' in payload['body']:
        return decode_base64(payload['body']['data'])
    return "No content available"

def decode_base64(encoded_str):
    """Decode a base64 encoded string."""
    try:
        return base64.urlsafe_b64decode(encoded_str).decode('utf-8')
    except Exception:
        return "Error decoding content"


def fetch_emails(user_id, days=7):
    """
    Fetch emails from Gmail inbox
    
    Args:
        user_id: The user ID to fetch emails for
        days: Number of days to look back for emails (default: 7)
    
    Returns:
        List of email objects with id, subject, content, and date
    """
    creds = load_credentials(user_id)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_credentials(user_id, creds)
        else:
            return None  # Handle this case properly in your application

    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Calculate the date range based on the days parameter
        from datetime import datetime, timedelta
        date_from = (datetime.now() - timedelta(days=days)).strftime('%Y/%m/%d')
        
        # Create query to get emails from the specified time period
        query = f'after:{date_from}'
        
        messages = service.users().messages().list(
            userId='me',
            maxResults=10,  # Increased to get more emails for filtering
            labelIds=['INBOX'],
            q=query
        ).execute().get('messages', [])
        
        return [get_email_details(service, msg['id']) for msg in messages]
    except Exception as e:
        print(f"Error fetching emails: {str(e)}")
        return {'error': str(e)}