import pandas as pd
import glob
import logging
from database.sqlite_manager import SQLiteManager
from repository.repository import ArticleRepository
from models.base import Article
from services.content_analyzer import SemanticDeduplicator
from datetime import datetime

# ... existing code ... 