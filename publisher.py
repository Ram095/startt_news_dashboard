# api/publisher.py
import requests
import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime
import hashlib
import base64
from base import Article, PublishResult, PublishStatus
import streamlit as st
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)

class PublishStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"

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
    def __init__(self, config: Dict[str, Any]):
        self.publishing_config = config.get('publishing', {})
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    def is_platform_enabled(self, platform: str) -> bool:
        """Checks if a given publishing platform is enabled in the config."""
        return self.publishing_config.get(platform, {}).get('enabled', False)

    def publish_articles(self, article_ids: List[int], platform: str, repository) -> List[PublishResult]:
        """
        Publishes a list of articles by their IDs to a specified platform.
        It fetches article data from the provided repository.
        """
        if not self.is_platform_enabled(platform):
            logger.warning(f"Publishing platform '{platform}' is not enabled.")
            return []

        results = []
        for article_id in article_ids:
            article = repository.get_article_by_id(article_id)
            if article:
                result = self._publish_single_article(article, platform)
                results.append(result)
                # Log the outcome
                status = "success" if result.status == PublishStatus.SUCCESS else "error"
                details = f"Published to {platform}."
                if result.error_message:
                    details += f" Error: {result.error_message}"
                repository.log_activity("Article Publish", details, status)
            else:
                logger.warning(f"Could not find article with ID {article_id} to publish.")
        return results

    def _publish_single_article(self, article: Article, platform: str) -> PublishResult:
        """Manages the publishing process for a single article, including retries."""
        platform_conf = self.publishing_config.get(platform, {})
        
        for attempt in range(self.max_retries):
            try:
                endpoint = platform_conf.get('endpoint')
                if not endpoint:
                    raise ValueError("Endpoint is not configured for this platform.")

                headers = self._prepare_headers(platform_conf)
                payload = self._prepare_payload(article, platform_conf)

                response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
                response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)

                # If successful
                response_data = response.json()
                return PublishResult(
                    status=PublishStatus.SUCCESS,
                    article_id=article.id,
                    platform=platform,
                    published_url=response_data.get('url') or response_data.get('link')
                )

            except requests.exceptions.RequestException as e:
                logger.error(f"Publishing failed for article {article.id} on attempt {attempt + 1}: {e}")
                if attempt >= self.max_retries - 1:
                    return PublishResult(
                        status=PublishStatus.FAILED,
                        article_id=article.id,
                        platform=platform,
                        error_message=str(e)
                    )
        
        # This part should ideally not be reached, but as a fallback:
        return PublishResult(
            status=PublishStatus.FAILED,
            article_id=article.id,
            platform=platform,
            error_message="All retry attempts failed."
        )

    def _prepare_headers(self, config: Dict[str, Any]) -> Dict[str, str]:
        """Prepares request headers, including authentication."""
        headers = config.get('defaults', {}).get('custom_headers', {})
        auth_conf = config.get('auth', {})

        if auth_conf.get('api_key'):
            headers['Authorization'] = f"Bearer {auth_conf['api_key']}"
        elif auth_conf.get('username') and auth_conf.get('password'):
            # Basic Auth example, though less common for modern APIs
            from requests.auth import HTTPBasicAuth
            # This part is simplified; direct use in requests is better.
            # For simplicity, we assume an API key or other header token is used.
            pass

        return headers

    def _prepare_payload(self, article: Article, config: Dict[str, Any]) -> Dict[str, Any]:
        """Constructs the request payload based on platform-specific mapping."""
        payload_mapping = config.get('payload_mapping', {})
        if not payload_mapping:
            # Default payload structure if no mapping is provided
            return {
                "title": article.title,
                "content": article.article_body,
                "excerpt": article.description,
                "source_url": article.url,
                "tags": article.ai_tags,
                "category": article.category
            }
        
        payload = {}
        for dest_field, source_field in payload_mapping.items():
            # Handle nested fields if needed, e.g., "author.name"
            if '.' in source_field:
                parts = source_field.split('.')
                value = article
                for part in parts:
                    value = getattr(value, part, None)
                    if value is None:
                        break
                payload[dest_field] = value
            else:
                payload[dest_field] = getattr(article, source_field, None)
        
        # Include default fields from config
        payload.update(config.get('defaults', {}).get('payload_fields', {}))

        return payload

# Enhanced article repository with publishing tracking
class PublishingRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_publishing_tables()
    
    def _init_publishing_tables(self):
        """Initialize publishing-related tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS publishing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                platform TEXT,
                status TEXT,
                external_id TEXT,
                published_url TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (article_id) REFERENCES articles (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_publish_result(self, result: PublishResult):
        """Log publishing result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO publishing_logs (
                article_id, platform, status, external_id, 
                published_url, error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            result.article_id, result.platform, result.status.value,
            result.external_id, result.published_url, 
            result.error_message, result.retry_count
        ))
        
        conn.commit()
        conn.close()
    
    def get_publishing_stats(self) -> Dict:
        """Get publishing statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Overall stats
        cursor.execute('SELECT status, COUNT(*) FROM publishing_logs GROUP BY status')
        status_counts = dict(cursor.fetchall())
        
        # Recent publishes
        cursor.execute('''
            SELECT platform, status, COUNT(*) 
            FROM publishing_logs 
            WHERE created_at > datetime('now', '-24 hours')
            GROUP BY platform, status
        ''')
        recent_stats = cursor.fetchall()
        
        # Failed articles that need attention
        cursor.execute('''
            SELECT pl.article_id, a.title, pl.platform, pl.error_message, pl.created_at
            FROM publishing_logs pl
            JOIN articles a ON pl.article_id = a.id
            WHERE pl.status = 'failed'
            ORDER BY pl.created_at DESC
            LIMIT 10
        ''')
        failed_articles = cursor.fetchall()
        
        conn.close()
        
        return {
            'status_counts': status_counts,
            'recent_stats': recent_stats,
            'failed_articles': failed_articles
        }

# Usage in Streamlit app
def add_publishing_tab_to_streamlit(repo: PublishingRepository, publisher: APIPublisher):
    """Add publishing functionality to Streamlit app"""
    
    with st.tab("🚀 Publishing"):
        st.subheader("📤 Publish Articles")
        
        # Get approved articles
        approved_articles = repo.get_articles('approved')
        
        if not approved_articles:
            st.info("No approved articles available for publishing.")
            return
        
        # Platform selection
        available_platforms = []
        config = publisher.publishing_config
        for platform, platform_config in config.items():
            if platform_config.get('enabled', False):
                available_platforms.append(platform)
        
        if not available_platforms:
            st.warning("No publishing platforms are configured and enabled.")
            return
        
        selected_platform = st.selectbox("Select Platform", available_platforms)
        
        # Article selection
        selected_articles = st.multiselect(
            "Select articles to publish:",
            options=[a.id for a in approved_articles],
            format_func=lambda x: next(a.title for a in approved_articles if a.id == x)
        )
        
        if selected_articles and st.button("🚀 Publish Selected Articles"):
            # Convert to dict format for publisher
            articles_to_publish = [
                {
                    'id': a.id,
                    'title': a.title,
                    'article_body': a.article_body,
                    'description': a.description,
                    'url': a.url,
                    'source': a.source,
                    'author': a.author,
                    'category': a.category,
                    'date': a.date
                }
                for a in approved_articles if a.id in selected_articles
            ]
            
            with st.spinner("Publishing articles..."):
                results = publisher.publish_articles(selected_articles, selected_platform, repo)
            
            # Show results
            success_count = 0
            failed_count = 0
            
            for result in results:
                # Log result to database
                repo.log_publish_result(result)
                
                if result.status == PublishStatus.SUCCESS:
                    success_count += 1
                    st.success(f"✅ Published: {result.article_title}")
                    if result.published_url:
                        st.write(f"   📎 URL: {result.published_url}")
                else:
                    failed_count += 1
                    st.error(f"❌ Failed: {result.article_title}")
                    if result.error_message:
                        st.write(f"   🚨 Error: {result.error_message}")
            
            st.info(f"📊 Results: {success_count} published, {failed_count} failed")
        
        # Publishing statistics
        st.subheader("📊 Publishing Statistics")
        stats = repo.get_publishing_stats()
        
        if stats['status_counts']:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Published", stats['status_counts'].get('success', 0))
            with col2:
                st.metric("Failed", stats['status_counts'].get('failed', 0))
            with col3:
                st.metric("Retries", stats['status_counts'].get('retry', 0))
        
        # Recent failed articles
        if stats['failed_articles']:
            st.subheader("🚨 Recent Failures")
            failed_df = pd.DataFrame(stats['failed_articles'], 
                                   columns=['Article ID', 'Title', 'Platform', 'Error', 'Date'])
            st.dataframe(failed_df, use_container_width=True)