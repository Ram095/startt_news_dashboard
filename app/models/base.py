# models/base.py
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json

class ArticleStatus(Enum):
    PULLED = "pulled"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"

class PublishStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"

@dataclass
class Article:
    id: Optional[int] = None
    display_id: Optional[str] = None
    title: str = ""
    url: str = ""
    source: str = ""
    author: str = "Unknown"
    date: Optional[datetime] = None
    category: str = "News"
    description: str = ""
    article_body: str = ""
    image_url: str = ""
    status: ArticleStatus = ArticleStatus.PULLED
    content_hash: str = ""
    quality_score: int = 0
    ai_tags: List[str] = field(default_factory=list)
    ai_summary: str = ""
    sentiment_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None

@dataclass
class ScraperRun:
    scraper_name: str
    status: str
    articles_found: int = 0
    new_articles: int = 0
    duplicates_found: int = 0
    duration_seconds: float = 0.0
    error_message: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

@dataclass
class PublishResult:
    status: PublishStatus
    article_id: int
    platform: str
    published_url: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    id: Optional[int] = None
    created_at: Optional[datetime] = None

@dataclass
class ActivityLog:
    id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    activity_type: str = ""
    details: str = ""
    status: str = "success"


