from typing import Tuple, Dict, Any, Optional
import uuid
from models.base import Article
from repository.repository import ArticleRepository
from services.content_analyzer import ContentAnalyzer, SemanticDeduplicator
from config.settings import Settings
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ContentService:
    def __init__(self, repository: ArticleRepository, analyzer: ContentAnalyzer, deduplicator: SemanticDeduplicator, settings: Settings):
        self.repository = repository
        self.analyzer = analyzer
        self.deduplicator = deduplicator
        self.settings = settings

    def process_article(self, article_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Main entry point for processing a pulled article.
        Handles content analysis, deduplication, and saving.
        """
        try:
            # 1. Flexible data extraction
            title = article_data.get('title') or article_data.get('Title')
            url = article_data.get('url') or article_data.get('URL')

            # 2. Basic validation
            if not title or not url:
                keys = list(article_data.keys())
                self.repository.ui_logger.log(f"Validation failed: Missing title or URL. Available keys: {keys}")
                return False, {"status": "error", "message": f"Missing title or URL. Available keys: {keys}"}

            # 3. Generate content hash (conditionally)
            if self.settings.is_deduplication_enabled():
                description = article_data.get('description') or article_data.get('Description', '')
                body = article_data.get('article_body') or article_data.get('ArticleBody', '')
                content_hash = self.deduplicator.generate_content_hash(title, description, body)
            else:
                # If deduplication is disabled, generate a unique hash to bypass it
                content_hash = str(uuid.uuid4())
            
            # 4. Content Analysis
            analysis = self.analyzer.analyze_content(
                title,
                article_data.get('description', ''), 
                article_data.get('article_body', ''), 
                article_data.get('source', '')
            )
            
            # 5. Create Article object
            article = Article(
                title=title,
                url=url,
                source=article_data.get('source', 'Unknown'),
                author=article_data.get('author') or article_data.get('Author', 'Unknown'),
                date=self._parse_date(article_data.get('date') or article_data.get('Date')),
                category=analysis.topic_category,
                description=article_data.get('description') or article_data.get('Description', ''),
                article_body=article_data.get('article_body') or article_data.get('ArticleBody', ''),
                image_url=article_data.get('image_url') or article_data.get('Image', ''),
                content_hash=content_hash,
                quality_score=analysis.quality_score,
                ai_tags=analysis.ai_tags,
                ai_summary=analysis.ai_summary,
                sentiment_score=analysis.sentiment_score
            )
            
            # 6. Save to database
            success, message = self.repository.save_article(article)
            
            if success:
                return True, {'status': 'success', 'message': 'Article processed and saved', 'article_id': article.id}
            elif message in ["duplicate_hash", "duplicate_url"]:
                return False, {'status': 'duplicate', 'message': f'Article already exists ({message}).'}
            else:
                return False, {'status': 'db_error', 'message': message}
                
        except Exception as e:
            logger.error(f"Error processing article '{title}': {e}", exc_info=True)
            return False, {'status': 'error', 'message': str(e)}

    def enhance_article(self, article: Article) -> bool:
        """
        Runs AI analysis on an existing article and updates it.
        """
        try:
            # 1. Perform content analysis
            analysis = self.analyzer.analyze_content(
                article.title,
                article.description,
                article.article_body,
                article.source
            )
            
            # 2. Update the article in the database with the new analysis
            success = self.repository.update_article_analysis(article.id, analysis)
            
            if success:
                logger.info(f"Successfully enhanced article ID: {article.id}")
                return True
            else:
                logger.error(f"Failed to update article ID: {article.id} with new analysis.")
                return False
        except Exception as e:
            logger.error(f"Error enhancing article ID {article.id}: {e}", exc_info=True)
            return False

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Safely parse date strings into datetime objects."""
        if not date_str or not isinstance(date_str, str):
            return None
        
        # Handle ordinal suffixes (e.g., "10th June, 2025")
        cleaned_date_str = date_str.replace('st,', ',').replace('nd,', ',').replace('rd,', ',').replace('th,', ',')

        # Add more formats here if needed
        for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%d', '%B %d, %Y / %H:%M', '%d %B, %Y'):
            try:
                return datetime.strptime(cleaned_date_str, fmt)
            except (ValueError, TypeError):
                continue
        logger.warning(f"Could not parse date: {date_str}")
        return None