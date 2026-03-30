import os
import json
import hashlib
from datetime import datetime, timedelta, timezone
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle
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

def trim_text(text: str, max_len: int = 1200) -> str:
    """API 토큰 절약을 위한 텍스트 자르기"""
    return text[:max_len]

def save_to_json(data: list, filepath: str):
    """데이터를 JSON으로 저장"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_to_txt(content: str, filepath: str):
    """내용을 TXT로 저장"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def get_google_creds(oauth_client_file='client_secret.json'):
    SCOPES = [
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/gmail.readonly'
    ]
    creds = None
    
    # 1. Streamlit Secrets 확인 (Cloud 배포용)
    if st:
        try:
            if "GOOGLE_TOKEN_PICKLE_BASE64" in st.secrets:
                token_data = base64.b64decode(st.secrets["GOOGLE_TOKEN_PICKLE_BASE64"])
                creds = pickle.loads(token_data)
        except Exception:
            pass
    
    # 2. 환경 변수 확인 (GitHub Actions용)
    if not creds and os.getenv("GOOGLE_TOKEN_PICKLE_BASE64"):
        try:
            token_data = base64.b64decode(os.getenv("GOOGLE_TOKEN_PICKLE_BASE64"))
            creds = pickle.loads(token_data)
        except Exception as e:
            print(f"Env Token Error: {e}")

    # 3. 로컬 파일 확인 (Local Dev용)
    if not creds and os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # 기존 토큰의 스코프 확인 및 갱신
    if creds and hasattr(creds, 'scopes'):
        if not all(scope in creds.scopes for scope in SCOPES):
            creds = None # 재인증 유도
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # OAuth 클라이언트 파일 정보 가져오기 (Secrets/Env/File 순)
            client_config = None
            if st:
                try:
                    if "GOOGLE_CLIENT_SECRET_JSON" in st.secrets:
                        client_config = json.loads(st.secrets["GOOGLE_CLIENT_SECRET_JSON"])
                except Exception:
                    pass
            
            if not client_config and os.getenv("GOOGLE_CLIENT_SECRET_JSON"):
                client_config = json.loads(os.getenv("GOOGLE_CLIENT_SECRET_JSON"))
            elif os.path.exists(oauth_client_file):
                with open(oauth_client_file, 'r') as f:
                    client_config = json.load(f)

            if not client_config:
                return None

            # GitHub Actions나 서버 환경 등 브라우저를 열 수 없는 환경인지 체크
            if os.getenv("GITHUB_ACTIONS") or os.getenv("NON_INTERACTIVE"):
                return None
                
            try:
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=0, timeout_seconds=60)
            except Exception as e:
                print(f"❌ OAuth Flow Error: {e}")
                return None
            
        # 새로운 토큰 저장 (로컬 환경일 때만)
        is_streamlit_cloud = False
        try:
            if st and st.secrets:
                is_streamlit_cloud = True
        except Exception:
            pass
            
        if not is_streamlit_cloud:
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
                
    return creds

def get_drive_service(service_account_file, oauth_client_file='client_secret.json'):
    # 1. 일반 OAuth 우선 (최상위: 개인 계정 쿼터 사용)
    creds = get_google_creds(oauth_client_file)
    if creds:
        return build('drive', 'v3', credentials=creds)
    
    # 2. 서비스 계정 (Fallback)
    sa_info = None
    if st:
        try:
            if "GCP_SERVICE_ACCOUNT" in st.secrets:
                sa_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        except Exception:
            pass
            
    if not sa_info and os.getenv("GCP_SERVICE_ACCOUNT"):
        try:
            sa_info = json.loads(os.getenv("GCP_SERVICE_ACCOUNT").strip())
            required_fields = ["project_id", "private_key", "client_email", "token_uri"]
            missing = [f for f in required_fields if f not in sa_info]
            if missing:
                print(f"⚠️ GCP_SERVICE_ACCOUNT JSON에 다음 필드가 누락되었습니다: {missing}")
        except Exception as e:
            print(f"❌ GCP_SERVICE_ACCOUNT 파싱 에러: {e}")
    elif os.path.exists(service_account_file):
        with open(service_account_file, 'r') as f:
            sa_info = json.load(f)

    if sa_info:
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
        
    return None

@cache_data(ttl=3600)
def fetch_nyt_newsletter(oauth_client_file='client_secret.json'):
    """지메일에서 NYT 'The Morning' 뉴스레터 최신 1건을 가져와 텍스트로 파싱"""
    try:
        creds = get_google_creds(oauth_client_file)
        if not creds:
            return "Error: 인증 정보가 없습니다."
            
        service = build('gmail', 'v1', credentials=creds)
        query = 'from:nytdirect@nytimes.com subject:Morning'
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return "Error: NYT 뉴스레터를 찾을 수 없습니다."
            
        msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()
        parts = msg['payload'].get('parts', [])
        html_content = ""
        
        def parse_parts(parts):
            content = ""
            for part in parts:
                mime_type = part.get('mimeType')
                body_data = part.get('body', {}).get('data')
                if mime_type == 'text/html' and body_data:
                    content += base64.urlsafe_b64decode(body_data).decode('utf-8')
                elif 'parts' in part:
                    content += parse_parts(part['parts'])
            return content

        if 'data' in msg['payload']['body']:
            html_content = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
        else:
            html_content = parse_parts(parts)
            
        if not html_content:
            return "Error: 이메일 본문을 읽을 수 없습니다."
            
        soup = BeautifulSoup(html_content, 'html.parser')
        for junk in soup(["script", "style", "nav", "footer"]):
            junk.decompose()
            
        ad_keywords = ['ad', 'marketing', 'promo', 'pixel', 'logo', 'icon', 'social', 'facebook', 'twitter', 'instagram']
        for img in soup.find_all('img'):
            src = img.get('src', '').lower()
            alt = img.get('alt', '').lower()
            width = img.get('width', '')
            height = img.get('height', '')
            is_ad = any(kw in src or kw in alt for kw in ad_keywords)
            is_tiny = (width == '1' or height == '1')
            
            if src and not is_ad and not is_tiny:
                original_src = img.get('src')
                original_alt = img.get('alt', 'NYT Image')
                img.replace_with(f'\n\n<img src="{original_src}" alt="{original_alt}" style="max-width:100%; border-radius:10px;">\n\n')
            else:
                img.decompose()

        for h in soup.find_all(['h1', 'h2', 'h3', 'h4']):
            h.replace_with(f'\n\n### {h.get_text(strip=True)}\n\n')
        for p in soup.find_all('p'):
            p.replace_with(f'\n\n{p.get_text(strip=True)}\n\n')

        clean_text = soup.get_text()
        final_lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        return "\n\n".join(final_lines)
    except Exception as e:
        return f"Error: {str(e)}"

def upload_to_drive(content: str, filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    """구글 드라이브에 파일 업로드"""
    try:
        service = get_drive_service(service_account_file)
        if not service:
            return "Error: 인증 서비스(OAuth/ServiceAccount)를 초기화할 수 없습니다."
            
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
        
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        error_msg = str(e)
        if "storageQuotaExceeded" in error_msg:
            return "Error: Storage Quota Exceeded. 서비스 계정 대신 OAuth 인증(token.pickle)을 사용해 주세요."
        return error_msg

def list_drive_files(folder_id, service_account_file: str = 'credentials.json'):
    """지정된 폴더 내의 파일 목록을 최신순으로 반환"""
    try:
        service = get_drive_service(service_account_file)
        if not service: return []
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(q=query, pageSize=15, fields="files(id, name, createdTime)", orderBy="createdTime desc").execute()
        return results.get('files', [])
    except Exception as e:
        print(f"Drive List Error: {e}")
        return []

def download_drive_file(file_id, service_account_file: str = 'credentials.json'):
    """파일 ID로 내용을 다운로드하여 문자열로 반환"""
    try:
        service = get_drive_service(service_account_file)
        if not service: return None
        content = service.files().get_media(fileId=file_id).execute()
        return content.decode('utf-8')
    except Exception as e:
        print(f"Drive Download Error: {e}")
        return None

def save_and_upload_json(data: dict, filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    """데이터를 JSON으로 저장하고 구글 드라이브에 업로드"""
    filepath = os.path.join("daily", filename)
    save_to_json(data, filepath)
    return upload_to_drive(json.dumps(data, ensure_ascii=False), filename, folder_id, service_account_file)

@cache_data(ttl=600)
def find_and_download_json(filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    """드라이브에서 파일명으로 찾아 JSON 데이터 반환 (캐싱 사용)"""
    return _get_json_from_drive(filename, folder_id, service_account_file)

def get_alert_status_uncached(filename: str, folder_id: str, service_account_file: str = 'credentials.json'):
    """캐시 없이 드라이브에서 직접 상태 파일을 읽어옴 (대시보드 실시간용)"""
    return _get_json_from_drive(filename, folder_id, service_account_file)

def _get_json_from_drive(filename: str, folder_id: str, service_account_file: str):
    """드라이브에서 파일을 찾는 내부 공통 로직 (실제 API 호출)"""
    files = list_drive_files(folder_id, service_account_file)
    target = next((f for f in files if f['name'] == filename), None)
    if target:
        content = download_drive_file(target['id'], service_account_file)
        if content:
            return json.loads(content)
    return None
