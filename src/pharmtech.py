from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
from datetime import datetime, timedelta

SITEMAP_URL = "https://www.pharmtech.com/sitemap.xml?category=Article%20Detail&page=51"
OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/pharmtech_sitemap_table_selenium.csv"
SCRAPED_OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/pharmtech_scraped_articles.csv"

def get_urls_from_table_selenium(sitemap_url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('user-agent=Mozilla/5.0')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(sitemap_url)
    time.sleep(5)  # Wait for Cloudflare challenge and page load
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    urls = []
    table = soup.find("table")
    if not table:
        print("⚠️ No table found on sitemap page.")
        return []
    for row in table.find_all("tr"):
        cols = row.find_all("td")
        if not cols:
            continue
        url = cols[0].get_text(strip=True)
        lastmod = cols[1].get_text(strip=True) if len(cols) > 1 else None
        if url:
            urls.append({"URL": url, "LastMod": lastmod})
    return urls

def scrape_article_selenium(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('user-agent=Mozilla/5.0')
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.set_page_load_timeout(180)
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        title = soup.title.string if soup.title else ""
        body = ""
        body_div = soup.find("div", class_="field--name-body")
        if not body_div:
            body_div = soup.find("div", class_="article-content")
        if body_div:
            body = body_div.get_text(separator="\n", strip=True)
        else:
            paragraphs = soup.find_all("p")
            body = "\n".join([p.get_text(strip=True) for p in paragraphs])
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
        print(f"Error scraping {url}: {e}")
        with open("C:/Users/AnjaliRani/Documents/pharmtech_skipped_urls.txt", "a", encoding="utf-8") as f:
            f.write(f"{url}\t{str(e)}\n")
        return {"Site URL": url, "Title": "", "Body": "", "Date": ""}

def main():
    print(f"🔎 Fetching sitemap table with Selenium: {SITEMAP_URL}")
    url_entries = get_urls_from_table_selenium(SITEMAP_URL)
    print(f"Found {len(url_entries)} URLs in table")
    df = pd.DataFrame(url_entries)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"🎯 Saved {len(df)} URLs to {OUTPUT_FILE}")

    # Now read URLs and scrape each article
    print(f"🔎 Scraping articles from URLs...")
    # Remove existing output file if present
    if os.path.exists(SCRAPED_OUTPUT_FILE):
        os.remove(SCRAPED_OUTPUT_FILE)
    columns = ["Site URL", "Title", "Body", "Date"]
    today = datetime.now()
    two_months_ago = today - timedelta(days=60)
    for idx, entry in enumerate(url_entries, 1):
        url = entry["URL"]
        lastmod = entry.get("LastMod", "")
        # Try to parse lastmod date
        date_ok = False
        if lastmod:
            try:
                # Try common date formats
                for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        article_date = datetime.strptime(lastmod[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    article_date = None
                if article_date and article_date >= two_months_ago:
                    date_ok = True
            except Exception:
                pass
        if not lastmod or date_ok:
            print(f"[{idx}/{len(url_entries)}] Scraping: {url}")
            result = scrape_article_selenium(url)
            # If the scraped date is available, check it too
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
                        print(f"    → Skipped: Article date older than 2 months ({scraped_date})")
                        continue
                except Exception:
                    pass
            print(f"    → Done: Title length={len(result['Title'])}, Body length={len(result['Body'])}")
            # Write/append to CSV after each scrape
            df_row = pd.DataFrame([result], columns=columns)
            if not os.path.exists(SCRAPED_OUTPUT_FILE):
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode='w')
            else:
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode='a', header=False)
        else:
            print(f"[{idx}/{len(url_entries)}] Skipped: Article date older than 2 months ({lastmod})")
    print(f"✅ Scraped articles saved to {SCRAPED_OUTPUT_FILE}")

if __name__ == "__main__":
    main()
 