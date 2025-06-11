# ai/content_analyzer.py
import google.generativeai as genai
import hashlib
import json
import re
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from textblob import TextBlob
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from models.base import Article

logger = logging.getLogger(__name__)

# --- NLTK Data Check ---
def ensure_nltk_data():
    """Downloads NLTK data if not already present."""
    required_packages = [('tokenizers/punkt', 'punkt'), ('corpora/stopwords', 'stopwords')]
    for path, pkg_id in required_packages:
        try:
            nltk.data.find(path)
            logger.info(f"NLTK package '{pkg_id}' already downloaded.")
        except LookupError:
            logger.info(f"Downloading NLTK package: '{pkg_id}'...")
            nltk.download(pkg_id)

ensure_nltk_data()

@dataclass
class ContentAnalysis:
    quality_score: int
    ai_tags: List[str]
    ai_summary: str
    sentiment_score: float
    readability_score: float
    key_entities: List[str]
    topic_category: str

@dataclass
class DuplicationResult:
    is_duplicate: bool
    similarity_score: float
    similar_article_id: Optional[int] = None
    similar_article_title: Optional[str] = None
    confidence: str = "medium"

class ContentAnalyzer:
    """A content analyzer that can use either Gemini or basic NLP."""
    def __init__(self, gemini_api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self.gemini_api_key = gemini_api_key
        self.model_name = model
        self.stop_words = set(stopwords.words('english'))
        
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini model '{self.model_name}' initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini model: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None

        # Initialize sentence transformer for semantic similarity
        try:
            logger.info("Loading sentence transformer model: 'all-MiniLM-L6-v2'...")
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {e}", exc_info=True)
            self.sentence_model = None
        
        # Initialize TF-IDF as fallback
        self.tfidf = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 3),
            min_df=1,
            max_df=0.95
        )

    def analyze_content(self, title: str, description: str, article_body: str, source: str) -> ContentAnalysis:
        """Comprehensive content analysis using AI and NLP"""
        try:
            # Combine content for analysis
            full_content = f"{title}\n\n{description}\n\n{article_body}"
            
            # Basic quality scoring
            quality_score = self._calculate_quality_score(title, description, article_body)
            
            # Sentiment analysis
            sentiment_score = self._analyze_sentiment(full_content)
            
            # Readability score
            readability_score = self._calculate_readability(article_body)
            
            # Extract key entities
            key_entities = self._extract_entities(full_content)
            
            # Generate AI tags and summary if a Gemini model is available
            if self.gemini_model:
                ai_tags, ai_summary, topic_category = self._generate_ai_insights(title, description, article_body)
            else:
                logger.warning("Gemini model not available. Falling back to basic analysis.")
                ai_tags = self._generate_basic_tags(full_content)
                ai_summary = self._generate_basic_summary(description, article_body)
                topic_category = self._classify_topic(full_content)
            
            return ContentAnalysis(
                quality_score=quality_score,
                ai_tags=ai_tags,
                ai_summary=ai_summary,
                sentiment_score=sentiment_score,
                readability_score=readability_score,
                key_entities=key_entities,
                topic_category=topic_category
            )
            
        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            return self._default_analysis()

    def _calculate_quality_score(self, title: str, description: str, article_body: str) -> int:
        """Calculate content quality score based on multiple factors"""
        score = 0
        
        # Title quality (0-20 points)
        title_words = len(title.split())
        if 5 <= title_words <= 15:
            score += 15
        elif 3 <= title_words <= 20:
            score += 10
        else:
            score += 5
        
        # High-value keywords in title
        high_value_keywords = [
            'funding', 'raises', 'startup', 'ipo', 'acquisition', 'merger',
            'launch', 'partnership', 'investment', 'series', 'round',
            'breakthrough', 'innovation', 'growth', 'expansion'
        ]
        title_lower = title.lower()
        keyword_matches = sum(1 for keyword in high_value_keywords if keyword in title_lower)
        score += min(keyword_matches * 3, 15)
        
        # Content depth (0-25 points)
        content_length = len(article_body)
        if content_length > 2000:
            score += 25
        elif content_length > 1000:
            score += 20
        elif content_length > 500:
            score += 15
        elif content_length > 200:
            score += 10
        else:
            score += 5
        
        # Description quality (0-10 points)
        if description and len(description) > 50:
            score += 10
        elif description:
            score += 5
        
        # Content structure (0-15 points)
        sentences = sent_tokenize(article_body)
        if len(sentences) > 5:
            score += 10
            # Check for variety in sentence length
            sentence_lengths = [len(sent.split()) for sent in sentences]
            if len(set(sentence_lengths)) > 3:
                score += 5
        
        # Penalize poor quality indicators
        if any(indicator in article_body.lower() for indicator in ['lorem ipsum', 'placeholder', 'test content']):
            score -= 20
        
        return max(0, min(100, score))
    
    def _analyze_sentiment(self, content: str) -> float:
        """Analyze sentiment of content (-1 to 1)"""
        try:
            blob = TextBlob(content)
            return float(blob.sentiment.polarity)
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return 0.0
    
    def _calculate_readability(self, content: str) -> float:
        """Calculate readability score (Flesch Reading Ease approximation)"""
        try:
            sentences = sent_tokenize(content)
            words = word_tokenize(content)
            
            if not sentences or not words:
                return 0.0
            
            avg_sentence_length = len(words) / len(sentences)
            syllable_count = sum(self._count_syllables(word) for word in words)
            avg_syllables_per_word = syllable_count / len(words) if words else 0
            
            # Simplified Flesch Reading Ease formula
            score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            return max(0, min(100, score))
            
        except Exception as e:
            logger.warning(f"Readability calculation failed: {e}")
            return 50.0  # Default neutral score
    
    def _count_syllables(self, word: str) -> int:
        """Approximate syllable count for a word"""
        word = word.lower()
        count = 0
        vowels = 'aeiouy'
        if word[0] in vowels:
            count += 1
        for index in range(1, len(word)):
            if word[index] in vowels and word[index-1] not in vowels:
                count += 1
        if word.endswith('e'):
            count -= 1
        if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
            count += 1
        if count == 0:
            count += 1
        return count
    
    def _extract_entities(self, content: str) -> List[str]:
        """Extract key entities (companies, people, etc.)"""
        # Simple regex-based entity extraction
        entities = []
        
        # Company patterns
        company_patterns = [
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|Corp|Ltd|LLC|Technologies|Tech|Labs|Systems)\b',
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b(?=\s+(?:raised|announces|launches|acquires))',
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, content)
            entities.extend(matches)
        
        # Remove duplicates and common words
        common_words = {'The', 'This', 'That', 'These', 'Those', 'Inc', 'Corp', 'Ltd'}
        entities = list(set(entity for entity in entities if entity not in common_words))
        
        return entities[:10]  # Limit to top 10
    
    def _generate_ai_insights(self, title: str, description: str, article_body: str) -> Tuple[List[str], str, str]:
        """Generate AI-powered tags, summary, and topic classification using Gemini."""
        try:
            content = f"Title: {title}\n\nDescription: {description}\n\nContent: {article_body[:3000]}"
            
            prompt = f"""
            Analyze the following news article and provide the response in JSON format.
            The JSON object should have three keys: "tags", "summary", and "category".
            
            - "tags": An array of 5-8 relevant and specific tags (e.g., "startup-funding", "fintech", "Series A", "e-commerce-platform").
            - "summary": A concise, engaging summary of the article, approximately 55-60 words, capturing the main point.
            - "category": The primary topic category from this list: funding, product-launch, acquisition, partnership, regulatory, human-resources, general-news.

            Article for analysis:
            ---
            {content}
            ---
            """
            
            response = self.gemini_model.generate_content(prompt)
            
            # Clean and parse the JSON response
            cleaned_response_text = response.text.strip().replace("```json", "").replace("```", "").strip()
            
            try:
                insights = json.loads(cleaned_response_text)
                tags = insights.get("tags", [])
                summary = insights.get("summary", "")
                category = insights.get("category", "general-news")
                
                # Basic validation
                if not isinstance(tags, list) or not isinstance(summary, str) or not isinstance(category, str):
                    raise ValueError("Invalid format for generated insights.")

                return tags, summary, category

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse Gemini response: {e}\nResponse text: {cleaned_response_text}")
                # Fallback parsing if JSON is invalid
                tags = re.findall(r'"tags":\s*\[([^\]]+)\]', cleaned_response_text)
                if tags:
                    tags = [t.strip().strip('"') for t in tags[0].split(',')]
                else:
                    tags = []
                
                summary_match = re.search(r'"summary":\s*"([^"]+)"', cleaned_response_text)
                summary = summary_match.group(1) if summary_match else ""

                category_match = re.search(r'"category":\s*"([^"]+)"', cleaned_response_text)
                category = category_match.group(1) if category_match else "general-news"
                
                return tags, summary, category

        except Exception as e:
            logger.error(f"AI insight generation failed: {e}")
            return self._generate_basic_tags(content), self._generate_basic_summary(description, article_body), "general-news"

    def _generate_basic_tags(self, content: str) -> List[str]:
        """Generate basic tags from content using TF-IDF"""
        try:
            # Tokenize and remove stop words
            tokens = [word for word in word_tokenize(content.lower()) if word.isalpha() and word not in self.stop_words]
            
            # Use TF-IDF to find important keywords
            tfidf_matrix = self.tfidf.fit_transform([" ".join(tokens)])
            feature_names = self.tfidf.get_feature_names_out()
            
            # Get top N keywords
            top_n = 10
            top_indices = tfidf_matrix.toarray()[0].argsort()[-top_n:][::-1]
            keywords = [feature_names[i] for i in top_indices]
            
            return keywords
        except Exception as e:
            logger.warning(f"Basic tag generation failed: {e}")
            return []

    def _generate_basic_summary(self, description: str, article_body: str) -> str:
        """Generate a basic summary from description or first few sentences"""
        if description and len(description) > 50:
            return description
        
        try:
            sentences = sent_tokenize(article_body)
            return " ".join(sentences[:2])  # Return first two sentences
        except Exception as e:
            logger.warning(f"Basic summary generation failed: {e}")
            return ""

    def _classify_topic(self, content: str) -> str:
        """Basic topic classification based on keywords"""
        content_lower = content.lower()
        if any(kw in content_lower for kw in ['funding', 'raised', 'investment', 'series', 'round']):
            return 'funding'
        if any(kw in content_lower for kw in ['launch', 'unveil', 'release', 'new product']):
            return 'product-launch'
        if any(kw in content_lower for kw in ['acquire', 'merger', 'buyout']):
            return 'acquisition'
        if any(kw in content_lower for kw in ['partner', 'collaboration', 'agreement']):
            return 'partnership'
        return 'general'

    def _default_analysis(self) -> ContentAnalysis:
        """Return a default analysis object in case of errors"""
        return ContentAnalysis(
            quality_score=0,
            ai_tags=[],
            ai_summary="",
            sentiment_score=0.0,
            readability_score=0.0,
            key_entities=[],
            topic_category='unknown'
        )

@dataclass
class SemanticDeduplicator:
    similarity_threshold: float = 0.85
    sentence_model: Optional[SentenceTransformer] = field(init=False, default=None)
    
    def __post_init__(self):
        try:
            logger.info("Deduplicator: Loading sentence transformer model 'all-MiniLM-L6-v2'...")
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Deduplicator: Sentence transformer loaded successfully.")
        except Exception as e:
            logger.error(f"Deduplicator: Failed to load sentence transformer model: {e}", exc_info=True)
            self.sentence_model = None

    def check_for_duplicates(self, new_article: Dict, existing_articles: List[Dict]) -> DuplicationResult:
        """Check for duplicates using semantic and keyword-based methods"""
        if not existing_articles:
            return DuplicationResult(is_duplicate=False, similarity_score=0.0)

        new_text = self._prepare_text(new_article)
        existing_texts = [self._prepare_text(a) for a in existing_articles]
        
        # First, try semantic check if model is available
        if self.sentence_model:
            result = self._semantic_similarity_check(new_text, existing_texts, existing_articles)
            if result.is_duplicate:
                return result

        # Fallback to TF-IDF check
        result = self._tfidf_similarity_check(new_text, existing_texts, existing_articles)
        if result.is_duplicate:
            return result
            
        # Final quick check on normalized titles
        result = self._simple_title_check(new_text, existing_texts, existing_articles)
        if result.is_duplicate:
            return result

        return DuplicationResult(is_duplicate=False, similarity_score=0.0)
    
    def _prepare_text(self, article: Dict) -> str:
        """Prepare text for similarity comparison"""
        title = article.get('title', '')
        description = article.get('description', '')
        # Only use first 500 chars of body to avoid noise and save computation
        body = article.get('article_body', '')[:500]
        
        text = f"{title} {description} {body}".strip()
        return self._normalize_text(text)

    def _normalize_text(self, text: any) -> str:
        """Normalize text for consistent comparison"""
        if not isinstance(text, str):
            text = ""  # Treat non-strings (like NaN floats or None) as empty strings.

        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r'[^\w\s]', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _semantic_similarity_check(self, new_text: str, existing_texts: List[str], 
                                 existing_articles: List[Dict]) -> DuplicationResult:
        """Use sentence embeddings for semantic similarity check"""
        try:
            new_embedding = self.sentence_model.encode(new_text, convert_to_tensor=True)
            existing_embeddings = self.sentence_model.encode(existing_texts, convert_to_tensor=True)
            
            similarities = cosine_similarity(
                new_embedding.reshape(1, -1),
                existing_embeddings
            )[0]
            
            max_similarity = np.max(similarities)
            
            if max_similarity > self.similarity_threshold:
                most_similar_idx = np.argmax(similarities)
                return DuplicationResult(
                    is_duplicate=True,
                    similarity_score=float(max_similarity),
                    similar_article_id=existing_articles[most_similar_idx]['id'],
                    similar_article_title=existing_articles[most_similar_idx]['title'],
                    confidence="high"
                )
        except Exception as e:
            logger.warning(f"Semantic similarity check failed: {e}")
        
        return DuplicationResult(is_duplicate=False, similarity_score=0.0)

    def _tfidf_similarity_check(self, new_text: str, existing_texts: List[str], 
                               existing_articles: List[Dict]) -> DuplicationResult:
        """Use TF-IDF for keyword-based similarity check"""
        try:
            vectorizer = TfidfVectorizer().fit(existing_texts + [new_text])
            
            existing_vectors = vectorizer.transform(existing_texts)
            new_vector = vectorizer.transform([new_text])
            
            similarities = cosine_similarity(new_vector, existing_vectors)[0]
            max_similarity = np.max(similarities)
            
            # Use a slightly lower threshold for TF-IDF as it's less nuanced
            if max_similarity > (self.similarity_threshold - 0.05):
                most_similar_idx = np.argmax(similarities)
                return DuplicationResult(
                    is_duplicate=True,
                    similarity_score=float(max_similarity),
                    similar_article_id=existing_articles[most_similar_idx]['id'],
                    similar_article_title=existing_articles[most_similar_idx]['title'],
                    confidence="medium"
                )
        except Exception as e:
            logger.warning(f"TF-IDF similarity check failed: {e}")
            
        return DuplicationResult(is_duplicate=False, similarity_score=0.0)

    def _simple_title_check(self, new_text: str, existing_texts: List[str], 
                          existing_articles: List[Dict]) -> DuplicationResult:
        """A very basic check on normalized titles for exact or near-exact matches"""
        new_title = new_text.split(' ')[0:10] # Approx first 10 words
        new_title_str = " ".join(new_title)

        for i, text in enumerate(existing_texts):
            existing_title = text.split(' ')[0:10]
            existing_title_str = " ".join(existing_title)
            
            if new_title_str == existing_title_str:
                return DuplicationResult(
                    is_duplicate=True,
                    similarity_score=1.0,
                    similar_article_id=existing_articles[i]['id'],
                    similar_article_title=existing_articles[i]['title'],
                    confidence="low"
                )
        return DuplicationResult(is_duplicate=False, similarity_score=0.0)

    def generate_content_hash(self, title: str, description: str, article_body: str) -> str:
        """Generate a consistent hash for a given article's content."""
        
        # Normalize content for hashing
        norm_title = self._normalize_text(title)
        norm_desc = self._normalize_text(description)
        norm_body = self._normalize_text(article_body)
        
        # Combine the most important parts for the hash
        content_string = f"{norm_title}|{norm_desc[:200]}|{norm_body[:500]}"
        
        return hashlib.sha256(content_string.encode('utf-8')).hexdigest()