import streamlit as st
import os
import json
import utils
from models.news_item import NewsItem

def sync_daily_reports(target_date, drive_folder_id, credentials_file):
    """
    Synchronizes all news reports for a specific date using a 2-tier cache:
    1. Checks local 'daily/' directory.
    2. Downloads from Google Drive if local is missing.
    Converts list of dicts to list of NewsItem for the 'articles' key.
    """
    sync_results = []
    
    # Files to sync
    sync_map = {
        "articles": f"{target_date}_articles.json",
        "nyt": f"{target_date}_nyt.json",
        "insight": f"{target_date}_insight.json"
    }

    for key, filename in sync_map.items():
        local_path = os.path.join("daily", filename)
        data = None
        
        # Tier 1: Local Cache
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                st.toast(f"📦 로컬 캐시 로드: {filename}")
            except Exception as e:
                st.error(f"캐시 로드 실패 ({filename}): {e}")

        # Tier 2: Google Drive
        if not data:
            with st.spinner(f"☁️ 드라이브 검색 중: {filename}"):
                data = utils.find_and_download_json(filename, drive_folder_id, credentials_file)
                if data:
                    st.toast(f"✅ 드라이브 다운로드 완료: {filename}")
                    # Save to local for future use
                    utils.save_to_json(data, local_path)

        # Update Session State based on key
        if data:
            if key == "articles":
                # Convert list of dicts -> list of NewsItem objects
                try:
                    news_items = [NewsItem.from_dict(d) for d in data]
                    st.session_state['data'] = news_items
                except Exception as e:
                    st.error(f"뉴스 데이터 모델 변환 실패: {e}")
            elif key == "nyt":
                st.session_state['nyt_text'] = data.get('raw', '')
                st.session_state['nyt_translation'] = data.get('translation', '')
            elif key == "insight":
                st.session_state['final_report'] = data.get('report', '')
            sync_results.append(key)

    return sync_results
