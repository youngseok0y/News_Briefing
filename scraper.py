import time
import random
import requests
from bs4 import BeautifulSoup
import re
from utils import get_latest_date

class NewsScraper:
    def __init__(self):
        self.press_map = {
            "조선일보": "023", "중앙일보": "025", "동아일보": "020",
            "한국일보": "469", "한겨레": "028", "경향신문": "032"
        }
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
        ]
        
        self.important_keywords = [
            "1면", "사설", "칼럼", "오피니언", "기획", "특집", "데스크", "논단"
        ]

    def _get_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def _retry_request(self, url, retries=3, delay=1.0):
        for i in range(retries):
            try:
                time.sleep(delay)
                res = requests.get(url, headers=self._get_headers(), timeout=10)
                res.raise_for_status()
                return res
            except Exception as e:
                if i == retries - 1:
                    print(f"Failed to fetch {url}: {e}")
                    return None
        return None

    def _safe_select(self, soup, selectors):
        for sel in selectors:
            result = soup.select(sel)
            if result:
                return result
        return []

    def _safe_select_one(self, soup, selectors):
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                return el
        return None

    def _calculate_importance(self, page_title):
        score = 0
        normalized_title = page_title.replace(" ", "").upper()
        
        # B1면 등이 1면으로 인식되지 않도록 정확한 시작 단어 일치 검사로 변경
        is_a1 = (normalized_title in ["1면", "A1면", "A1"] or 
                 normalized_title.startswith("종합1면") or 
                 normalized_title.startswith("A1면") or 
                 normalized_title.startswith("1면"))
                 
        if is_a1: score += 5
        elif "사설" in normalized_title: score += 4
        elif "칼럼" in normalized_title: score += 3
        elif "오피니언" in normalized_title: score += 3
        elif any(k in normalized_title for k in ["기획", "특집", "데스크", "논단"]): score += 2
        
        # '상/중/하' 아카이빙용 등급 판별
        if score >= 4: grade = "상"
        elif score >= 2: grade = "중"
        else: grade = "하"
        
        return score, grade, score > 0

    def fetch_opinions(self, name, pid):
        url = f"https://media.naver.com/press/{pid}?sid=110"
        res = self._retry_request(url, delay=0.5)
        results = []
        if not res:
            return results
        
        soup = BeautifulSoup(res.text, 'html.parser')
        # 각 언론사 오피니언 메인의 기사 링크들 추출 (중복 제거)
        links = soup.find_all('a', href=re.compile(fr'article/{pid}'))
        seen_hrefs = set()
        
        for a in links:
            href = a.get('href', '')
            title = a.get_text(strip=True)
            # 타임스탬프 텍스트(예: "10시간전") 등 불필요한 짧은 텍스트 필터링
            title = re.sub(r'\d+시간\s*전$', '', title).strip()
            
            if len(title) > 5 and href not in seen_hrefs:
                seen_hrefs.add(href)
                # 사설 여부 판단을 통해 가중치 차등 부여
                score = 4 if "사설" in title else 3
                grade = "상" if score >= 4 else "중"
                results.append({
                    "신문사": name,
                    "지면": "사설/칼럼(sid=110)",
                    "중요도점수": score,
                    "중요도등급": grade,
                    "중요": True,
                    "제목": title,
                    "링크": href
                })
                if len(results) >= 5: # 주요 오피니언 상위 5개만 수집
                    break
        return results

    def fetch_metadata(self):
        target_date = get_latest_date()
        results = []
        
        for name, pid in self.press_map.items():
            press_daily_results = []
            
            # 1. 지면 기사 크롤링
            url = f"https://media.naver.com/press/{pid}/newspaper?date={target_date}"
            res = self._retry_request(url, delay=0.5)
            if res:
                soup = BeautifulSoup(res.text, 'html.parser')
                sections = self._safe_select(soup, ['.newspaper_inner', '.press_newspaper', '.np_view'])
                for sec in sections:
                    page_el = self._safe_select_one(sec, ['.newspaper_grid_title', '.page_title', '.page_notation'])
                    page = page_el.get_text(strip=True) if page_el else "알 수 없음"
                    
                    score, grade, is_imp = self._calculate_importance(page)
                    
                    article_links = self._safe_select(sec, ['.as_thumb .as_tit a', '.news_list a.tit', '.list_title', '.newspaper_article_lst a'])
                    for a in article_links:
                        link = a['href']
                        # Some links might not have strong text tags but direct text
                        title_el = self._safe_select_one(a, ['strong', '.tit'])
                        title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
                        if not title:
                            continue
                            
                        press_daily_results.append({
                            "신문사": name,
                            "지면": page,
                            "중요도점수": score,
                            "중요도등급": grade,
                            "중요": is_imp,
                            "제목": title,
                            "링크": link
                        })
            
            # 2. 오피니언(sid=110) 섹션 별도 크롤링 후 교차 검증 (Cross Check)
            opinion_results = self.fetch_opinions(name, pid)
            daily_links_map = {item['링크']: item for item in press_daily_results}
            
            for op in opinion_results:
                if op['링크'] in daily_links_map:
                    # 지면에 실린 오피니언 기사 발견! 강조 처리 및 중요도 상향
                    matched = daily_links_map[op['링크']]
                    matched['중요'] = True
                    matched['중요도점수'] = max(matched['중요도점수'], op['중요도점수'])
                    matched['중요도등급'] = "상" if matched['중요도점수'] >= 4 else "중"
                    
                    if "[사설/칼럼]" not in matched['제목']:
                        matched['제목'] = f"💡[사설/칼럼] {matched['제목']}"
                else:
                    # 지면엔 없지만 온라인 오피니언에 실린 기사 (보통 당일 최신)
                    press_daily_results.append(op)
                    
            results.extend(press_daily_results)
            
        return results

    def get_article_details(self, url):
        res = self._retry_request(url, delay=0.2) # 빠른 전체 수집을 위해 0.2초 딜레이
        if not res:
            return "본문을 가져올 수 없습니다", ""
            
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 기사 내용 추출
        selectors = [
            '#newsct_article',
            '#articeBody',
            '.article_body',
            '.news_end',
            'article'
        ]
        body_el = self._safe_select_one(soup, selectors)
        body = body_el.get_text(strip=True) if body_el else ""
        
        # 등록 일시 추출
        date_selectors = ['.media_end_head_info_datestamp_time', '.t11', '.info']
        date_el = self._safe_select_one(soup, date_selectors)
        date = date_el.get_text(strip=True) if date_el else ""
        
        return body, date
