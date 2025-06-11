import requests
from bs4 import BeautifulSoup
import csv
import json
import os
import traceback

BASE_URL = "https://indianstartupnews.com"
LIST_URL = f"{BASE_URL}/news"
SEEN_FILE = "seen_urls.json"
CSV_FILE = "funding_news_detailed.csv"

# Load previously seen article URLs
if os.path.exists(SEEN_FILE):
    with open(SEEN_FILE, "r") as f:
        seen_urls = set(json.load(f))
else:
    seen_urls = set()

print(f"Loaded {len(seen_urls)} previously seen URLs.")

# Prepare CSV writer
file_exists = os.path.isfile(CSV_FILE)
csv_file = open(CSV_FILE, mode="a", newline="", encoding="utf-8")
writer = csv.writer(csv_file)

# Write headers if file is new
if not file_exists:
    writer.writerow([
        'Title', 'URL', 'Image', 'Author', 'Date', 'Category',
        'Description', 'ArticleBody'
    ])

# Fetch and parse listing page
try:
    response = requests.get(LIST_URL)
    soup = BeautifulSoup(response.text, 'html.parser')
    posts = soup.select('div.small-post')
    print(f"Found {len(posts)} articles.")

    new_urls = set()

    for i, post in enumerate(posts):
        try:
            anchor = post.select_one('a[href]')
            relative_url = anchor['href']
            full_url = BASE_URL + relative_url

            if full_url in seen_urls:
                print(f"Skipping already seen: {full_url}")
                continue

            print(f"\n--- New Article {i + 1}: {full_url} ---")

            # Article Metadata
            title = post.select_one('div.post-title').text.strip()
            author = post.select_one('span.author-name').text.strip()
            date = post.select_one('span.publish-date').text.strip()
            img_tag = post.select_one('img.p-cover')
            image_url = img_tag['src'] if img_tag else ''
            category = post.select_one('span.category_tag').text.strip() if post.select_one('span.category_tag') else ''

            # Fetch article page
            article_resp = requests.get(full_url)
            article_soup = BeautifulSoup(article_resp.text, 'html.parser')

            # Try JSON-LD block
            script_tag = article_soup.find('script', type='application/ld+json')
            article_json = json.loads(script_tag.string) if script_tag else {}
            description = article_json.get('description', '').strip()
            article_body = article_json.get('articleBody', '').strip()

            # Fallback: extract body from HTML
            if not article_body:
                print("Falling back to HTML body scrape...")
                body_div = article_soup.find('div', id='post-container')
                if body_div:
                    article_body = "\n".join(p.text.strip() for p in body_div.find_all('p'))

            # Save row
            writer.writerow([title, full_url, image_url, author, date, category, description, article_body])
            print("✔ Saved to CSV")

            new_urls.add(full_url)

        except Exception as e:
            print(f"❌ Error parsing article: {e}")
            traceback.print_exc()

    # Update seen URLs
    if new_urls:
        seen_urls.update(new_urls)
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen_urls), f)
        print(f"\n✅ Updated seen URLs with {len(new_urls)} new articles.")
    else:
        print("\n📭 No new articles found.")

except Exception as e:
    print("❌ Script failed at listing level")
    traceback.print_exc()
finally:
    csv_file.close()
