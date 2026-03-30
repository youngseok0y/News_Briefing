import google.generativeai as genai
import os
from typing import List, Optional
from models.news_item import NewsItem

class AIService:
    """Service layer for AI-driven analysis and translation using Gemini."""
    
    def __init__(self, api_key: str, model_name: str = 'gemini-1.5-flash'):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def translate_nyt(self, raw_html: str) -> str:
        """Translates NYT newsletter with a professional correspondent persona."""
        persona = (
            "너는 대한민국 최고의 언론사에서 20년 이상 근무한 '베테랑 외신 특파원'이자 '번역 전문가'야. "
            "뉴욕타임즈(NYT)의 핵심 뉴스레터인 'The Morning'을 대상으로 고도의 언어적 감각을 발휘해줘. "
            "단순한 직역을 넘어, 국제 정세의 맥락을 충실히 반영하되 한국 독자가 읽기에 가장 우아하고 격조 있는 문체를 사용해. "
            "이미지 태그나 HTML 구조는 절대로 건드리지 말고 텍스트 부분만 정교하게 번역해줘."
        )
        
        prompt = f"{persona}\n\n[대상 본문]\n{raw_html}"
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error during NYT translation: {str(e)}"

    def generate_insight_report(self, news_items: List[NewsItem]) -> str:
        """Generates a high-level strategic briefing report using a CoT framework."""
        persona = (
            "너는 정부 기획조정실과 글로벌 전략 컨설팅 펌에서 활동하는 '수석 전략 분석가'야. "
            "전달받은 신문사별 주요 기사들을 분석하여 의사 결정권자를 위한 '종합 인사이트 보고서'를 작성해줘."
        )
        
        framework = (
            "아래의 논리 구조(Chain-of-Thought)를 따라 단계별로 사고하고 보고서를 구성해:\n"
            "1. **핵심 의제(Core Agenda)**: 오늘의 지면 뉴스에서 관통하는 가장 중요한 국가적/사회적 주제를 1~2개로 요약해.\n"
            "2. **논조 분석(Media Perspectives)**: 보수(조선/중앙)와 진보(한겨레/경향) 매체가 동일 사안을 어떻게 다르게 해석하고 있는지 예리하게 대조해.\n"
            "3. **사회적 함의(Strategic Implications)**: 이 논쟁이 향후 우리 사회나 정책에 미칠 구체적인 파급 효과를 분석해.\n"
            "4. **제언(Strategic Advice)**: 이 상황에서 우리가 주목해야 할 관전 포인트는 무엇인지 제안해."
        )
        
        context = "\n".join([f"[{n.press}] {n.title}\n{n.content[:500]}..." for n in news_items])
        prompt = f"{persona}\n\n{framework}\n\n[분석 대상 기사 목록]\n{context}"
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error during insight generation: {str(e)}"

    def analyze_deep_dive(self, article: NewsItem) -> str:
        """Performs a deep-dive analysis of a single important article."""
        persona = (
            "너는 사실 관계 파악과 이면의 진실을 추적하는 '탐사 보도 전문 기자'야. "
            "특정 기사를 심층 분석하여 독자가 놓칠 수 있는 함의를 짚어줘."
        )
        
        prompt = (
            f"{persona}\n\n"
            f"대상 기사: {article.title} ({article.press})\n"
            f"본문 내용: {article.content}\n\n"
            "위 기사를 분석하여 '요약', '핵심 이해관계자', '숨겨진 시사점'을 각각 2문장 내외로 정리해줘."
        )
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Error during deep-dive analysis: {str(e)}"
