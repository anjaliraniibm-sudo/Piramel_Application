from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
import pandas as pd
import time
import os
from datetime import datetime, timedelta
import requests
import json
import csv

# ---------------- CONFIG ----------------
BASE_SITEMAP_URL = "https://resilience.com/sitemap.xml"
SCRAPED_OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/resilience_scraped_articles.csv"
SKIPPED_FILE = "C:/Users/AnjaliRani/Documents/resilience_skipped_urls.txt"
# ----------------------------------------


def get_urls_from_sitemap():
    try:
        response = requests.get(BASE_SITEMAP_URL, timeout=30)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to fetch sitemap: {e}")
        return []

    soup = BeautifulSoup(response.content, "xml")
    urls = []
    for url_tag in soup.find_all("url"):
        loc = url_tag.find("loc")
        lastmod_tag = url_tag.find("lastmod")
        lastmod = lastmod_tag.get_text(strip=True) if lastmod_tag else None
        if loc:
            urls.append({"URL": loc.get_text(strip=True), "LastMod": lastmod})
    return urls


def extract_date(soup, sitemap_date=None):
    """Extract publication/modification date from JSON-LD, meta tags, <time>, or fallback."""
    date = None

    # --- JSON-LD ---
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text(strip=True))
            if isinstance(data, dict):
                date = data.get("dateModified") or data.get("datePublished")
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict):
                        date = entry.get("dateModified") or entry.get("datePublished")
                        if date:
                            break
            if date:
                break
        except Exception:
            continue

    # --- Meta tags ---
    if not date:
        meta = (
            soup.find("meta", attrs={"property": "article:published_time"})
            or soup.find("meta", attrs={"name": "pubdate"})
            or soup.find("meta", attrs={"name": "date"})
        )
        if meta and meta.get("content"):
            date = meta["content"]

    # --- <time> tag ---
    if not date:
        time_tag = soup.find("time")
        if time_tag:
            date = time_tag.get("datetime") or time_tag.get_text(strip=True)

    # --- Fallback to sitemap <lastmod> ---
    if not date and sitemap_date:
        date = sitemap_date

    # --- Normalize to YYYY-MM-DD ---
    if date:
        try:
            date_obj = dateparser.parse(date)
            date = date_obj.strftime("%Y-%m-%d")
        except Exception:
            date = str(date)

    return date or "Unknown"


def scrape_article_selenium(url, sitemap_date=None):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.set_page_load_timeout(60)
        driver.get(url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Title
        title = soup.title.string.strip() if soup.title else ""
        title = title.replace('"', '""')

        # Body
        body_texts = []
        for tag in ["p", "div", "span", "section", "article", "main"]:
            for el in soup.find_all(tag):
                text = el.get_text(separator=" ", strip=True)
                if text and len(text) > 30:
                    body_texts.append(text)
        seen = set()
        body = "||".join([t for t in body_texts if not (t in seen or seen.add(t))])
        if not body:
            body_elem = soup.find("body")
            body = body_elem.get_text(separator=" ", strip=True) if body_elem else ""
        body = body.replace("\n", " ").replace("\t", " ").replace('"', '""')

        # Date (with fallback)
        date = extract_date(soup, sitemap_date)
        print(f"🗓 Extracted date for {url}: {date}")

        driver.quit()
        return {"Site URL": url, "Title": title, "Body": body, "Date": date}

    except Exception as e:
        driver.quit()
        print(f"❌ Error scraping {url}: {e}")
        with open(SKIPPED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{url}\t{str(e)}\n")
        return {"Site URL": url, "Title": "", "Body": "", "Date": "Unknown"}


def main():
    print("🚀 Starting Resilience Scraper...")

    if os.path.exists(SCRAPED_OUTPUT_FILE):
        os.remove(SCRAPED_OUTPUT_FILE)

    today = datetime.now()
    two_months_ago = today - timedelta(days=62)
    columns = ["Site URL", "Title", "Body", "Date"]

    url_entries = get_urls_from_sitemap()
    print(f"🔎 Found {len(url_entries)} URLs in sitemap")

    for idx, entry in enumerate(url_entries, 1):
        url = entry["URL"]
        lastmod = entry.get("LastMod", "")

        # Skip old articles based on sitemap <lastmod>
        skip_article = False
        if lastmod:
            try:
                article_date = dateparser.parse(lastmod)
                if article_date < two_months_ago:
                    skip_article = True
            except Exception:
                pass

        if skip_article:
            print(f"⏭️ Skipping old article → {url}")
            continue

        print(f"[{idx}/{len(url_entries)}] Scraping: {url}")
        result = scrape_article_selenium(url, lastmod)

        # Skip if scraped date is older than 2 months
        if result["Date"] and result["Date"] != "Unknown":
            try:
                sd = datetime.strptime(result["Date"], "%Y-%m-%d")
                if sd < two_months_ago:
                    print(f"⏭️ Skipping old article (scraped date) → {url}")
                    continue
            except Exception:
                pass

        # Write CSV with fixed columns
        df_row = pd.DataFrame([result], columns=columns)
        if not os.path.exists(SCRAPED_OUTPUT_FILE):
            df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="w", quoting=csv.QUOTE_ALL)
        else:
            df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="a", header=False, quoting=csv.QUOTE_ALL)

        print(
            f"    → Done: Title length={len(result['Title'])}, Body length={len(result['Body'])}, Date={result['Date']}"
        )

    print(f"✅ Scraping complete. Articles saved to {SCRAPED_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
