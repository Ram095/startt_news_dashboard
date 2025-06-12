# api/publisher.py
import requests
import time
import logging
import json
import base64
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
import streamlit as st

from models.base import Article, PublishResult, PublishStatus
from repository.repository import ArticleRepository

logger = logging.getLogger(__name__)

@dataclass
class PublishingPlatform:
    name: str
    enabled: bool
    endpoint: str
    auth_config: Dict[str, str]
    default_settings: Dict[str, Any]

@dataclass
class PublishResult:
    status: PublishStatus
    article_id: int
    article_title: str
    platform: str
    external_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    published_url: Optional[str] = None

class APIPublisher:
    def __init__(self, config: Dict[str, Any], repository: ArticleRepository):
        self.config = config
        self.repository = repository
        self.platforms = self._load_publishing_platforms()
        self.max_retries = 3
        self.retry_delay = 5
    
    def _load_publishing_platforms(self) -> Dict[str, PublishingPlatform]:
        """Load publishing platform configurations"""
        platforms = {}
        publishing_config = self.config.get('publishing', {})
        for platform_name, platform_config in publishing_config.items():
            if platform_config.get('enabled', False):
                platforms[platform_name] = PublishingPlatform(
                    name=platform_name,
                    enabled=True,
                    endpoint=platform_config['endpoint'],
                    auth_config=platform_config.get('auth', {}),
                    default_settings=platform_config.get('defaults', {})
                )
        
        return platforms
    
    def is_platform_enabled(self, platform: str) -> bool:
        """Checks if a given publishing platform is enabled in the config."""
        return self.config.get('publishing', {}).get(platform, {}).get('enabled', False)

    def publish_articles(self, article_ids: List[int], platform: str) -> List[PublishResult]:
        """Publish multiple articles to specified platform"""
        if not self.is_platform_enabled(platform):
            logger.warning(f"Publishing platform '{platform}' is not enabled.")
            return []

        results = []
        for article_id in article_ids:
            article = self.repository.get_article_by_id(article_id)
            print(f"Article: {article}")
            if article:
                result = self._publish_single_article(article, platform)
                results.append(result)
                # Log the outcome
                status = "success" if result.status == PublishStatus.SUCCESS else "error"
                details = f"Published to {platform}."
                if result.error_message:
                    details += f" Error: {result.error_message}"
                self.repository.log_activity("Article Publish", details, status)
            else:
                logger.warning(f"Could not find article with ID {article_id} to publish.")
        return results
    
    def _publish_single_article(self, article: Article, platform: str) -> PublishResult:
        """Publish a single article with retry logic"""
        platform_config = self.platforms[platform]
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Publishing article {article.id} to {platform} (attempt {attempt + 1})")
                
                if platform == 'wordpress':
                    result = self._publish_to_wordpress(article, platform_config)
                elif platform == 'custom_api':
                    result = self._publish_to_custom_api(article, platform_config)
                elif platform == 'ghost':
                    result = self._publish_to_ghost(article, platform_config)
                elif platform == 'webhook':
                    result = self._publish_to_webhook(article, platform_config)
                else:
                    return PublishResult(
                        article_id=article.id,
                        article_title=article.title,
                        platform=platform,
                        status=PublishStatus.FAILED,
                        error_message=f"Unknown platform type: {platform}"
                    )
                
                if result.status == PublishStatus.SUCCESS:
                    logger.info(f"Successfully published article {article.id} to {platform}")
                    return result
                elif result.status == PublishStatus.FAILED and attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed for article {article.id}: {result.error_message}")
                    time.sleep(self.retry_delay * (attempt + 1))
                    result.retry_count = attempt + 1
                else:
                    return result
                    
            except Exception as e:
                logger.error(f"Unexpected error publishing article {article.id}: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    return PublishResult(
                        article_id=article.id,
                        article_title=article.title,
                        platform=platform,
                        status=PublishStatus.FAILED,
                        error_message=str(e),
                        retry_count=attempt + 1
                    )
        
        return PublishResult(
            article_id=article.id,
            article_title=article.title,
            platform=platform,
            status=PublishStatus.FAILED,
            error_message="Max retries exceeded"
        )
    
    def _publish_to_wordpress(self, article: Article, platform: PublishingPlatform) -> PublishResult:
        """Publish to WordPress using REST API"""
        try:
            auth = platform.auth_config
            
            # Prepare post data
            post_data = {
                'title': article.title,
                'content': self._format_article_content(article),
                'status': platform.default_settings.get('status', 'draft'),
                'categories': [platform.default_settings.get('category_id', 1)],
                'excerpt': article.ai_summary or article.description[:150],
                'tags': article.ai_tags,
                'meta': {
                    'source_url': article.url,
                    'source_name': article.source,
                    'original_author': article.author,
                    'original_date': article.date,
                    'quality_score': article.quality_score,
                    'sentiment_score': article.sentiment_score
                }
            }
            
            # Set up authentication
            if 'username' in auth and 'password' in auth:
                credentials = base64.b64encode(f"{auth['username']}:{auth['password']}".encode()).decode()
                headers = {
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/json'
                }
            elif 'api_key' in auth:
                headers = {
                    'Authorization': f'Bearer {auth["api_key"]}',
                    'Content-Type': 'application/json'
                }
            else:
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.FAILED,
                    error_message="No valid authentication configured"
                )
            
            response = requests.post(platform.endpoint, json=post_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                wp_post = response.json()
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.SUCCESS,
                    external_id=str(wp_post.get('id')),
                    published_url=wp_post.get('link')
                )
            else:
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.FAILED,
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return PublishResult(
                article_id=article.id,
                article_title=article.title,
                platform=platform.name,
                status=PublishStatus.FAILED,
                error_message=str(e)
            )
    
    def _publish_to_custom_api(self, article: Article, platform: PublishingPlatform) -> PublishResult:
        """Publish to custom API"""
        try:
            auth = platform.auth_config
                
            # Prepare article data according to the /v1/article endpoint specification
            article_data = {
                'title': article.title,
                'description': article.description,
                'redirect_url': article.url,
                'source': article.source,
                'image_url': article.image_url if hasattr(article, 'image_url') else None,
                'active': True,
                'category': article.category.lower() if article.category else 'general',
                'created_at': article.date.isoformat() if article.date else datetime.now().isoformat()
            }
            
            # Set up headers
            headers = {'Content-Type': 'application/json'}
            if 'api_key' in auth:
                if 'id_token' in st.session_state:
                    headers['Authorization'] = f"Bearer {st.session_state['id_token']}"
                else:
                    headers['Authorization'] = f"Bearer {auth['api_key']}"
            if 'custom_headers' in platform.default_settings:
                headers.update(platform.default_settings['custom_headers'])
            
            
            # Use the backend API URL from environment
            endpoint = f"{os.getenv('BACKEND_API_URL', '').rstrip('/')}/v1/article"
            
            response = requests.post(endpoint, json=article_data, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                api_response = response.json()
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.SUCCESS,
                    external_id=str(api_response.get('id', '')),
                    published_url=api_response.get('url', '')
                )
            elif response.status_code == 409:
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.SKIPPED,
                    error_message="Article has already been published"
                )
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.FAILED,
                    error_message=error_msg
                )
                
        except Exception as e:
            return PublishResult(
                article_id=article.id,
                article_title=article.title,
                platform=platform.name,
                status=PublishStatus.FAILED,
                error_message=str(e)
            )
    
    def _publish_to_ghost(self, article: Article, platform: PublishingPlatform) -> PublishResult:
        """Publish to Ghost CMS"""
        try:
            # Ghost implementation would go here
            # This is a placeholder for Ghost-specific publishing logic
            return PublishResult(
                article_id=article.id,
                article_title=article.title,
                platform=platform.name,
                status=PublishStatus.SKIPPED,
                error_message="Ghost publishing not implemented yet"
            )
        except Exception as e:
            return PublishResult(
                article_id=article.id,
                article_title=article.title,
                platform=platform.name,
                status=PublishStatus.FAILED,
                error_message=str(e)
            )
    
    def _publish_to_webhook(self, article: Article, platform: PublishingPlatform) -> PublishResult:
        """Publish via webhook"""
        try:
            # Prepare webhook payload
            payload = {
                'event': 'article.published',
                'timestamp': datetime.now().isoformat(),
                'article': {
                    'id': article.id,
                    'title': article.title,
                    'content': article.article_body,
                    'description': article.description,
                    'summary': article.ai_summary,
                    'tags': article.ai_tags,
                    'source_url': article.url,
                    'source_name': article.source,
                    'author': article.author,
                    'category': article.category,
                    'quality_score': article.quality_score,
                    'sentiment_score': article.sentiment_score
                }
            }
            
            headers = {'Content-Type': 'application/json'}
            if 'secret' in platform.auth_config:
                # Add signature for webhook verification
                secret = platform.auth_config['secret']
                payload_str = json.dumps(payload, sort_keys=True)
                signature = hashlib.sha256((payload_str + secret).encode()).hexdigest()
                headers['X-Webhook-Signature'] = signature
            
            response = requests.post(platform.endpoint, json=payload, headers=headers, timeout=30)
            
            if response.status_code in [200, 201, 202]:
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.SUCCESS,
                    external_id=f"webhook_{int(time.time())}"
                )
            else:
                return PublishResult(
                    article_id=article.id,
                    article_title=article.title,
                    platform=platform.name,
                    status=PublishStatus.FAILED,
                    error_message=f"HTTP {response.status_code}: {response.text[:200]}"
                )
                
        except Exception as e:
            return PublishResult(
                article_id=article.id,
                article_title=article.title,
                platform=platform.name,
                status=PublishStatus.FAILED,
                error_message=str(e)
            )
    
    def _format_article_content(self, article: Article) -> str:
        """Format article content for publishing"""
        content_parts = []
        
        # Add AI summary if available
        if article.ai_summary:
            content_parts.append(f"<div class='ai-summary'><strong>Summary:</strong> {article.ai_summary}</div>")
        
        # Add description if different from summary
        if article.description and article.description != article.ai_summary:
            content_parts.append(f"<p><strong>{article.description}</strong></p>")
        
        # Add main content
        if article.article_body:
            # Convert newlines to paragraphs
            paragraphs = article.article_body.split('\n\n')
            for para in paragraphs:
                if para.strip():
                    content_parts.append(f"<p>{para.strip()}</p>")
        
        # Add tags
        if article.ai_tags:
            tags_html = ' '.join([f'<span class="tag">#{tag}</span>' for tag in article.ai_tags])
            content_parts.append(f"<div class='article-tags'>{tags_html}</div>")
        
        # Add source attribution
        content_parts.append(
            f'<div class="source-attribution">'
            f'<p><em>Originally published on <a href="{article.url}" target="_blank">{article.source}</a></em></p>'
            f'<p><em>Author: {article.author}</em></p>'
            f'</div>'
        )
        
        return '\n'.join(content_parts)
    
    def _get_article_by_id(self, article_id: int) -> Optional[Article]:
        """Get article by ID from repository"""
        try:
            articles = self.repository.get_articles(limit=1)  # This would need to be modified to get by ID
            # For now, we'll need to add a get_by_id method to the repository
            # This is a placeholder
            return None
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            return None
    
    def get_publishing_stats(self) -> Dict[str, Any]:
        """Get publishing statistics"""
        # This would be implemented to get stats from the repository
        # Placeholder for now
        return {
            'total_published': 0,
            'recent_publishes': [],
            'platform_stats': {}
        }

# utils/logging_config.py
import logging
import logging.handlers
from pathlib import Path

def setup_logging(config: Dict[str, Any]):
    """Set up comprehensive logging"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO').upper())
    log_file = log_config.get('file', 'logs/news_dashboard.log')
    
    # Create logs directory if it doesn't exist
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Set up root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_file_handler = logging.handlers.RotatingFileHandler(
        log_file.replace('.log', '_errors.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=3
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_file_handler)