import os
import json
import io
import streamlit as st
from typing import List, Dict, Any, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import utils # Base auth remains in utils for now, or moved slowly
from config.settings import settings

class StorageService:
    """Infrastructure layer for managing Google Drive and Local File System I/O."""
    
    def __init__(self, service_account_file: str = 'credentials.json'):
        self.service_account_file = service_account_file
        self.drive_folder_id = settings.drive_folder_id

    def save_local_json(self, data: Any, filename: str):
        """Saves data to a local JSON file in the 'daily' directory."""
        path = os.path.join("daily", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_local_txt(self, content: str, filename: str):
        """Saves content to a local TXT file in the 'daily' directory."""
        path = os.path.join("daily", filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def get_drive_service(self):
        """Initializes the Google Drive service using OAuth or Service Account fallback."""
        return utils.get_drive_service(self.service_account_file)

    def upload_content_to_drive(self, content: str, filename: str, mime_type: str = 'text/plain') -> str:
        """Uploads raw content as a file to the defined Google Drive folder."""
        try:
            service = self.get_drive_service()
            if not service: return "Error: Drive service initialization failed"
            
            file_metadata = {'name': filename, 'parents': [self.drive_folder_id]}
            media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype=mime_type)
            
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return file.get('id')
        except Exception as e:
            return f"Drive Upload Error: {str(e)}"

    def find_and_download_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """Downloads a specific JSON file from the Drive folder if it exists."""
        try:
            service = self.get_drive_service()
            if not service: return None
            
            # List files to find match
            query = f"'{self.drive_folder_id}' in parents and name = '{filename}' and trashed = false"
            results = service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            if not files: return None
            
            # Download first match
            file_id = files[0]['id']
            content = service.files().get_media(fileId=file_id).execute()
            return json.loads(content.decode('utf-8'))
        except Exception as e:
            print(f"Drive Download Error: {e}")
            return None

    def get_alert_status_uncached(self, filename: str = "alert_state.json") -> Optional[Dict[str, Any]]:
        """Fetches the latest alert status directly from Drive, bypassing Streamlit cache."""
        return self.find_and_download_json(filename)
