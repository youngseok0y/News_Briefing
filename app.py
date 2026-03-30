import streamlit as st
import os
from datetime import datetime
import utils
from services import ui_service, sync_service, news_service, ai_service

# 1. 초기화 및 설정
st.set_page_config(page_title="AI News Briefing Center", layout="wide", initial_sidebar_state="expanded")
ui_service.inject_custom_css()

# 2. 보안 설정 및 서비스 초기화 (Session State 활용)
if 'initialized' not in st.session_state:
    try:
        # 서비스 인스턴스 생성
        st.session_state['news_svc'] = news_service.NewsService(st.secrets["DRIVE_FOLDER_ID"], 'credentials.json')
        st.session_state['ai_svc'] = ai_service.AIService(st.secrets["GEMINI_API_KEY"])
        st.session_state['initialized'] = True
    except Exception as e:
        st.error(f"⚠️ 시스템 초기화 에러: {e}")
        st.stop()

# 3. Session 데이터 기본값 설정
DEFAULTS = {'data': [], 'analysis_cache': {}, 'nyt_text': "", 'nyt_translation': "", 'final_report': ""}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

# 4. 사이드바 (컨트롤 & 실시간 상태)
logo_base64 = ui_service.get_base64_image("logo.png")
ui_service.render_sidebar_header(logo_base64)

target_date = utils.get_latest_date()
alert_info = st.session_state['news_svc'].get_latest_alert_status()

# 버튼 이벤트 핸들러 정의
def handle_sync():
    sync_service.sync_daily_reports(target_date, st.secrets["DRIVE_FOLDER_ID"], 'credentials.json')

def handle_scrape():
    with st.spinner("엔진 가동 중..."):
        st.session_state['data'] = st.session_state['news_svc'].fetch_and_process_daily_news(target_date)
        st.toast("✅ 수집 완료!")

def handle_upload():
    success, msg = st.session_state['news_svc'].upload_for_notebook_lm(st.session_state['data'], target_date)
    st.toast("✅ 업로드 성공!" if success else f"❌ 실패: {msg}")

ui_service.render_sidebar_controls(handle_sync, handle_scrape, handle_upload, alert_info)

# 5. 메인 대시보드
st.title("🗞️ AI 데일리 지면 신문 서비스")
st.caption(f"🕒 현재 시각 (KST): {datetime.now(utils.KST).strftime('%Y-%m-%d %H:%M:%S')} | 아키텍처 v3.0 (Enterprise)")

tab1, tab2, tab3 = st.tabs(["📈 NYT Global", "🤖 Gemini Insight", "📑 Archive"])

with tab1:
    def handle_nyt():
        with st.spinner("NYT 로드 중..."):
            raw_email = utils.fetch_nyt_newsletter()
            translated = st.session_state['ai_svc'].translate_nyt(raw_email)
            st.session_state['nyt_text'], st.session_state['nyt_translation'] = raw_email, translated
            utils.save_and_upload_json({"raw": raw_email, "translation": translated, "date": target_date}, f"{target_date}_nyt.json", st.secrets["DRIVE_FOLDER_ID"], 'credentials.json')

    ui_service.render_nyt_viewer(st.session_state['nyt_translation'], handle_nyt)

with tab2:
    def handle_insight():
        with st.spinner("인사이트 분석 중..."):
            report = st.session_state['ai_svc'].generate_insight_report(st.session_state['data'])
            st.session_state['final_report'] = report
            utils.save_and_upload_json({"report": report, "date": target_date}, f"{target_date}_insight.json", st.secrets["DRIVE_FOLDER_ID"], 'credentials.json')

    ui_service.render_insight_report(st.session_state['final_report'], handle_insight)

with tab3:
    def handle_deep_dive(item):
        analysis = st.session_state['ai_svc'].analyze_deep_dive(item)
        st.session_state['analysis_cache'][item.link] = analysis

    ui_service.render_news_grid(st.session_state['data'], handle_deep_dive, st.session_state['analysis_cache'])

ui_service.render_footer()
