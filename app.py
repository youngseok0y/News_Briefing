import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import json
from datetime import datetime, timezone, timedelta
import time
from scraper import NewsScraper
from utils import get_latest_date, hash_text, trim_text, save_to_json, save_to_txt, upload_to_drive, fetch_nyt_newsletter, list_drive_files, download_drive_file, KST

# ==========================================
# 1. 설정 (사용자 정보 입력)
# ==========================================
# 실제 서비스 시 Streamlit Secrets이나 환경변수 사용 권장
# Streamlit Secrets 우선 사용 (Cloud 배포 시 안전함)
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyDe4P6W9wuYo2OFvsOhW6Idth_3_-20Qc0")
DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "1VZ2GdtdoXCZFnhuDlYqj2DUoMKQZrlCF")
SERVICE_ACCOUNT_FILE = 'credentials.json' 

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Gemini 초기화 에러: {e}")

# ==========================================
# 2. 상태 초기화 및 공통 UI 스타일링
# ==========================================
st.set_page_config(page_title="AI 신문 브리핑 센터", layout="wide", initial_sidebar_state="expanded")

# 고정 상단 네비게이션 탭용 커스텀 CSS
st.markdown("""
<style>
    /* 상단 고정 네비게이션(Tab) 메뉴 디자인 최후 시도 (role=tablist) */
    div[role="tablist"] {
        position: -webkit-sticky !important;
        position: sticky !important;
        top: 2rem !important; 
        z-index: 99999 !important;
        background-color: var(--background-color) !important;
        padding-top: 10px;
        padding-bottom: 5px;
        border-bottom: 2px solid var(--secondary-background-color) !important;
    }
    .main .block-container {
        overflow: visible !important;
    }
</style>
""", unsafe_allow_html=True)

if 'data' not in st.session_state:
    st.session_state['data'] = []
if 'analysis_cache' not in st.session_state:
    st.session_state['analysis_cache'] = {}
if 'scraper_engine' not in st.session_state:
    st.session_state['scraper_engine'] = NewsScraper()
if 'nyt_text' not in st.session_state:
    st.session_state['nyt_text'] = ""
if 'nyt_translation' not in st.session_state:
    st.session_state['nyt_translation'] = ""
if 'nyt_summary' not in st.session_state:
    st.session_state['nyt_summary'] = ""

st.title("🗞️ AI 데일리 지면 신문 서비스 (최적화 버전)")
# 현재 KST 시간 표시
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"🕒 현재 동기화 시간 (KST): {now_kst}")

# ==========================================
# 3. 사이드바 컨트롤 (접었다 펼 수 있는 기능 제공)
# ==========================================
st.sidebar.header("실행 컨트롤")

target_date = get_latest_date()
save_path = os.path.join("daily", f"{target_date}_articles.json")

# 사이드바 내부에서 한 번 더 접을 수 있도록 expander 위젯 사용
with st.sidebar.expander("🛠️ 데이터 수집 및 자동화 결과", expanded=True):
    # --- 추가: 클라우드 자동화 결과 불러오기 ---
    if st.button("☁️ 최신 자동화 리포트 불러오기 (Drive)"):
        with st.spinner("구글 드라이브에서 최신 파일을 찾는 중..."):
            files = list_drive_files(DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
            if not files:
                st.error("드라이브에 저장된 파일이 없거나 접근할 수 없습니다.")
            else:
                # 가장 최신 JSON(데이터)과 TXT(리포트) 찾기
                latest_json = next((f for f in files if f['name'].endswith('_articles.json')), None)
                latest_txt = next((f for f in files if f['name'].endswith('_summary.txt')), None)
                
                if latest_json:
                    json_content = download_drive_file(latest_json['id'], SERVICE_ACCOUNT_FILE)
                    if json_content:
                        st.session_state['data'] = json.loads(json_content)
                        st.session_state['last_loaded'] = latest_json['name']
                        st.toast(f"✅ 데이터 로드 완료: {latest_json['name']}", icon="📥")
                        
                if latest_txt:
                    txt_report = download_drive_file(latest_txt['id'], SERVICE_ACCOUNT_FILE)
                    if txt_report:
                        # 분석 리포트 캐시 등에 저장하거나 바로 표시 가능 (여기서는 우선 성공 알림만)
                        st.toast(f"✅ 요약 리포트 확인 완료: {latest_txt['name']}", icon="📄")
    
    st.markdown("---")
    
    if st.button("🔄 오늘자 신문 데이터 로컬 로드/스크랩"):
        if os.path.exists(save_path):
            with open(save_path, 'r', encoding='utf-8') as f:
                st.session_state['data'] = json.load(f)
            st.toast(f"✅ 로컬 데이터({target_date}) 로드 완료!", icon="✅")
        else:
            with st.spinner("데이터(목록)를 가져오는 중..."):
                engine = st.session_state['scraper_engine']
                raw_data = engine.fetch_metadata()
                
                df = pd.DataFrame(raw_data)
                if not df.empty:
                    df = df.drop_duplicates(subset=["링크"])
                    unique_data = df.to_dict('records')
                    
                    st.info(f"총 {len(unique_data)}개의 기사 분석 중... (수 분 소요)")
                    progress_bar = st.progress(0)
                    
                    for idx, item in enumerate(unique_data):
                        body, date = engine.get_article_details(item['링크'])
                        item['기사내용'] = body
                        item['등록일시'] = date
                        progress_bar.progress((idx + 1) / len(unique_data))
                        
                    st.session_state['data'] = unique_data
                    save_to_json(st.session_state['data'], save_path)
                    st.toast(f"✅ 데이터 수집 완료 ({len(unique_data)}건)", icon="🎉")
                else:
                    st.toast("⚠️ 수집된 기사가 없습니다.", icon="⚠️")

    if st.button("⚠️ 강제 재수집(업데이트)"):
        with st.spinner("기존 데이터를 무시하고 새로 수집합니다..."):
            engine = st.session_state['scraper_engine']
            raw_data = engine.fetch_metadata()
            df = pd.DataFrame(raw_data)
            if not df.empty:
                df = df.drop_duplicates(subset=["링크"])
                unique_data = df.to_dict('records')
                st.info(f"총 {len(unique_data)}개의 기사 페이지 재수집 중...")
                progress_bar = st.progress(0)
                for idx, item in enumerate(unique_data):
                    body, date = engine.get_article_details(item['링크'])
                    item['기사내용'] = body
                    item['등록일시'] = date
                    progress_bar.progress((idx + 1) / len(unique_data))
                st.session_state['data'] = unique_data
                save_to_json(st.session_state['data'], save_path)
                st.toast(f"✅ 강제 재수집 완료 ({len(unique_data)}건)", icon="🔄")
            else:
                st.toast("⚠️ 수집된 기사가 없습니다.", icon="⚠️")

    st.markdown("---")

    if st.button("📤 구글 드라이브 업로드 (NotebookLM)"):
        if st.session_state['data']:
            with st.spinner("드라이브에 업로드 중..."):
                txt_content = f"오늘의 전체 지면 기사 원문 ({get_latest_date()})\n" + "="*50 + "\n\n"
                for d in st.session_state['data']:
                    grade = d.get('중요도등급', '하')
                    txt_content += f"[{grade}] [{d['신문사']}-{d['지면']}] {d['제목']}\n"
                    txt_content += f"등록일시: {d.get('등록일시', '')}\n"
                    txt_content += f"링크: {d['링크']}\n\n"
                    txt_content += f"{d.get('기사내용', '본문 없음')}\n\n"
                    txt_content += "-"*50 + "\n\n"
                
                # 텍스트 파일 로컬 저장 기능
                txt_path = os.path.join("daily", f"{target_date}_summary.txt")
                save_to_txt(txt_content, txt_path)
                
                # 드라이브 업로드
                fid = upload_to_drive(txt_content, os.path.basename(txt_path), DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
                if fid and "error" not in str(fid).lower():
                    st.toast(f"✅ 드라이브 업로드 완료!", icon="☁️")
                else:
                    st.toast(f"❌ 업로드 실패: {fid}", icon="❌")
        else:
            st.toast("⚠️ 먼저 스크랩을 진행해주세요.", icon="⚠️")

# ==========================================
# 4. 메인 탭 구성
# ==========================================
# ==========================================
# 4. 메인 탭 구성
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "🇺🇸 1면: NYT 아침 뉴스레터", 
    "📊 2면: AI 종합 리포트", 
    "📑 3면: 신문사별 상세 & 개별분석"
])

with tab1:
    st.header("🇺🇸 New York Times: The Morning")
    st.info("오늘 아침 NYT 뉴스레터를 가져와서 전체 번역 및 요약을 진행합니다.")
    
    col1, col2 = st.columns([1, 1])
    if col1.button("📩 이메일 불러오기 및 전문 번역"):
        with st.spinner("지메일 로드 및 Gemini 번역 중..."):
            raw_email = fetch_nyt_newsletter()
            if "Error" in raw_email:
                st.error(raw_email)
            else:
                st.session_state['nyt_text'] = raw_email
                # 이미지 태그 보존을 명시적으로 요청하는 프롬프트
                prompt = (
                    "너는 뉴욕타임즈 전문 번역가야. 다음은 오늘자 NYT 'The Morning' 뉴스레터의 본문(HTML/마크다운 혼합)이야.\n"
                    "지침:\n"
                    "1. 모든 이미지 태그(예: <img ...>)와 구조적 마크다운은 절대 수정하지 말고 제자리에 둬.\n"
                    "2. 텍스트 내용만 한국어로 자연스럽고 지적으로 번역해.\n"
                    "3. 인포그래픽이나 복잡한 데이터 설명은 독자가 이해하기 쉽게 풀어서 번역해.\n\n"
                    f"본문:\n{raw_email}"
                )
                try:
                    res = model.generate_content(prompt)
                    st.session_state['nyt_translation'] = res.text
                    st.toast("✅ 시각 자료를 포함한 번역이 완료되었습니다!", icon="🖼️")
                except Exception as e:
                    st.error(f"번역 실패: {e}")
                    
    if st.session_state['nyt_translation']:
        st.markdown("---")
        st.subheader("📝 뉴스레터 시각화 번역본")
        # 이미지 렌더링을 위해 unsafe_allow_html=True 설정
        st.markdown(st.session_state['nyt_translation'], unsafe_allow_html=True)
        
        # 전문 번역이 있을 때만 요약 버튼 표시
        if st.button("💡 핵심 3줄 요약 보기"):
            with st.spinner("핵심 요약 생성 중..."):
                prompt = f"다음 뉴스레터 번역본을 바탕으로, 바쁜 직장인을 위해 가장 중요한 핵심 포인트 3가지를 불렛포인트 형식으로 요약해줘:\n\n{st.session_state['nyt_translation']}"
                try:
                    res = model.generate_content(prompt)
                    st.session_state['nyt_summary'] = res.text
                except Exception as e:
                    st.error(f"요약 실패: {e}")
                    
        if st.session_state['nyt_summary']:
            st.success("### 📌 핵심 요약 (3-Lines Summary)")
            st.markdown(st.session_state['nyt_summary'])

with tab2:
    st.header("🤖 Gemini 종합 이슈 분석")
    st.info("중요도가 높은 기사들만 선별하여 2단계 분석 파이프라인(본문 요약 -> 종합 분석)을 실행해 토큰을 절약합니다.")
    
    if st.button("🚀 종합 분석 실행"):
        if not st.session_state['data']:
            st.warning("먼저 좌측 사이드바에서 '오늘자 신문 데이터 로드/스크랩'을 눌러주세요.")
        else:
            df_full = pd.DataFrame(st.session_state['data'])
            # 각 신문사별로 중요도 점수가 가장 높은 상위 3개씩 추출 (균형 있는 분석을 위함, 총 최대 18개)
            imp_news_df = df_full[df_full['중요'] == True].sort_values(by="중요도점수", ascending=False)
            imp_news = imp_news_df.groupby('신문사').head(3).to_dict('records')
            
            with st.spinner(f"총 {len(imp_news)}개의 주요 기사를 일괄 분석 중입니다..."):
                engine = st.session_state['scraper_engine']
                
                # 기사 본문들 병합 (하나의 거대한 프롬프트 생성용)
                full_context = ""
                for n in imp_news:
                    body = n.get('기사내용', '')
                    trimmed_body = trim_text(body, max_len=1500)
                    full_context += f"[{n['신문사']}] 지역/지면: {n['지면']}\n제목: {n['제목']}\n내용: {trimmed_body}\n\n"
            
            with st.spinner("AI가 종합 논조 분석 리포트를 작성 중입니다..."):
                prompt = f"다음은 오늘 아침 주요 6개 신문의 1면 및 사설/칼럼 원문들입니다. 전체적인 이슈 흐름과 매체별 논조(시각) 차이를 상세히 분석하여 1500자 내외의 종합 보고서를 마크다운으로 깔끔하게 작성해줘:\n\n{full_context}"
                try:
                    res = model.generate_content(prompt)
                    final_report = res.text
                    
                    st.markdown("### 📝 데일리 신문 종합 브리핑")
                    st.markdown(final_report)
                    
                    # 브리핑 텍스트 로컬 파일 내용에 추가
                    target_date = get_latest_date()
                    txt_path = os.path.join("daily", f"{target_date}_summary.txt")
                    if os.path.exists(txt_path):
                        with open(txt_path, 'a', encoding='utf-8') as f:
                            f.write("\n\n" + "="*50 + "\n[종합 분석 리포트]\n\n" + final_report)
                except Exception as e:
                    st.error("종합 분석 실패: API 설정이나 할당량을 확인하세요.")
                    st.error(str(e))

with tab3:
    st.header("📰 상세 기사 및 개별 AI 분석")
    st.info("개별 기사 분석 시에만 본문을 실시간으로 크롤링하여 불필요한 트래픽 및 딜레이를 방지합니다.")
    
    df = pd.DataFrame(st.session_state['data'])
    if not df.empty:
        for press in df['신문사'].unique():
            with st.expander(f"📍 {press} (전체 기사 목록)"):
                items = df[(df['신문사'] == press)]
                for _, row in items.iterrows():
                    c1, c2 = st.columns([5, 1])
                    if row['중요']:
                        c1.write(f"⭐ **[{row['지면']}]** [{row['제목']}]({row['링크']})")
                    else:
                        c1.write(f"[{row['지면']}] [{row['제목']}]({row['링크']})")
                    
                    # session_state 키가 고유해야 하므로 링크 활용
                    if c2.button("개별 분석", key=row['링크']):
                        with st.spinner("본문 분석 중..."):
                            article_body = row.get('기사내용', '')
                            trimmed_body = trim_text(article_body)
                            body_hash = hash_text(trimmed_body)
                            
                            if body_hash in st.session_state['analysis_cache']:
                                st.info(st.session_state['analysis_cache'][body_hash])
                            else:
                                try:
                                    res = model.generate_content(f"이 기사의 핵심 요약과 짤막한 논평을 작성해줘:\n\n{trimmed_body}")
                                    st.session_state['analysis_cache'][body_hash] = res.text
                                    st.info(res.text)
                                except Exception as e:
                                    st.error("API 요청 실패")
