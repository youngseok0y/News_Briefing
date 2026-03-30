import feedparser
import requests
import os
import json
import utils
from datetime import datetime

def run_alert_system():
    # 1. 설정값 로드 (GitHub Secrets/Env)
    DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK')
    DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')
    # GitHub Actions에서는 GCP_SERVICE_ACCOUNT 환경변수를 사용하며, 로컬에서는 파일명을 참조함
    SERVICE_ACCOUNT_FILE = 'credentials.json' 
    STATE_FILE = "alert_state.json"

    if not DISCORD_WEBHOOK or not DRIVE_FOLDER_ID:
        print("❌ 필수 환경변수(DISCORD_WEBHOOK, DRIVE_FOLDER_ID)가 없습니다.")
        return

    # 2. 기존 상태 로드 (GDrive에서 마지막 전송 항목 확인)
    print("🔍 상태 확인 (GCP_SERVICE_ACCOUNT 환경변수 또는 credentials.json) 중...")
    last_state = utils.find_and_download_json(STATE_FILE, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
    last_title = last_state.get('last_title', '') if last_state else ''

    # 3. RSS 피드 수집 (연합뉴스 속보)
    print("📡 연합뉴스 RSS 피드 수집 중...")
    feed = feedparser.parse("https://www.yonhapnews.co.kr/rss/news.xml")
    
    if not feed.entries:
        print("⚠️ 수집된 기사가 없습니다.")
        return

    # 최신 순으로 정렬 (보통 RSS는 이미 정렬되어 있음)
    latest_news = feed.entries[0]
    current_title = latest_news.title
    current_link = latest_news.link

    # 4. 중복 체크 및 알림 발송
    if current_title != last_title:
        print(f"🚨 새로운 기사 발견: {current_title}")
        
        # 디스코드 메시지 구성
        payload = {
            "content": f"🚨 **[연합뉴스 속보]**\n\n**{current_title}**\n\n🔗 [기사 읽기]({current_link})",
            "username": "AI News Notifier",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3208/3208035.png"
        }
        
        response = requests.post(DISCORD_WEBHOOK, json=payload)
        
        if response.status_code == 204:
            print("✅ 디스코드 알림 발송 성공!")
            
            # 5. 최신 상태 업데이트 (GDrive)
            new_state = {
                "last_title": current_title,
                "link": current_link,
                "updated_at": datetime.now(utils.KST).strftime("%Y-%m-%d %H:%M:%S")
            }
            utils.save_and_upload_json(new_state, STATE_FILE, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
            print("💾 GDrive 상태 업데이트 완료.")
        else:
            print(f"❌ 알림 발송 실패: {response.status_code}")
    else:
        print("✅ 업데이트된 새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    run_alert_system()
