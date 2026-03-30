from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Article:
    제목: str
    신문사: str
    지면: str
    링크: str
    중요도등급: str = "하"
    중요: bool = False
    중요도점수: int = 0
    기사내용: str = ""
    등록일시: str = ""

@dataclass
class AnalysisResult:
    date: str
    nyt_raw: str = ""
    nyt_translation: str = ""
    final_report: str = ""
