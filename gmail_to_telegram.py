import os
import pickle
import base64
import requests
import time
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'
TELEGRAM_CHAT_ID = 'YOUR_TELEGRAM_USER_ID_HERE'
# ---------------

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

LAST_ID_FILE = 'last_msg_id.txt'


def get_last_msg_id():
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, 'r') as f:
            return f.read().strip()
    return None

def set_last_msg_id(msg_id):
    with open(LAST_ID_FILE, 'w') as f:
        f.write(msg_id)


def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service


def fetch_new_inbox_messages(service, last_msg_id=None, max_results=10):
    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=max_results).execute()
    messages = results.get('messages', [])
    email_data = []
    found_last = False
    for msg in messages:
        if last_msg_id and msg['id'] == last_msg_id:
            found_last = True
            break
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['From', 'Subject', 'Date']).execute()
        headers = msg_data['payload']['headers']
        msg_info = {h['name']: h['value'] for h in headers}
        snippet = msg_data.get('snippet', '')
        email_data.append({
            'id': msg['id'],
            'from': msg_info.get('From', ''),
            'subject': msg_info.get('Subject', ''),
            'date': msg_info.get('Date', ''),
            'snippet': snippet
        })
    return email_data, (messages[0]['id'] if messages else last_msg_id)


def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    response = requests.post(url, data=data)
    return response.json()


def main():
    service = get_gmail_service()
    print('Polling for new Gmail messages. Press Ctrl+C to stop.')
    while True:
        last_id = get_last_msg_id()
        emails, newest_id = fetch_new_inbox_messages(service, last_msg_id=last_id)
        # Only send if there are new messages
        if emails:
            # Send in reverse order so the oldest comes first
            for email in reversed(emails):
                msg = f"<b>From:</b> {email['from']}\n<b>Subject:</b> {email['subject']}\n<b>Date:</b> {email['date']}\n<pre>{email['snippet']}</pre>"
                send_telegram_message(msg)
            set_last_msg_id(newest_id)
        time.sleep(30)

if __name__ == '__main__':
    main()
