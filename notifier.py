import requests
import os
import utils
from datetime import datetime
from bs4 import BeautifulSoup

def run_alert_system():
    # 1. 환경 변수 로드
    DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK', '').strip()
    DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID', '').strip()
    SERVICE_ACCOUNT_FILE = 'credentials.json' # GitHub Actions에서는 Env에서 로드됨
    STATE_FILE = "alert_state.json"

    if not DISCORD_WEBHOOK or not DRIVE_FOLDER_ID:
        print("❌ 필수 환경변수(DISCORD_WEBHOOK, DRIVE_FOLDER_ID)가 없습니다.")
        return

    # 2. 이전 상태 로드 (GDrive)
    print("📂 이전 상태 파일을 드라이브에서 가져오는 중...")
    last_state = utils.find_and_download_json(STATE_FILE, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
    last_title = last_state.get('last_title', '') if last_state else ''
    print(f"📌 이전 마지막 기사: {last_title}")

    # 3. 최신 뉴스 수집 (네이버 연합뉴스 속보 페이지)
    current_title = None
    current_link = None

    print("🔍 네이버 연합뉴스 속보 페이지(Flash) 크롤링 시도...")
    try:
        # 연합뉴스 전용 속보 페이지 (헤드라인이 포함된 chronological list)
        url = "https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&sid1=001&sid2=140&oid=001&isYeonhapFlash=Y"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 브라우저 분석 결과 가장 확실한 선택자 리스트
        selectors = [
            ".list_body ul li dl dt:not(.photo) a",
            "#main_content ul.type06_headline li dl dt:not(.photo) a",
            "#main_content div.list_body ul li a"
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            for item in items:
                temp_title = item.get_text(strip=True)
                temp_link = item.get("href", "")
                
                # 🔗 필터링 완화: URL 패턴 대신 영역 기반 수집을 신뢰함
                # (이전의 ntype=RANKING 필터링이 실제 최신 속보인 1009번 등을 막고 있었음)
                if temp_title and len(temp_title) > 5:
                    current_title = temp_title
                    current_link = temp_link if temp_link.startswith("http") else "https://news.naver.com" + temp_link
                    break
            
            if current_title:
                break
                
        if current_title:
            print(f"✅ 최신 속보 수집 완료: {current_title[:40]}...")
        else:
            print("❌ 네이버 페이지에서 적절한 속보 리스트를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 크롤링 중 에러 발생: {e}")

    if not current_title:
        print("⚠️ 최종 수집된 기사가 없습니다. 워크플로우를 종료합니다.")
        return

    # 4. 중복 체크 및 알림 발송
    print(f"📊 비교 분석: [이전] '{last_title[:20]}...' vs [현재] '{current_title[:20]}...'")
    
    if current_title != last_title:
        print(f"🚨 새로운 기사 발견! 알림을 전송합니다.")
        
        # 디스코드 메시지 구성
        payload = {
            "content": f"🚨 **[연합뉴스 속보]**\n\n**{current_title}**\n\n🔗 [기사 읽기]({current_link})",
            "username": "AI News Notifier",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3208/3208035.png"
        }
        
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        
        if response.status_code in [200, 204]:
            print("✅ 디스코드 알림 발송 완료!")
            
            # 5. 최신 상태 업데이트 (GDrive)
            new_state = {
                "last_title": current_title,
                "link": current_link,
                "updated_at": datetime.now(utils.KST).strftime("%Y-%m-%d %H:%M:%S")
            }
            utils.save_and_upload_json(new_state, STATE_FILE, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
            print("💾 GDrive 상태 업데이트(alert_state.json)를 성공적으로 완료했습니다.")
        else:
            print(f"❌ 알림 발송 실패: {response.status_code}")
    else:
        print("✅ 업데이트된 새로운 뉴스가 없습니다.")

if __name__ == "__main__":
    run_alert_system()
