import os

class Settings:
    """
    Centralized configuration and secrets management.
    V5.4: Safe for CI/CD environments without streamlit installed.
    """
    
    # Static config
    SERVICE_ACCOUNT_FILE = 'credentials.json'
    
    def _get_secret(self, key: str, default: str = "") -> str:
        """Heuristic secret retrieval with lazy streamlit import."""
        
        # 🟢 1. Try Streamlit Secrets ONLY if we are inside a running Streamlit app
        is_streamlit_run = False
        try:
            # 💡 Lazy import to allow running in CLI without streamlit package
            import streamlit as st
            from streamlit.runtime import exists
            is_streamlit_run = exists()
            
            if is_streamlit_run:
                if key in st.secrets:
                    return st.secrets[key]
        except (ImportError, Exception):
            pass
            
        # 🔵 2. Try Environment Variables (Priority for CLI/GitHub Actions)
        val = os.getenv(key)
        if val:
            return val.strip()
        
        return default

    def _require_secret(self, key: str) -> str:
        value = self._get_secret(key)
        if not value:
            raise RuntimeError(f"Missing required configuration: {key}")
        return value

    @property
    def drive_folder_id(self) -> str:
        return self._require_secret("DRIVE_FOLDER_ID")
        
    @property
    def gemini_api_key(self) -> str:
        return self._require_secret("GEMINI_API_KEY")

    @property
    def groq_api_key(self) -> str:
        """Optional API key for Groq fallback model."""
        return self._get_secret("GROQ_API_KEY")
        
    @property
    def discord_webhook(self) -> str:
        return self._get_secret("DISCORD_WEBHOOK")

    @property
    def ai_model_name(self) -> str:
        """Centralizes which Gemini model the project should target."""
        return self._get_secret("AI_MODEL_NAME", "gemini-2.5-flash")

    @property
    def is_streamlit_cloud(self) -> bool:
        """Checks if running on Streamlit Cloud environment."""
        return os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud"

# Singleton instance
settings = Settings()
