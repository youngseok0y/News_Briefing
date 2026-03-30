import streamlit as st

class Settings:
    """Centralized configuration and secrets management."""
    
    # Google API Credentials
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    
    @property
    def drive_folder_id(self) -> str:
        return st.secrets.get("DRIVE_FOLDER_ID", "")
        
    @property
    def gemini_api_key(self) -> str:
        return st.secrets.get("GEMINI_API_KEY", "")
        
    @property
    def discord_webhook(self) -> str:
        return st.secrets.get("DISCORD_WEBHOOK", "")

    @property
    def is_streamlit_cloud(self) -> bool:
        try:
            return "st" in str(st.secrets)
        except Exception:
            return False

# 싱글톤 설정 객체
settings = Settings()
