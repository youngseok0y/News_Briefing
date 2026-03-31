import requests
from bs4 import BeautifulSoup

url = "https://news.naver.com/main/list.naver?mode=LPOD&mid=sec&sid1=001&sid2=140&oid=001&isYeonhapFlash=Y"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}

res = requests.get(url, headers=headers, timeout=15)
print(f"HTTP Status: {res.status_code}")
soup = BeautifulSoup(res.text, "html.parser")

# 1. 현재 notifier.py 선택자 테스트
print("\n=== 현재 선택자 ===")
items = soup.select(".list_body ul li dl dt:not(.photo) a")
print(f"결과: {len(items)}개")

# 2. 다양한 대안 선택자 테스트
print("\n=== 대안 선택자 탐색 ===")
selectors = [
    "ul.type06_headline li a",
    "ul.type06 li a",
    ".list_body li a",
    "#main_content li a",
    "li.sh_item a",
    "div.list_body a",
]
for sel in selectors:
    found = soup.select(sel)
    if found:
        first = found[0]
        txt = first.get_text(strip=True)
        href = first.get("href", "")
        if txt and len(txt) > 5:
            print(f"HIT [{sel}]: {len(found)}개")
            print(f"  첫번째 제목: {txt[:50]}")
            print(f"  첫번째 href: {href[:100]}")
    else:
        print(f"MISS [{sel}]: 0개")

# 3. 모든 링크 중 연합뉴스 기사 찾기
print("\n=== 연합뉴스 기사 링크 탐색 (oid=001) ===")
all_a = soup.find_all("a", href=True)
yonhap_links = [
    a for a in all_a
    if "oid=001" in a.get("href", "") or "/001/" in a.get("href", "")
    and a.get_text(strip=True)
]
print(f"연합뉴스 관련 링크: {len(yonhap_links)}개")
for a in yonhap_links[:5]:
    print(f"  [{a.get_text(strip=True)[:40]}]")
    print(f"  {a['href'][:100]}")

# 4. HTML 구조 힌트
print("\n=== HTML 구조 힌트 ===")
main = soup.find(id="main_content")
if main:
    print("main_content 발견. 하위 태그:")
    for tag in main.children:
        if hasattr(tag, 'name') and tag.name:
            cls = tag.get("class", [])
            print(f"  <{tag.name} class={cls}>")
else:
    print("main_content 없음 - 페이지가 JS 렌더링일 수 있음")
    print(f"HTML 길이: {len(res.text)} 바이트")
    print("HTML 앞부분 500자:")
    print(res.text[:500])
