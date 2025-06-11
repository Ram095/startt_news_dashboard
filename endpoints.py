# api/endpoints.py
from fastapi import FastAPI, HTTPException, Depends, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from base import Article, ArticleStatus
from database.repository import ArticleRepository
from scraper.manager import ScraperManager
from api.publisher import APIPublisher
from config.settings import Settings

# Initialize FastAPI app
app = FastAPI(
    title="News Dashboard API",
    description="Advanced AI-powered news aggregation and publishing API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Pydantic models for API
class ArticleResponse(BaseModel):
    id: int
    title: str
    url: str
    source: str
    author: str
    date: str
    category: str
    description: str
    status: str
    quality_score: int
    ai_tags: List[str]
    ai_summary: str
    sentiment_score: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class ArticleCreate(BaseModel):
    title: str = Field(..., max_length=500)
    url: str = Field(..., max_length=1000)
    source: str = Field(..., max_length=100)
    author: str = Field(default="Unknown", max_length=200)
    date: str = Field(default="")
    category: str = Field(default="News", max_length=100)
    description: str = Field(default="", max_length=2000)
    article_body: str = Field(default="", max_length=50000)
    image_url: str = Field(default="", max_length=1000)

class ArticleUpdate(BaseModel):
    status: Optional[str] = None
    ai_tags: Optional[List[str]] = None
    ai_summary: Optional[str] = None
    quality_score: Optional[int] = None

class ScraperRunRequest(BaseModel):
    scrapers: Optional[List[str]] = None
    
class PublishRequest(BaseModel):
    article_ids: List[int]
    platform: str

class DashboardStats(BaseModel):
    total_articles: int
    status_counts: Dict[str, int]
    source_counts: Dict[str, int]
    recent_articles: int
    quality_distribution: Dict[str, int]
    top_tags: Dict[str, int]

# Dependency injection
def get_repository() -> ArticleRepository:
    # This would be initialized from your main app
    # For now, returning a placeholder
    return app.state.repository

def get_scraper_manager() -> ScraperManager:
    return app.state.scraper_manager

def get_api_publisher() -> APIPublisher:
    return app.state.api_publisher

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API token (implement your auth logic here)"""
    token = credentials.credentials
    # Implement your token verification logic
    if token != "your-api-token":  # Replace with proper auth
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        repository = get_repository()
        stats = repository.get_dashboard_stats()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(),
            "database": "connected",
            "total_articles": stats.get('total_articles', 0)
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

# Articles endpoints
@app.get("/api/articles", response_model=List[ArticleResponse])
async def get_articles(
    status: Optional[str] = Query(None, description="Filter by status"),
    source: Optional[List[str]] = Query(None, description="Filter by source"),
    search: Optional[str] = Query(None, description="Search term"),
    limit: int = Query(100, ge=1, le=1000, description="Number of articles to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    repository: ArticleRepository = Depends(get_repository)
):
    """Get articles with filtering and pagination"""
    try:
        articles = repository.get_articles(
            status_filter=status,
            source_filter=source,
            search_term=search,
            limit=limit,
            offset=offset
        )
        return articles
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/articles/{article_id}", response_model=ArticleResponse)
async def get_article(
    article_id: int,
    repository: ArticleRepository = Depends(get_repository)
):
    """Get a specific article by ID"""
    try:
        articles = repository.get_articles(limit=1)  # This needs get_by_id method
        article = next((a for a in articles if a.id == article_id), None)
        
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/articles", response_model=ArticleResponse)
async def create_article(
    article_data: ArticleCreate,
    repository: ArticleRepository = Depends(get_repository),
    token: str = Depends(verify_token)
):
    """Create a new article"""
    try:
        article = Article(
            title=article_data.title,
            url=article_data.url,
            source=article_data.source,
            author=article_data.author,
            date=article_data.date,
            category=article_data.category,
            description=article_data.description,
            article_body=article_data.article_body,
            image_url=article_data.image_url
        )
        
        success, error = repository.save_article(article)
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
        
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating article: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/articles/{article_id}")
async def update_article(
    article_id: int,
    update_data: ArticleUpdate,
    repository: ArticleRepository = Depends(get_repository),
    token: str = Depends(verify_token)
):
    """Update an article"""
    try:
        if update_data.status:
            try:
                status = ArticleStatus(update_data.status)
                success = repository.update_article_status([article_id], status)
                if not success:
                    raise HTTPException(status_code=400, detail="Failed to update status")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid status")
        
        if any([update_data.ai_tags, update_data.ai_summary, update_data.quality_score]):
            success = repository.update_article_ai_data(
                article_id,
                update_data.ai_tags or [],
                update_data.ai_summary or "",
                0.0,  # sentiment score not provided in update
                update_data.quality_score or 0
            )
            if not success:
                raise HTTPException(status_code=400, detail="Failed to update AI data")
        
        return {"message": "Article updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/articles/{article_id}")
async def delete_article(
    article_id: int,
    repository: ArticleRepository = Depends(get_repository),
    token: str = Depends(verify_token)
):
    """Delete an article"""
    # This would require implementing a delete method in the repository
    raise HTTPException(status_code=501, detail="Delete functionality not implemented")

# Bulk operations
@app.put("/api/articles/bulk/status")
async def bulk_update_status(
    article_ids: List[int],
    status: str,
    repository: ArticleRepository = Depends(get_repository),
    token: str = Depends(verify_token)
):
    """Bulk update article status"""
    try:
        article_status = ArticleStatus(status)
        success = repository.update_article_status(article_ids, article_status)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update articles")
        
        return {"message": f"Updated {len(article_ids)} articles to {status}"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")
    except Exception as e:
        logger.error(f"Error bulk updating articles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Dashboard endpoints
@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    repository: ArticleRepository = Depends(get_repository)
):
    """Get dashboard statistics"""
    try:
        stats = repository.get_dashboard_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Scraper endpoints
@app.post("/api/scrapers/run")
async def run_scrapers(
    request: ScraperRunRequest,
    background_tasks: BackgroundTasks,
    scraper_manager: ScraperManager = Depends(get_scraper_manager),
    token: str = Depends(verify_token)
):
    """Run scrapers in the background"""
    try:
        # Run scrapers in background
        background_tasks.add_task(
            scraper_manager.run_all_scrapers,
            request.scrapers
        )
        
        return {"message": "Scrapers started in background"}
    except Exception as e:
        logger.error(f"Error running scrapers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/scrapers/status")
async def get_scraper_status(
    scraper_manager: ScraperManager = Depends(get_scraper_manager)
):
    """Get scraper status"""
    try:
        status = scraper_manager.get_scraper_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scraper status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Publishing endpoints
@app.post("/api/publish")
async def publish_articles(
    request: PublishRequest,
    background_tasks: BackgroundTasks,
    publisher: APIPublisher = Depends(get_api_publisher),
    token: str = Depends(verify_token)
):
    """Publish articles to specified platform"""
    try:
        # Publish in background
        background_tasks.add_task(
            publisher.publish_articles,
            request.article_ids,
            request.platform
        )
        
        return {"message": f"Publishing {len(request.article_ids)} articles to {request.platform}"}
    except Exception as e:
        logger.error(f"Error publishing articles: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/publish/stats")
async def get_publishing_stats(
    publisher: APIPublisher = Depends(get_api_publisher)
):
    """Get publishing statistics"""
    try:
        stats = publisher.get_publishing_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting publishing stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Initialize app state (call this from your main app)
def initialize_api(repository: ArticleRepository, scraper_manager: ScraperManager, api_publisher: APIPublisher):
    """Initialize API with dependencies"""
    app.state.repository = repository
    app.state.scraper_manager = scraper_manager
    app.state.api_publisher = api_publisher

#---

