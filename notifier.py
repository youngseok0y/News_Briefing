import requests
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
from config.settings import settings
from services.storage_service import StorageService
import utils

def run_alert_system():
    """V5.0 Optimized Alert System using StorageService and robust error handling."""
    
    # 1. 인프라 초기화
    storage_svc = StorageService(settings.SERVICE_ACCOUNT_FILE)
    STATE_FILE = "alert_state.json"
    
    webhook_url = settings.discord_webhook
    if not webhook_url:
        print("❌ DISCORD_WEBHOOK 설정이 없습니다.")
        return

    # 2. 이전 상태 로드 (StorageService 경유)
    print("📂 GDrive에서 이전 상태 확인 중...")
    last_state = storage_svc.get_alert_status_uncached(STATE_FILE)
    last_title = last_state.get('last_title', '') if last_state else ''
    
    # 3. 최신 뉴스 수집
    current_title = None
    current_link = None

    print("🔍 네이버 연합뉴스 속보 크롤링 시도...")
    try:
        url = "https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&sid1=001&sid2=140&oid=001&isYeonhapFlash=Y"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
        
        res = requests.get(url, headers=headers, timeout=15)
        # 💡 [V5.0 Improvement] Claude audit check
        res.raise_for_status() 
        
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 최적화된 선택자
        selector = ".list_body ul li dl dt:not(.photo) a"
        items = soup.select(selector)
        
        for item in items:
            temp_title = item.get_text(strip=True)
            if temp_title and len(temp_title) > 5:
                current_title = temp_title
                temp_link = item.get("href", "")
                current_link = temp_link if temp_link.startswith("http") else "https://news.naver.com" + temp_link
                break
                
        if current_title:
            print(f"✅ 최신 속보 확보: {current_title[:30]}...")
        else:
            print("⚠️ 속보 내용을 찾을 수 없습니다.")
            return

    except Exception as e:
        print(f"❌ 크롤링 장애 발생: {e}")
        return

    # 4. 중복 체크 및 발송
    if current_title != last_title:
        print(f"🚨 새 속보 발견! 알림 전송 시작.")
        
        payload = {
            "content": f"🚨 **[연합뉴스 속보]**\n\n**{current_title}**\n\n🔗 [기사 읽기]({current_link})",
            "username": "AI News Briefing (KST)",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3208/3208035.png"
        }
        
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            print("✅ 디스코드 메시지 전송 성공.")
            
            # 5. 상태 업데이트
            new_state = {
                "last_title": current_title,
                "link": current_link,
                "updated_at": datetime.now(utils.KST).strftime("%Y-%m-%d %H:%M:%S")
            }
            storage_svc.save_local_json(new_state, STATE_FILE)
            storage_svc.upload_content_to_drive(json.dumps(new_state, ensure_ascii=False), STATE_FILE)
            print("💾 GDrive 상태 파일 갱신 완료.")
            
        except Exception as e:
            print(f"❌ 알림 전송/상태 업데이트 실패: {e}")
    else:
        print("✅ 업데이트가 없습니다. (대기 중)")

if __name__ == "__main__":
    import json
    run_alert_system()
