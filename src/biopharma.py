
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime, timedelta

# ---------------- CONFIG ----------------
BASE_SITEMAP_URL = "https://www.biopharminternational.com/sitemap.xml?category=Article%20Detail&page={}"
OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/biopharma_sitemap_urls.csv"
SCRAPED_OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/biopharma_scraped_articles.csv"
SKIPPED_FILE = "C:/Users/AnjaliRani/Documents/biopharma_skipped_urls.txt"
# ----------------------------------------

def get_urls_from_sitemap(page_num):
    """Fetch URLs from a given sitemap page"""
    url = BASE_SITEMAP_URL.format(page_num)

    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('user-agent=Mozilla/5.0')

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(3)  # Wait for page load
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    urls = []
    # First check XML <loc> tags
    loc_tags = soup.find_all("loc")
    if loc_tags:
        for loc in loc_tags:
            parent = loc.find_parent()
            lastmod = parent.find("lastmod").get_text(strip=True) if parent and parent.find("lastmod") else None
            urls.append({"URL": loc.get_text(strip=True), "LastMod": lastmod})
    else:
        # Fallback: try table rows
        table = soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cols = row.find_all("td")
                if not cols:
                    continue
                link = cols[0].get_text(strip=True)
                lastmod = cols[1].get_text(strip=True) if len(cols) > 1 else None
                if link:
                    urls.append({"URL": link, "LastMod": lastmod})

    return urls

def scrape_article_selenium(url):
    """Scrape title, body, date from an article URL"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('user-agent=Mozilla/5.0')

    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.set_page_load_timeout(60)
        driver.get(url)
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Title
        title = soup.title.string.strip() if soup.title else ""

        # Body
        body = ""
        body_div = soup.find("div", class_="field--name-body")
        if not body_div:
            body_div = soup.find("div", class_="article-content")
        if body_div:
            body = body_div.get_text(separator="\n", strip=True)
        else:
            paragraphs = soup.find_all("p")
            body = "||".join([p.get_text(strip=True) for p in paragraphs])

        # Date
        date = ""
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            date = meta_date["content"]
        else:
            time_tag = soup.find("time")
            if time_tag and time_tag.get("datetime"):
                date = time_tag["datetime"]
            elif time_tag:
                date = time_tag.get_text(strip=True)

        driver.quit()
        return {"Site URL": url, "Title": title, "Body": body, "Date": date}

    except Exception as e:
        driver.quit()
        print(f"❌ Error scraping {url}: {e}")
        with open(SKIPPED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{url}\t{str(e)}\n")
        return {"Site URL": url, "Title": "", "Body": "", "Date": ""}

def main():
    print("🚀 Starting PharmTech Scraper...")

    if os.path.exists(SCRAPED_OUTPUT_FILE):
        os.remove(SCRAPED_OUTPUT_FILE)

    today = datetime.now()
    two_months_ago = today - timedelta(days=62)
    columns = ["Site URL", "Title", "Body", "Date"]

    page = 1
    while True:
        print(f"🔎 Fetching sitemap page {page}...")
        url_entries = get_urls_from_sitemap(page)
        if not url_entries:
            print(f"✅ No more URLs found at page {page}. Stopping pagination.")
            break

        stop_current_page = False
        for idx, entry in enumerate(url_entries, 1):
            url = entry["URL"]
            lastmod = entry.get("LastMod", "")

            # Check sitemap lastmod date first
            if lastmod:
                try:
                    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            article_date = datetime.strptime(lastmod[:19], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        article_date = None
                    if article_date and article_date < two_months_ago:
                        print(f"⏭️ Found old article ({lastmod}) → Skipping rest of sitemap page {page}")
                        stop_current_page = True
                        break
                except Exception:
                    pass

            print(f"[Page {page} | {idx}/{len(url_entries)}] Scraping: {url}")
            result = scrape_article_selenium(url)

            # Validate scraped date
            scraped_date = result.get("Date", "")
            if scraped_date:
                try:
                    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            sd = datetime.strptime(scraped_date[:19], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        sd = None
                    if sd and sd < two_months_ago:
                        print(f"⏭️ Found old article ({scraped_date}) → Skipping rest of sitemap page {page}")
                        stop_current_page = True
                        break
                except Exception:
                    pass

            df_row = pd.DataFrame([result], columns=columns)
            if not os.path.exists(SCRAPED_OUTPUT_FILE):
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="w")
            else:
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="a", header=False)

            print(f"    → Done: Title length={len(result['Title'])}, Body length={len(result['Body'])}")

        if stop_current_page:
            page += 1
            continue

        page += 1

    print(f"✅ Scraping complete. Articles saved to {SCRAPED_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
