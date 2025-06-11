#!/usr/bin/env python3
"""
Enhanced Inc42 scraper - extracts ALL content including paragraphs and blockquotes
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import os
import traceback
import time
import re

BASE_URL = "https://inc42.com"
LIST_URL = f"{BASE_URL}/buzz/"
SEEN_FILE = "inc42_seen_urls.json"
CSV_FILE = "inc42_news_detailed.csv"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return ''
    # Consolidate whitespace and remove non-breaking spaces
    text = re.sub(r'\s+', ' ', text.strip())
    text = text.replace('\u00a0', ' ').replace('&nbsp;', ' ')
    return text.strip()

def extract_complete_article_content(url, debug=False):
    """
    Extract complete article content by intelligently iterating through content tags.
    """
    if debug:
        print(f"🔍 Extracting COMPLETE content from: {url}")
    
    content_parts = []
    description = ""
    article_body = ""
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- FIX: Prioritize JSON-LD data, as it's structured and more reliable ---
        # This also fixes the "'list' object has no attribute 'get'" error.
        script_tag = soup.find('script', type='application/ld+json')
        if script_tag:
            try:
                json_data = json.loads(script_tag.string)
                
                # The data can be a single dict or a list of dicts.
                article_json = None
                if isinstance(json_data, list):
                    # If it's a list, find the main article object.
                    for item in json_data:
                        if isinstance(item, dict) and item.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                            article_json = item
                            break
                elif isinstance(json_data, dict):
                    # If it's already a dict, use it.
                    article_json = json_data

                if article_json:
                    description = clean_text(article_json.get('description', ''))
                    article_body = clean_text(article_json.get('articleBody', ''))
                    if debug and article_body:
                         print("✅ Extracted content from JSON-LD metadata.")
            except (json.JSONDecodeError, AttributeError):
                if debug:
                    print("⚠️ Could not parse JSON-LD, falling back to HTML.")
                pass # Fallback to HTML parsing if JSON fails

        # Fallback to HTML parsing if JSON-LD fails or doesn't provide a body
        if not article_body:
            if debug:
                print("📄 JSON-LD not found or empty. Parsing HTML content.")

            # Find the main content container
            content_containers = [
                'div.single-post-content', '.post-content', '.entry-content',
                '.article-content', 'article .content', '.post-body', 'main article'
            ]
            main_container = None
            for selector in content_containers:
                container = soup.select_one(selector)
                if container:
                    main_container = container
                    if debug:
                        print(f"🎯 Found main container: {selector}")
                    break
            
            if main_container:
                # First, remove known junk elements to clean the tree
                elements_to_remove = [
                    '.wp-block-image', 'figure', '.post-tags', '.author-bio', 
                    '.social-share-wrapper', '.yarpp-related', '.jp-relatedposts',
                    'script', 'style', '.entry-meta', '.single-post-meta',
                    'form', '.comments-area', 'iframe', '.recommend-article-wrapper'
                ]
                for selector in elements_to_remove:
                    for junk_element in main_container.select(selector):
                        junk_element.decompose()

                # Find all potential content tags
                allowed_tags = ['p', 'blockquote', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li']
                all_content_elements = main_container.find_all(allowed_tags)
                
                for i, element in enumerate(all_content_elements):
                    is_nested = False
                    for parent in element.find_parents():
                        if parent == main_container:
                            break
                        if parent in all_content_elements:
                            is_nested = True
                            break
                    if is_nested:
                        continue

                    text = clean_text(element.get_text())

                    if len(text) < 20:
                        continue
                    if any(pattern in text.lower() for pattern in [
                        'share this article', 'follow us on', 'subscribe to', 'recommended for you',
                        'advertisement', 'sponsored content', 'read also', 'also read',
                        'you may also like', 'related articles', 'trending now'
                    ]):
                        continue
                    
                    if text not in content_parts:
                        content_parts.append(text)

                article_body = "\n\n".join(content_parts)

        # Final fallback for description if it wasn't in JSON-LD
        if not description:
             meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
             if meta_desc_tag:
                 description = clean_text(meta_desc_tag.get('content'))
        
        if debug:
            print(f"\n📊 FINAL EXTRACTION RESULTS:")
            print(f"   Description: {len(description)} chars")
            print(f"   Article body: {len(article_body)} chars")
            
            if article_body:
                para_count = article_body.count('\n\n') + 1
                print(f"   Estimated paragraphs: {para_count}")
                print(f"\n📝 Content preview:")
                preview_lines = article_body.split('\n\n')[:3]
                for i, line in enumerate(preview_lines):
                    print(f"   Para {i+1}: {line[:100]}...")
        
        return description, article_body
        
    except Exception as e:
        if debug:
            print(f"❌ Content extraction failed: {e}")
            traceback.print_exc()
        return description, article_body # Return whatever was found

def test_single_url():
    """Test function for debugging"""
    test_url = "https://inc42.com/buzz/lenskart-turns-into-a-public-entity-ahead-of-its-ipo/"
    print(f"🧪 TESTING COMPLETE CONTENT EXTRACTION")
    print(f"URL: {test_url}")
    print("=" * 80)
    
    description, content = extract_complete_article_content(test_url, debug=True)
    
    print("\n" + "=" * 80)
    print("FINAL RESULTS:")
    print(f"Description: {description}")
    print(f"Content length: {len(content)} characters")
    
    if content:
        print(f"Estimated paragraphs: {content.count(chr(10)+chr(10)) + 1}")
        print(f"\nContent preview (first 500 chars):\n{content[:500]}...")
        with open('complete_extraction_fixed.txt', 'w', encoding='utf-8') as f:
            f.write(content)
        print("\n💾 Complete content saved to 'complete_extraction_fixed.txt'")
    else:
        print("❌ No content extracted")

def main():
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        test_single_url()
        return
    
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            seen_urls = set(json.load(f))
    else:
        seen_urls = set()
    
    print(f"Loaded {len(seen_urls)} previously seen URLs.")
    
    file_exists = os.path.isfile(CSV_FILE)
    if file_exists:
        print(f"'{CSV_FILE}' exists. Appending new articles.")
    else:
        print(f"'{CSV_FILE}' not found. Creating new file.")

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        
        if not file_exists:
            writer.writerow([
                'Title', 'URL', 'Image', 'Author', 'Date', 'Category',
                'Description', 'ArticleBody'
            ])
        
        try:
            print(f"Fetching: {LIST_URL}")
            response = requests.get(LIST_URL, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            articles = soup.find_all('div', class_='card-wrapper')
            print(f"Found {len(articles)} articles on the page.")
            
            new_articles = 0
            
            for i, article in enumerate(articles):
                try:
                    title_link = article.select_one('h2.entry-title a')
                    if not title_link: continue
                    
                    url = title_link.get('href')
                    if url in seen_urls: continue
                    
                    title = clean_text(title_link.get_text())
                    
                    print(f"\n{'='*60}")
                    print(f"PROCESSING ARTICLE {i+1}: {title}")
                    print(f"{'='*60}")
                    
                    img_elem = article.select_one('figure.card-image img')
                    image_url = img_elem.get('src', '') if img_elem else ''
                    
                    author_elem = article.select_one('span.author a')
                    author = clean_text(author_elem.get_text()) if author_elem else 'Unknown'
                    
                    date_elem = article.select_one('span.date')
                    date = clean_text(date_elem.get_text()) if date_elem else 'Unknown'
                    
                    category_elem = article.select_one('span.post-category a')
                    category = clean_text(category_elem.get_text()) if category_elem else 'News'
                    
                    print(f"Author: {author} | Date: {date} | Category: {category}")
                    print(f"URL: {url}")
                    
                    print("\nExtracting complete content...")
                    description, article_body = extract_complete_article_content(url, debug=True)
                    
                    if not article_body:
                        print("⚠️ Could not extract article body, skipping save.")
                        continue

                    writer.writerow([title, url, image_url, author, date, category, description, article_body])
                    seen_urls.add(url)
                    new_articles += 1
                    
                    print("✅ Saved to CSV")
                    
                    para_count = article_body.count('\n\n') + 1 if article_body else 0
                    print(f"📊 Summary: {len(article_body)} chars, ~{para_count} paragraphs")
                    
                    time.sleep(1) # Be respectful
                    
                except Exception as e:
                    print(f"❌ Error processing article: {title} ({url})")
                    traceback.print_exc()
            
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen_urls), f)
            
            print(f"\n✅ Processed {new_articles} new articles with complete content")
            
        except Exception as e:
            print(f"❌ Script failed: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
