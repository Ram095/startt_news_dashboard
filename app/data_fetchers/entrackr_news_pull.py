#!/usr/bin/env python3
"""
Scraper for Entrackr News - extracts ALL content including paragraphs and blockquotes
"""

import requests
from bs4 import BeautifulSoup
import csv
import json
import os
import traceback
import time
import re

BASE_URL = "https://entrackr.com"
LIST_URL = f"{BASE_URL}/news"
SEEN_FILE = "entrackr_seen_urls.json"
CSV_FILE = "entrackr_news_detailed.csv"

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
    Extract complete article content from an Entrackr article page.
    """
    if debug:
        print(f"🔍 Extracting COMPLETE content from: {url}")
    
    description = ""
    article_body = ""
    author = "Unknown"
    date = "Unknown"
    
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Entrackr uses JSON-LD for article metadata, which is the most reliable source
        script_tags = soup.find_all('script', type='application/ld+json')
        for script_tag in script_tags:
            if not script_tag.string:
                continue
            try:
                # Clean up the JSON string before parsing
                json_string = script_tag.string.replace('\n', ' ').replace('\r', ' ')
                json_data = json.loads(json_string)
                article_json = None
                
                # The data can be a single dict or a list of dicts.
                if isinstance(json_data, list):
                    # If it's a list, find the main article object.
                    for item in json_data:
                        if isinstance(item, dict) and item.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                            article_json = item
                            break
                elif isinstance(json_data, dict) and json_data.get('@type') in ('Article', 'NewsArticle', 'BlogPosting'):
                    # If it's already a dict, use it.
                    article_json = json_data

                if article_json:
                    description = clean_text(article_json.get('description', ''))
                    article_body = clean_text(article_json.get('articleBody', ''))
                    if 'author' in article_json and article_json.get('author'):
                        if isinstance(article_json['author'], list) and article_json['author']:
                             author = clean_text(article_json['author'][0].get('name'))
                        elif isinstance(article_json['author'], dict):
                             author = clean_text(article_json['author'].get('name'))
                    if 'datePublished' in article_json:
                        date = clean_text(article_json.get('datePublished', '').split('T')[0])

                    if debug and article_body:
                         print("✅ Extracted content from JSON-LD metadata.")
                    # If we found the article body in JSON, we can stop searching other scripts
                    if article_body:
                        break
            except (json.JSONDecodeError, AttributeError, IndexError):
                # Ignore scripts that don't parse correctly or don't have the expected structure
                continue

        # Fallback to HTML parsing ONLY if the JSON-LD articleBody is empty
        if not article_body:
            if debug:
                print("📄 JSON-LD articleBody is empty. Parsing HTML for full content.")

            # Main content container selector for Entrackr
            main_container = soup.select_one('.post-content, .td-post-content')
            
            if main_container:
                # Remove known junk elements
                elements_to_remove = ['script', 'style', '.ad-box', 'figure', 'blockquote.twitter-tweet', '.code-block']
                for selector in elements_to_remove:
                    for junk_element in main_container.select(selector):
                        junk_element.decompose()

                # Extract text from paragraphs
                paragraphs = main_container.find_all('p')
                content_parts = [clean_text(p.get_text()) for p in paragraphs if len(clean_text(p.get_text())) > 25]
                article_body = "\n\n".join(content_parts)

        # Fallbacks for metadata if they weren't found in JSON-LD
        if author == "Unknown":
            author_tag = soup.select_one('.author-name a, .td-author-name a')
            if author_tag: author = clean_text(author_tag.get_text())
        if date == "Unknown":
            date_tag = soup.select_one('.posted-on .value-title, .td-module-meta-info .td-post-date')
            if date_tag: date = clean_text(date_tag.get_text())

        # Final fallback for description if it wasn't in any JSON-LD
        if not description:
             meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
             if meta_desc_tag:
                 description = clean_text(meta_desc_tag.get('content'))
        
        if debug:
            print(f"\n📊 FINAL EXTRACTION RESULTS:")
            print(f"   Description: {len(description)} chars")
            print(f"   Article body: {len(article_body)} chars")
            if article_body:
                print(f"   Author: {author} | Date: {date}")
        
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
    
    print(f"Loaded {len(seen_urls)} previously seen URLs for Entrackr.")
    
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
            response = requests.get(LIST_URL, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            script_tags = soup.find_all('script', type='application/ld+json')
            article_list = []
            for script_tag in script_tags:
                try:
                    if not script_tag.string:
                        continue
                    
                    json_data = json.loads(script_tag.string.replace('\n', ' '))
                    
                    if isinstance(json_data, list):
                        for item in json_data:
                            if isinstance(item, dict) and item.get('@type') == 'ItemList':
                                article_list = item.get('itemListElement', [])
                                break
                    elif isinstance(json_data, dict):
                        if json_data.get('@type') == 'ItemList':
                            article_list = json_data.get('itemListElement', [])
                            break
                    
                    if article_list:
                        break
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            if not article_list:
                print("Could not find JSON-LD article list. Falling back to HTML scraping of the list page.")
                # This is a fallback if the main JSON-LD method fails
                articles_on_page = soup.select('.td-module-thumb a[title]')
                for article_link in articles_on_page:
                    article_list.append({
                        'url': article_link['href'],
                        'name': article_link['title']
                    })

            print(f"Found {len(article_list)} articles to process on the page.")
            
            new_articles = 0
            
            for i, article_data in enumerate(article_list):
                try:
                    url = article_data.get('url')
                    if not url or url in seen_urls:
                        continue
                    
                    title = clean_text(article_data.get('name'))
                    
                    print(f"\n{'='*60}")
                    print(f"PROCESSING ARTICLE {i+1}: {title}")
                    print(f"{'='*60}")
                    
                    print(f"URL: {url}")
                    
                    print("\nExtracting complete content...")
                    description, article_body, author, date = extract_complete_article_content(url, debug=True)
                    
                    if not article_body and not description:
                        print("⚠️  Article body and description are empty, skipping save.")
                        continue

                    writer.writerow([title, url, author, date, description, article_body])
                    seen_urls.add(url)
                    new_articles += 1
                    
                    print("✅ Saved to CSV")
                    
                    para_count = article_body.count('\n\n') + 1 if article_body else 0
                    print(f"📊 Summary: {len(article_body)} chars, ~{para_count} paragraphs")
                    
                    time.sleep(1)
                    
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
