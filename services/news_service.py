import os
import pandas as pd
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from models.news_item import NewsItem
from scraper import NewsScraper
from services.storage_service import StorageService
import utils

class NewsService:
    """Professional News Service using Parallel Scrapers and Storage Layer."""
    
    def __init__(self, storage_svc: StorageService):
        self.scraper = NewsScraper()
        self.storage = storage_svc
        self.kst = utils.KST

    def fetch_and_process_daily_news(self, target_date: str) -> List[NewsItem]:
        """Orchestrates parallel scraping and saves results via StorageService."""
        print(f"🔄 Fetching news with optimized storage for {target_date}...")
        
        raw_data = self.scraper.fetch_metadata()
        if not raw_data: return []
            
        df = pd.DataFrame(raw_data).drop_duplicates(subset=["링크"])
        unique_list = df.to_dict('records')
        
        processed_items = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_item = {executor.submit(self.scraper.get_article_details, item['링크']): item for item in unique_list}
            
            for future in as_completed(future_to_item):
                item = future_to_item[future]
                try:
                    body, date_str = future.result()
                    processed_items.append(NewsItem.from_dict({
                        **item, '기사내용': body, 'date': target_date, '등록일시': date_str
                    }))
                except Exception as exc:
                    print(f"❌ Article error on {item['링크']}: {exc}")
            
        # 💡 [Optimization] Save results using specialized StorageService
        self.storage.save_local_json([i.to_dict() for i in processed_items], f"{target_date}_articles.json")
        
        return processed_items

    def upload_for_notebook_lm(self, news_items: List[NewsItem], target_date: str) -> Tuple[bool, str]:
        """Formats and uploads optimized data for NotebookLM via StorageService."""
        if not news_items: return False, "No items"
            
        content_header = f"🗞️ AI News Briefing: Full Press Coverage ({target_date})\n" + "="*60 + "\n\n"
        body = ""
        for item in sorted(news_items, key=lambda x: x.importance_score, reverse=True):
            body += f"[{item.grade}] [{item.press} - {item.page}] {item.title}\n{item.created_at}\n{item.link}\n\n{item.content}\n\n" + "-"*60 + "\n\n"
            
        full_text = content_header + body
        filename = f"{target_date}_summary.txt"
        
        self.storage.save_local_txt(full_text, filename)
        result_id = self.storage.upload_content_to_drive(full_text, filename)
        
        return ("Error" not in str(result_id)), str(result_id)

    def get_latest_alert_status(self) -> Dict[str, Any]:
        """Delegates alert status fetching to StorageService."""
        return self.storage.get_alert_status_uncached()
