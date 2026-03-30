import os
import json
import pandas as pd
import google.generativeai as genai
from datetime import datetime
from scraper import NewsScraper
from utils import get_latest_date, trim_text, save_to_json, save_to_txt, upload_to_drive, fetch_nyt_newsletter

# ==========================================
# 1. 설정 (환경 변수 우선 사용)
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDe4P6W9wuYo2OFvsOhW6Idth_3_-20Qc0")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID", "1VZ2GdtdoXCZFnhuDlYqj2DUoMKQZrlCF")
SERVICE_ACCOUNT_FILE = 'credentials.json' 

def run_automation():
    print(f"🚀 자동화 작업 시작: {datetime.now()}")
    
    # 1. Gemini 초기화
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        print(f"❌ Gemini 초기화 에러: {e}")
        return

    # 2. 뉴스 스크랩 (지면 신문)
    print("📡 네이버 뉴스 지면 데이터 수집 중...")
    scraper = NewsScraper()
    raw_data = scraper.fetch_metadata()
    
    df = pd.DataFrame(raw_data)
    if df.empty:
        print("⚠️ 수집된 지면 기사가 없습니다.")
        unique_data = []
    else:
        df = df.drop_duplicates(subset=["링크"])
        unique_data = df.to_dict('records')
        print(f"✅ 총 {len(unique_data)}건의 기사 메타데이터 확보.")
        
        # 상세 내용 크롤링
        for idx, item in enumerate(unique_data):
            body, date = scraper.get_article_details(item['링크'])
            item['기사내용'] = body
            item['등록일시'] = date
            if (idx + 1) % 10 == 0:
                print(f"   - 진행률: {idx + 1}/{len(unique_data)}")
    
    # 3. 로컬 저장 (JSON)
    target_date = get_latest_date()
    save_path = os.path.join("daily", f"{target_date}_articles.json")
    save_to_json(unique_data, save_path)
    print(f"💾 JSON 저장 완료: {save_path}")

    # 4. 종합 분석 리포트 생성 (Gemini)
    final_report = ""
    if unique_data:
        print("🤖 Gemini 종합 이슈 분석 중...")
        df_full = pd.DataFrame(unique_data)
        imp_news_df = df_full[df_full['중요'] == True].sort_values(by="중요도점수", ascending=False)
        imp_news = imp_news_df.groupby('신문사').head(3).to_dict('records')
        
        full_context = ""
        for n in imp_news:
            body = n.get('기사내용', '')
            trimmed_body = trim_text(body, max_len=1500)
            full_context += f"[{n['신문사']}] {n['지면']} | {n['제목']}\n내용: {trimmed_body}\n\n"
            
        prompt = f"다음은 오늘 아침 주요 신문들의 주요 기사 원문이야. 전체적인 이슈 흐름과 매체별 논조 차이를 분석하여 종합 보고서를 마크다운으로 작성해줘:\n\n{full_context}"
        try:
            res = model.generate_content(prompt)
            final_report = res.text
            print("✅ 종합 분석 완료.")
        except Exception as e:
            print(f"❌ 종합 분석 실패: {e}")

    # 5. NYT 뉴스레터 연동
    print("🇺🇸 NYT 뉴스레터 가져오는 중...")
    nyt_content = fetch_nyt_newsletter()
    nyt_report = ""
    if nyt_content and "Error" not in nyt_content:
        prompt = f"다음은 오늘자 NYT 뉴스레터야. 한국어로 전문 번역하고 이미지 태그는 유지해줘:\n\n{nyt_content}"
        try:
            res = model.generate_content(prompt)
            nyt_report = f"\n\n[NYT News Letter]\n\n{res.text}"
            print("✅ NYT 번역 완료.")
        except Exception as e:
            nyt_report = f"\n\n⚠️ NYT 번역 실패 (Gemini API 오류): {e}"
            print(f"❌ NYT 번역 실패: {e}")
    else:
        # 뉴스레터 수집 실패 시 안내 문구 추가
        nyt_report = f"\n\n⚠️ NYT 미수집: {nyt_content}"
        print(f"⚠️ NYT 미수집: {nyt_content}")

    # 6. 구글 드라이브 업로드용 텍스트 병합
    print("📤 구글 드라이브 업로드 준비 중...")
    txt_content = f"오늘의 전체 지면 기사 ({target_date})\n" + "="*50 + "\n\n"
    if final_report:
        txt_content += "[종합 분석 리포트]\n\n" + final_report + "\n\n" + "="*50 + "\n\n"
    
    if nyt_report:
        txt_content += nyt_report + "\n\n" + "="*50 + "\n\n"

    for d in unique_data:
        grade = d.get('중요도등급', '하')
        txt_content += f"[{grade}] [{d['신문사']}-{d['지면']}] {d['제목']}\n"
        txt_content += f"등록일시: {d.get('등록일시', '')}\n링크: {d['링크']}\n\n{d.get('기사내용', '')}\n\n"
        txt_content += "-"*50 + "\n\n"
        
    txt_path = os.path.join("daily", f"{target_date}_summary.txt")
    save_to_txt(txt_content, txt_path)
    
    # 드라이브 업로드
    fid = upload_to_drive(txt_content, os.path.basename(txt_path), DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
    if fid and "error" not in str(fid).lower():
        print(f"🎉 드라이브 업로드 성공! (ID: {fid})")
    else:
        print(f"❌ 업로드 실패: {fid}")

if __name__ == "__main__":
    run_automation()
