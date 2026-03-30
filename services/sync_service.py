import streamlit as st
import os
import json
import utils
from models.news_item import NewsItem
from services.storage_service import StorageService

def sync_daily_reports(target_date, storage_svc: StorageService):
    """
    Synchronizes daily reports using the architectural StorageService.
    Ensures type safety via NewsItem model transformation.
    """
    sync_results = []
    
    # Target file pattern mapping
    sync_map = {
        "articles": f"{target_date}_articles.json",
        "nyt": f"{target_date}_nyt.json",
        "insight": f"{target_date}_insight.json"
    }

    for key, filename in sync_map.items():
        local_path = os.path.join("daily", filename)
        data = None
        
        # 🟢 Tier 1: Local Case-first
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                st.toast(f"📦 Local Cache: {filename}")
            except Exception as e:
                st.error(f"Cache Load Failed: {e}")

        # 🔵 Tier 2: Drive Sync (via StorageService)
        if not data:
            with st.spinner(f"☁️ Syncing: {filename}"):
                data = storage_svc.find_and_download_json(filename)
                if data:
                    st.toast(f"✅ Sync Complete: {filename}")
                    storage_svc.save_local_json(data, filename)

        # 🧩 Process Synchronized Data
        if data:
            if key == "articles":
                st.session_state['data'] = [NewsItem.from_dict(d) for d in data]
            elif key == "nyt":
                st.session_state['nyt_text'] = data.get('raw', '')
                st.session_state['nyt_translation'] = data.get('translation', '')
            elif key == "insight":
                st.session_state['final_report'] = data.get('report', '')
            sync_results.append(key)

    return sync_results
