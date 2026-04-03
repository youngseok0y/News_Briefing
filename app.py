import streamlit as st
import os
from datetime import datetime
import utils
from config.settings import settings
from services import ui_service, sync_service, news_service, ai_service, storage_service

# 1. 초기화 및 설정 (Pure Presentation Initialization)
st.set_page_config(page_title="AI News Briefing Center", layout="wide", initial_sidebar_state="expanded")
ui_service.inject_custom_css()

# 💡 [V4.0 Optimization] Singletons for Unified Resources
@st.cache_resource(show_spinner="시스템 인프라 구축 중...")
def get_resource_layer():
    """Initializes the base singleton services (Infrastructure & UI)."""
    # 1. Infrastructure Layer
    storage_svc = storage_service.StorageService(settings.SERVICE_ACCOUNT_FILE)
    
    # 2. Business Layer
    # 💡 [V7.1] AIService now takes storage_svc for GDrive-backed persistent cache
    news_svc = news_service.NewsService(storage_svc)
    ai_svc = ai_service.AIService(settings.gemini_api_key, storage_svc)
    
    return storage_svc, news_svc, ai_svc

# Initialize core services once
storage_svc, news_svc, ai_svc = get_resource_layer()

# 2. Page Orchestration Logic
target_date = utils.get_latest_date()

# Session state defaults
DEFAULTS = {'data': [], 'analysis_cache': {}, 'nyt_text': "", 'nyt_translation': "", 'final_report': ""}
for k, v in DEFAULTS.items():
    if k not in st.session_state: st.session_state[k] = v

# 3. Sidebar: Branding & Control Center
logo_base64 = ui_service.get_base64_image("logo.png")
ui_service.render_sidebar_header(logo_base64)

# Real-time alert status (delegated to services)
alert_info = news_svc.get_latest_alert_status()

# Event Handlers
def handle_sync():
    sync_service.sync_daily_reports(target_date, storage_svc)

def handle_scrape():
    with st.spinner("🚀 최적화된 병렬 엔진 가동 중..."):
        st.session_state['data'] = news_svc.fetch_and_process_daily_news(target_date)
        st.toast("✅ 전체 뉴스 수집 완료!")

def handle_upload():
    success, msg = news_svc.upload_for_notebook_lm(st.session_state['data'], target_date)
    st.toast("✅ 드라이브 업로드 완료!" if success else f"❌ 에러: {msg}")

# Render Control Panel
ui_service.render_sidebar_controls(handle_sync, handle_scrape, handle_upload, alert_info)

# 4. Main View
st.title("🗞️ AI 데일리 지면 신문 서비스")
st.caption(f"🕒 KST: {datetime.now(utils.KST).strftime('%Y-%m-%d %H:%M:%S')} | Architecture V4.0 Professional")

tab1, tab2, tab3 = st.tabs(["📈 NYT Global", "🤖 Gemini Insight", "📑 Archive"])

with tab1:
    def handle_nyt():
        with st.spinner("NYT 기사 수집 및 고품격 번역 중..."):
            raw_email = utils.fetch_nyt_newsletter()
            
            # 💡 [V8.1] 번역 전 원본 추출물 GDrive에 선업로드
            storage_svc.upload_content_to_drive(raw_email, f"{target_date}_nyt_raw.txt")
            
            # 💡 [V7.0] Pass target_date for persistent disk cache (quota saver)
            translated = ai_svc.translate_nyt(raw_email, target_date)
            st.session_state['nyt_text'], st.session_state['nyt_translation'] = raw_email, translated
            storage_svc.save_local_json({"raw": raw_email, "translation": translated, "date": target_date}, f"{target_date}_nyt.json")
            storage_svc.upload_content_to_drive(translated, f"{target_date}_nyt_translated.txt")

    ui_service.render_nyt_viewer(st.session_state['nyt_translation'], handle_nyt)

with tab2:
    def handle_insight():
        if not st.session_state['data']:
            st.warning("먼저 데이터를 수집(Scrape)하거나 동기화(Sync)해 주세요.")
            return
        with st.spinner("🤖 Gemini 수석 전략 분석가가 리포트 생성 중..."):
            # 💡 [V7.0] Pass target_date for persistent disk cache (quota saver)
            report = ai_svc.generate_insight_report(st.session_state['data'], target_date)
            st.session_state['final_report'] = report
            storage_svc.save_local_json({"report": report, "date": target_date}, f"{target_date}_insight.json")

    ui_service.render_insight_report(st.session_state['final_report'], handle_insight)

with tab3:
    # 💡 [V7.0] Pre-load batch analysis cache to save quota (5 articles → 1 API call)
    if st.session_state['data'] and not st.session_state.get('batch_loaded'):
        batch_results = ai_svc.analyze_top_articles_batch(st.session_state['data'], target_date)
        st.session_state['analysis_cache'].update(batch_results)
        st.session_state['batch_loaded'] = True

    def handle_deep_dive(item):
        with st.spinner("상세 분석 리포트 생성 중..."):
            analysis = ai_svc.analyze_deep_dive(item)
            st.session_state['analysis_cache'][item.link] = analysis

    ui_service.render_news_grid(st.session_state['data'], handle_deep_dive, st.session_state['analysis_cache'])

ui_service.render_footer()
