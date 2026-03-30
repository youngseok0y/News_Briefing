import streamlit as st
import pandas as pd
import google.generativeai as genai
import os
from datetime import datetime
import utils
from scraper import NewsScraper
from services import ui_service, sync_service

# 1. 초기 Streamlit 설정 (가장 먼저 실행되어야 함)
st.set_page_config(page_title="AI News Briefing Center", layout="wide", initial_sidebar_state="expanded")

# 2. 설정 및 보안 (Secrets 관리)
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    DRIVE_FOLDER_ID = st.secrets["DRIVE_FOLDER_ID"]
except KeyError as e:
    st.error(f"⚠️ 시스템 구성 오류: secrets.toml에 필수 키가 없습니다. ({e})")
    st.stop()

SERVICE_ACCOUNT_FILE = 'credentials.json' 

# 3. 모델 초기화
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Gemini 초기화 에러: {e}")
    st.stop()

# 4. UI 스타일링 및 로고
ui_service.inject_custom_css()
logo_base64 = ui_service.get_base64_image("logo.png")

# 5. Session State 통합 초기화
SESSION_DEFAULTS = {
    'data': [],
    'analysis_cache': {},
    'scraper_engine': NewsScraper(),
    'nyt_text': "",
    'nyt_translation': "",
    'final_report': "",
    'last_sync': None
}

for key, default in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# 6. Sidebar 구성
if logo_base64:
    st.sidebar.markdown(f'<div class="logo-container"><img src="data:image/png;base64,{logo_base64}" width="140" style="filter: drop-shadow(0 0 10px rgba(88,225,255,0.4));"></div>', unsafe_allow_html=True)
else:
    st.sidebar.title("🗞️ AI News Briefing")

st.sidebar.header("🕹️ 컨트롤 센터")
target_date = utils.get_latest_date()

# Sidebar: Sync & Scrape
with st.sidebar.expander("🛠️ 데이터 수집 및 자동화", expanded=False):
    if st.button("☁️ 클라우드 리포트 동기화", help="로컬 캐시 및 드라이브에서 오늘 날짜의 정보를 가져옵니다."):
        results = sync_service.sync_daily_reports(target_date, DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
        if results:
            st.session_state['last_sync'] = datetime.now(utils.KST).strftime("%H:%M:%S")
            st.toast(f"✅ {len(results)}개 항목 동기화 완료")

    if st.button("🔄 오늘자 신문 강제 수집"):
        with st.spinner("AI 수집 엔진 가동 중..."):
            engine = st.session_state['scraper_engine']
            raw_data = engine.fetch_metadata()
            df = pd.DataFrame(raw_data)
            if not df.empty:
                df = df.drop_duplicates(subset=["링크"])
                unique_data = df.to_dict('records')
                progress_bar = st.progress(0, text="기사 본문 로드 중...")
                for idx, item in enumerate(unique_data):
                    body, date = engine.get_article_details(item['リンク'])
                    item['기사내용'] = body
                    item['등록일시'] = date
                    progress_bar.progress((idx + 1) / len(unique_data), text=f"수집 중 ({idx+1}/{len(unique_data)})")
                st.session_state['data'] = unique_data
                utils.save_to_json(st.session_state['data'], os.path.join("daily", f"{target_date}_articles.json"))
                st.toast("✅ 수집 및 분석 준비 완료!", icon="🎉")
            else:
                st.warning("수집된 데이터가 없습니다.")

    st.markdown("---")
    
    if st.button("📤 구글 드라이브 업로드 (NotebookLM)"):
        if st.session_state['data']:
            with st.spinner("드라이브에 업로드 중..."):
                txt_content = f"오늘의 전체 지면 기사 원문 ({utils.get_latest_date()})\n" + "="*50 + "\n\n"
                for d in st.session_state['data']:
                    grade = d.get('중요도등급', '하')
                    txt_content += f"[{grade}] [{d['신문사']}-{d['지면']}] {d['제목']}\n"
                    txt_content += f"등록일시: {d.get('등록일시', '')}\n"
                    txt_content += f"링크: {d['링크']}\n\n"
                    txt_content += f"{d.get('기사내용', '본문 없음')}\n\n"
                    txt_content += "-"*50 + "\n\n"
                
                txt_path = os.path.join("daily", f"{target_date}_summary.txt")
                utils.save_to_txt(txt_content, txt_path)
                fid = utils.upload_to_drive(txt_content, os.path.basename(txt_path), DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
                if fid and "error" not in str(fid).lower():
                    st.toast(f"✅ 드라이브 업로드 완료!", icon="☁️")
                else:
                    st.toast(f"❌ 업로드 실패: {fid}", icon="❌")

# 7. Main Dashboard Content
st.title("🗞️ AI 데일리 지면 신문 서비스")
now_kst = datetime.now(utils.KST).strftime("%Y-%m-%d %H:%M:%S")
st.caption(f"🕒 현재 동기화 시간 (KST): {now_kst} | 아키텍처 v2.0 (Service Oriented)")

tab1, tab2, tab3 = st.tabs(["📈 NYT Global", "🤖 Gemini Insight", "📑 Archive"])

with tab1:
    st.subheader("🇺🇸 New York Times: The Morning")
    if st.button("📩 최신 뉴스레터 번역 실행"):
        with st.spinner("NYT 이메일 로드 중..."):
            raw_email = utils.fetch_nyt_newsletter()
            if "Error" in raw_email:
                st.error(f"수집 실패: {raw_email}")
            else:
                st.session_state['nyt_text'] = raw_email
                prompt = f"너는 뉴욕타임즈 전문 번역가야. HTML 이미지 태그를 절대 수정하지 말고 한국어로 고품격 번역해줘.\n본문:\n{raw_email}"
                try:
                    res = model.generate_content(prompt)
                    st.session_state['nyt_translation'] = res.text
                    nyt_data = {"raw": raw_email, "translation": res.text, "date": target_date}
                    utils.save_and_upload_json(nyt_data, f"{target_date}_nyt.json", DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
                    st.toast("✅ 번역 완료 및 클라우드 저장!", icon="☁️")
                except Exception as e:
                    st.error(f"번역 실패: {e}")
    
    if st.session_state['nyt_translation']:
        st.markdown(f'<div style="background: rgba(255,255,255,0.02); padding: 2rem; border-radius: 20px; border: 1px solid var(--glass-border);">{st.session_state["nyt_translation"]}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("🤖 Gemini 종합 이슈 인사이트")
    if st.button("🚀 종합 논조 분석 리포트 생성"):
        if not st.session_state['data']:
            st.warning("먼저 데이터를 동기화하거나 수집해 주세요.")
        else:
            df_full = pd.DataFrame(st.session_state['data'])
            imp_news = df_full[df_full['중요'] == True].sort_values(by="중요도점수", ascending=False).groupby('신문사').head(3).to_dict('records')
            full_context = "\n".join([f"[{n['신문사']}] {n['제목']}\n{utils.trim_text(n.get('기사내용',''))}" for n in imp_news])
            
            with st.spinner("Gemini AI가 신문사별 논조를 비교 중입니다..."):
                try:
                    res = model.generate_content(f"오늘 대한민국의 주요 의제를 정의하고 신문사별 논조 차이를 분석해줘:\n\n{full_context}")
                    st.session_state['final_report'] = res.text
                    utils.save_and_upload_json({"report": res.text, "date": target_date}, f"{target_date}_insight.json", DRIVE_FOLDER_ID, SERVICE_ACCOUNT_FILE)
                    st.toast("✅ 분석 완료 및 클라우드 저장!", icon="☁️")
                except Exception as e:
                    st.error(f"분석 실패: {e}")

    if st.session_state.get('final_report'):
        st.markdown(f'<div style="background: linear-gradient(to right, #0F172A, #1E293B); padding: 2rem; border-radius: 20px; border-left: 5px solid var(--primary);">{st.session_state["final_report"]}</div>', unsafe_allow_html=True)

with tab3:
    st.subheader("📅 개별 기사 보관소")
    if not st.session_state['data']:
        st.info("데이터가 없습니다. 사이드바에서 수집을 시작해 주세요.")
    else:
        df = pd.DataFrame(st.session_state['data'])
        press_list = df['신문사'].unique().tolist()
        selected_press = st.multiselect("신문사 필터링", press_list, default=press_list)
        filtered_df = df[df['신문사'].isin(selected_press)]
        
        cols = st.columns(3)
        for idx, (_, row) in enumerate(filtered_df.iterrows()):
            with cols[idx % 3]:
                ui_service.render_news_card(row)
                if st.button("심층 분석", key=f"btn_{row['링크']}"):
                    cache_key = row['링크']
                    if cache_key not in st.session_state['analysis_cache']:
                        with st.spinner("본문 심층 분석 중..."):
                            try:
                                res = model.generate_content(f"이 기사의 요약과 시사점을 간단히 작성해줘:\n\n{utils.trim_text(row.get('기사내용',''))}")
                                st.session_state['analysis_cache'][cache_key] = res.text
                            except Exception as e:
                                st.error(f"분석 실패: {e}")
                    
                    analysis_result = st.session_state['analysis_cache'].get(cache_key)
                    if analysis_result:
                        st.markdown(f'<div style="background: rgba(88,225,255,0.05); padding: 1rem; border-radius: 10px; font-size: 0.9rem; border: 1px dashed var(--primary); margin-top: 5px;">{analysis_result}</div>', unsafe_allow_html=True)

ui_service.render_footer()
