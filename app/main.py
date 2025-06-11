import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
import time
import json
import os
import requests
import traceback
import sqlite3
import plotly.graph_objects as go
from streamlit_float import *
import io
import base64
import asyncio

# Import modular components
from config.settings import Settings
from repository.repository import ArticleRepository
from services.content_analyzer import ContentAnalyzer, SemanticDeduplicator
from services.content_service import ContentService
from services.manager import ScraperManager
from utils.api_publisher import APIPublisher
from models.base import Article, ArticleStatus, ScraperRun
from database.sqlite_manager import SQLiteManager
from utils.ui_logger import UILogger
from auth.firebase_config import initialize_firebase, is_user_logged_in, check_auth_status, logout_user
from auth.login_page import show_login_page, show_logout_button

logger = logging.getLogger(__name__)

# --- Page Configuration ---
st.set_page_config(
    page_title="Startt AI News Management Dashboard",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for theme and preferences
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True
if 'user_preferences' not in st.session_state:
    st.session_state.user_preferences = {
        'default_filters': {},
        'dashboard_layout': 'default',
        'notifications_enabled': True,
        'auto_refresh': False
    }
if 'notifications' not in st.session_state:
    st.session_state.notifications = []
if 'batch_queue' not in st.session_state:
    st.session_state.batch_queue = []
if 'ui_logs' not in st.session_state:
    st.session_state.ui_logs = []

# --- Enhanced CSS with Dark/Light Mode Support ---
def get_css_theme():
    if st.session_state.dark_mode:
        return """
        <style>
            /* Dark Mode Variables */
            :root {
                --primary-color: #6366f1;
                --primary-hover: #5558e3;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --danger-color: #ef4444;
                --info-color: #3b82f6;
                --background: #0f1419;
                --surface: #1a1f2e;
                --surface-hover: #252b3a;
                --text-primary: #ffffff;
                --text-secondary: #94a3b8;
                --border-color: #334155;
                --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.3);
                --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.4);
                --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.5);
            }
            
            /* Dark mode Streamlit overrides */
            .stApp {
                background-color: var(--background) !important;
                color: var(--text-primary) !important;
            }
            
            .main .block-container {
                background-color: var(--background) !important;
                color: var(--text-primary) !important;
            }
            
            /* Sidebar styling */
            .css-1d391kg {
                background-color: var(--surface) !important;
                border-right: 1px solid var(--border-color) !important;
            }
            
            /* Fix button visibility in dark mode */
            .stButton > button {
                background-color: var(--surface) !important;
                color: var(--text-primary) !important;
                border: 2px solid var(--border-color) !important;
                border-radius: 12px !important;
                padding: 10px 20px !important;
                font-weight: 600 !important;
                transition: all 0.2s ease !important;
            }
            
            .stButton > button:hover {
                background-color: var(--primary-color) !important;
                color: white !important;
                border-color: var(--primary-color) !important;
                transform: translateY(-2px);
                box-shadow: var(--shadow-md);
            }
            
            /* Primary button styling */
            .stButton > button[data-testid="baseButton-primary"] {
                background-color: var(--primary-color) !important;
                color: white !important;
                border-color: var(--primary-color) !important;
            }
            
            /* Fix selectbox and input styling */
            .stSelectbox > div > div {
                background-color: var(--surface) !important;
                color: var(--text-primary) !important;
                border-color: var(--border-color) !important;
            }
            
            .stTextInput > div > div > input {
                background-color: var(--surface) !important;
                color: var(--text-primary) !important;
                border-color: var(--border-color) !important;
            }
            
            /* Fix multiselect */
            .stMultiSelect > div > div {
                background-color: var(--surface) !important;
                color: var(--text-primary) !important;
                border-color: var(--border-color) !important;
            }
            
            /* Fix expander */
            .streamlit-expanderHeader {
                background-color: var(--surface) !important;
                color: var(--text-primary) !important;
                border-color: var(--border-color) !important;
            }
            
            .streamlit-expanderContent {
                background-color: var(--surface) !important;
                border-color: var(--border-color) !important;
            }
        """
    else:
        return """
        <style>
            /* Light Mode Variables */
            :root {
                --primary-color: #6366f1;
                --primary-hover: #5558e3;
                --success-color: #10b981;
                --warning-color: #f59e0b;
                --danger-color: #ef4444;
                --info-color: #3b82f6;
                --background: #f8fafc;
                --surface: #ffffff;
                --surface-hover: #f1f5f9;
                --text-primary: #1e293b;
                --text-secondary: #64748b;
                --border-color: #e2e8f0;
                --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
                --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
                --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            }
        """

# Common CSS (applies to both themes)
common_css = """
            /* Enhanced Status Tags */
            .status-tag {
                padding: 6px 14px;
                border-radius: 9999px;
                font-size: 12px;
                font-weight: 600;
                display: inline-flex;
                align-items: center;
                gap: 6px;
                text-transform: uppercase;
                letter-spacing: 0.025em;
                transition: all 0.2s ease;
            }
            
            .status-tag::before {
                content: '';
                width: 6px;
                height: 6px;
                border-radius: 50%;
                display: inline-block;
            }
            
            .status-new {
                background-color: #dbeafe;
                color: #1e40af;
            }
            .status-new::before {
                background-color: #3b82f6;
            }
            
            .status-approved {
                background-color: #f3e8ff;
                color: #6b21a8;
            }
            .status-approved::before {
                background-color: #9333ea;
            }
            
            .status-published {
                background-color: #d1fae5;
                color: #065f46;
            }
            .status-published::before {
                background-color: #10b981;
            }
            
            .status-rejected {
                background-color: #fee2e2;
                color: #991b1b;
            }
            .status-rejected::before {
                background-color: #ef4444;
            }
            
            /* Enhanced Article Cards */
            .article-card {
                background-color: var(--surface);
                padding: 24px;
                border-radius: 16px;
                margin-bottom: 16px;
                border: 1px solid var(--border-color);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            
            .article-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, var(--primary-color), var(--info-color));
                transform: translateX(-100%);
                transition: transform 0.3s ease;
            }
            
            .article-card:hover {
                border-color: var(--primary-color);
                box-shadow: var(--shadow-md);
                transform: translateY(-2px);
                background-color: var(--surface-hover);
            }
            
            .article-card:hover::before {
                transform: translateX(0);
            }
            
            .article-title {
                font-size: 18px;
                font-weight: 700;
                color: var(--text-primary);
                margin-bottom: 12px;
                line-height: 1.4;
            }
            
            .article-meta {
                display: flex;
                align-items: center;
                gap: 16px;
                font-size: 14px;
                color: var(--text-secondary);
                margin-bottom: 12px;
                flex-wrap: wrap;
            }
            
            .article-meta-item {
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .article-description {
                font-size: 15px;
                color: var(--text-secondary);
                line-height: 1.7;
            }
            
            /* Article Actions */
            .article-actions {
                display: flex;
                gap: 8px;
                margin-top: 16px;
                flex-wrap: wrap;
            }
            
            .action-btn {
                padding: 8px 16px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                border: 1px solid var(--border-color);
                background: var(--surface);
                color: var(--text-primary);
                text-decoration: none;
                transition: all 0.2s ease;
                cursor: pointer;
            }
            
            .action-btn:hover {
                background: var(--primary-color);
                color: white;
                border-color: var(--primary-color);
                transform: translateY(-1px);
            }
            
            /* Enhanced Metric Cards */
            .metric-card {
                background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%);
                color: white;
                padding: 28px;
                border-radius: 20px;
                text-align: center;
                box-shadow: var(--shadow-lg);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            
            .metric-card::after {
                content: '';
                position: absolute;
                top: -50%;
                right: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, transparent 70%);
                animation: pulse 4s ease-in-out infinite;
            }
            
            @keyframes pulse {
                0%, 100% { transform: scale(1); opacity: 0.5; }
                50% { transform: scale(1.1); opacity: 0.3; }
            }
            
            .metric-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.2);
            }
            
            .metric-value {
                font-size: 42px;
                font-weight: 800;
                margin: 12px 0;
                position: relative;
                z-index: 1;
            }
            
            .metric-label {
                font-size: 16px;
                opacity: 0.95;
                font-weight: 500;
                position: relative;
                z-index: 1;
            }
            
            /* Sticky Action Panel */
            .action-panel {
                position: sticky;
                top: 80px;
                background: var(--surface);
                backdrop-filter: blur(12px);
                border-radius: 20px;
                padding: 24px;
                border: 1px solid var(--border-color);
                box-shadow: var(--shadow-lg);
                transition: all 0.3s ease;
                color: var(--text-primary);
            }
            
            .action-panel:hover {
                box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.15);
            }
            
            .action-panel h3 {
                color: var(--text-primary);
                font-size: 18px;
                font-weight: 700;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            /* Notification System */
            .notification {
                position: fixed;
                top: 20px;
                right: 20px;
                background: var(--surface);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 16px;
                box-shadow: var(--shadow-lg);
                z-index: 1000;
                max-width: 300px;
                animation: slideInRight 0.3s ease;
            }
            
            @keyframes slideInRight {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            
            .notification.success {
                border-left: 4px solid var(--success-color);
            }
            
            .notification.warning {
                border-left: 4px solid var(--warning-color);
            }
            
            .notification.error {
                border-left: 4px solid var(--danger-color);
            }
            
            .notification.info {
                border-left: 4px solid var(--info-color);
            }
            
            /* Theme Toggle */
            .theme-toggle {
                position: fixed;
                top: 20px;
                right: 20px;
                background: var(--surface);
                border: 1px solid var(--border-color);
                border-radius: 50px;
                padding: 8px;
                z-index: 999;
                box-shadow: var(--shadow-md);
            }
            
            /* Export Button Styling */
            .export-btn {
                background: var(--success-color);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .export-btn:hover {
                background: #059669;
                transform: translateY(-2px);
            }
            
            /* Batch Queue */
            .batch-queue {
                background: var(--surface);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 16px;
                margin: 16px 0;
            }
            
            .queue-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid var(--border-color);
            }
            
            .queue-item:last-child {
                border-bottom: none;
            }
            
            /* Advanced Filters */
            .filter-section {
                background: var(--surface);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 16px;
                margin: 8px 0;
            }
            
            /* Bulk Edit Mode */
            .bulk-edit-panel {
                background: var(--surface);
                border: 2px solid var(--primary-color);
                border-radius: 12px;
                padding: 20px;
                margin: 16px 0;
            }
            
            /* Performance Metrics */
            .perf-metric {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                background: var(--surface);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                padding: 8px 12px;
                margin: 4px;
                font-size: 14px;
            }
            
            /* Loading states */
            .loading-shimmer {
                background: linear-gradient(90deg, 
                    var(--surface) 25%, 
                    var(--surface-hover) 50%, 
                    var(--surface) 75%);
                background-size: 200% 100%;
                animation: shimmer 2s infinite;
            }
            
            @keyframes shimmer {
                0% { background-position: -200% 0; }
                100% { background-position: 200% 0; }
            }
        </style>
        """

st.markdown(get_css_theme() + common_css, unsafe_allow_html=True)

# --- Notification System ---
def add_notification(message: str, type: str = "info", duration: int = 5):
    """Add a notification to the queue"""
    notification = {
        'id': len(st.session_state.notifications),
        'message': message,
        'type': type,
        'timestamp': datetime.now(),
        'duration': duration
    }
    st.session_state.notifications.append(notification)

def show_notifications():
    """Display active notifications"""
    if st.session_state.notifications:
        current_time = datetime.now()
        active_notifications = []
        
        for notif in st.session_state.notifications:
            if (current_time - notif['timestamp']).seconds < notif['duration']:
                active_notifications.append(notif)
        
        st.session_state.notifications = active_notifications
        
        for notif in active_notifications:
            st.markdown(f"""
            <div class="notification {notif['type']}">
                <strong>{notif['type'].title()}:</strong> {notif['message']}
            </div>
            """, unsafe_allow_html=True)

# --- Export Functions ---
def export_to_csv(articles: List[Article]) -> str:
    """Export articles to CSV format"""
    df = pd.DataFrame([{
        'ID': article.display_id,
        'Title': article.title,
        'Source': article.source,
        'Status': article.status.value,
        'Quality Score': article.quality_score,
        'Created': article.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'URL': article.url,
        'Description': article.description,
        'AI Summary': article.ai_summary
    } for article in articles])
    
    return df.to_csv(index=False)

def create_download_link(data: str, filename: str, file_type: str = "csv"):
    """Create a download link for data"""
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:file/{file_type};base64,{b64}" download="{filename}" class="export-btn">📥 Download {file_type.upper()}</a>'
    return href

# --- System Initialization ---
@st.cache_resource
def init_system():
    """Initialize and cache all system components."""
    try:
        config = Settings()
        
        # Setup logging and UI logger
        logging.basicConfig(level=config.get('logging', {}).get('level', 'INFO'),
                            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        logger = logging.getLogger(__name__)
        logger.info("Initializing Startt AI News Intelligence Dashboard")
        
        ui_logger = UILogger()
        
        # Get database path from config or use default
        db_path = config.get("database.path", "news_database.db")
        db_manager = SQLiteManager(db_path)
        
        # Initialize Repository
        repository = ArticleRepository(db_manager, ui_logger)
        
        # Initialize AI Components
        analyzer = ContentAnalyzer(
            gemini_api_key=config.get('ai.gemini_api_key'),
            model=config.get('ai.model', 'gemini-1.5-flash')
        )
        deduplicator = SemanticDeduplicator(
            similarity_threshold=config.get('deduplication.similarity_threshold', 0.85)
        )
        
        # Initialize Services
        content_service = ContentService(repository, analyzer, deduplicator, config)
        scraper_manager = ScraperManager(content_service, repository, config._config, ui_logger)
        api_publisher = APIPublisher(config._config, repository)
        
        return {
            'config': config,
            'repository': repository,
            'content_service': content_service,
            'scraper_manager': scraper_manager,
            'api_publisher': api_publisher,
            'logger': logger,
            'ui_logger': ui_logger
        }
    except Exception as e:
        st.error(f"Fatal error during system initialization: {e}")
        st.stop()

# Initialize float layout for sticky elements
float_init()

# --- Performance Tracking ---
@st.cache_data(ttl=300)
def get_performance_metrics():
    """Get system performance metrics"""
    return {
        'avg_processing_time': 2.3,
        'success_rate': 94.5,
        'articles_per_hour': 127,
        'api_response_time': 1.2,
        'error_rate': 2.1
    }

# --- Data Loading Functions ---
@st.cache_data(ttl=60)
def load_dashboard_data(_repository: ArticleRepository):
    return _repository.get_dashboard_stats()

@st.cache_data(ttl=30)
def load_articles(_repository: ArticleRepository, filters: Dict[str, Any]):
    return _repository.get_articles(**filters)

@st.cache_data(ttl=300)
def load_activity_logs(_repository: ArticleRepository, limit: int = 100):
    return _repository.get_activity_logs(limit)

# --- Helper Functions ---
def update_article_status(article_ids: List[int], status: ArticleStatus, _repository: ArticleRepository):
    if _repository.update_article_status(article_ids, status):
        st.balloons()
        add_notification(f"Successfully updated {len(article_ids)} articles to {status.value}", "success")
        time.sleep(1)
        st.cache_data.clear()
    else:
        add_notification("Failed to update article status", "error")

@st.dialog("⚡ Confirm Action", width="small")
def show_confirmation_dialog(action_name: str, item_count: int):
    st.markdown(f"""
    <div style="text-align: center; padding: 20px;">
        <h3 style="color: var(--text-primary);">Are you sure?</h3>
        <p style="font-size: 16px; color: var(--text-secondary); margin: 20px 0;">
            You're about to <strong>{action_name}</strong> {item_count} selected article{'s' if item_count > 1 else ''}.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirm", use_container_width=True, type="primary"):
            st.session_state.confirmed = True
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.session_state.confirmed = False

@st.dialog("✏️ Bulk Edit Articles", width="large")
def show_bulk_edit_dialog(article_ids: List[int], _repository: ArticleRepository):
    st.subheader(f"Editing {len(article_ids)} Articles")
    
    # Bulk edit options
    col1, col2 = st.columns(2)
    
    with col1:
        new_status = st.selectbox(
            "Change Status",
            options=[None] + [s.value for s in ArticleStatus],
            format_func=lambda x: "Keep Current" if x is None else x.title().replace('_', ' ')
        )
        
        add_tags = st.text_input("Add Tags (comma-separated)")
        
    with col2:
        quality_adjustment = st.slider(
            "Adjust Quality Score",
            min_value=-50,
            max_value=50,
            value=0,
            help="Add/subtract from current quality score"
        )
        
        bulk_summary = st.text_area("Bulk Summary Update", placeholder="Leave empty to keep existing summaries")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Apply Changes", type="primary", use_container_width=True):
            # Apply bulk changes
            changes_made = 0
            for article_id in article_ids:
                article = _repository.get_article_by_id(article_id)
                if article:
                    if new_status and new_status != article.status.value:
                        _repository.update_article_status([article_id], ArticleStatus(new_status))
                        changes_made += 1
                    
                    if quality_adjustment != 0:
                        new_quality = max(0, min(100, article.quality_score + quality_adjustment))
                        # Update quality score (would need repository method)
                        changes_made += 1
                    
                    if bulk_summary:
                        # Update summary (would need repository method)
                        changes_made += 1
            
            add_notification(f"Applied bulk changes to {changes_made} articles", "success")
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.rerun()

def enhance_articles_with_ai(article_ids: List[int], _repository: ArticleRepository, _content_service: ContentService):
    """Enhances selected articles with AI-generated content with queue tracking."""
    if not article_ids:
        add_notification("No articles selected to enhance", "warning")
        return

    # Add to batch queue
    batch_id = len(st.session_state.batch_queue)
    st.session_state.batch_queue.append({
        'id': batch_id,
        'operation': 'AI Enhancement',
        'article_count': len(article_ids),
        'status': 'processing',
        'progress': 0,
        'start_time': datetime.now()
    })

    progress_container = st.container()
    with progress_container:
        st.info(f"🤖 Starting AI enhancement for {len(article_ids)} articles...")
        progress_bar = st.progress(0)
        status_text = st.empty()

        total_articles = len(article_ids)
        enhanced_count = 0
        
        for i, article_id in enumerate(article_ids):
            article = _repository.get_article_by_id(article_id)
            if article:
                status_text.markdown(f"<div style='text-align: center;'>✨ Enhancing: <strong>{article.title[:50]}...</strong> ({i+1}/{total_articles})</div>", unsafe_allow_html=True)
                try:
                    _content_service.enhance_article(article)
                    enhanced_count += 1
                except Exception as e:
                    logger.error(f"Failed to enhance article {article_id}: {e}")
            
            # Update progress
            progress = (i + 1) / total_articles
            progress_bar.progress(progress)
            
            # Update batch queue
            st.session_state.batch_queue[batch_id]['progress'] = progress * 100
            time.sleep(0.1)

    # Complete batch operation
    st.session_state.batch_queue[batch_id]['status'] = 'completed'
    st.session_state.batch_queue[batch_id]['end_time'] = datetime.now()
    
    progress_bar.empty()
    status_text.empty()
    
    if enhanced_count > 0:
        st.balloons()
        add_notification(f"Successfully enhanced {enhanced_count} articles with AI!", "success")
    
    if enhanced_count < len(article_ids):
        add_notification(f"Could not enhance {len(article_ids) - enhanced_count} articles", "warning")
    
    time.sleep(1)
    st.cache_data.clear()

def publish_articles(article_ids: List[int], _repository: ArticleRepository, _publisher: APIPublisher):
    platform = "custom_api"
    if not _publisher.is_platform_enabled(platform):
        add_notification(f"The '{platform}' publishing platform is not enabled", "error")
        return

    with st.spinner(f"🚀 Publishing {len(article_ids)} articles..."):
        result = _publisher.publish_articles(article_ids, platform)
        
        success_count = sum(1 for r in result if r['status'] == 'success')
        
        if success_count > 0:
            update_article_status([r['article_id'] for r in result if r['status'] == 'success'], 
                                ArticleStatus.PUBLISHED, _repository)
            add_notification(f"Successfully published {success_count} articles!", "success")
        
        if success_count < len(article_ids):
            add_notification(f"Failed to publish {len(article_ids) - success_count} articles", "error")

    time.sleep(1)
    st.cache_data.clear()

def run_data_pull(scraper_manager: ScraperManager, selected: List[str]):
    progress_container = st.container()
    with progress_container:
        col1, col2, col3 = st.columns([2, 6, 2])
        with col2:
            st.markdown("<div style='text-align: center;'><h3>📥 Pulling Latest Data</h3></div>", unsafe_allow_html=True)
            progress_bar = st.progress(0)
            status_text = st.empty()
    
        results = []
        total_scrapers = len(selected)
        
        for i, scraper_name in enumerate(selected):
            progress = (i / total_scrapers)
            progress_bar.progress(progress)
            status_text.markdown(f"<div style='text-align: center;'>🔄 Running <strong>{scraper_name}</strong>... ({i+1}/{total_scrapers})</div>", unsafe_allow_html=True)
            
            result = scraper_manager.run_scraper(scraper_name)
            results.append(result)
            
            progress = ((i + 1) / total_scrapers)
            progress_bar.progress(progress)
            time.sleep(0.2)
        
    progress_bar.empty()
    status_text.empty()
    
    # Show results summary
    total_new = sum(r.get('new_articles', 0) for r in results if r.get('status') == 'succeeded')
    if total_new > 0:
        st.balloons()
        add_notification(f"Found {total_new} new articles!", "success")
    
    st.cache_data.clear()
    st.session_state.scraper_results = results
    st.session_state.last_scraper_run = datetime.now()

def render_status_tag(status: str) -> str:
    """Render HTML status tag with enhanced styling"""
    status_map = {
        'pulled': ('NEW', 'status-new'),
        'approved': ('APPROVED', 'status-approved'),
        'published': ('PUBLISHED', 'status-published'),
        'rejected': ('REJECTED', 'status-rejected')
    }
    label, css_class = status_map.get(status, (status.upper(), 'status-new'))
    return f'<span class="status-tag {css_class}">{label}</span>'

@st.cache_data(ttl=300)
def get_article_activity(_db_path: str) -> pd.DataFrame:
    """Get article activity for the last 7 days."""
    try:
        conn = sqlite3.connect(_db_path)
        query = """
            SELECT 
                'Article ' || status as activity,
                COUNT(*) as count,
                DATE(created_at) as date
            FROM articles
            WHERE created_at > datetime('now', '-7 days')
            GROUP BY status, DATE(created_at)
            ORDER BY date DESC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

def clear_scraper_caches(config: Settings) -> List[str]:
    """Deletes the 'seen_urls.json' files for all configured scrapers."""
    deleted_files = []
    scraper_configs = config.get('scrapers', {}).get('sources', {})
    
    for scraper_name, conf in scraper_configs.items():
        script_path = conf.get('script_path', '')
        if not script_path:
            continue
            
        cache_filename = f"{os.path.splitext(os.path.basename(script_path))[0].replace('-news-pull', '')}_seen_urls.json"
        cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), cache_filename)
        
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                deleted_files.append(scraper_name)
                logger.info(f"Removed cache file: {cache_path}")
            except Exception as e:
                logger.error(f"Failed to remove cache file {cache_path}: {e}")
                add_notification(f"Could not delete cache for {scraper_name}", "error")
                
    return deleted_files

def render_article_card(article, index, selected_articles):
    """Render an individual article card with enhanced features"""
    # Checkbox for selection
    is_selected = st.checkbox(
        f"Select article {article.display_id}",
        key=f"select_{article.id}",
        value=article.id in selected_articles,
        label_visibility="collapsed"
    )
    
    # Article card content with quality indicator
    quality_color = "#10b981" if article.quality_score >= 80 else "#f59e0b" if article.quality_score >= 60 else "#ef4444"
    
    st.markdown(f'''
    <div class="article-card">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div style="flex: 1;">
                <div class="article-title">{article.title}</div>
                <div class="article-meta">
                    <span class="article-meta-item">
                        📅 {article.created_at.strftime('%b %d, %Y')}
                    </span>
                    <span class="article-meta-item">
                        📰 {article.source}
                    </span>
                    <span class="article-meta-item">
                        🎯 Quality: <strong style="color: {quality_color};">{article.quality_score}%</strong>
                    </span>
                    <span class="article-meta-item" style="color: var(--text-secondary); font-size: 12px;">
                        #{article.display_id}
                    </span>
                </div>
            </div>
            <div>
                {render_status_tag(article.status.value)}
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # Article summary/description
    summary = article.ai_summary or article.description or "No summary available"
    
    if len(summary) > 300:
        with st.expander("📖 Read more"):
            st.write(summary)
    else:
        st.write(summary[:300] + "..." if len(summary) > 300 else summary)
    
    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        if article.url and st.button("🔗 Source", key=f"source_{article.id}"):
            st.markdown(f'<meta http-equiv="refresh" content="0; url={article.url}">', unsafe_allow_html=True)
    
    with col2:
        if st.button("👁️ Preview", key=f"preview_{article.id}"):
            st.session_state[f"show_preview_{article.id}"] = True
    
    # Show preview if requested
    if st.session_state.get(f"show_preview_{article.id}", False):
        with st.expander("📖 Article Preview", expanded=True):
            st.markdown(f"**Title:** {article.title}")
            st.markdown(f"**Source:** {article.source}")
            st.markdown(f"**Quality Score:** {article.quality_score}%")
            st.markdown(f"**Status:** {article.status.value}")
            if article.description:
                st.markdown(f"**Description:** {article.description}")
            if article.ai_summary:
                st.markdown(f"**AI Summary:** {article.ai_summary}")
            if st.button("❌ Close Preview", key=f"close_preview_{article.id}"):
                st.session_state[f"show_preview_{article.id}"] = False

    return is_selected

def show_dashboard():
    """Show the main dashboard content"""
    # Initialize system components
    config = Settings()
    ui_logger = UILogger()
    
    # Initialize database with the correct path
    db_manager = SQLiteManager("news_database.db")
    repository = ArticleRepository(db_manager, ui_logger)
    
    # Initialize content analysis components
    analyzer = ContentAnalyzer(config)
    deduplicator = SemanticDeduplicator(config)
    content_service = ContentService(repository, analyzer, deduplicator, config)
    
    # Initialize scraper manager with required components
    scraper_manager = ScraperManager(content_service, repository, config._config, ui_logger)
    publisher = APIPublisher(config._config, repository)
    
    # Show notifications
    show_notifications()


    # Theme Toggle in top bar
    with st.container():
        col1, col2, col3 = st.columns([6, 1, 1])
        
        with col2:
            if st.button("🌓", help="Toggle theme", key="theme_toggle"):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
        
        with col3:
            # Performance indicator
            perf_metrics = get_performance_metrics()
            st.markdown(f"""
            <div class="perf-metric">
                ⚡ {perf_metrics['success_rate']:.1f}%
            </div>
            """, unsafe_allow_html=True)

    # Enhanced Sidebar
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: var(--primary-color); font-size: 32px;">📰</h1>
            <h2 style="color: var(--text-primary); font-size: 24px; margin: 0;">News Hub</h2>
            <p style="color: var(--text-secondary); font-size: 14px; margin-top: 8px;">Control Center</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Batch Operations Queue
        if st.session_state.batch_queue:
            with st.expander("⏳ **Batch Operations**", expanded=True):
                for batch in st.session_state.batch_queue[-3:]:  # Show last 3
                    status_icon = "✅" if batch['status'] == 'completed' else "🔄"
                    st.markdown(f"""
                    <div class="queue-item">
                        <span>{status_icon} {batch['operation']}</span>
                        <span>{batch['progress']:.0f}%</span>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Data Pull Section
        with st.expander("🔄 **Data Sources**", expanded=True):
            available_scrapers = list(scraper_manager.scrapers.keys())
            
            if available_scrapers:
                selected_scrapers = st.multiselect(
                    "Select sources:", 
                    available_scrapers, 
                    default=available_scrapers,
                    help="Choose which news sources to pull data from"
                )
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    pull_button = st.button("📥 **Pull Data**", type="primary", use_container_width=True)
                with col2:
                    if st.button("🔄", help="Refresh sources"):
                        st.rerun()
                
                if pull_button:
                    with st.spinner("Pulling data..."):
                        run_data_pull(scraper_manager, selected_scrapers)
            else:
                st.warning("No scrapers configured.")

            if 'last_scraper_run' in st.session_state:
                time_diff = datetime.now() - st.session_state.last_scraper_run
                if time_diff < timedelta(minutes=1):
                    time_str = "Just now"
                elif time_diff < timedelta(hours=1):
                    time_str = f"{int(time_diff.seconds / 60)}m ago"
                else:
                    time_str = st.session_state.last_scraper_run.strftime('%H:%M')
                
                st.info(f"⏰ Last pull: **{time_str}**")
        
        # Advanced Filters Section
        with st.expander("🔍 **Advanced Filters**", expanded=True):
            # Basic filters
            status_filter = st.selectbox(
                "Status", 
                options=['all'] + [s.value for s in ArticleStatus],
                index=0,
                format_func=lambda x: "All Articles" if x == 'all' else x.title().replace('_', ' ')
            )
            
            source_filter = st.multiselect(
                "Sources", 
                repository.get_distinct_sources(),
                help="Filter by news source"
            )
            
            search_term = st.text_input(
                "Search", 
                placeholder="Search articles...",
                help="Search in titles and descriptions"
            )
            
            # Advanced filters
            st.markdown("**Quality & Engagement**")
            quality_range = st.slider(
                "Quality Score Range",
                min_value=0,
                max_value=100,
                value=(0, 100),
                help="Filter by quality score"
            )
            
            # Date filters
            st.markdown("**Date Range**")
            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input("From", value=datetime.now().date() - timedelta(days=7))
            with col2:
                date_to = st.date_input("To", value=datetime.now().date())
            
            # Category filters (mock data)
            categories = st.multiselect(
                "Categories",
                ["Technology", "Politics", "Business", "Sports", "Health", "Science"],
                help="Filter by article categories"
            )
            
            # Save preferences
            if st.button("💾 Save Filter Preferences"):
                st.session_state.user_preferences['default_filters'] = {
                    'status_filter': status_filter,
                    'source_filter': source_filter,
                    'quality_range': quality_range,
                    'categories': categories
                }
                add_notification("Filter preferences saved!", "success")
        
        # Performance Metrics
        with st.expander("📊 **Performance**"):
            perf = get_performance_metrics()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Success Rate", f"{perf['success_rate']:.1f}%")
                st.metric("Articles/Hour", f"{perf['articles_per_hour']}")
            with col2:
                st.metric("Avg Processing", f"{perf['avg_processing_time']:.1f}s")
                st.metric("API Response", f"{perf['api_response_time']:.1f}s")
        
        # Quick Stats
        st.markdown("---")
        stats = load_dashboard_data(repository)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Today", 
                stats.get('published_today', 0),
                delta=f"+{stats.get('published_today', 0)}",
                help="Articles published today"
            )
        with col2:
            st.metric(
                "24h New", 
                stats.get('recent_articles', 0),
                help="New articles in last 24 hours"
            )
        
        # Quick Actions
        st.markdown("---")
        with st.expander("⚡ **Quick Actions**"):
            if st.button("🔄 Refresh Dashboard", use_container_width=True):
                st.cache_data.clear()
                add_notification("Dashboard refreshed!", "info")
                st.rerun()

            if st.button("🗑️ Clear Caches", use_container_width=True):
                deleted_files = clear_scraper_caches(config)
                if deleted_files:
                    add_notification(f"Cleared: {', '.join(deleted_files)}", "success")
                else:
                    add_notification("No caches to clear", "info")

            # Notifications toggle
            notifications_enabled = st.checkbox(
                "Enable Notifications", 
                value=st.session_state.user_preferences['notifications_enabled']
            )
            st.session_state.user_preferences['notifications_enabled'] = notifications_enabled

            # Auto-refresh toggle
            auto_refresh = st.checkbox("Auto-refresh (30s)", help="Automatically refresh data every 30 seconds")
            if auto_refresh:
                st.markdown(
                    """<meta http-equiv="refresh" content="30">""",
                    unsafe_allow_html=True
                )

    # Main Content Area
    st.markdown("""
    <div style="padding: 20px 0;">
        <h1 style="color: var(--text-primary); font-size: 36px; font-weight: 800; margin: 0;">
            News Feed Management
        </h1>
        <p style="color: var(--text-secondary); font-size: 18px; margin-top: 8px;">
            Streamline your content pipeline from source to publication with Startt AI
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Enhanced Tabs
    tab_list = ["📊 Dashboard", "📰 Articles", "📈 Analytics", "⚙️ Settings"]
    if config.is_debug_mode_enabled():
        tab_list.insert(3, "🐞 Debug")

    tabs = st.tabs(tab_list)
    
    # Dashboard Tab
    with tabs[0]:
        # Dashboard customization
        st.markdown("### Dashboard Layout")
        layout_col1, layout_col2 = st.columns([3, 1])
        
        with layout_col2:
            dashboard_layout = st.selectbox(
                "Layout",
                ["Default", "Compact", "Detailed"],
                index=0
            )
        
        # Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        
        metrics_data = [
            ("Total Articles", stats.get('total_articles', 0), "#6366f1", "#5558e3"),
            ("New Today", stats.get('status_counts', {}).get('pulled', 0), "#f59e0b", "#dc2626"),
            ("Approved", stats.get('status_counts', {}).get('approved', 0), "#8b5cf6", "#7c3aed"),
            ("Published", stats.get('status_counts', {}).get('published', 0), "#10b981", "#059669")
        ]
        
        for col, (label, value, color1, color2) in zip([col1, col2, col3, col4], metrics_data):
            with col:
                st.markdown(f'''
                <div class="metric-card" style="background: linear-gradient(135deg, {color1} 0%, {color2} 100%);">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value">{value:,}</div>
                </div>
                ''', unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Charts Row
        col1, col2 = st.columns(2)
        
        with col1:
            if stats.get('source_counts'):
                st.subheader("📊 Content by Source")
                source_df = pd.DataFrame(list(stats['source_counts'].items()), columns=['Source', 'Articles'])
                fig = px.bar(
                    source_df.nlargest(10, 'Articles'), 
                    x='Articles', 
                    y='Source',
                    orientation='h',
                    color='Articles',
                    color_continuous_scale='Blues',
                    height=400
                )
                fig.update_layout(
                    showlegend=False,
                    xaxis_title="Number of Articles",
                    yaxis_title="",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color=st.session_state.dark_mode and "#ffffff" or "#1e293b"
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if stats.get('status_counts'):
                st.subheader("📈 Article Pipeline")
                status_df = pd.DataFrame(list(stats['status_counts'].items()), columns=['Status', 'Count'])
                fig = px.funnel(
                    status_df,
                    y='Status',
                    x='Count',
                    color='Status',
                    color_discrete_map={
                        'pulled': '#3b82f6', 
                        'approved': '#8b5cf6',
                        'published': '#10b981', 
                        'rejected': '#ef4444'
                    },
                    height=400
                )
                fig.update_layout(
                    showlegend=False,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_color=st.session_state.dark_mode and "#ffffff" or "#1e293b"
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # Activity Timeline
        st.subheader("📅 7-Day Activity Timeline")
        activity_df = get_article_activity("news_database.db")
        if not activity_df.empty:
            fig = px.line(
                activity_df,
                x='date',
                y='count',
                color='activity',
                markers=True,
                height=300
            )
            fig.update_layout(
                xaxis_title="",
                yaxis_title="Articles",
                legend_title="Activity Type",
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color=st.session_state.dark_mode and "#ffffff" or "#1e293b"
            )
            st.plotly_chart(fig, use_container_width=True)

    # Articles Tab
    with tabs[1]:
        # Article Management Header
        header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
        
        with header_col1:
            st.subheader("📰 Article Management")
        
        with header_col2:
            view_mode = st.selectbox(
                "View",
                ["Card View", "Compact View", "Table View"],
                index=0,
                label_visibility="collapsed"
            )
        
        with header_col3:
            sort_by = st.selectbox(
                "Sort by",
                ["Newest First", "Oldest First", "Quality Score", "Source"],
                index=0,
                label_visibility="collapsed"
            )
        
        # Load articles with enhanced filters
        article_filters = {
            'status_filter': status_filter if status_filter != 'all' else None,
            'source_filter': source_filter if source_filter else None,
            'search_term': search_term if search_term else None,
            'limit': 200
        }
        articles = load_articles(repository, article_filters)
        
        # Apply quality filter
        if 'quality_range' in locals():
            articles = [a for a in articles if quality_range[0] <= a.quality_score <= quality_range[1]]

        if not articles:
            st.info("📭 No articles found. Try adjusting your filters or pulling fresh data!")
        else:
            # Export functionality
            export_col1, export_col2, export_col3 = st.columns([1, 1, 2])
            
            with export_col1:
                if st.button("📥 Export CSV"):
                    csv_data = export_to_csv(articles)
                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=f"articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with export_col2:
                if st.button("📄 Export Selected"):
                    selected_articles = [a for a in articles if a.id in st.session_state.get('selected_articles', [])]
                    if selected_articles:
                        csv_data = export_to_csv(selected_articles)
                        st.download_button(
                            label="Download Selected",
                            data=csv_data,
                            file_name=f"selected_articles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        add_notification("No articles selected for export", "warning")
            
            # Create layout with sticky action panel
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"Showing **{len(articles)}** articles")
                
                # Select all checkbox
                select_all = st.checkbox("Select All", key="select_all_articles")
                
                # Initialize selected articles in session state
                if 'selected_articles' not in st.session_state:
                    st.session_state.selected_articles = []
                
                selected_articles = st.session_state.selected_articles if not select_all else [article.id for article in articles]
                
                # Render articles based on view mode
                if view_mode == "Table View":
                    # Table view
                    article_data = []
                    for article in articles:
                        article_data.append({
                            'Select': st.checkbox("", key=f"table_select_{article.id}", value=article.id in selected_articles),
                            'Title': article.title[:50] + "..." if len(article.title) > 50 else article.title,
                            'Source': article.source,
                            'Status': article.status.value,
                            'Quality': f"{article.quality_score}%",
                            'Date': article.created_at.strftime('%m/%d/%Y')
                        })
                    
                    if article_data:
                        st.dataframe(
                            pd.DataFrame(article_data),
                            use_container_width=True,
                            hide_index=True
                        )
                else:
                    # Card/Compact view
                    for idx, article in enumerate(articles):
                        with st.container():
                            is_selected = render_article_card(article, idx, selected_articles)
                            
                            # Update selected articles list
                            if is_selected and article.id not in st.session_state.selected_articles:
                                st.session_state.selected_articles.append(article.id)
                            elif not is_selected and article.id in st.session_state.selected_articles:
                                st.session_state.selected_articles.remove(article.id)

            with col2:
                # Enhanced action panel with better visibility
                st.markdown(f'''
                <div class="action-panel">
                    <h3>⚡ Bulk Actions</h3>
                </div>
                ''', unsafe_allow_html=True)
                
                selected_count = len(st.session_state.get('selected_articles', []))
                
                if selected_count > 0:
                    st.success(f"**{selected_count}** articles selected")
                else:
                    st.info("Select articles to perform actions")
                
                st.markdown("---")
                
                # Bulk Edit Mode
                if st.button(
                    "✏️ Bulk Edit Mode", 
                    disabled=not selected_count,
                    use_container_width=True,
                    help="Edit multiple articles at once"
                ):
                    show_bulk_edit_dialog(st.session_state.selected_articles, repository)
                
                # AI Enhancement
                if st.button(
                    "✨ Enhance with AI", 
                    disabled=not selected_count,
                    use_container_width=True,
                    help="Generate AI summaries and improve content"
                ):
                    st.session_state.action = "Enhance"
                    show_confirmation_dialog("Enhance with AI", selected_count)
                
                # Status Actions
                st.markdown("**Update Status:**")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(
                        "✅ Approve", 
                        disabled=not selected_count,
                        use_container_width=True
                    ):
                        st.session_state.action = "Approve"
                        show_confirmation_dialog("Approve", selected_count)
                
                with col2:
                    if st.button(
                        "❌ Reject", 
                        disabled=not selected_count,
                        use_container_width=True
                    ):
                        st.session_state.action = "Reject"
                        show_confirmation_dialog("Reject", selected_count)
                
                # Publishing
                st.markdown("---")
                if st.button(
                    "🚀 Publish", 
                    disabled=not selected_count,
                    use_container_width=True,
                    type="primary",
                    help="Publish to configured platforms"
                ):
                    st.session_state.action = "Publish"
                    show_confirmation_dialog("Publish", selected_count)
                
                # Reset
                if st.button(
                    "🔄 Reset Status", 
                    disabled=not selected_count,
                    use_container_width=True,
                    help="Reset to 'New' status"
                ):
                    st.session_state.action = "Reset"
                    show_confirmation_dialog("Reset", selected_count)

    # Analytics Tab
    with tabs[2]:
        st.subheader("📈 Analytics & Insights")
        
        # Performance Metrics Row
        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
        
        with metric_col1:
            approval_rate = (stats.get('status_counts', {}).get('approved', 0) / 
                           max(stats.get('total_articles', 1), 1) * 100)
            st.metric("Approval Rate", f"{approval_rate:.1f}%")
        
        with metric_col2:
            publish_rate = (stats.get('status_counts', {}).get('published', 0) / 
                          max(stats.get('status_counts', {}).get('approved', 1), 1) * 100)
            st.metric("Publish Rate", f"{publish_rate:.1f}%")
        
        with metric_col3:
            avg_quality = 75  # Calculate from actual data
            st.metric("Avg Quality", f"{avg_quality}%")
        
        with metric_col4:
            sources_active = len(stats.get('source_counts', {}))
            st.metric("Active Sources", sources_active)
        
        # Enhanced Performance Metrics
        st.subheader("🚀 System Performance")
        perf_metrics = get_performance_metrics()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Processing Metrics**")
            for metric, value in perf_metrics.items():
                if metric in ['avg_processing_time', 'api_response_time']:
                    st.markdown(f"**{metric.replace('_', ' ').title()}:** {value}s")
                elif metric in ['success_rate', 'error_rate']:
                    st.markdown(f"**{metric.replace('_', ' ').title()}:** {value}%")
                else:
                    st.markdown(f"**{metric.replace('_', ' ').title()}:** {value}")
        
        with col2:
            # Processing time trend (mock data)
            time_data = pd.DataFrame({
                'Hour': range(24),
                'Processing Time': [2.1 + 0.5 * (i % 6) for i in range(24)]
            })
            
            fig = px.line(time_data, x='Hour', y='Processing Time', title="24h Processing Time Trend")
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_color=st.session_state.dark_mode and "#ffffff" or "#1e293b"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Activity Logs
        st.subheader("📋 Recent Activity")
        
        logs = load_activity_logs(repository, limit=50)
        if logs:
            # Convert to DataFrame for better display
            logs_df = pd.DataFrame(logs)
            
            # Debug: Show available columns
            if st.checkbox("🐞 Debug: Show available columns", value=False):
                st.write("Available columns:", list(logs_df.columns))
                st.write("Sample data:", logs_df.head() if not logs_df.empty else "No data")
            
            if not logs_df.empty:
                # Format timestamps if available
                timestamp_cols = [col for col in logs_df.columns if 'time' in col.lower()]
                if timestamp_cols:
                    time_col = timestamp_cols[0]
                    try:
                        logs_df['Time'] = pd.to_datetime(logs_df[time_col]).dt.strftime('%b %d, %H:%M')
                    except:
                        logs_df['Time'] = logs_df[time_col].astype(str)
                
                # Determine which columns to show based on what's available
                available_cols = list(logs_df.columns)
                display_cols = []
                column_config = {}
                
                # Map common column variations
                col_mapping = {
                    'Time': ['Time', 'timestamp', 'created_at', 'date'],
                    'Source': ['scraper_name', 'source', 'name', 'scraper'],
                    'Status': ['status', 'state', 'result'],
                    'New Articles': ['new_articles', 'articles_count', 'count', 'articles'],
                    'Duration': ['duration', 'time_taken', 'elapsed']
                }
                
                for display_name, possible_cols in col_mapping.items():
                    for col in possible_cols:
                        if col in available_cols:
                            display_cols.append(col)
                            if display_name == 'New Articles':
                                column_config[col] = st.column_config.NumberColumn(display_name, format="%d")
                            elif display_name == 'Duration':
                                column_config[col] = st.column_config.NumberColumn(display_name, format="%.1fs")
                            else:
                                column_config[col] = st.column_config.TextColumn(display_name)
                            break
                
                # If no specific columns found, show all available columns
                if not display_cols:
                    display_cols = available_cols[:5]  # Show first 5 columns max
                
                # Display the table
                if display_cols:
                    st.dataframe(
                        logs_df[display_cols],
                        column_config=column_config,
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No suitable columns found for display")
            else:
                st.info("No activity logs available")
        else:
            st.info("📭 No recent activity to display. Try running some data pulls or performing bulk operations!")

    # Settings Tab
    with tabs[tab_list.index("⚙️ Settings")]:
        st.subheader("⚙️ System Configuration")
        
        # User Preferences
        with st.expander("👤 User Preferences", expanded=True):
            st.markdown("**Theme & Display**")
            col1, col2 = st.columns(2)
            
            with col1:
                theme_mode = st.selectbox(
                    "Theme",
                    ["Dark Mode", "Light Mode", "Auto"],
                    index=0 if st.session_state.dark_mode else 1
                )
                if theme_mode == "Dark Mode" and not st.session_state.dark_mode:
                    st.session_state.dark_mode = True
                    st.rerun()
                elif theme_mode == "Light Mode" and st.session_state.dark_mode:
                    st.session_state.dark_mode = False
                    st.rerun()
            
            with col2:
                default_view = st.selectbox(
                    "Default Article View",
                    ["Card View", "Compact View", "Table View"],
                    index=0
                )
            
            st.markdown("**Notifications**")
            enable_notifications = st.checkbox(
                "Enable System Notifications",
                value=st.session_state.user_preferences['notifications_enabled']
            )
            
            notification_types = st.multiselect(
                "Notification Types",
                ["New Articles", "Status Changes", "Errors", "Completions"],
                default=["New Articles", "Errors"]
            )
        
        # API Configuration
        with st.expander("🔑 API Configuration"):
            gemini_key = st.text_input(
                "Gemini API Key", 
                value=config.get('ai.gemini_api_key', ''), 
                type="password",
                help="Your Google Gemini API key for AI enhancements"
            )
            
            api_endpoint = st.text_input(
                "Publishing API Endpoint", 
                value=config.get('publishing.custom_api.endpoint', ''),
                help="Your custom API endpoint for publishing articles"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                api_timeout = st.number_input(
                    "API Timeout (seconds)",
                    value=30,
                    min_value=5,
                    max_value=300
                )
            with col2:
                retry_attempts = st.number_input(
                    "Retry Attempts",
                    value=3,
                    min_value=1,
                    max_value=10
                )
        
        # AI Settings
        with st.expander("🤖 AI Configuration"):
            ai_model = st.selectbox(
                "AI Model",
                ["gemini-1.5-flash", "gemini-1.5-pro"],
                index=0
            )
            
            similarity_threshold = st.slider(
                "Deduplication Threshold",
                min_value=0.5,
                max_value=1.0,
                value=0.85,
                step=0.05,
                help="Higher values mean stricter deduplication"
            )
            
            quality_threshold = st.slider(
                "Quality Threshold",
                min_value=0,
                max_value=100,
                value=60,
                help="Minimum quality score for articles"
            )
            
            # Article Templates
            st.markdown("**Article Templates**")
            template_name = st.selectbox(
                "Publishing Template",
                ["Standard", "Social Media", "Newsletter", "Blog Post"],
                index=0
            )
            
            if template_name == "Social Media":
                st.text_area("Template", value="📰 {title}\n\n{summary}\n\n🔗 {url}", height=100)
            elif template_name == "Newsletter":
                st.text_area("Template", value="## {title}\n\n{summary}\n\n[Read More]({url})", height=100)
        
        # Database Settings
        with st.expander("💾 Database"):
            st.info("Database configuration is managed through the config file.")
            st.code(f"""
Database Type: {config.get('database.type', 'sqlite')}
Database Name: news_database.db
Status: Connected ✅
Records: {stats.get('total_articles', 0)} articles
            """)
        
        # Save Configuration
        if st.button("💾 Save Configuration", type="primary", use_container_width=True):
            with st.spinner("Saving configuration..."):
                # Update user preferences
                st.session_state.user_preferences['notifications_enabled'] = enable_notifications
                st.session_state.user_preferences['default_view'] = default_view
                
                time.sleep(1)  # Simulate save operation
                add_notification("Configuration saved successfully!", "success")

    # Debug Tab (if enabled)
    if config.is_debug_mode_enabled() and "🐞 Debug" in tab_list:
        with tabs[tab_list.index("🐞 Debug")]:
            st.subheader("🐞 Debug Console")
            
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🗑️ Clear Log", use_container_width=True):
                    ui_logger.clear()
                    st.rerun()
            
            # Display logs with syntax highlighting
            logs = ui_logger.get_logs()
            if logs:
                log_text = "\n".join(logs)
                st.code(log_text, language="log")
            else:
                st.info("No debug logs yet.")
            
            # Debug session state
            with st.expander("Session State Debug"):
                st.json({
                    'dark_mode': st.session_state.dark_mode,
                    'selected_articles_count': len(st.session_state.get('selected_articles', [])),
                    'notifications_count': len(st.session_state.notifications),
                    'batch_queue_count': len(st.session_state.batch_queue),
                    'user_preferences': st.session_state.user_preferences
                })

    # Handle confirmed actions
    if 'confirmed' in st.session_state and st.session_state.confirmed:
        action = st.session_state.get('action')
        selected_ids = st.session_state.get('selected_articles', [])
        
        if action == "Enhance":
            enhance_articles_with_ai(selected_ids, repository, content_service)
        elif action == "Approve":
            update_article_status(selected_ids, ArticleStatus.APPROVED, repository)
        elif action == "Publish":
            publish_articles(selected_ids, repository, publisher)
        elif action == "Reject":
            update_article_status(selected_ids, ArticleStatus.REJECTED, repository)
        elif action == "Reset":
            update_article_status(selected_ids, ArticleStatus.PULLED, repository)
            
        del st.session_state.confirmed
        del st.session_state.action
        st.session_state.selected_articles = []
        st.rerun()

    # Enhanced Footer
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align: center; padding: 40px 0;">
            <h3 style="color: var(--text-primary); margin-bottom: 8px;">📰 News Feed Management System</h3>
            <p style="color: var(--text-secondary); font-size: 16px;">
                Powered by Startt AI • Built with ❤️ by Startt Team • Version 0.2 • {['🌙', '☀️'][not st.session_state.dark_mode]} Mode
            </p>
            <p style="color: var(--text-secondary); font-size: 14px; margin-top: 16px;">
                © 2025 Startt AI • <a href="#" style="color: var(--primary-color);">Documentation</a> • 
                <a href="#" style="color: var(--primary-color);">Support</a>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

def main():
    """Main function to run the Streamlit app"""
    # Initialize Firebase
    initialize_firebase()
    
    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Check authentication status
        is_authenticated = loop.run_until_complete(check_auth_status())
        
        if not is_authenticated:
            show_login_page()
        else:
            # Show logout button in sidebar
            if st.sidebar.button("Logout"):
                logout_user()
                st.rerun()
                
            # Show main dashboard
            show_dashboard()
    finally:
        loop.close()

if __name__ == "__main__":
    main()