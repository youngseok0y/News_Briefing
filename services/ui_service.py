import streamlit as st
import base64
import os

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

        /* News Card Design */
        .news-card {{
            position: relative;
            background: var(--card-bg);
            backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            padding: 1.5rem;
            margin-bottom: 0px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            height: 200px;
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
            font-size: 0.7rem;
            color: var(--text-dim);
            position: absolute;
            bottom: 1.2rem;
            left: 1.2rem;
        }}

        /* Buttons */
        [data-testid="stSidebar"] .stButton>button, 
        .stButton>button {{
            width: 100% !important;
            border-radius: 8px !important;
            background: linear-gradient(135deg, #1E3A8A 0%, #060914 100%) !important;
            color: white !important;
            border: 1px solid var(--glass-border) !important;
            padding: 0.5rem 1rem !important;
            font-weight: 600 !important;
            transition: all 0.2s !important;
            font-size: 0.8rem !important;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        }}

        .stButton>button:hover {{
            border-color: var(--primary) !important;
            box-shadow: 0 0 10px rgba(88, 225, 255, 0.2) !important;
        }}

        .logo-container {{
            text-align: center;
            padding-bottom: 1.5rem;
        }}
    </style>
    """, unsafe_allow_html=True)

def render_news_card(row):
    """Renders a single news card with premium styling."""
    is_important = row.get('중요', False)
    badge_class = "news-tag important-badge" if is_important else "news-tag"
    badge_icon = "⭐ " if is_important else ""
    
    card_html = f"""
    <div class="card-wrapper">
        <div class="news-card">
            <span class="{badge_class}">{badge_icon}{row['신문사']}</span>
            <div class="news-title"><a href="{row['링크']}" target="_blank">{row['제목']}</a></div>
            <div class="news-meta">
                <span>📍 {row['지면']}</span>
                <span>📊 등급: {row.get('중요도등급', '하')}</span>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

def render_footer():
    """Renders the premium footer branding."""
    st.markdown("---")
    st.markdown(f"""
        <div style="text-align: center; color: var(--text-dim); font-size: 0.8rem; padding: 1rem;">
            ⚡ Powered by <strong>Gemini 2.5 Flash</strong> & <strong>Google Drive Cloud Insight</strong><br>
            Produced for High-End Intelligence Briefing | © 2026 AI News Aggregator
        </div>
    """, unsafe_allow_html=True)
