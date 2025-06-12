from typing import List, Optional, Dict, Any, Tuple
import json
from datetime import datetime, timedelta
import logging
from collections import Counter
from models.base import Article, ArticleStatus, ScraperRun, PublishResult
from database.sqlite_manager import SQLiteManager
from utils.ui_logger import UILogger

logger = logging.getLogger(__name__)

class ArticleRepository:
    def __init__(self, db_manager: SQLiteManager, ui_logger: UILogger):
        self.db = db_manager
        self.ui_logger = ui_logger
    
    def _get_next_display_id(self) -> str:
        """Generates the next display_id in the format 'st-n-X'."""
        try:
            query = "SELECT display_id FROM articles WHERE display_id LIKE 'st-n-%' ORDER BY id DESC LIMIT 1"
            result = self.db.execute_query(query)
            if result:
                last_id = result[0]['display_id']
                last_num = int(last_id.split('-')[-1])
                return f"st-n-{last_num + 1}"
            return "st-n-1"
        except Exception as e:
            logger.error(f"Could not generate next display ID: {e}")
            # Fallback to a timestamp-based unique ID
            return f"st-n-err-{int(datetime.now().timestamp())}"

    def save_article(self, article: Article) -> Tuple[bool, str]:
        """Saves a new article to the database, handling uniqueness."""
        self.ui_logger.log(f"Attempting to save article: {article.url}")
        
        # First, check for existing hash
        self.ui_logger.log(f"Checking for duplicate hash: {article.content_hash}")
        if self.get_article_by_hash(article.content_hash):
            self.ui_logger.log("-> Result: Duplicate hash found.")
            return False, "duplicate_hash"
        
        # Then, check for existing URL
        self.ui_logger.log(f"Checking for duplicate URL: {article.url}")
        query_url = "SELECT id FROM articles WHERE url = ?"
        if self.db.execute_query(query_url, (article.url,)):
            self.ui_logger.log("-> Result: Duplicate URL found.")
            return False, "duplicate_url"
            
        # If no duplicates, insert the new article
        self.ui_logger.log("No duplicates found. Proceeding to add article to DB.")
        try:
            query = """
                INSERT INTO articles (
                    title, url, source, author, date, category, description,
                    article_body, status, image_url, quality_score, ai_tags,
                    ai_summary, sentiment_score, content_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                article.title,
                article.url,
                article.source,
                article.author,
                article.date,
                article.category,
                article.description,
                article.article_body,
                article.status.value,
                article.image_url,
                article.quality_score,
                json.dumps(article.ai_tags) if article.ai_tags else None,
                article.ai_summary,
                article.sentiment_score,
                article.content_hash,
                article.created_at
            )
            
            last_id = self.db.execute_update(query, params)
            if last_id:
                self.ui_logger.log(f"-> Result: Successfully added article with DB ID {last_id}.")
                # Assign the new ID back to the article object
                article.id = last_id
                # Generate a user-friendly display ID
                display_id = f"st-n-{last_id}"
                update_query = "UPDATE articles SET display_id = ? WHERE id = ?"
                self.db.execute_update(update_query, (display_id, last_id))
                article.display_id = display_id
                self.log_activity("Article Save", f"Saved article: {article.title}")
                return True, "success"
            
            self.ui_logger.log("-> Result: Database insert failed.")
            return False, "db_insert_failed"
            
        except Exception as e:
            logger.error(f"Error saving article: {e}")
            self.ui_logger.log(f"-> Result: Error during save: {str(e)}")
            return False, "db_error"

    def get_articles(self, **filters: Any) -> List[Article]:
        """Retrieves articles with flexible filtering."""
        query = "SELECT * FROM articles WHERE 1=1"
        params = []

        if filters.get('status_filter'):
            query += " AND status = ?"
            params.append(filters['status_filter'])
        if filters.get('source_filter'):
            placeholders = ','.join('?' for _ in filters['source_filter'])
            query += f" AND source IN ({placeholders})"
            params.extend(filters['source_filter'])
        if filters.get('search_term'):
            term = f"%{filters['search_term']}%"
            query += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([term, term])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([filters.get('limit', 100), filters.get('offset', 0)])
        
        try:
            rows = self.db.execute_query(query, tuple(params))
            return [self._row_to_article(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting articles: {e}")
            return []

    def get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Retrieves a single article by its primary key ID."""
        try:
            row = self.db.execute_query("SELECT * FROM articles WHERE id = ?", (article_id,))
            return self._row_to_article(row[0]) if row else None
        except Exception as e:
            logger.error(f"Error getting article by ID {article_id}: {e}")
            return None

    def update_article_status(self, article_ids: List[int], new_status: ArticleStatus) -> bool:
        """Updates the status of one or more articles."""
        if not article_ids:
            return False
        
        try:
            placeholders = ','.join('?' for _ in article_ids)
            query = f"UPDATE articles SET status = ? WHERE id IN ({placeholders})"
            params = [new_status.value] + article_ids

            if new_status == ArticleStatus.PUBLISHED:
                query = f"UPDATE articles SET status = ?, published_at = ? WHERE id IN ({placeholders})"
                params = [new_status.value, datetime.now()] + article_ids
            
            self.db.execute_update(query, tuple(params))
            self.log_activity("Status Update", f"Updated {len(article_ids)} articles to {new_status.value}.")
            return True
        except Exception as e:
            logger.error(f"Error updating article status: {e}")
            return False

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Gathers various statistics for the main dashboard."""
        try:
            stats = {}
            # Total articles, status counts, source counts
            stats['total_articles'] = self.db.execute_query("SELECT COUNT(*) as c FROM articles")[0]['c']
            stats['status_counts'] = {r['status']: r['c'] for r in self.db.execute_query("SELECT status, COUNT(*) as c FROM articles GROUP BY status")}
            stats['source_counts'] = {r['source']: r['c'] for r in self.db.execute_query("SELECT source, COUNT(*) as c FROM articles GROUP BY source")}

            # Pulled in last 24 hours
            yesterday = datetime.now() - timedelta(days=1)
            stats['recent_articles'] = self.db.execute_query("SELECT COUNT(*) as c FROM articles WHERE created_at >= ?", (yesterday,))[0]['c']
            
            # Published today
            today_start = datetime.now().replace(hour=0, minute=0, second=0)
            stats['published_today'] = self.db.execute_query("SELECT COUNT(*) as c FROM articles WHERE published_at >= ?", (today_start,))[0]['c']
            
            return stats
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {}

    def get_distinct_sources(self) -> List[str]:
        """Gets a list of all unique source names."""
        try:
            rows = self.db.execute_query("SELECT DISTINCT source FROM articles WHERE source IS NOT NULL ORDER BY source")
            return [row['source'] for row in rows]
        except Exception as e:
            logger.error(f"Error getting distinct sources: {e}")
            return []
            
    def log_activity(self, activity_type: str, details: str, status: str = "success"):
        """Logs a generic activity to the activity_logs table."""
        try:
            query = "INSERT INTO activity_logs (activity_type, details, status) VALUES (?, ?, ?)"
            self.db.execute_update(query, (activity_type, details, status))
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def get_activity_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves the most recent activity logs."""
        try:
            query = "SELECT timestamp, activity_type, details, status FROM activity_logs ORDER BY timestamp DESC LIMIT ?"
            return self.db.execute_query(query, (limit,))
        except Exception as e:
            logger.error(f"Error getting activity logs: {e}")
            return []

    def _row_to_article(self, row: Dict[str, Any]) -> Article:
        """Convert a database row to an Article object"""
        try:
            # Handle datetime parsing - only use date part
            published_at = None
            if row.get('published_at'):
                try:
                    # Just parse the date part (YYYY-MM-DD)
                    date_str = row['published_at'].split()[0]  # Get just the date part
                    published_at = datetime.strptime(date_str, '%Y-%m-%d')
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse published_at date: {row['published_at']}")
            
            # Parse article date similarly
            article_date = None
            if row.get('date'):
                try:
                    date_str = row['date'].split()[0]  # Get just the date part
                    article_date = datetime.strptime(date_str, '%Y-%m-%d')
                except (ValueError, IndexError):
                    logger.warning(f"Could not parse article date: {row['date']}")
            
            return Article(
                id=row['id'],
                title=row['title'],
                url=row['url'],
                source=row['source'],
                author=row.get('author'),
                date=article_date,
                published_at=published_at,
                article_body=row.get('article_body', ''),
                description=row.get('description', ''),
                category=row.get('category'),
                status=ArticleStatus(row['status']) if row.get('status') else ArticleStatus.PENDING,
                ai_summary=row.get('ai_summary'),
                ai_tags=row.get('ai_tags', []),
                quality_score=row.get('quality_score'),
                sentiment_score=row.get('sentiment_score'),
                image_url=row.get('image_url')
            )
        except Exception as e:
            logger.error(f"Error converting row to article: {e}")
            logger.error(f"Row data: {row}")
            raise

    def add_article(self, article: Article) -> Optional[int]:
        """Adds a new article to the database."""
        query = """
            INSERT INTO articles (
                title, url, source, author, date, category, description,
                article_body, image_url, status, content_hash, quality_score,
                ai_tags, ai_summary, sentiment_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            article.title, article.url, article.source, article.author,
            article.date.strftime('%Y-%m-%d %H:%M:%S') if article.date else None,
            article.category, article.description, article.article_body,
            article.image_url, article.status.value, article.content_hash,
            article.quality_score, json.dumps(article.ai_tags),
            article.ai_summary, article.sentiment_score
        )
        try:
            last_id = self.db.execute_update(query, params)
            if last_id:
                self.log_activity("Article Added", f"New article '{article.title[:50]}...' added from {article.source}.")
                self.db.commit()
            return last_id
        except Exception as e:
            logger.error(f"Failed to add article {article.url}: {e}")
            return None

    def get_article_by_hash(self, content_hash: str) -> Optional[Article]:
        query = "SELECT * FROM articles WHERE content_hash = ?"
        result = self.db.execute_query(query, (content_hash,))
        return self._row_to_article(result[0]) if result else None

    def get_articles(self, status_filter: Optional[str] = None, source_filter: Optional[List[str]] = None, search_term: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Article]:
        query = "SELECT * FROM articles"
        conditions = []
        params = []

        if status_filter:
            conditions.append("status = ?")
            params.append(status_filter)
        if source_filter:
            placeholders = ','.join('?' for _ in source_filter)
            conditions.append(f"source IN ({placeholders})")
            params.extend(source_filter)
        if search_term:
            conditions.append("(title LIKE ? OR description LIKE ? OR ai_summary LIKE ?)")
            term = f"%{search_term}%"
            params.extend([term, term, term])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        results = self.db.execute_query(query, tuple(params))
        return [self._row_to_article(row) for row in results]

    def update_article_status(self, article_ids: List[int], status: ArticleStatus) -> bool:
        if not article_ids:
            return False
        placeholders = ','.join('?' for _ in article_ids)
        query = f"UPDATE articles SET status = ?, published_at = ? WHERE id IN ({placeholders})"
        
        now = datetime.now() if status == ArticleStatus.PUBLISHED else None
        params = [status.value, now] + article_ids
        
        try:
            self.db.execute_update(query, tuple(params))
            self.log_activity("Status Update", f"Updated {len(article_ids)} articles to '{status.value}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to update article status: {e}")
            return False

    def get_distinct_sources(self) -> List[str]:
        query = "SELECT DISTINCT source FROM articles"
        results = self.db.execute_query(query)
        return [row['source'] for row in results if row['source']]

    def get_dashboard_stats(self) -> Dict[str, Any]:
        stats = {}
        
        # Total articles
        total_query = "SELECT COUNT(*) as total FROM articles"
        stats['total_articles'] = self.db.execute_query(total_query)[0]['total']
        
        # Recent articles (last 24h)
        recent_query = "SELECT COUNT(*) as total FROM articles WHERE created_at >= date('now', '-1 day')"
        stats['recent_articles'] = self.db.execute_query(recent_query)[0]['total']

        # Published today
        pub_query = "SELECT COUNT(*) as total FROM articles WHERE status = 'published' AND date(published_at) = date('now')"
        stats['published_today'] = self.db.execute_query(pub_query)[0]['total']

        # Status counts
        status_query = "SELECT status, COUNT(*) as count FROM articles GROUP BY status"
        stats['status_counts'] = {row['status']: row['count'] for row in self.db.execute_query(status_query)}

        # Source counts
        source_query = "SELECT source, COUNT(*) as count FROM articles GROUP BY source"
        stats['source_counts'] = {row['source']: row['count'] for row in self.db.execute_query(source_query)}

        return stats
    
    def log_activity(self, activity_type: str, details: str, status: str = "success"):
        query = "INSERT INTO activity_logs (activity_type, details, status) VALUES (?, ?, ?)"
        self.db.execute_update(query, (activity_type, details, status))
        
    def get_activity_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        query = "SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT ?"
        return self.db.execute_query(query, (limit,))

    def clear_all_articles(self) -> bool:
        """Deletes all articles from the articles table."""
        try:
            self.db.execute_update("DELETE FROM articles")
            # Optional: Reset the autoincrement sequence for a clean slate
            self.db.execute_update("DELETE FROM sqlite_sequence WHERE name='articles'")
            self.db.commit()
            self.log_activity("Database Cleared", "All articles were deleted from the database.")
            logger.info("All articles have been cleared from the database.")
            return True
        except Exception as e:
            logger.error(f"Failed to clear articles table: {e}")
            return False

    def update_article_analysis(self, article_id: int, analysis) -> bool:
        """Updates an article with new analysis data from ContentAnalyzer."""
        try:
            query = """
                UPDATE articles
                SET
                    ai_summary = ?,
                    ai_tags = ?,
                    category = ?,
                    quality_score = ?,
                    sentiment_score = ?
                WHERE id = ?
            """
            params = (
                analysis.ai_summary,
                json.dumps(analysis.ai_tags),
                analysis.topic_category,
                analysis.quality_score,
                analysis.sentiment_score,
                article_id
            )
            self.db.execute_update(query, params)
            self.log_activity("AI Enhancement", f"Enhanced article ID {article_id} with new AI insights.")
            return True
        except Exception as e:
            logger.error(f"Error updating article analysis for ID {article_id}: {e}")
            return False