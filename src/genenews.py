# catalent_scraper_robust_sitemap.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import json
import requests

# ---------------- CONFIG ----------------
BASE_SITEMAP_URL = "https://www.genengnews.com/sitemap_index.xml"
OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/genenews_sitemap_urls.csv"
SCRAPED_OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/genenews_scraped_articles.csv"
SKIPPED_FILE = "C:/Users/AnjaliRani/Documents/genenews_skipped_urls.txt"
DEBUG_SITEMAP_DUMP = "C:/Users/AnjaliRani/Documents/debug_genenews_index.html"
HEADLESS = True
# ----------------------------------------

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/116.0.0.0 Safari/537.36")


def make_driver():
    chrome_options = Options()
    if HEADLESS:
        chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument(f'user-agent={USER_AGENT}')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=chrome_options)
    try:
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": USER_AGENT})
    except Exception:
        pass
    return driver


def parse_date(date_str):
    """Parse various date formats into datetime."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str[:19], fmt)
        except Exception:
            continue
    return None


def get_child_sitemaps(base_url, two_months_ago):
    """Fetch child sitemaps and direct articles from base sitemap, applying date filter."""
    try:
        response = requests.get(base_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        page_src = response.text

        # XML parsing
        root = ET.fromstring(page_src)
        urls = []
        for elem in root.iter():
            if isinstance(elem.tag, str) and elem.tag.lower().endswith("loc"):
                loc = elem.text.strip()
                lastmod_elem = elem.getparent() if hasattr(elem, 'getparent') else None
                lastmod_tag = elem.find("../lastmod") if elem.find("../lastmod") is not None else None
                lastmod = lastmod_tag.text.strip() if lastmod_tag is not None else None
                urls.append({"URL": loc, "LastMod": lastmod})

        # Separate child sitemaps vs direct article URLs
        child_sitemaps = []
        direct_articles = []

        for entry in urls:
            url = entry["URL"]
            lastmod = entry.get("LastMod")
            keep = True
            if lastmod:
                dt = parse_date(lastmod)
                if dt and dt < two_months_ago:
                    keep = False
            if keep:
                if re.search(r'post-sitemap\d*\.xml$', url):
                    child_sitemaps.append(url)
                else:
                    direct_articles.append(url)

        # Scrape direct articles immediately
        for url in direct_articles:
            print(f"🔎 Found direct article URL: {url} → scraping now")
            result = scrape_article_selenium(url)
            columns = ["Site URL", "Title", "Body", "Date"]
            df_row = pd.DataFrame([result], columns=columns)
            if not os.path.exists(SCRAPED_OUTPUT_FILE):
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="w")
            else:
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="a", header=False)

        return child_sitemaps

    except Exception as e:
        print(f" Error fetching base sitemap: {e}")
        with open(DEBUG_SITEMAP_DUMP, "w", encoding="utf-8") as fh:
            fh.write(response.text if 'response' in locals() else "")
        return []


def get_urls_from_sitemap(sitemap_url, two_months_ago):
    """Fetch URLs + LastMod from a child sitemap with date filtering."""
    urls = []
    try:
        response = requests.get(sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        page_src = response.text

        root = ET.fromstring(page_src)
        for elem in root.iter():
            if isinstance(elem.tag, str) and elem.tag.lower().endswith("url"):
                loc = elem.find("{*}loc")
                lastmod = elem.find("{*}lastmod")
                url_text = loc.text.strip() if loc is not None else None
                lastmod_text = lastmod.text.strip() if lastmod is not None else None
                if url_text:
                    if lastmod_text:
                        dt = parse_date(lastmod_text)
                        if dt and dt >= two_months_ago:
                            urls.append({"URL": url_text, "LastMod": lastmod_text})
                    else:
                        urls.append({"URL": url_text, "LastMod": None})
        return urls
    except Exception as e:
        print(f" Error fetching sitemap {sitemap_url}: {e}")
        return []


def scrape_article_selenium(url):
    """Scrape title, body, and published date from an article URL"""
    driver = None
    try:
        driver = make_driver()
        driver.set_page_load_timeout(60)
        driver.get(url)
        try:
            WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        title = soup.title.string.strip() if soup.title else ""

        body = ""
        body_div = soup.find("div", class_="field--name-body") or soup.find("div", class_="article-content")
        if body_div:
            body = body_div.get_text(separator="\n", strip=True)
        else:
            paragraphs = soup.find_all("p")
            body = "||".join([p.get_text(strip=True) for p in paragraphs])

        date = ""
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            date = meta_date["content"]
        if not date:
            time_tag = soup.find("time")
            if time_tag and time_tag.get("datetime"):
                date = time_tag["datetime"]
            elif time_tag:
                date = time_tag.get_text(strip=True)
        if not date:
            ld_json = soup.find("script", {"type": "application/ld+json"})
            if ld_json:
                try:
                    data = json.loads(ld_json.string)
                    if isinstance(data, dict) and "datePublished" in data:
                        date = data["datePublished"]
                    elif isinstance(data, list):
                        for item in data:
                            if "datePublished" in item:
                                date = item["datePublished"]
                                break
                except Exception as e:
                    print(f" Could not parse JSON-LD for {url}: {e}")

        return {"Site URL": url, "Title": title, "Body": body, "Date": date}
    except Exception as e:
        print(f" Error scraping {url}: {e}")
        with open(SKIPPED_FILE, "a", encoding="utf-8") as f:
            f.write(f"{url}\t{str(e)}\n")
        return {"Site URL": url, "Title": "", "Body": "", "Date": ""}
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def main():
    print(" Starting Genenews Scraper...")

    if os.path.exists(SCRAPED_OUTPUT_FILE):
        os.remove(SCRAPED_OUTPUT_FILE)
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)
    if os.path.exists(DEBUG_SITEMAP_DUMP):
        try:
            os.remove(DEBUG_SITEMAP_DUMP)
        except:
            pass

    today = datetime.now()
    two_months_ago = today - timedelta(days=62)
    columns = ["Site URL", "Title", "Body", "Date"]

    child_sitemaps = get_child_sitemaps(BASE_SITEMAP_URL, two_months_ago)

    for sm_idx, sm in enumerate(child_sitemaps, 1):
        print(f"\n🔎 Processing sitemap {sm_idx}/{len(child_sitemaps)}: {sm}")
        url_entries = get_urls_from_sitemap(sm, two_months_ago)

        if url_entries:
            df_urls = pd.DataFrame(url_entries)
            if not os.path.exists(OUTPUT_FILE):
                df_urls.to_csv(OUTPUT_FILE, index=False, mode="w")
            else:
                df_urls.to_csv(OUTPUT_FILE, index=False, mode="a", header=False)
        else:
            print(f" No URLs found in sitemap: {sm}")

        for idx, entry in enumerate(url_entries, 1):
            url = entry["URL"]
            print(f"[Sitemap {sm_idx} | {idx}/{len(url_entries)}] Scraping: {url}")
            result = scrape_article_selenium(url)

            df_row = pd.DataFrame([result], columns=columns)
            if not os.path.exists(SCRAPED_OUTPUT_FILE):
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="w")
            else:
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="a", header=False)

            print(f"    → Done: Title length={len(result['Title'])}, Body length={len(result['Body'])}, Date={result['Date']}")

    print(f" Scraping complete.")
    print(f" Sitemap URLs saved to: {OUTPUT_FILE}")
    print(f" Articles saved to: {SCRAPED_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
