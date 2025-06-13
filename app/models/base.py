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
    id: int
    title: str
    url: str
    source: str
    article_body: str
    description: Optional[str] = None
    author: Optional[str] = None
    date: Optional[datetime] = None
    category: Optional[str] = None
    status: ArticleStatus = ArticleStatus.PULLED
    quality_score: Optional[float] = None
    sentiment_score: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_tags: Optional[List[str]] = None
    image_url: Optional[str] = None
    display_id: Optional[str] = None
    content_hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert Article object to a dictionary for serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'source': self.source,
            'article_body': self.article_body,
            'description': self.description,
            'author': self.author,
            'date': self.date.isoformat() if self.date else None,
            'category': self.category,
            'status': self.status.value,
            'quality_score': self.quality_score,
            'sentiment_score': self.sentiment_score,
            'ai_summary': self.ai_summary,
            'ai_tags': self.ai_tags,
            'image_url': self.image_url,
            'display_id': self.display_id,
            'content_hash': self.content_hash,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """Create an Article object from a dictionary"""
        # Convert string dates back to datetime objects
        if data.get('date'):
            data['date'] = datetime.fromisoformat(data['date'])
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('published_at'):
            data['published_at'] = datetime.fromisoformat(data['published_at'])
        
        # Convert status string back to enum
        if data.get('status'):
            data['status'] = ArticleStatus(data['status'])
        
        return cls(**data)

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


