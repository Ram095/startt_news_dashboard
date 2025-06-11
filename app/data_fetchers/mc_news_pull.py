#!/usr/bin/env python3
"""
Scraper for Moneycontrol Startup News - extracts ALL content.
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import os
import traceback
import time
import re

BASE_URL = "https://www.moneycontrol.com"
LIST_URL = f"{BASE_URL}/news/business/startup/"
SEEN_FILE = "moneycontrol_seen_urls.json"
CSV_FILE = "moneycontrol_news_detailed.csv"

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
    Extract complete article content from a Moneycontrol article page.
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
        
        # Moneycontrol sometimes uses JSON-LD for article metadata
        script_tags = soup.find_all('script', type='application/ld+json')
        for script_tag in script_tags:
            if not script_tag.string:
                continue
            try:
                json_data = json.loads(script_tag.string.replace('\n', ' '))
                article_json = None
                
                if isinstance(json_data, list):
                    for item in json_data:
                        if isinstance(item, dict) and item.get('@type') in ('Article', 'NewsArticle'):
                            article_json = item
                            break
                elif isinstance(json_data, dict) and json_data.get('@type') in ('Article', 'NewsArticle'):
                    article_json = json_data

                if article_json:
                    description = clean_text(article_json.get('description', ''))
                    article_body = clean_text(article_json.get('articleBody', ''))
                    if 'author' in article_json and article_json.get('author'):
                        if isinstance(article_json['author'], list) and article_json['author']:
                            author = clean_text(article_json['author'][0].get('name'))
                    if 'datePublished' in article_json:
                        date = clean_text(article_json.get('datePublished', '').split('T')[0])

                    if debug and article_body:
                         print("✅ Extracted content from JSON-LD metadata.")
                    if article_body:
                        break
            except (json.JSONDecodeError, AttributeError, IndexError):
                continue

        # --- FIX: Using the precise selector you provided ---
        if not article_body:
            if debug:
                print("📄 Parsing HTML for full content.")

            # Targeting the specific ID you found is the most reliable method.
            main_container = soup.select_one('#contentdata')
            
            if main_container:
                if debug:
                    print("   🎯 Found main container with selector: '#contentdata'")
                
                # Remove known junk elements like related articles, ads, etc.
                elements_to_remove = [
                    'script', 'style', '.adv_content', '.embed-container', 
                    '.tags_first_para', '.related_stories', '.subscribe_block',
                    '.article_social_media', '.next_sibling', '.clearfix', 'a.app_a_tag'
                ]
                for selector in elements_to_remove:
                    for junk_element in main_container.select(selector):
                        junk_element.decompose()

                # Find ALL 'p' tags within the container, as you suggested
                paragraphs = main_container.find_all('p') 
                content_parts = []
                for p in paragraphs:
                    text = clean_text(p.get_text())
                    # Filter for meaningful paragraphs
                    if text and len(text) > 25 and 'also read' not in text.lower() and 'disclaimer' not in text.lower():
                        content_parts.append(text)
                
                article_body = "\n\n".join(content_parts)

        # Fallbacks for metadata if not found elsewhere
        if date == "Unknown":
            date_tag = soup.select_one('.article_schedule, .content_pub_date')
            if date_tag: 
                date_text = clean_text(date_tag.get_text())
                date = date_text.replace('IST', '').strip().replace('Published on: ', '')

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
    
    print(f"Loaded {len(seen_urls)} previously seen URLs for Moneycontrol.")
    
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
            
            # Moneycontrol uses a standard list of articles
            article_list = soup.select('#cagetory li.clearfix')
            print(f"Found {len(article_list)} articles on the page.")
            
            new_articles = 0
            
            for i, article_item in enumerate(article_list):
                try:
                    link_tag = article_item.select_one('h2 a')
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
                    
                    # If after all attempts, body is empty, we skip
                    if not article_body:
                        print("⚠️  Article body is empty after all extraction attempts, skipping save.")
                        continue

                    writer.writerow([title, url, author, date, description, article_body])
                    seen_urls.add(url)
                    new_articles += 1
                    
                    print("✅ Saved to CSV")
                    
                    para_count = article_body.count('\n\n') + 1 if article_body else 0
                    print(f"📊 Summary: {len(article_body)} chars, ~{para_count} paragraphs")
                    
                    time.sleep(2) # Be respectful
                    
                except Exception as e:
                    print(f"❌ Error processing article: {title} ({url})")
                    traceback.print_exc()
            
            with open(SEEN_FILE, "w") as f:
                json.dump(list(seen_urls), f)
            
            print(f"\n Processed {new_articles} new articles with complete content")
            
        except Exception as e:
            print(f"❌ Script failed: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
