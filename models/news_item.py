from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class NewsItem:
    """Represents a single news article with standardized fields."""
    title: str
    link: str
    press: str            # 신문사
    page: str             # 지면 정보 (예: A01)
    importance: bool      # 중요 기사 여부
    importance_score: int # 1~100 중요도 점수
    grade: str            # 상, 중, 하 등급
    content: str          # 기사 본문
    date: str             # 발행일 (YYYYMMDD)
    created_at: Optional[str] = None # 수집 일시 (ISO format)

    def to_dict(self) -> Dict[str, Any]:
        """Converts the model instance to a dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'NewsItem':
        """
        Creates an instance from a dictionary.
        Handles BOTH Korean keys (from scraper) and English keys (from to_dict/GDrive sync).
        """
        def get(ko_key: str, en_key: str, default=None):
            """Tries Korean key first, falls back to English key."""
            return data.get(ko_key) or data.get(en_key) or default

        return cls(
            title=get('제목', 'title', ''),
            link=get('링크', 'link', ''),
            press=get('신문사', 'press', ''),
            page=get('지면', 'page', ''),
            importance=get('중요', 'importance', False),
            importance_score=get('중요도점수', 'importance_score', 0),
            grade=get('중요도등급', 'grade', '하'),
            content=get('기사내용', 'content', ''),
            date=get('date', 'date', ''),
            created_at=get('등록일시', 'created_at', None)
        )
