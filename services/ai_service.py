from google import genai
from google.genai import types
import os
import time
import json
from typing import List, Optional, TYPE_CHECKING
from models.news_item import NewsItem
from utils import cache_data
from config.settings import settings

if TYPE_CHECKING:
    from services.storage_service import StorageService

# ============================================================
# 🤖 Core API Caller with Retry Logic (V7.1)
# ============================================================

def _notify_user(message: str):
    """Pushes a notification to Streamlit UI if available, otherwise logs to console."""
    print(message)
    try:
        import streamlit as st
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx():
            st.toast(message, icon="⚠️")
    except Exception:
        pass


def _call_ai_with_fallback(prompt: str, system_instruction: Optional[str] = None, initial_model: str = 'gemini-2.5-flash') -> str:
    """Model Router that triggers fallback across providers upon quota exhaustion."""
    
    # 💡 Fallback Chain
    models_to_try = [
        {"provider": "gemini", "model": initial_model},
        {"provider": "gemini", "model": "gemini-2.0-flash-lite"},
    ]
    
    if settings.groq_api_key:
        models_to_try.append({"provider": "groq", "model": "llama3-70b-8192"})

    for idx, conf in enumerate(models_to_try):
        provider = conf["provider"]
        model_name = conf["model"]
        
        try:
            if provider == "gemini":
                # Raw API call (Google Gen AI)
                client = genai.Client(api_key=settings.gemini_api_key)
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.7
                )
                response = client.models.generate_content(
                    model=model_name, contents=prompt, config=config
                )
                return response.text
                
            elif provider == "groq":
                # Raw API call (Groq SDK)
                try:
                    from groq import Groq
                except ImportError:
                    return f"❌ 시스템 에러: 외부 모델({model_name})을 사용하려면 'groq' 라이브러리가 필요합니다."
                    
                client = Groq(api_key=settings.groq_api_key)
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                messages.append({"role": "user", "content": prompt})
                
                chat_completion = client.chat.completions.create(
                    messages=messages,
                    model=model_name,
                    temperature=0.7,
                )
                return chat_completion.choices[0].message.content

        except Exception as e:
            err_str = str(e)
            
            # 💡 할당량 초과(429) 감지 및 Fallback 전개
            if '429' in err_str or 'quota' in err_str.lower() or 'exhausted' in err_str.lower():
                is_last_model = idx == len(models_to_try) - 1
                if not is_last_model:
                    next_model = models_to_try[idx+1]["model"]
                    _notify_user(f"💡 {model_name} 할당량 소진됨. {next_model} 대체 모델로 재진행합니다.")
                    time.sleep(1) # 부드러운 전환을 위한 대기
                    continue # 다음 모델 시도
                else:
                    _notify_user("🚨 모든 AI 모델의 할당량이 완전히 소진되었습니다.")
                    return (
                        "❌ **모든 AI 모델 할당량 초과**\n\n"
                        "현재 설정된 주력 모델과 외부 대체 모델의 무료 사용량이 모두 소진되었습니다.\n"
                        "- **내일 UTC 자정** 기점으로 자동 초기화 대상은 복구됩니다.\n"
                        "- 이전에 성공했던 분석 결과들은 캐시에서 안전하게 보호되고 있습니다."
                    )
            
            # 일반 네트워크, 구문 에러는 즉시 반환
            return f"❌ {model_name} 서비스 장애: {err_str}"
            
    return "❌ AI 서비스 에러: 알 수 없는 이유로 모든 모델 생성 실패"


class AIService:
    """
    Service layer for AI-driven analysis using Google Gen AI SDK.
    V7.1: GDrive-backed persistent cache via StorageService.
          Quota-efficient with token budgeting and batch analysis.
    """

    def __init__(self, api_key: str, storage_svc: 'StorageService', model_name: Optional[str] = None):
        self.api_key = api_key
        self.model_name = model_name or settings.ai_model_name
        self.storage = storage_svc  # 💡 GDrive cache backend

    # ============================================================
    # 💾 GDrive Cache Helpers (Replaces local disk cache)
    # ============================================================

    def _cache_key_filename(self, key: str) -> str:
        """Standardized cache filename on GDrive."""
        return f"ai_cache_{key}.json"

    def _load_from_gdrive(self, cache_key: str) -> Optional[str]:
        """Checks GDrive for a cached AI result. Returns None on miss."""
        try:
            data = self.storage.find_and_download_json(self._cache_key_filename(cache_key))
            if data and 'result' in data:
                print(f"✅ [GDrive 캐시 HIT] {cache_key}")
                return data['result']
        except Exception:
            pass
        return None

    def _save_to_gdrive(self, cache_key: str, result: str):
        """Saves AI result to GDrive for persistent reuse across reboots."""
        try:
            payload = json.dumps({'result': result}, ensure_ascii=False)
            self.storage.upload_content_to_drive(payload, self._cache_key_filename(cache_key), mime_type='application/json')
            print(f"💾 [GDrive 캐시 저장] {cache_key}")
        except Exception as e:
            print(f"⚠️ GDrive 캐시 저장 실패 (무시됨): {e}")

    # ============================================================
    # Token Budget Helper
    # ============================================================

    def _build_news_context(self, news_items: List[NewsItem], chars_per_article: int = 200) -> str:
        """Builds a token-efficient context string from news items."""
        return "\n".join([
            f"[{n.press}/{n.page}] {n.title}\n{n.content[:chars_per_article]}..."
            for n in news_items
        ])

    # ============================================================
    # CORE SERVICES with GDrive Cache
    # ============================================================

    def translate_nyt(self, raw_html: str, target_date: str) -> str:
        """NYT 번역 - GDrive 캐시로 당일 재호출 차단."""
        cache_key = f"{target_date}_nyt_translation"

        cached = self._load_from_gdrive(cache_key)
        if cached:
            return cached

        persona = (
            "너는 대한민국 최고 언론사의 20년 경력 베테랑 외신 특파원이야. "
            "NYT 'The Morning'을 국제 정세 맥락을 살려 우아하고 격조 있게 번역해."
        )
        prompt = f"다음 본문을 한국인 정서에 맞게 번역해:\n\n{raw_html[:3000]}"

        result = _call_ai_with_fallback(prompt, system_instruction=persona, initial_model=self.model_name)
        if "에러" not in result and "❌" not in result:
            self._save_to_gdrive(cache_key, result)
        return result

    def generate_insight_report(self, news_items: List[NewsItem], target_date: str) -> str:
        """종합 분석 리포트 - GDrive 캐시로 당일 1회만 생성."""
        cache_key = f"{target_date}_insight_report"

        cached = self._load_from_gdrive(cache_key)
        if cached:
            return cached

        persona = (
            "너는 정부 기획조정실과 글로벌 전략 컨설팅 펌의 수석 전략 분석가야. "
            "의사 결정권자를 위한 종합 인사이트 보고서를 작성해."
        )
        framework = (
            "1. **핵심 의제**: 오늘의 가장 중요한 주제\n"
            "2. **논조 분석**: 보수·진보 매체 해석 차이\n"
            "3. **사회적 함의**: 향후 파급 효과\n"
            "4. **제언**: 전략적 관전 포인트"
        )
        context = self._build_news_context(news_items[:10], chars_per_article=200)
        prompt = f"{framework}\n\n[분석 대상]\n{context}"

        result = _call_ai_with_fallback(prompt, system_instruction=persona, initial_model=self.model_name)
        if "에러" not in result and "❌" not in result:
            self._save_to_gdrive(cache_key, result)
        return result

    def analyze_top_articles_batch(self, news_items: List[NewsItem], target_date: str) -> dict:
        """
        상위 5개 기사를 1회 API 호출로 배치 분석.
        결과는 GDrive에 캐싱하여 당일 재호출 차단.
        """
        cache_key = f"{target_date}_batch_analysis"

        cached = self._load_from_gdrive(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                pass

        top_items = sorted(news_items, key=lambda x: x.importance_score, reverse=True)[:5]
        persona = "너는 탐사 보도 전문 기자야. 각 기사를 간결하게 심층 분석해줘."
        articles_text = "\n\n".join([
            f"[기사 {i+1}] {item.title} ({item.press})\n{item.content[:300]}"
            for i, item in enumerate(top_items)
        ])
        prompt = (
            f"아래 {len(top_items)}개 기사를 각각 분석하여 "
            f"'[기사 N] 요약 / 이해관계자 / 시사점' 형식으로 답해:\n\n{articles_text}"
        )

        result_text = _call_ai_with_fallback(prompt, system_instruction=persona, initial_model=self.model_name)
        result_map = {item.link: result_text for item in top_items}

        if "에러" not in result_text and "❌" not in result_text:
            self._save_to_gdrive(cache_key, json.dumps(result_map, ensure_ascii=False))
        return result_map

    def analyze_deep_dive(self, article: NewsItem) -> str:
        """단일 기사 심층 분석 (배치 분석으로 커버되지 않은 기사용)."""
        persona = "너는 탐사 보도 전문 기자야."
        prompt = (
            f"기사: {article.title} ({article.press})\n"
            f"본문: {article.content[:800]}\n\n"
            "요약 / 핵심 이해관계자 / 숨겨진 시사점을 각 2문장으로 정리."
        )
        return _call_ai_with_fallback(prompt, system_instruction=persona, initial_model=self.model_name)
