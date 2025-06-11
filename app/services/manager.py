# scraper/manager.py
import concurrent.futures
import subprocess
import sys
import os
import time
import logging
import pandas as pd
from typing import List, Dict, Optional, Any
from services.content_service import ContentService
from repository.repository import ArticleRepository
from utils.ui_logger import UILogger

logger = logging.getLogger(__name__)

class ScraperManager:
    def __init__(self, content_service: ContentService, repository: ArticleRepository, config: Dict[str, Any], ui_logger: UILogger):
        self.content_service = content_service
        self.repository = repository
        self.scraper_configs = self._load_scraper_configs(config)
        self.max_workers = config.get('scrapers', {}).get('max_workers', 3)
        self.ui_logger = ui_logger

    def _load_scraper_configs(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Loads scraper configurations from the main config file."""
        return config.get('scrapers', {}).get('sources', {})

    def run_scraper(self, scraper_name: str) -> Dict[str, Any]:
        """
        Runs a single, specified scraper script and processes its output.
        """
        start_time = time.time()
        
        def create_error_result(error_msg: str, status: str = 'failed') -> Dict[str, Any]:
            """Helper to create a consistent error dictionary."""
            duration = time.time() - start_time
            self.repository.log_activity(f"Data Pull Error: {scraper_name}", error_msg, "error")
            return {
                "status": status,
                "scraper_name": scraper_name,
                "error_message": error_msg,
                "duration": duration,
                "articles_found": 0,
                "new_articles": 0,
            }

        if scraper_name not in self.scraper_configs:
            return create_error_result("Configuration not found")

        config = self.scraper_configs[scraper_name]
        script_path = config.get('script_path')

        if not script_path or not os.path.exists(script_path):
            return create_error_result(f"Scraper script not found at {script_path}")

        try:
            # Run the scraper script as a subprocess
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True, timeout=config.get('timeout', 300),
                encoding='utf-8', errors='replace', env=env
            )
            
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, script_path, output=result.stdout, stderr=result.stderr)

            # Process the output CSV
            return self._process_output(scraper_name, config, time.time() - start_time)

        except subprocess.TimeoutExpired:
            return create_error_result(f"Timeout after {config.get('timeout', 300)}s.", status='timeout')
        except subprocess.CalledProcessError as e:
            # Capture stderr for better error reporting
            error_details = e.stderr or e.output or "No output from script."
            return create_error_result(f"Scraper script failed with return code {e.returncode}. Details: {error_details[:500]}")
        except Exception as e:
            return create_error_result(f"An unexpected error occurred: {str(e)}")

    def _process_output(self, scraper_name: str, config: Dict[str, Any], duration: float) -> Dict[str, Any]:
        """Reads the CSV output of a scraper and sends it to the ContentService."""
        csv_file = config.get('csv_output')
        if not csv_file or not os.path.exists(csv_file):
            return {
                "status": "failed",
                "scraper_name": scraper_name,
                "error_message": f"Output file not found: {csv_file}",
                "duration": duration,
                "articles_found": 0,
                "new_articles": 0,
            }

        try:
            self.ui_logger.log(f"Processing output file: {csv_file}")
            df = pd.read_csv(csv_file)
            articles_data = df.to_dict('records')
            self.ui_logger.log(f"Found {len(articles_data)} articles in CSV.")
            
            new_count = 0
            duplicate_count = 0
            
            for i, article_data in enumerate(articles_data):
                url = article_data.get('url', f"Article-{i}")
                self.ui_logger.log(f"--- Processing article {i+1}/{len(articles_data)} ({url}) ---")
                # Add source from config
                article_data['source'] = config.get('source_name', scraper_name)
                # Let the content service handle the rest
                is_new, result = self.content_service.process_article(article_data)
                self.ui_logger.log(f"-> Result from ContentService: is_new={is_new}, message='{result.get('message')}'")
                if is_new:
                    new_count += 1
                else:
                    duplicate_count += 1
            
            details = f"Found {len(articles_data)} articles. Added {new_count} new, {duplicate_count} duplicates."
            self.ui_logger.log(f"Finished processing for {scraper_name}. {details}")
            self.repository.log_activity("Data Pull", details, "success")
            
            return {
                "status": "succeeded",
                "scraper_name": scraper_name,
                "articles_found": len(articles_data),
                "new_articles": new_count,
                "duration": duration,
            }
        except Exception as e:
            error_msg = f"Error processing {csv_file} for {scraper_name}: {e}"
            self.repository.log_activity("Data Pull Error", error_msg, "error")
            return {
                "status": "failed",
                "scraper_name": scraper_name,
                "error_message": error_msg,
                "duration": duration,
                "articles_found": 0,
                "new_articles": 0,
            }
    
    @property
    def scrapers(self) -> Dict[str, Any]:
        """Returns the loaded scraper configurations."""
        return self.scraper_configs

