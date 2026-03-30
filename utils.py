import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import base64
from bs4 import BeautifulSoup
from config.settings import settings # 💡 Use unified settings
try:
    import streamlit as st
except ImportError:
    st = None 

# 한국 표준시 (KST, UTC+9) 설정
KST = timezone(timedelta(hours=9))

# Streamlit 데코레이터 안전 처리 (CLI 대응)
def st_cache_data_safe(ttl=None, **kwargs):
    def decorator(func):
        return func
    return decorator

cache_data = st.cache_data if st is not None else st_cache_data_safe

def get_latest_date():
    """6시 이전이면 전날짜 반환 (KST 기준)"""
    now = datetime.now(KST)
    if now.hour < 6:
        now -= timedelta(days=1)
    return now.strftime("%Y%m%d")

def hash_text(text: str) -> str:
    """텍스트의 MD5 해시 반환 (캐싱용)"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def trim_text(text: str, max_len: int = 2500) -> str:
    """Intelligence: Truncates text at sentence boundary."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_boundary = max(truncated.rfind('\n'), truncated.rfind('. '))
    if last_boundary > max_len * 0.7:
        return truncated[:last_boundary + 1]
    return truncated

def save_to_json(data: list, filepath: str):
    dirname = os.path.dirname(filepath)
    if dirname: os.makedirs(dirname, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_txt(content: str, filepath: str):
    dirname = os.path.dirname(filepath)
    if dirname: os.makedirs(dirname, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def get_google_creds(oauth_client_file='client_secret.json'):
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/gmail.readonly'
    ]
    creds = None
    
    # 💡 [V5.3 Fix] Use 'settings' instead of direct 'st.secrets' (Claude audit)
    
    # 1. Cloud Token (Streamlit Secrets or Env Var)
    token_b64 = os.getenv("GOOGLE_TOKEN_PICKLE_BASE64")
    if not token_b64 and st:
        # Check settings singleton which handles runtime safety
        token_b64 = settings._get_secret("GOOGLE_TOKEN_PICKLE_BASE64")

    if token_b64:
        try:
            token_json = base64.b64decode(token_b64).decode('utf-8')
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception: pass

    # 2. Local File
    token_file = 'token.json'
    if not creds and os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_info(json.load(open(token_file)), SCOPES)
        except Exception: pass
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Client secret loading
            client_config_raw = os.getenv("GOOGLE_CLIENT_SECRET_JSON")
            if not client_config_raw and st:
                client_config_raw = settings._get_secret("GOOGLE_CLIENT_SECRET_JSON")

            if client_config_raw:
                try: client_config = json.loads(client_config_raw)
                except Exception: client_config = None
            elif os.path.exists(oauth_client_file):
                client_config = json.load(open(oauth_client_file))
            else: client_config = None

            if not client_config: return None
            if os.getenv("GITHUB_ACTIONS") or os.getenv("NON_INTERACTIVE"): return None
                
            try:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
                # Save locally for future use
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception: return None
                
    return creds

def get_drive_service(service_account_file, oauth_client_file='client_secret.json'):
    creds = get_google_creds(oauth_client_file)
    if creds: return build('drive', 'v3', credentials=creds)
    
    # Fallback to Service Account
    sa_info_raw = os.getenv("GCP_SERVICE_ACCOUNT")
    if not sa_info_raw and st:
        sa_info_raw = settings._get_secret("GCP_SERVICE_ACCOUNT")

    if sa_info_raw:
        try:
            sa_info = json.loads(sa_info_raw.strip())
            SCOPES = ['https://www.googleapis.com/auth/drive.file']
            creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
        except Exception: pass
        
    elif os.path.exists(service_account_file):
        sa_info = json.load(open(service_account_file))
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
        
    return None

def fetch_nyt_newsletter(target_date: str = None, oauth_client_file='client_secret.json'):
    try:
        creds = get_google_creds(oauth_client_file)
        if not creds: return "Error: No Auth"
        service = build('gmail', 'v1', credentials=creds)
        query = 'from:nytdirect@nytimes.com subject:Morning'
        if target_date:
            query += f" after:{datetime.strptime(target_date, '%Y%m%d').strftime('%Y/%m/%d')}"
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])
        if not messages: return "Error: No NYT mail found"
        msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
        return _parse_gmail_msg(msg)
    except Exception as e: return f"Error: {e}"

def _parse_gmail_msg(msg):
    html_content = ""
    def parse_parts(parts):
        content = ""
        for part in parts:
            if part.get('mimeType') == 'text/html' and part.get('body', {}).get('data'):
                content += base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'parts' in part: content += parse_parts(part['parts'])
        return content
    if 'data' in msg['payload']['body']:
        html_content = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
    else: html_content = parse_parts(msg['payload'].get('parts', []))
    soup = BeautifulSoup(html_content, 'html.parser')
    for img in soup.find_all('img'):
        src = img.get('src', '').lower()
        if 'ad' not in src and 'promo' not in src:
            img.replace_with(f'\n\n![NYT Image]({img.get("src")})\n\n')
        else: img.decompose()
    return soup.get_text(separator='\n\n')

def upload_to_drive(content: str, filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    try:
        service = get_drive_service(service_account_file)
        if not service: return "Error: Init Fail"
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e: return str(e)

def list_drive_files(folder_id, service_account_file: str = 'credentials.json'):
    try:
        service = get_drive_service(service_account_file)
        if not service: return []
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, pageSize=15, fields="files(id, name, createdTime)", orderBy="createdTime desc").execute()
        return results.get('files', [])
    except Exception: return []

def download_drive_file(file_id, service_account_file: str = 'credentials.json'):
    try:
        service = get_drive_service(service_account_file)
        if not service: return None
        content = service.files().get_media(fileId=file_id).execute()
        return content.decode('utf-8')
    except Exception: return None

def save_and_upload_json(data: dict, filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    filepath = os.path.join("daily", filename)
    save_to_json(data, filepath)
    return upload_to_drive(json.dumps(data, ensure_ascii=False), filename, folder_id, service_account_file)

def find_and_download_json(filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    files = list_drive_files(folder_id, service_account_file)
    target = next((f for f in files if f['name'] == filename), None)
    if target:
        content = download_drive_file(target['id'], service_account_file)
        if content: return json.loads(content)
    return None

def get_alert_status_uncached(filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    return find_and_download_json(filename, folder_id, service_account_file)
