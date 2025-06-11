# utils/deduplication.py
import hashlib
import re
import numpy as np
from typing import List, Tuple, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class SemanticDeduplicator:
    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold
        self.stop_words = set(stopwords.words('english'))
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95
        )
        
    def normalize_text(self, text: str) -> str:
        """Normalize text for better comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common news artifacts
        text = re.sub(r'\b(inc42|entrackr|moneycontrol|startupnews)\b', '', text)
        text = re.sub(r'\b(source|image|reuters|pti|ians)\b', '', text)
        
        # Remove URLs and email addresses
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove special characters but keep sentence structure
        text = re.sub(r'[^\w\s\.]', ' ', text)
        
        # Remove stopwords
        tokens = word_tokenize(text)
        tokens = [token for token in tokens if token not in self.stop_words and len(token) > 2]
        
        return ' '.join(tokens)
    
    def generate_content_hash(self, title: str, description: str, body: str) -> str:
        """Generate a semantic-aware content hash"""
        # Normalize each component
        title_norm = self.normalize_text(title)
        desc_norm = self.normalize_text(description)
        body_norm = self.normalize_text(body[:1000])  # First 1000 chars
        
        # Weight title more heavily as it's most distinctive
        content = f"{title_norm} {title_norm} {desc_norm} {body_norm}"
        
        return hashlib.sha256(content.encode()).hexdigest()
    
    def find_similar_articles(self, new_article: dict, existing_articles: List[dict]) -> List[Tuple[dict, float]]:
        """Find articles similar to the new one"""
        if not existing_articles:
            return []
        
        # Prepare texts for comparison
        new_text = self._prepare_text_for_comparison(new_article)
        existing_texts = [self._prepare_text_for_comparison(article) for article in existing_articles]
        
        # Add new text to fit the vectorizer
        all_texts = existing_texts + [new_text]
        
        try:
            # Create TF-IDF vectors
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)
            
            # Calculate similarities
            new_vector = tfidf_matrix[-1]  # Last one is the new article
            existing_vectors = tfidf_matrix[:-1]
            
            similarities = cosine_similarity(new_vector, existing_vectors).flatten()
            
            # Find similar articles above threshold
            similar_articles = []
            for i, similarity in enumerate(similarities):
                if similarity >= self.similarity_threshold:
                    similar_articles.append((existing_articles[i], similarity))
            
            # Sort by similarity (highest first)
            similar_articles.sort(key=lambda x: x[1], reverse=True)
            return similar_articles
            
        except Exception as e:
            # Fallback to simple text comparison
            return self._simple_similarity_check(new_article, existing_articles)
    
    def _prepare_text_for_comparison(self, article: dict) -> str:
        """Prepare article text for similarity comparison"""
        title = article.get('title', '')
        description = article.get('description', '')
        body = article.get('article_body', '')[:500]  # First 500 chars
        
        # Combine and normalize
        combined = f"{title} {description} {body}"
        return self.normalize_text(combined)
    
    def _simple_similarity_check(self, new_article: dict, existing_articles: List[dict]) -> List[Tuple[dict, float]]:
        """Fallback simple similarity check"""
        new_title_words = set(self.normalize_text(new_article.get('title', '')).split())
        similar_articles = []
        
        for article in existing_articles:
            existing_title_words = set(self.normalize_text(article.get('title', '')).split())
            
            if len(new_title_words) > 0 and len(existing_title_words) > 0:
                jaccard_similarity = len(new_title_words & existing_title_words) / len(new_title_words | existing_title_words)
                
                if jaccard_similarity >= 0.6:  # 60% word overlap
                    similar_articles.append((article, jaccard_similarity))
        
        return sorted(similar_articles, key=lambda x: x[1], reverse=True)

# Enhanced ArticleRepository with semantic deduplication
class EnhancedArticleRepository(ArticleRepository):
    def __init__(self, db_path: str):
        super().__init__(db_path)
        self.deduplicator = SemanticDeduplicator()
    
    def save_article_with_dedup_check(self, article: Article) -> dict:
        """Save article with advanced deduplication checking"""
        # Get existing articles from same source (for efficiency)
        existing_articles = self.get_articles_by_source(article.source, limit=1000)
        
        # Convert to dict format for deduplicator
        new_article_dict = {
            'title': article.title,
            'description': article.description,
            'article_body': article.article_body,
            'url': article.url
        }
        
        existing_articles_dict = [
            {
                'title': a.title,
                'description': a.description, 
                'article_body': a.article_body,
                'url': a.url,
                'id': a.id
            }
            for a in existing_articles
        ]
        
        # Check for similar articles
        similar_articles = self.deduplicator.find_similar_articles(
            new_article_dict, existing_articles_dict
        )
        
        if similar_articles:
            # Found similar articles
            most_similar = similar_articles[0]
            return {
                'status': 'duplicate',
                'similarity_score': most_similar[1],
                'similar_article': most_similar[0],
                'all_similar': similar_articles
            }
        
        # No duplicates found, save the article
        content_hash = self.deduplicator.generate_content_hash(
            article.title, article.description, article.article_body
        )
        
        success = self._save_article_with_hash(article, content_hash)
        
        return {
            'status': 'saved' if success else 'error',
            'content_hash': content_hash
        }
    
    def get_articles_by_source(self, source: str, limit: int = 1000) -> List[Article]:
        """Get articles filtered by source"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM articles 
            WHERE source = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (source, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_article(row) for row in rows]
    
    def _save_article_with_hash(self, article: Article, content_hash: str) -> bool:
        """Save article with provided content hash"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO articles (
                    title, url, source, author, date, category, 
                    description, article_body, image_url, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (article.title, article.url, article.source, article.author, 
                  article.date, article.category, article.description, 
                  article.article_body, article.image_url, content_hash))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Duplicate
        finally:
            conn.close()

# Usage example in your CSV processing
def process_csv_with_smart_deduplication(csv_file: str, source: str, repo: EnhancedArticleRepository):
    """Process CSV with intelligent deduplication reporting"""
    import pandas as pd
    
    if not os.path.exists(csv_file):
        return {'error': f"CSV file {csv_file} not found"}
    
    df = pd.read_csv(csv_file)
    results = {
        'total_processed': len(df),
        'new_articles': 0,
        'duplicates_found': 0,
        'duplicate_details': [],
        'errors': 0
    }
    
    for _, row in df.iterrows():
        try:
            article = Article(
                title=str(row.get('Title', '')).strip(),
                url=str(row.get('URL', '')).strip(),
                source=source,
                author=str(row.get('Author', 'Unknown')).strip(),
                date=str(row.get('Date', '')).strip(),
                category=str(row.get('Category', 'News')).strip(),
                description=str(row.get('Description', '')).strip(),
                article_body=str(row.get('ArticleBody', '')).strip()
            )
            
            if not article.title or not article.url:
                continue
            
            result = repo.save_article_with_dedup_check(article)
            
            if result['status'] == 'saved':
                results['new_articles'] += 1
            elif result['status'] == 'duplicate':
                results['duplicates_found'] += 1
                results['duplicate_details'].append({
                    'new_title': article.title,
                    'similar_title': result['similar_article']['title'],
                    'similarity_score': result['similarity_score']
                })
            else:
                results['errors'] += 1
                
        except Exception as e:
            results['errors'] += 1
    
    return results