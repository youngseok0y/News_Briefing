import os
import pandas as pd
from typing import List, Dict, Any, Tuple
from models.news_item import NewsItem
from scraper import NewsScraper
import utils

class NewsService:
    """Service to manage news scraping, processing, and cloud storage workflows."""
    
    def __init__(self, drive_folder_id: str, service_account_file: str):
        self.scraper = NewsScraper()
        self.drive_folder_id = drive_folder_id
        self.service_account_file = service_account_file
        self.kst = utils.KST

    def fetch_and_process_daily_news(self, target_date: str) -> List[NewsItem]:
        """Orchestrates the full scraping workflow for a specific date."""
        print(f"🔄 Starting news collection for {target_date}...")
        
        # 1. Fetch metadata
        raw_data = self.scraper.fetch_metadata()
        if not raw_data:
            return []
            
        # 2. Cleanup & Deduplicate
        df = pd.DataFrame(raw_data)
        df = df.drop_duplicates(subset=["링크"])
        unique_list = df.to_dict('records')
        
        # 3. Load full content
        processed_items = []
        for item in unique_list:
            body, date_str = self.scraper.get_article_details(item['링크'])
            # Map raw data to NewsItem model
            mapped_data = {
                '제목': item['제목'],
                '링크': item['링크'],
                '신문사': item['신문사'],
                '지면': item['지면'],
                '중요': item.get('중요', False),
                '중요도점수': item.get('중요도점수', 0),
                '중요도등급': item.get('중요도등급', '하'),
                '기사내용': body,
                'date': target_date,
                '등록일시': date_str
            }
            processed_items.append(NewsItem.from_dict(mapped_data))
            
        # 4. Save to local cache
        cache_path = os.path.join("daily", f"{target_date}_articles.json")
        utils.save_to_json([item.to_dict() for item in processed_items], cache_path)
        
        return processed_items

    def upload_for_notebook_lm(self, news_items: List[NewsItem], target_date: str) -> Tuple[bool, str]:
        """Formats and uploads news content for NotebookLM analysis."""
        if not news_items:
            return False, "No items to upload"
            
        # Build optimized text for AI analysis
        content_header = f"🗞️ AI News Briefing: Full Press Coverage ({target_date})\n"
        content_header += "="*60 + "\n\n"
        
        body = ""
        for item in news_items:
            body += f"[{item.grade}] [{item.press} - {item.page}] {item.title}\n"
            body += f"Timestamp: {item.created_at}\n"
            body += f"Link: {item.link}\n\n"
            body += f"{item.content}\n\n"
            body += "-"*60 + "\n\n"
            
        full_text = content_header + body
        filename = f"{target_date}_summary.txt"
        
        # Local save & Cloud upload
        utils.save_to_txt(full_text, os.path.join("daily", filename))
        result_id = utils.upload_to_drive(full_text, filename, self.drive_folder_id, self.service_account_file)
        
        if result_id and "Error" not in str(result_id):
            return True, result_id
        return False, str(result_id)

    def get_latest_alert_status(self) -> Dict[str, Any]:
        """Provides direct access to the latest breaking news alert status."""
        return utils.get_alert_status_uncached("alert_state.json", self.drive_folder_id, self.service_account_file)
