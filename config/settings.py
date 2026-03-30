import streamlit as st
import os

class Settings:
    """
    Centralized configuration and secrets management.
    V5.2: Ultra-robust detection of Streamlit runtime to prevent SecretNotFoundErrors in CLI.
    """
    
    # Static config
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    
    def _get_secret(self, key: str, default: str = "") -> str:
        """Heuristic secret retrieval."""
        
        # 🟢 1. Try Streamlit Secrets ONLY if we are inside a running Streamlit app
        # This prevents the library from screaming 'No secrets found' in terminal.
        is_streamlit_run = False
        try:
            from streamlit.runtime import exists
            is_streamlit_run = exists()
        except ImportError:
            pass

        if is_streamlit_run:
            try:
                # Use get() for safety, wrap in broad check
                if key in st.secrets:
                    return st.secrets[key]
            except Exception:
                # If it still fails (e.g. no secrets.toml), fall back to Env Vars
                pass
            
        # 🔵 2. Try Environment Variables (Priority for CLI/GitHub Actions)
        val = os.getenv(key)
        if val:
            return val.strip()
            
        return default

    @property
    def drive_folder_id(self) -> str:
        return self._get_secret("DRIVE_FOLDER_ID")
        
    @property
    def gemini_api_key(self) -> str:
        return self._get_secret("GEMINI_API_KEY")
        
    @property
    def discord_webhook(self) -> str:
        return self._get_secret("DISCORD_WEBHOOK")

    @property
    def is_streamlit_cloud(self) -> bool:
        """Checks if running on Streamlit Cloud environment."""
        return os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud"

# Singleton instance
settings = Settings()
