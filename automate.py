import os
import json
from datetime import datetime
from config.settings import settings
from services.storage_service import StorageService
from services.news_service import NewsService
from services.ai_service import AIService
import utils

def run_automation():
    """
    V5.0 Modernized Automation Script.
    Orchestrates the full pipeline using official V4.0/V5.0 services.
    """
    print(f"🚀 [V5.0] Daily News Pipeline Automation Starting: {datetime.now(utils.KST)}")
    
    # 1. 인프라 및 서비스 초기화 (Settings 기반)
    try:
        storage_svc = StorageService(settings.SERVICE_ACCOUNT_FILE)
        news_svc = NewsService(storage_svc)
        # 💡 [V7.1] AIService requires storage_svc for GDrive-backed cache
        ai_svc = AIService(settings.gemini_api_key, storage_svc)
        print("✅ Services initialized successfully.")
    except Exception as e:
        print(f"❌ Service Init Failed: {e}")
        return

    target_date = utils.get_latest_date()
    
    # 2. 뉴스 수집 (Parallel Scraper Engine 가동)
    print(f"📡 Scraping news for {target_date}...")
    try:
        news_items = news_svc.fetch_and_process_daily_news(target_date)
        if not news_items:
            print("⚠️ No news articles collected. Exiting.")
            return
        print(f"✅ Collected {len(news_items)} articles.")
    except Exception as e:
        print(f"❌ Scraping Failed: {e}")
        return

    # 3. AI 종합 인사이트 보고서 생성
    print("🤖 Generating strategic insight report via Gemini...")
    try:
        final_report = ai_svc.generate_insight_report(news_items)
        storage_svc.save_local_json({"report": final_report, "date": target_date}, f"{target_date}_insight.json")
        print("✅ Insight report generated.")
    except Exception as e:
        print(f"❌ Insight Generation Failed: {e}")
        final_report = "Analysis failed."

    # 4. NYT 뉴스레터 연동 및 번역
    print("🇺🇸 Fetching and translating NYT newsletter...")
    try:
        nyt_raw = utils.fetch_nyt_newsletter(target_date)
        if "Error" not in nyt_raw:
            nyt_translation = ai_svc.translate_nyt(nyt_raw)
            storage_svc.save_local_json({"raw": nyt_raw, "translation": nyt_translation, "date": target_date}, f"{target_date}_nyt.json")
            print("✅ NYT Newsletter processed.")
        else:
            print(f"⚠️ NYT Fetch Skipped: {nyt_raw}")
    except Exception as e:
        print(f"❌ NYT Processing Error: {e}")

    # 5. 최종 통합 업로드
    print("📤 Formatting and uploading to Google Drive...")
    try:
        success, fid = news_svc.upload_for_notebook_lm(news_items, target_date)
        if success:
            print(f"🎉 Pipeline Complete! Drive ID: {fid}")
        else:
            print(f"❌ Cloud Upload Failed: {fid}")
    except Exception as e:
        print(f"❌ Upload Stage Error: {e}")

if __name__ == "__main__":
    run_automation()
