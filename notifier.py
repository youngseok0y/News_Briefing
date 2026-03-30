import feedparser
import requests
import os
import json
import utils
from datetime import datetime

def run_alert_system():
    # 1. 설정값 로드 (GitHub Secrets/Env)
    DISCORD_WEBHOOK = os.environ.get('DISCORD_WEBHOOK', '').strip()
    DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID', '').strip()
    # GitHub Actions에서는 GCP_SERVICE_ACCOUNT 환경변수를 사용하며, 로컬에서는 파일명을 참조함
    SERVICE_ACCOUNT_FILE = 'credentials.json' 
    STATE_FILE = "alert_state.json"

    if not DISCORD_WEBHOOK or not DRIVE_FOLDER_ID:
        print(f"❌ 필수 환경변수가 누락되었습니다. (WEBHOOK: {'OK' if DISCORD_WEBHOOK else 'MISSING'}, DRIVE_ID: {'OK' if DRIVE_FOLDER_ID else 'MISSING'})")
        return

    # 2. 기존 상태 로드 (GDrive에서 마지막 전송 항목 확인)
    print("🔍 상태 확인 (GCP_SERVICE_ACCOUNT 환경변수 또는 credentials.json) 중...")
    last_state = utils.find_and_download_json(STATE_FILE, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
    last_title = last_state.get('last_title', '') if last_state else ''

    # 3. 뉴스 수집 (RSS 우선 -> 네이버 크롤링 백업)
    print("📡 뉴스 데이터 수집 중...")
    current_title, current_link = None, None
    
    # 전략 A: RSS 피드 확인
    try:
        feed = feedparser.parse("https://www.yonhapnews.co.kr/rss/news.xml")
        if feed.entries:
            current_title = feed.entries[0].title
            current_link = feed.entries[0].link
            print("✅ RSS 피드에서 뉴스 수집 성공")
    except Exception as e:
        print(f"⚠️ RSS 수집 실패: {e}")

    # 전략 B: 네이버 연합뉴스 속보 페이지 크롤링 (RSS 실패 혹은 보조 확인)
    if not current_title:
        print("🔍 네이버 연합뉴스 속보 페이지(Flash) 크롤링 시도...")
        from bs4 import BeautifulSoup
        try:
            # 연합뉴스 전용 속보 페이지는 구조가 일반 뉴스 리스트와 다를 수 있음
            url = "https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&sid1=001&sid2=140&oid=001&isYeonhapFlash=Y"
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            
            # 연합뉴스 전용 페이지의 실제 구조 타겟팅
            selectors = [
                "div.list_body ul li dl dt:not(.photo) a", # 네이버 속보 리스트의 표준 구조
                "ul.type06_headline li dl dt:not(.photo) a",
                "td.content div.list_body ul li a"
            ]
            
            for selector in selectors:
                first_news = soup.select_one(selector)
                if first_news:
                    temp_title = first_news.get_text(strip=True)
                    if temp_title:
                        current_title = temp_title
                        current_link = first_news["href"]
                        if not current_link.startswith("http"):
                            current_link = "https://news.naver.com" + current_link
                        break
                    
            if current_title:
                print(f"✅ 네이버 크롤링으로 뉴스 수집 성공: {current_title[:30]}...")
            else:
                print("❌ 네이버 페이지에서 기사 제목을 찾을 수 없습니다. (HTML 구조 미매치)")
                # 디버깅을 위한 HTML 일부 출력 (Actions 로그 확인용)
                print(f"DEBUG: HTML body snippet: {res.text[:500]}...")
        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {e}")

    if not current_title:
        print("⚠️ 최종 수집된 기사가 없습니다. 워크플로우를 종료합니다.")
        return

    # 4. 중복 체크 및 알림 발송
    print(f"📊 비교 분석: [이전] '{last_title}' vs [현재] '{current_title}'")
    
    if current_title != last_title:
        print(f"🚨 새로운 기사 발견! 디스코드 알림을 전송합니다.")
        
        # 디스코드 메시지 구성
        payload = {
            "content": f"🚨 **[연합뉴스 속보]**\n\n**{current_title}**\n\n🔗 [기사 읽기]({current_link})",
            "username": "AI News Notifier",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/3208/3208035.png"
        }
        
        response = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        
        # 디스코드 응답 상태 로그 추가
        print(f"📡 디스코드 응답 상태: {response.status_code}")
        if response.text:
            print(f"📡 디스코드 응답 본문: {response.text}")
        
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
