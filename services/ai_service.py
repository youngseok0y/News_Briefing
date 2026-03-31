from google import genai
from google.genai import types
import os
from typing import List, Optional
from models.news_item import NewsItem
from utils import cache_data

# 💡 고품격 캐싱을 위해 전역 캐시 함수 정의
@cache_data(ttl=86400, show_spinner=False)
def _cached_gemini_call(api_key: str, model_name: str, prompt: str, system_instruction: Optional[str] = None) -> str:
    """
    Standalone cached function using the official Google Gen AI SDK.
    V6.3: Use v1beta (default) + gemini-2.0-flash (model that supports system_instruction)
    """
    try:
        # 💡 [V6.3 FIX] Let SDK use its default v1alpha/v1beta endpoint
        # system_instruction is a v1beta feature, so do NOT force v1
        client = genai.Client(api_key=api_key)
        
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7
        )
            
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        return response.text
    except Exception as e:
        return f"AI 서비스 호출 에러: {str(e)}"

class AIService:
    """
    Service layer for AI-driven analysis using the official Google Gen AI SDK.
    V6.3: Uses gemini-2.0-flash, fully supported with system_instruction in v1beta.
    """
    
    def __init__(self, api_key: str, model_name: str = 'gemini-2.0-flash'):
        # 💡 [V6.3 FIX] Model changed: gemini-1.5-flash (deprecated) → gemini-2.0-flash
        self.api_key = api_key
        self.model_name = model_name
        
    def translate_nyt(self, raw_html: str) -> str:
        """Translates NYT newsletter with a professional correspondent persona."""
        persona = (
            "너는 대한민국 최고의 언론사에서 20년 이상 근무한 '베테랑 외신 특파원'이자 '번역 전문가'야. "
            "뉴욕타임즈(NYT)의 핵심 뉴스레터인 'The Morning' 내용을 바탕으로 고도의 언어적 감각을 발휘해줘. "
            "국제 정세의 맥락을 충실히 반영하되 한국 독자가 읽기에 가장 우아하고 격조 있는 문체를 사용해."
        )
        
        prompt = f"다음 뉴욕타임즈 본문을 한국인 정서에 맞게 자연스럽고 품격 있게 번역해:\n\n[대상 본문]\n{raw_html}"
        return _cached_gemini_call(self.api_key, self.model_name, prompt, system_instruction=persona)

    def generate_insight_report(self, news_items: List[NewsItem]) -> str:
        """Generates a high-level strategic briefing report using a CoT framework."""
        persona = (
            "너는 정부 기획조정실과 글로벌 전략 컨설팅 펌에서 활동하는 '수석 전략 분석가'야. "
            "전달받은 주요 기사들을 분석하여 의사 결정권자를 위한 '종합 인사이트 보고서'를 작성해."
        )
        
        framework = (
            "아래의 논리 구조(Chain-of-Thought)를 따라 보고서를 구성해:\n"
            "1. **핵심 의제(Core Agenda)**: 오늘의 가장 중요한 주제 요약\n"
            "2. **논조 분석(Media Perspectives)**: 매체별 해석 차이 대조\n"
            "3. **사회적 함의(Strategic Implications)**: 향후 파급 효과\n"
            "4. **제언(Strategic Advice)**: 전략적 관전 포인트"
        )
        
        content = "\n".join([f"[{n.press}] {n.title}\n{n.content[:500]}..." for n in news_items])
        prompt = f"{framework}\n\n[분석 대상 기사 목록]\n{content}"
        
        return _cached_gemini_call(self.api_key, self.model_name, prompt, system_instruction=persona)

    def analyze_deep_dive(self, article: NewsItem) -> str:
        """Performs a deep-dive analysis of a single important article."""
        persona = "너는 사실 관계 파악과 이면의 진실을 추적하는 '탐사 보도 전문 기자'야."
        
        prompt = (
            f"대상 기사: {article.title} ({article.press})\n"
            f"본문 내용: {article.content[:2000]}\n\n"
            "위 기사를 분석하여 '요약', '핵심 이해관계자', '숨겨진 시사점'을 각각 2문장 내외로 정리해."
        )
        
        return _cached_gemini_call(self.api_key, self.model_name, prompt, system_instruction=persona)
