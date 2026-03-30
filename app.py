import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
import json
from datetime import datetime, timezone, timedelta
import time
import base64
from scraper import NewsScraper
from utils import get_latest_date, hash_text, trim_text, save_to_json, save_to_txt, upload_to_drive, fetch_nyt_newsletter, list_drive_files, download_drive_file, KST

# ==========================================
# 1. 설정 (사용자 정보 입력)
# ==========================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "AIzaSyDe4P6W9wuYo2OFvsOhW6Idth_3_-20Qc0")
DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", "1VZ2GdtdoXCZFnhuDlYqj2DUoMKQZrlCF")
SERVICE_ACCOUNT_FILE = 'credentials.json' 

try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Gemini 초기화 에러: {e}")

# ==========================================
# 2. 상태 초기화 및 프리미엄 UI 스타일링 (Sleek Dark)
# ==========================================
st.set_page_config(page_title="AI News Briefing Center", layout="wide", initial_sidebar_state="expanded")

def get_base64_image(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

logo_base64 = get_base64_image("logo.png")

# 고해상도 프리미엄 CSS (Sleek Dark & Glassmorphism)
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@500;700&display=swap');

    :root {{
        --primary: #58E1FF;
        --accent: #FFD700;
        --bg-color: #0A0F1E;
        --card-bg: rgba(255, 255, 255, 0.05);
        --text-main: #E2E8F0;
        --text-dim: #94A3B8;
        --glass-border: rgba(255, 255, 255, 0.1);
    }}

    /* Global Styles */
    .main .block-container {{
        padding: 3rem 5rem;
        font-family: 'Inter', sans-serif;
        background-color: var(--bg-color);
        color: var(--text-main);
    }}

    h1, h2, h3 {{
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }}

    /* News Card Design - Fixed Height & Flexbox */
    .news-card {{
        background: var(--card-bg);
        backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 0px; /* 버튼과 밀착시키기 위해 0으로 조정 */
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        height: 200px; /* 고정 높이 부여 */
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        overflow: hidden;
        border-bottom-left-radius: 0;
        border-bottom-right-radius: 0;
    }}

    .news-card:hover {{
        transform: translateY(-5px);
        border-color: var(--primary);
        box-shadow: 0 10px 30px rgba(88, 225, 255, 0.1);
    }}

    .news-tag {{
        display: inline-block;
        background: rgba(88, 225, 255, 0.1);
        color: var(--primary);
        padding: 0.2rem 0.6rem;
        border-radius: 50px;
        font-size: 0.7rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        border: 1px solid rgba(88, 225, 255, 0.3);
    }}

    .important-badge {{
        background: rgba(255, 215, 0, 0.1);
        color: var(--accent);
        border: 1px solid rgba(255, 215, 0, 0.4);
    }}

    .news-title {{
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.4;
        margin-bottom: 0.8rem;
        color: #FFFFFF;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
    }}

    .news-title a {{
        text-decoration: none !important;
        color: inherit !important;
        transition: color 0.2s;
    }}

    .news-title a:hover {{
        color: var(--primary) !important;
    }}

    .news-meta {{
        font-size: 0.75rem;
        color: var(--text-dim);
        margin-top: auto;
    }}

    /* Sidebar & Global Button Refinement */
    .stButton>button {{
        width: 100% !important;
        border-radius: 10px !important;
        background: linear-gradient(135deg, #1E3A8A 0%, #0F172A 100%) !important;
        color: white !important;
        border: 1px solid var(--glass-border) !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
        font-size: 0.85rem !important;
    }}

    /* Card Bottom Button Logic */
    .card-btn-container .stButton>button {{
        border-top: none !important;
        border-top-left-radius: 0 !important;
        border-top-right-radius: 0 !important;
        border-bottom-left-radius: 16px !important;
        border-bottom-right-radius: 16px !important;
        background: rgba(255,255,255,0.03) !important;
        text-align: right !important;
        padding-right: 1.5rem !important;
        color: var(--primary) !important;
        height: 40px !important;
    }}

    /* Sidebar Logo Positioning */
    .logo-container {{
        text-align: center;
        padding-bottom: 1.5rem;
    }}
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

# Sidebar Top
if logo_base64:
    st.sidebar.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_base64}" width="150" style="filter: drop-shadow(0 0 10px rgba(88,225,255,0.4));"></div>', unsafe_allow_html=True)
else:
    st.sidebar.title("🗞️ AI News Briefing")

st.sidebar.header("🕹️ 컨트롤 센터")

target_date = get_latest_date()
save_path = os.path.join("daily", f"{target_date}_articles.json")

# Sidebar Expander for technical ops
with st.sidebar.expander("🛠️ 데이터 수집 및 자동화", expanded=True):
    if st.button("☁️ 클라우드 리포트 동기화", help="구글 드라이브에서 최신 분석 결과물을 가져옵니다."):
        with st.spinner("동기화 중..."):
            files = list_drive_files(DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
            if files:
                latest_json = next((f for f in files if f['name'].endswith('_articles.json')), None)
                if latest_json:
                    json_content = download_drive_file(latest_json['id'], SERVICE_ACCOUNT_FILE)
                    if json_content:
                        st.session_state['data'] = json.loads(json_content)
                        st.toast(f"✅ 동기화 완료: {latest_json['name']}", icon="📥")
            else:
                st.error("파일을 찾을 수 없습니다.")

    if st.button("🔄 오늘자 신문 강제 수집", help="네이버 지면 기사를 실시간으로 새로 긁어옵니다."):
        with st.spinner("AI 수집 엔진 가동 중..."):
            engine = st.session_state['scraper_engine']
            raw_data = engine.fetch_metadata()
            df = pd.DataFrame(raw_data)
            if not df.empty:
                df = df.drop_duplicates(subset=["링크"])
                unique_data = df.to_dict('records')
                progress_bar = st.progress(0, text="기사 본문 로드 중...")
                for idx, item in enumerate(unique_data):
                    body, date = engine.get_article_details(item['링크'])
                    item['기사내용'] = body
                    item['등록일시'] = date
                    progress_bar.progress((idx + 1) / len(unique_data), text=f"수집 중 ({idx+1}/{len(unique_data)})")
                st.session_state['data'] = unique_data
                save_to_json(st.session_state['data'], save_path)
                st.toast("✅ 수집 및 분석 준비 완료!", icon="🎉")
                
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
                
                txt_path = os.path.join("daily", f"{target_date}_summary.txt")
                save_to_txt(txt_content, txt_path)
                fid = upload_to_drive(txt_content, os.path.basename(txt_path), DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
                if fid and "error" not in str(fid).lower():
                    st.toast(f"✅ 드라이브 업로드 완료!", icon="☁️")
                else: st.toast(f"❌ 업로드 실패: {fid}", icon="❌")
        else: st.toast("⚠️ 필터링된 기사가 없습니다.", icon="⚠️")

# Main Header
st.title("🗞️ AI 데일리 지면 신문 서비스")
now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"🕒 현재 동기화 시간 (KST): {now_kst} | 프리미엄 슬릭 다크 에디션")

# Tabs
tab1, tab2, tab3 = st.tabs([
    "📈 01: NYT Global", 
    "🤖 02: AI Insight", 
    "📑 03: News Archive"
])

with tab1:
    st.subheader("🇺🇸 New York Times: The Morning")
    st.markdown("전 세계가 주목하는 핵심 이슈를 번역과 시각 자료로 전달합니다.")
    
    if st.button("📩 최신 뉴스레터 번역 실행"):
        with st.spinner("NYT 이메일 로드 중..."):
            raw_email = fetch_nyt_newsletter()
            if "Error" in raw_email:
                st.error(f"수집 실패: {raw_email}")
            else:
                st.session_state['nyt_text'] = raw_email
                prompt = (
                    "너는 뉴욕타임즈 전문 번역가야. HTML 이미지 태그를 절대 수정하지 말고 텍스트만 한국어로 고품격 번역해줘.\n"
                    f"본문:\n{raw_email}"
                )
                try:
                    res = model.generate_content(prompt)
                    st.session_state['nyt_translation'] = res.text
                    st.toast("✅ 고품격 번역 완료!", icon="📜")
                except Exception as e:
                    st.error(f"번역 실패: {e}")
                    
    if st.session_state['nyt_translation']:
        st.markdown("---")
        # Custom container for newspaper feel
        st.markdown(f'<div style="background: rgba(255,255,255,0.02); padding: 2rem; border-radius: 20px; border: 1px solid var(--glass-border);">{st.session_state["nyt_translation"]}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("🤖 Gemini 종합 이슈 인사이트")
    st.info("국내 6개 주요 신문의 1면과 사설을 분석하여 핵심 정치/사회 맥락을 짚어줍니다.")
    
    if st.button("🚀 종합 논조 분석 리포트 생성"):
        if not st.session_state['data']:
            st.warning("먼저 데이터를 동기화하거나 수집해 주세요.")
        else:
            df_full = pd.DataFrame(st.session_state['data'])
            imp_news_df = df_full[df_full['중요'] == True].sort_values(by="중요도점수", ascending=False)
            imp_news = imp_news_df.groupby('신문사').head(3).to_dict('records')
            
            full_context = ""
            for n in imp_news:
                body = n.get('기사내용', '')
                trimmed_body = trim_text(body, max_len=1500)
                full_context += f"[{n['신문사']}] {n['제목']}\n{trimmed_body}\n\n"
            
            with st.spinner("Gemini AI가 신문사별 논조를 비교 중입니다..."):
                prompt = f"다음 기사들의 제목과 본문을 읽고, 오늘 대한민국의 주요 의제를 정의한 뒤 신문사별(보수/진보 등) 논조 차이를 분석해줘. 마크다운으로 가독성 좋게 작성해:\n\n{full_context}"
                try:
                    res = model.generate_content(prompt)
                    st.markdown(f'<div style="background: linear-gradient(to right, #0F172A, #1E293B); padding: 2rem; border-radius: 20px; border-left: 5px solid var(--primary);">{res.text}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error("분석 실패")

with tab3:
    st.subheader("📅 개별 기사 보관소")
    
    if not st.session_state['data']:
        st.info("데이터가 없습니다. 사이드바에서 수집을 시작해 주세요.")
    else:
        df = pd.DataFrame(st.session_state['data'])
        press_list = df['신문사'].unique().tolist()
        selected_press = st.multiselect("신문사 필터링", press_list, default=press_list)
        
        filtered_df = df[df['신문사'].isin(selected_press)]
        
        # Grid System for News Cards
        col_idx = 0
        cols = st.columns(3)
        
        for _, row in filtered_df.iterrows():
            with cols[col_idx % 3]:
                is_important = row['중요']
                badge_class = "news-tag important-badge" if is_important else "news-tag"
                badge_icon = "⭐ " if is_important else ""
                
                # Render Individual News Card Container
                # 카드 본체
                st.markdown(f"""
                <div class="news-card">
                    <span class="{badge_class}">{badge_icon}{row['신문사']}</span>
                    <div class="news-title"><a href="{row['링크']}" target="_blank">{row['제목']}</a></div>
                    <div class="news-meta">
                        <span>📍 {row['지면']}</span>
                        <span>📊 등급: {row.get('중요도등급', '하')}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Detail & Analyze Button in a small column within the grid
                if st.button("심층 분석", key=f"btn_{row['링크']}"):
                    with st.spinner("본문 심층 분석 중..."):
                        body = row.get('기사내용', '')
                        try:
                            res = model.generate_content(f"이 기사의 핵심 요약과 독자들에게 전하는 시사점을 간단히 작성해줘:\n\n{trim_text(body)}")
                            st.markdown(f'<div style="background: rgba(88,225,255,0.05); padding: 1rem; border-radius: 10px; font-size: 0.9rem; border: 1px dashed var(--primary); margin-top: 5px;">{res.text}</div>', unsafe_allow_html=True)
                        except: st.error("분석 불가")
            
            col_idx += 1

# Footer
st.markdown("---")
st.caption("Produced by Google Gemini-2.5-Flash | Styled for Premium Intelligence")
