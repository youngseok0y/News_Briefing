import streamlit as st
import base64
import os
from datetime import datetime
import pandas as pd
from typing import List, Optional, Callable
from models.news_item import NewsItem

def get_base64_image(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

def inject_custom_css():
    """Injects high-end premium CSS styles into the Streamlit app."""
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@500;700&display=swap');

        :root {{
            --primary: #58E1FF;
            --accent: #FFD700;
            --bg-color: #0A0F1E;
            --card-bg: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
            --text-main: #E2E8F0;
            --text-dim: #94A3B8;
        }}

        .main .block-container {{ padding: 2rem 4rem; font-family: 'Inter', sans-serif; }}
        h1, h2, h3 {{ font-family: 'Outfit', sans-serif !important; color: #FFFFFF; }}

        /* Glassmorphism Cards */
        .premium-card {{
            background: var(--card-bg);
            backdrop-filter: blur(15px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            transition: transform 0.3s ease;
        }}

        .news-card {{
            background: var(--card-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 1.2rem;
            height: 180px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.25s ease;
        }}
        .news-card:hover {{ transform: translateY(-3px); border-color: var(--primary); }}

        .news-tag {{
            display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px;
            font-size: 0.7rem; font-weight: 700; color: var(--primary);
            background: rgba(88, 225, 255, 0.1); border: 1px solid var(--primary);
            margin-bottom: 0.5rem; text-transform: uppercase;
        }}
        .important-badge {{ color: var(--accent); border-color: var(--accent); background: rgba(255, 215, 0, 0.1); }}

        .news-title {{ font-weight: 600; font-size: 0.95rem; line-height: 1.4; color: #FFF; }}
        .news-meta {{ font-size: 0.7rem; color: var(--text-dim); display: flex; justify-content: space-between; }}

        /* Insights Visualization */
        .insight-container {{
            background: linear-gradient(135deg, rgba(88, 225, 255, 0.05) 0%, rgba(15, 23, 42, 0.5) 100%);
            border-left: 4px solid var(--primary);
            padding: 2rem; border-radius: 0 16px 16px 0;
            line-height: 1.8;
        }}

        /* Sidebar Styling */
        [data-testid="stSidebar"] {{ background-color: #060914 !important; border-right: 1px solid var(--glass-border); }}
        .logo-container {{ text-align: center; padding: 1.5rem 0; }}
    </style>
    """, unsafe_allow_html=True)

def render_sidebar_header(logo_base64: Optional[str]):
    """Renders the top branding part of sidebar."""
    if logo_base64:
        st.sidebar.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_base64}" width="140"></div>', unsafe_allow_html=True)
    else:
        st.sidebar.title("🗞️ AI News Briefing")
    st.sidebar.header("🕹️ 컨트롤 센터")

def render_sidebar_controls(
    on_sync: Callable, 
    on_scrape: Callable, 
    on_upload: Callable, 
    alert_info: Optional[dict]
):
    """Renders the full control panel in sidebar."""
    with st.sidebar.expander("🛠️ 데이터 관리", expanded=False):
        if st.button("☁️ 리포트 동기화", key="sync_btn"): on_sync()
        if st.button("🔄 수집 엔진 가동", key="scrape_btn"): on_scrape()
        st.markdown("---")
        if st.button("📤 드라이브 업로드", key="upload_btn"): on_upload()

    st.sidebar.markdown("---")
    with st.sidebar.expander("🔔 속보 알림 상태", expanded=True):
        if alert_info:
            st.success("📟 시스템 정상 작동 중")
            st.caption(f"최근 전송: {alert_info.get('updated_at', 'N/A')}")
            st.markdown(f"**속보:** {alert_info.get('last_title', '내용 없음')}")
        else:
            st.warning("⚠️ 알림 상태 확인 불가")
            st.info("드라이브 인증 설정을 확인해 주세요.")

def render_nyt_viewer(translated_text: str, on_translate: Callable):
    """Renders the NYT Global tab content."""
    st.subheader("🇺🇸 New York Times: The Morning")
    if st.button("📩 최신 뉴스레터 번역 실행", key="nyt_btn"):
        on_translate()
    
    if translated_text:
        st.markdown(f'<div class="premium-card">{translated_text}</div>', unsafe_allow_html=True)
    else:
        st.info("번역 버튼을 누르면 오늘의 NYT 브리핑을 가져옵니다.")

def render_insight_report(report_text: str, on_generate: Callable):
    """Renders the Gemini Insight tab content."""
    st.subheader("🤖 Gemini 종합 이슈 인사이트")
    if st.button("🚀 종합 전략 분석 리포트 생성", key="insight_btn"):
        on_generate()

    if report_text:
        st.markdown(f'<div class="insight-container">{report_text}</div>', unsafe_allow_html=True)
    else:
        st.info("데이터를 수집한 후 분석 리포트 생성 버튼을 눌러주세요.")

def render_news_grid(news_items: List[NewsItem], on_deep_dive: Callable, analysis_cache: dict):
    """Renders the archive grid with individual article cards."""
    if not news_items:
        st.info("아카이브에 저장된 기사가 없습니다.")
        return

    # Press filter
    df = pd.DataFrame([item.to_dict() for item in news_items])
    press_list = df['press'].unique().tolist()
    selected_press = st.multiselect("신문사 필터링", press_list, default=press_list)
    
    # Filter and Display
    filtered_items = [item for item in news_items if item.press in selected_press]
    
    cols = st.columns(3)
    for idx, item in enumerate(filtered_items):
        with cols[idx % 3]:
            # Card UI
            badge_class = "news-tag important-badge" if item.importance else "news-tag"
            st.markdown(f"""
            <div class="news-card">
                <span class="{badge_class}">{item.press}</span>
                <div class="news-title"><a href="{item.link}" target="_blank">{item.title}</a></div>
                <div class="news-meta">
                    <span>📍 {item.page}</span>
                    <span>📊 등급: {item.grade}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Deep Dive Logic
            if st.button("심층 분석", key=f"dive_{item.link}"):
                if item.link not in analysis_cache:
                    on_deep_dive(item)
                
                analysis_result = analysis_cache.get(item.link)
                if analysis_result:
                    st.markdown(f'<div style="background: rgba(88,225,255,0.05); padding: 1rem; border-radius: 10px; border: 1px dashed var(--primary); margin-top: 5px;">{analysis_result}</div>', unsafe_allow_html=True)

def render_footer():
    """Renders the premium footer branding."""
    st.markdown("---")
    st.markdown(f"""
        <div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; padding: 1rem;">
            ⚡ Powered by <strong>AI & Drive Cloud Insight</strong><br>
            Produced for High-End Intelligence Briefing | © 2026 AI News Aggregator
        </div>
    """, unsafe_allow_html=True)
