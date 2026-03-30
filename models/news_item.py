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
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsItem':
        """Creates an instance from a dictionary with field mapping."""
        # 맵핑 (기존 딕셔너리 키 대응)
        return cls(
            title=data.get('제목', ''),
            link=data.get('링크', ''),
            press=data.get('신문사', ''),
            page=data.get('지면', ''),
            importance=data.get('중요', False),
            importance_score=data.get('중요도점수', 0),
            grade=data.get('중요도등급', '하'),
            content=data.get('기사내용', ''),
            date=data.get('date', ''),
            created_at=data.get('등록일시', None)
        )
