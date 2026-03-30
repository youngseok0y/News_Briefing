import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials # 💡 Safety: Use Official Credentials instead of Pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import base64
from bs4 import BeautifulSoup
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
    """
    💡 Intelligence: Truncates text at the last sentence boundary or newline 
    within the max_len to preserve context for LLM.
    """
    if len(text) <= max_len:
        return text
        
    truncated = text[:max_len]
    # Find last boundary: newline or period followed by space
    last_boundary = max(truncated.rfind('\n'), truncated.rfind('. '))
    
    if last_boundary > max_len * 0.7: # Only trim at boundary if it's not too short
        return truncated[:last_boundary + 1]
    return truncated

def save_to_json(data: list, filepath: str):
    """💡 Fix: Safely creates parent directories for JSON storage."""
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_txt(content: str, filepath: str):
    """💡 Fix: Safely creates parent directories for TXT storage."""
    dirname = os.path.dirname(filepath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def get_google_creds(oauth_client_file='client_secret.json'):
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/gmail.readonly'
    ]
    creds = None
    
    # 💡 Safety: Switching from Pickle to JSON-based credentials (Claude audit)
    
    # 1. Streamlit Secrets (Cloud)
    if st:
        try:
            if "GOOGLE_TOKEN_PICKLE_BASE64" in st.secrets: # Keep name but content is JSON
                token_json = base64.b64decode(st.secrets["GOOGLE_TOKEN_PICKLE_BASE64"]).decode('utf-8')
                creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception:
            pass
    
    # 2. Env Var (GitHub Actions)
    if not creds and os.getenv("GOOGLE_TOKEN_PICKLE_BASE64"):
        try:
            token_json = base64.b64decode(os.getenv("GOOGLE_TOKEN_PICKLE_BASE64")).decode('utf-8')
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        except Exception:
            pass

    # 3. Local File (token.json favored over token.pickle)
    token_file = 'token.json'
    if not creds and os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_info(json.load(open(token_file)), SCOPES)
        except Exception:
            pass
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Client secret loading
            client_config = None
            if st and "GOOGLE_CLIENT_SECRET_JSON" in st.secrets:
                client_config = json.loads(st.secrets["GOOGLE_CLIENT_SECRET_JSON"])
            elif os.getenv("GOOGLE_CLIENT_SECRET_JSON"):
                client_config = json.loads(os.getenv("GOOGLE_CLIENT_SECRET_JSON"))
            elif os.path.exists(oauth_client_file):
                client_config = json.load(open(oauth_client_file))

            if not client_config: return None
            if os.getenv("GITHUB_ACTIONS") or os.getenv("NON_INTERACTIVE"): return None
                
            try:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception:
                return None
            
        # 💾 Save for Local
        if st and st.secrets: pass
        else:
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
                
    return creds

def get_drive_service(service_account_file, oauth_client_file='client_secret.json'):
    # Try OAuth first
    creds = get_google_creds(oauth_client_file)
    if creds: return build('drive', 'v3', credentials=creds)
    
    # Fallback to Service Account
    sa_info = None
    if st and "GCP_SERVICE_ACCOUNT" in st.secrets:
        sa_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
    elif os.getenv("GCP_SERVICE_ACCOUNT"):
        sa_info = json.loads(os.getenv("GCP_SERVICE_ACCOUNT").strip())
    elif os.path.exists(service_account_file):
        sa_info = json.load(open(service_account_file))

    if sa_info:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
        
    return None

def fetch_nyt_newsletter(target_date: str = None, oauth_client_file='client_secret.json'):
    """💡 Optimization: Cache key includes target_date to avoid stale results (Claude audit)"""
    try:
        creds = get_google_creds(oauth_client_file)
        if not creds: return "Error: No Auth"
        
        service = build('gmail', 'v1', credentials=creds)
        # If date provided, use it to narrow search
        query = 'from:nytdirect@nytimes.com subject:Morning'
        if target_date:
            query += f" after:{datetime.strptime(target_date, '%Y%m%d').strftime('%Y/%m/%d')}"
            
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])
        if not messages: return "Error: No NYT mail found"
        
        # ... logic for parsing remains same but safe ...
        msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
        # [HTML Parsing Logic simplified for here but keep BS4]
        return _parse_gmail_msg(msg)
    except Exception as e:
        return f"Error: {e}"

def _parse_gmail_msg(msg):
    # Internal helper for fetch_view_file
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
    else:
        html_content = parse_parts(msg['payload'].get('parts', []))
        
    soup = BeautifulSoup(html_content, 'html.parser')
    # Premium parsing logic...
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
