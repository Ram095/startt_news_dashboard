#!/usr/bin/env python3
"""
Scraper for StartupNews.fyi - extracts ALL content.
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import os
import traceback
import time
import re

BASE_URL = "https://startupnews.fyi"
LIST_URL = f"{BASE_URL}/the-latest/"
SEEN_FILE = "startupnews_fyi_seen_urls.json"
CSV_FILE = "startupnews_fyi_detailed.csv"

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
    Extract complete article content from a StartupNews.fyi article page.
    """
    if debug:
        print(f"🔍 Extracting COMPLETE content from: {url}")
    
    description = ""
    article_body = ""
    author = "Unknown"
    date = "Unknown"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # This site also uses JSON-LD, so we prioritize it for metadata
        script_tags = soup.find_all('script', type='application/ld+json')
        for script_tag in script_tags:
            if not script_tag.string:
                continue
            try:
                json_string = re.sub(r'[\n\r\t]', ' ', script_tag.string)
                json_data = json.loads(json_string)
                article_json = None
                
                if isinstance(json_data, list):
                    for item in json_data:
                        if isinstance(item, dict) and item.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                            article_json = item
                            break
                elif isinstance(json_data, dict) and json_data.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                    article_json = json_data

                if article_json:
                    description = clean_text(article_json.get('description', ''))
                    if 'author' in article_json and article_json.get('author'):
                        if isinstance(article_json['author'], list) and article_json['author']:
                            author = clean_text(article_json['author'][0].get('name'))
                    if 'datePublished' in article_json:
                        date = clean_text(article_json.get('datePublished', '').split('T')[0])

                    if debug:
                         print("✅ Extracted metadata from JSON-LD.")
                    break 
            except (json.JSONDecodeError, AttributeError, IndexError):
                continue

        # --- FINAL FIX: More Robust HTML Parsing ---
        if debug:
            print("📄 Parsing HTML for full content.")

        # Targeting the specific div you found for the most reliable extraction.
        main_container = soup.select_one('div.tdb-block-inner.td-fix-index')
        
        if main_container:
            if debug:
                print("   🎯 Found main container with selector: 'div.tdb-block-inner.td-fix-index'")
            
            # This method avoids modifying the parse tree with decompose(), which was causing issues.
            # It gets all text and then filters out the junk.
            all_text = main_container.get_text(separator='\n', strip=True)
            
            lines = all_text.split('\n')
            content_parts = []
            
            # Filter the extracted lines to form clean paragraphs
            for line in lines:
                cleaned_line = clean_text(line)
                # Filter for meaningful lines and ignore common junk/headings
                if cleaned_line and len(cleaned_line) > 35: # Increased length filter slightly
                    if any(junk in cleaned_line.lower() for junk in ['share this:', 'like this:', 'related', 'also read', 'by:', 'source:', 'tags:']):
                        continue
                    content_parts.append(cleaned_line)

            article_body = "\n\n".join(content_parts)


        # Fallbacks for metadata if not found in JSON-LD
        if author == "Unknown":
            author_tag = soup.select_one('.td-post-author-name a, .author-name a')
            if author_tag: author = clean_text(author_tag.get_text())
        if date == "Unknown":
            date_tag = soup.select_one('time.entry-date')
            if date_tag: date = clean_text(date_tag.get_text())

        if not description:
             meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
             if meta_desc_tag:
                 description = clean_text(meta_desc_tag.get('content'))
        
        if debug:
            print(f"\n📊 FINAL EXTRACTION RESULTS:")
            print(f"   Description: {len(description)} chars")
            print(f"   Article body: {len(article_body)} chars")
        
        return description, article_body, author, date
        
    except Exception as e:
        if debug:
            print(f"❌ Content extraction failed: {e}")
            traceback.print_exc()
        return description, article_body, author, date

def main():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            seen_urls = set(json.load(f))
    else:
        seen_urls = set()
    
    print(f"Loaded {len(seen_urls)} previously seen URLs for StartupNews.fyi.")
    
    file_exists = os.path.isfile(CSV_FILE)
    if file_exists:
        print(f"'{CSV_FILE}' exists. Appending new articles.")
    else:
        print(f"'{CSV_FILE}' not found. Creating new file.")

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        
        if not file_exists:
            writer.writerow(['Title', 'URL', 'Author', 'Date', 'Description', 'ArticleBody'])
        
        try:
            print(f"Fetching: {LIST_URL}")
            response = requests.get(LIST_URL, headers=HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Select each article block on the main page
            article_list = soup.select('.td_module_flex')
            print(f"Found {len(article_list)} articles on the page.")
            
            new_articles = 0
            
            for i, article_item in enumerate(article_list):
                try:
                    link_tag = article_item.select_one('h3.entry-title a')
                    if not link_tag:
                        continue

                    url = link_tag.get('href')
                    if not url or url in seen_urls:
                        continue
                    
                    title = clean_text(link_tag.get('title'))
                    
                    print(f"\n{'='*60}")
                    print(f"PROCESSING ARTICLE {i+1}: {title}")
                    print(f"{'='*60}")
                    
                    print(f"URL: {url}")
                    
                    print("\nExtracting complete content...")
                    description, article_body, author, date = extract_complete_article_content(url, debug=True)
                    
                    if not article_body:
                        # Fallback to the excerpt from the list page if body extraction fails
                        excerpt_div = article_item.select_one('.td-excerpt')
                        if excerpt_div:
                            article_body = clean_text(excerpt_div.get_text())
                            print("⚠️  Article body empty, using excerpt as fallback.")

                    if not article_body:
                        print("⚠️  Article body is empty after all extraction attempts, skipping save.")
                        continue

                    writer.writerow([title, url, author, date, description, article_body])
                    seen_urls.add(url)
                    new_articles += 1
                    
                    print("✅ Saved to CSV")
                    
                    para_count = article_body.count('\n\n') + 1 if article_body else 0
                    print(f"📊 Summary: {len(article_body)} chars, ~{para_count} paragraphs")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"❌ Error processing article: {title} ({url})")
                    traceback.print_exc()
            
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen_urls), f)
            
            print(f"\n✅ Processed {new_articles} new articles with complete content")
            
        except KeyboardInterrupt:
            print("\nScript interrupted by user. Saving progress...")
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen_urls), f)
            print("Progress saved. Exiting.")
        except Exception as e:
            print(f"❌ Script failed: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
