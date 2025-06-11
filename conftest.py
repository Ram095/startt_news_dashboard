# tests/conftest.py
import pytest
import os
import tempfile
import shutil
from unittest.mock import Mock, patch
from datetime import datetime

# Add parent directory to path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import Settings
from database.sqlite_manager import SQLiteManager
from database.repository import ArticleRepository
from ai.content_analyzer import ContentAnalyzer, SemanticDeduplicator
from models.base import Article, ArticleStatus

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def test_config():
    """Test configuration"""
    return Settings({
        'database': {
            'type': 'sqlite',
            'name': ':memory:'
        },
        'ai': {
            'openai_api_key': 'test-key',
            'model': 'gpt-3.5-turbo',
            'enable_content_analysis': False
        },
        'deduplication': {
            'similarity_threshold': 0.85
        }
    })

@pytest.fixture
def db_manager(temp_dir):
    """Test database manager"""
    db_path = os.path.join(temp_dir, 'test.db')
    manager = SQLiteManager(db_path)
    return manager

@pytest.fixture
def repository(db_manager):
    """Test repository"""
    return ArticleRepository(db_manager)

@pytest.fixture
def sample_article():
    """Sample article for testing"""
    return Article(
        title="Test Startup Raises $10M Series A",
        url="https://example.com/test-article",
        source="TestSource",
        author="Test Author",
        date="2024-01-01",
        category="Funding",
        description="A test startup has raised $10M in Series A funding.",
        article_body="This is a test article about a startup raising funding. " * 20,
        image_url="https://example.com/image.jpg",
        status=ArticleStatus.SCRAPED
    )

@pytest.fixture
def mock_openai():
    """Mock OpenAI API responses"""
    with patch('openai.ChatCompletion.create') as mock:
        mock.return_value.choices = [
            Mock(message=Mock(content="""
                TAGS: startup, funding, series-a, investment, technology
                SUMMARY: A test startup has successfully raised $10M in Series A funding from investors.
                CATEGORY: funding
            """))
        ]
        yield mock

---

# tests/test_models.py
import pytest
from datetime import datetime
from models.base import Article, ArticleStatus, ScraperRun, PublishResult, PublishStatus

class TestArticle:
    def test_article_creation(self):
        article = Article(
            title="Test Article",
            url="https://example.com",
            source="TestSource"
        )
        
        assert article.title == "Test Article"
        assert article.url == "https://example.com"
        assert article.source == "TestSource"
        assert article.status == ArticleStatus.SCRAPED
        assert article.author == "Unknown"
    
    def test_article_status_enum(self):
        article = Article(
            title="Test",
            url="https://example.com",
            source="Test",
            status=ArticleStatus.APPROVED
        )
        
        assert article.status == ArticleStatus.APPROVED
        assert article.status.value == "approved"

class TestScraperRun:
    def test_scraper_run_creation(self):
        run = ScraperRun(
            scraper_name="test_scraper",
            status="success",
            articles_found=100,
            new_articles=50,
            duration_seconds=120.5
        )
        
        assert run.scraper_name == "test_scraper"
        assert run.articles_found == 100
        assert run.new_articles == 50
        assert run.duration_seconds == 120.5

class TestPublishResult:
    def test_publish_result_success(self):
        result = PublishResult(
            article_id=1,
            platform="wordpress",
            status=PublishStatus.SUCCESS,
            external_id="wp_123",
            published_url="https://site.com/article"
        )
        
        assert result.status == PublishStatus.SUCCESS
        assert result.external_id == "wp_123"
        assert result.published_url == "https://site.com/article"

---

# tests/test_repository.py
import pytest
from models.base import Article, ArticleStatus

class TestArticleRepository:
    def test_save_article(self, repository, sample_article):
        success, error = repository.save_article(sample_article)
        
        assert success is True
        assert error is None
        assert sample_article.id is not None
    
    def test_save_duplicate_article_by_url(self, repository, sample_article):
        # Save first article
        success1, _ = repository.save_article(sample_article)
        assert success1 is True
        
        # Try to save duplicate (same URL)
        duplicate_article = Article(
            title="Different Title",
            url=sample_article.url,  # Same URL
            source="DifferentSource"
        )
        success2, error = repository.save_article(duplicate_article)
        
        assert success2 is False
        assert "duplicate" in error.lower()
    
    def test_get_articles_with_filters(self, repository):
        # Create test articles
        articles = [
            Article(title="Article 1", url="https://example.com/1", source="Source1", status=ArticleStatus.SCRAPED),
            Article(title="Article 2", url="https://example.com/2", source="Source2", status=ArticleStatus.APPROVED),
            Article(title="Article 3", url="https://example.com/3", source="Source1", status=ArticleStatus.PUBLISHED)
        ]
        
        for article in articles:
            repository.save_article(article)
        
        # Test status filter
        scraped_articles = repository.get_articles(status_filter="scraped")
        assert len(scraped_articles) == 1
        assert scraped_articles[0].status == ArticleStatus.SCRAPED
        
        # Test source filter
        source1_articles = repository.get_articles(source_filter=["Source1"])
        assert len(source1_articles) == 2
        
        # Test search
        search_results = repository.get_articles(search_term="Article 2")
        assert len(search_results) == 1
        assert search_results[0].title == "Article 2"
    
    def test_update_article_status(self, repository, sample_article):
        repository.save_article(sample_article)
        
        success = repository.update_article_status([sample_article.id], ArticleStatus.APPROVED)
        assert success is True
        
        # Verify status was updated
        articles = repository.get_articles(status_filter="approved")
        assert len(articles) == 1
        assert articles[0].id == sample_article.id
    
    def test_get_dashboard_stats(self, repository):
        # Create test data
        articles = [
            Article(title="Article 1", url="https://example.com/1", source="Source1", quality_score=80),
            Article(title="Article 2", url="https://example.com/2", source="Source2", quality_score=60),
            Article(title="Article 3", url="https://example.com/3", source="Source1", quality_score=90)
        ]
        
        for article in articles:
            repository.save_article(article)
        
        stats = repository.get_dashboard_stats()
        
        assert stats['total_articles'] == 3
        assert 'status_counts' in stats
        assert 'source_counts' in stats
        assert stats['source_counts']['Source1'] == 2
        assert stats['source_counts']['Source2'] == 1

---

# tests/test_content_analyzer.py
import pytest
from unittest.mock import patch
from ai.content_analyzer import ContentAnalyzer, SemanticDeduplicator

class TestContentAnalyzer:
    def test_quality_score_calculation(self):
        analyzer = ContentAnalyzer("", "gpt-3.5-turbo")
        
        # Test high quality content
        high_quality_score = analyzer._calculate_quality_score(
            title="Startup Raises $50M Series B Funding Round",
            description="A comprehensive description of the funding round with detailed information about the company and investors.",
            article_body="This is a well-written article with substantial content. " * 100  # Long content
        )
        
        assert high_quality_score > 70
        
        # Test low quality content
        low_quality_score = analyzer._calculate_quality_score(
            title="Short",
            description="Brief",
            article_body="Short content."
        )
        
        assert low_quality_score < 50
    
    def test_sentiment_analysis(self):
        analyzer = ContentAnalyzer("", "gpt-3.5-turbo")
        
        positive_sentiment = analyzer._analyze_sentiment("This is amazing and wonderful news!")
        assert positive_sentiment > 0
        
        negative_sentiment = analyzer._analyze_sentiment("This is terrible and awful news!")
        assert negative_sentiment < 0
        
        neutral_sentiment = analyzer._analyze_sentiment("This is neutral information.")
        assert abs(neutral_sentiment) < 0.5
    
    def test_basic_tag_generation(self):
        analyzer = ContentAnalyzer("", "gpt-3.5-turbo")
        
        content = "The startup raised funding in a Series A round with venture capital investment."
        tags = analyzer._generate_basic_tags(content)
        
        assert "funding" in tags
        assert "startup" in tags
    
    @patch('openai.ChatCompletion.create')
    def test_ai_insights_generation(self, mock_openai):
        mock_openai.return_value.choices = [
            type('Choice', (), {
                'message': type('Message', (), {
                    'content': """
                    TAGS: startup, funding, series-a, investment, technology
                    SUMMARY: Company raises significant funding for growth.
                    CATEGORY: funding
                    """
                })()
            })()
        ]
        
        analyzer = ContentAnalyzer("test-key", "gpt-3.5-turbo")
        
        tags, summary, category = analyzer._generate_ai_insights(
            "Startup Raises $10M",
            "Company secures funding",
            "Detailed article content..."
        )
        
        assert "startup" in tags
        assert "funding" in tags
        assert len(summary) > 0
        assert category == "funding"

class TestSemanticDeduplicator:
    def test_text_normalization(self):
        deduplicator = SemanticDeduplicator()
        
        text = "This is a TEST with CAPS and   extra   spaces!"
        normalized = deduplicator._normalize_text(text)
        
        assert normalized.islower()
        assert "  " not in normalized  # No double spaces
        assert "caps" in normalized
    
    def test_duplicate_detection(self):
        deduplicator = SemanticDeduplicator()
        
        # Test identical articles
        new_article = {
            'title': 'Startup Raises Funding',
            'description': 'Company gets investment',
            'article_body': 'Full article content here'
        }
        
        existing_articles = [{
            'id': 1,
            'title': 'Startup Raises Funding',
            'description': 'Company gets investment',
            'article_body': 'Full article content here'
        }]
        
        result = deduplicator.check_for_duplicates(new_article, existing_articles)
        
        assert result.is_duplicate is True
        assert result.similarity_score > 0.8
    
    def test_non_duplicate_detection(self):
        deduplicator = SemanticDeduplicator()
        
        new_article = {
            'title': 'New Product Launch',
            'description': 'Company launches innovative product',
            'article_body': 'Completely different content about product launch'
        }
        
        existing_articles = [{
            'id': 1,
            'title': 'Startup Raises Funding',
            'description': 'Company gets investment',
            'article_body': 'Full article content about funding'
        }]
        
        result = deduplicator.check_for_duplicates(new_article, existing_articles)
        
        assert result.is_duplicate is False
        assert result.similarity_score < 0.5

---

# tests/test_scraper_manager.py
import pytest
import tempfile
import os
from unittest.mock import Mock, patch
from scraper.manager import ScraperManager, ScraperConfig

class TestScraperManager:
    def test_scraper_config_loading(self):
        config = {
            'scrapers': {
                'max_workers': 2,
                'sources': {
                    'test_scraper': {
                        'script_path': 'test.py',
                        'csv_output': 'test.csv',
                        'source_name': 'TestSource'
                    }
                }
            }
        }
        
        # Mock dependencies
        content_service = Mock()
        repository = Mock()
        
        manager = ScraperManager(content_service, repository, config)
        
        assert 'test_scraper' in manager.scrapers
        assert manager.scrapers['test_scraper'].source_name == 'TestSource'
        assert manager.max_workers == 2
    
    def test_scraper_status_check(self):
        config = {
            'scrapers': {
                'sources': {
                    'existing_scraper': {
                        'script_path': __file__,  # This file exists
                        'csv_output': 'test.csv',
                        'source_name': 'TestSource'
                    },
                    'missing_scraper': {
                        'script_path': 'nonexistent.py',
                        'csv_output': 'test.csv',
                        'source_name': 'TestSource'
                    }
                }
            }
        }
        
        content_service = Mock()
        repository = Mock()
        
        manager = ScraperManager(content_service, repository, config)
        status = manager.get_scraper_status()
        
        assert status['existing_scraper']['script_exists'] is True
        assert status['missing_scraper']['script_exists'] is False

---

# tests/test_api_publisher.py
import pytest
from unittest.mock import Mock, patch
import requests
from api.publisher import APIPublisher
from models.base import Article, PublishResult, PublishStatus

class TestAPIPublisher:
    def test_platform_loading(self):
        config = {
            'publishing': {
                'wordpress': {
                    'enabled': True,
                    'endpoint': 'https://example.com/wp-json/wp/v2/posts',
                    'auth': {'username': 'user', 'password': 'pass'}
                },
                'disabled_platform': {
                    'enabled': False,
                    'endpoint': 'https://example.com/api'
                }
            }
        }
        
        repository = Mock()
        publisher = APIPublisher(config, repository)
        
        assert 'wordpress' in publisher.platforms
        assert 'disabled_platform' not in publisher.platforms
    
    @patch('requests.post')
    def test_wordpress_publishing_success(self, mock_post):
        # Mock successful WordPress response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {'id': 123, 'link': 'https://example.com/post/123'}
        mock_post.return_value = mock_response
        
        config = {
            'publishing': {
                'wordpress': {
                    'enabled': True,
                    'endpoint': 'https://example.com/wp-json/wp/v2/posts',
                    'auth': {'username': 'user', 'password': 'pass'},
                    'defaults': {'status': 'draft', 'category_id': 1}
                }
            }
        }
        
        repository = Mock()
        publisher = APIPublisher(config, repository)
        
        article = Article(
            id=1,
            title="Test Article",
            url="https://example.com/original",
            source="TestSource",
            article_body="Test content"
        )
        
        platform = publisher.platforms['wordpress']
        result = publisher._publish_to_wordpress(article, platform)
        
        assert result.status == PublishStatus.SUCCESS
        assert result.external_id == "123"
        assert result.published_url == "https://example.com/post/123"
    
    @patch('requests.post')
    def test_wordpress_publishing_failure(self, mock_post):
        # Mock failed WordPress response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response
        
        config = {
            'publishing': {
                'wordpress': {
                    'enabled': True,
                    'endpoint': 'https://example.com/wp-json/wp/v2/posts',
                    'auth': {'username': 'user', 'password': 'pass'}
                }
            }
        }
        
        repository = Mock()
        publisher = APIPublisher(config, repository)
        
        article = Article(
            id=1,
            title="Test Article",
            url="https://example.com/original",
            source="TestSource"
        )
        
        platform = publisher.platforms['wordpress']
        result = publisher._publish_to_wordpress(article, platform)
        
        assert result.status == PublishStatus.FAILED
        assert "400" in result.error_message

---

# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_news_dashboard
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Cache pip dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
        restore-keys: |
          ${{ runner.os }}-pip-
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -e ".[dev]"
    
    - name: Download NLTK data
      run: |
        python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
    
    - name: Lint with flake8
      run: |
        flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
        flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    
    - name: Type check with mypy
      run: |
        mypy --install-types --non-interactive || true
        mypy . --ignore-missing-imports
    
    - name: Format check with black
      run: |
        black --check .
    
    - name: Test with pytest
      env:
        DB_HOST: localhost
        DB_NAME: test_news_dashboard
        DB_USER: postgres
        DB_PASSWORD: postgres
        REDIS_HOST: localhost
        OPENAI_API_KEY: test-key
      run: |
        pytest --cov=. --cov-report=xml --cov-report=html
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false

  security:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install safety bandit
    
    - name: Security check with safety
      run: safety check --json
    
    - name: Security check with bandit
      run: bandit -r . -f json || true

  build:
    needs: [test, security]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    
    - name: Login to Docker Hub
      uses: docker/login-action@v3
      with:
        username: ${{ secrets.DOCKER_USERNAME }}
        password: ${{ secrets.DOCKER_PASSWORD }}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: |
          ${{ secrets.DOCKER_USERNAME }}/news-dashboard:latest
          ${{ secrets.DOCKER_USERNAME }}/news-dashboard:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Deploy to production
      run: |
        echo "Deployment would happen here"
        # Add your deployment script here
        # Example: kubectl apply -f k8s/
        # Or: ssh to server and docker-compose pull && docker-compose up -d

---

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict
      - id: debug-statements
      - id: requirements-txt-fixer

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=127, --extend-ignore=E203,W503]

  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: [--profile=black]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-PyYAML]
        args: [--ignore-missing-imports]

---

# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --disable-warnings
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    ai: marks tests that require AI/OpenAI API

---

# Makefile
.PHONY: help install test lint format clean docker-build docker-run deploy

help:
	@echo "Available commands:"
	@echo "  install     Install dependencies and setup environment"
	@echo "  test        Run all tests"
	@echo "  lint        Run linting checks"
	@echo "  format      Format code with black and isort"
	@echo "  clean       Clean up temporary files"
	@echo "  docker-build Build Docker image"
	@echo "  docker-run  Run with Docker Compose"
	@echo "  deploy      Deploy to production"

install:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e ".[dev]"
	pre-commit install
	python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

test:
	pytest --cov=. --cov-report=html --cov-report=term

test-fast:
	pytest -m "not slow" --cov=. --cov-report=term

lint:
	flake8 .
	mypy . --ignore-missing-imports
	black --check .
	isort --check-only .

format:
	black .
	isort .

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .coverage htmlcov/ .pytest_cache/ dist/ build/

docker-build:
	docker build -t news-dashboard .

docker-run:
	docker-compose up -d

docker-stop:
	docker-compose down

deploy:
	@echo "Deploying to production..."
	# Add deployment commands here

backup:
	./scripts/backup.sh

monitor:
	python scripts/monitor.py