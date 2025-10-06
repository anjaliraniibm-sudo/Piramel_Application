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

# ---------------- CONFIG ----------------
BASE_SITEMAP_URL = "http://www.catalent.com/sitemap_index.xml"
OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/catalent_sitemap_urls.csv"
SCRAPED_OUTPUT_FILE = "C:/Users/AnjaliRani/Documents/catalent_scraped_articles.csv"
SKIPPED_FILE = "C:/Users/AnjaliRani/Documents/catalent_skipped_urls.txt"
DEBUG_SITEMAP_DUMP = "C:/Users/AnjaliRani/Documents/debug_sitemap_index.html"  # created if parsing yields 0 loc
HEADLESS = True  # Set to False to watch the browser when debugging
# ----------------------------------------

# a realistic user agent (change if you want)
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


def get_child_sitemaps(base_url):
    """Fetch child sitemap URLs from sitemap index."""
    driver = None
    try:
        driver = make_driver()
        driver.set_page_load_timeout(30)
        driver.get(base_url)

        try:
            WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            time.sleep(2)

        page_src = driver.page_source
        sitemaps = []

        # Try parsing with ElementTree
        try:
            root = ET.fromstring(page_src)
            for elem in root.iter():
                if isinstance(elem.tag, str) and elem.tag.lower().endswith('loc'):
                    if elem.text and elem.text.strip():
                        sitemaps.append(elem.text.strip())
            if sitemaps:
                print(f"✅ Found {len(sitemaps)} child sitemaps (via ElementTree)")
                return sitemaps
        except ET.ParseError:
            pass

        # Try BeautifulSoup XML
        soup = BeautifulSoup(page_src, "xml")
        loc_tags = soup.find_all("loc")
        if loc_tags:
            sitemaps = [loc.get_text(strip=True) for loc in loc_tags if loc.get_text(strip=True)]
            if sitemaps:
                print(f"✅ Found {len(sitemaps)} child sitemaps (via BeautifulSoup)")
                return sitemaps

        # Regex fallback
        text = soup.get_text(separator=" ")
        urls = re.findall(r"https?://[^\s\"'<>]+", text)
        filtered = [u for u in urls if ('sitemap' in u.lower()) or u.lower().endswith('.xml')]
        seen = set()
        sitemaps = []
        for u in filtered:
            if u not in seen:
                seen.add(u)
                sitemaps.append(u)
        if sitemaps:
            print(f"✅ Found {len(sitemaps)} child sitemaps (via regex fallback)")
            return sitemaps

        # Debug dump if nothing found
        with open(DEBUG_SITEMAP_DUMP, "w", encoding="utf-8") as fh:
            fh.write(page_src)
        print(f"⚠️ No <loc> tags found. Wrote debug dump to: {DEBUG_SITEMAP_DUMP}")
        return []
    except Exception as e:
        print(f"❌ Error fetching sitemap index: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def get_urls_from_sitemap(sitemap_url):
    """Fetch URLs + LastMod from a child sitemap (XML or HTML table)."""
    driver = None
    try:
        driver = make_driver()
        driver.set_page_load_timeout(30)
        driver.get(sitemap_url)
        try:
            WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        except Exception:
            time.sleep(2)

        page_src = driver.page_source
        urls = []

        # XML parsing
        try:
            root = ET.fromstring(page_src)
            for elem in root.iter():
                if isinstance(elem.tag, str) and elem.tag.lower().endswith('loc'):
                    loc_text = elem.text.strip() if elem.text else None
                    urls.append({"URL": loc_text, "LastMod": None})
            if urls:
                return urls
        except ET.ParseError:
            pass

        # loc tags with BS4
        soup = BeautifulSoup(page_src, "lxml-xml")
        loc_tags = soup.find_all("loc")
        for loc in loc_tags:
            parent = loc.find_parent()
            lastmod = parent.find("lastmod").get_text(strip=True) if parent and parent.find("lastmod") else None
            urls.append({"URL": loc.get_text(strip=True), "LastMod": lastmod})
        if urls:
            return urls

        # HTML table sitemap
        soup = BeautifulSoup(page_src, "html.parser")
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cols = row.find_all("td")
                if not cols:
                    continue
                link = cols[0].get_text(strip=True)
                lastmod = cols[2].get_text(strip=True) if len(cols) > 2 else None
                if link:
                    urls.append({"URL": link, "LastMod": lastmod})
            if urls:
                print(f"✅ Extracted {len(urls)} URLs from table sitemap")
                return urls

        print(f"⚠️ No URLs found in sitemap: {sitemap_url}")
        return []
    except Exception as e:
        print(f"❌ Error fetching sitemap {sitemap_url}: {e}")
        return []
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


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
        # meta tag
        meta_date = soup.find("meta", attrs={"property": "article:published_time"})
        if meta_date and meta_date.get("content"):
            date = meta_date["content"]

        # time tag
        if not date:
            time_tag = soup.find("time")
            if time_tag and time_tag.get("datetime"):
                date = time_tag["datetime"]
            elif time_tag:
                date = time_tag.get_text(strip=True)

        # JSON-LD schema (Yoast)
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
                    print(f"⚠️ Could not parse JSON-LD for {url}: {e}")

        return {"Site URL": url, "Title": title, "Body": body, "Date": date}
    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
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
    print("🚀 Starting Catalent Scraper...")

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
    two_months_ago = today - timedelta(days=60)
    columns = ["Site URL", "Title", "Body", "Date"]

    child_sitemaps = get_child_sitemaps(BASE_SITEMAP_URL)

    for sm_idx, sm in enumerate(child_sitemaps, 1):
        print(f"\n🔎 Processing sitemap {sm_idx}/{len(child_sitemaps)}: {sm}")
        url_entries = get_urls_from_sitemap(sm)

        if url_entries:
            df_urls = pd.DataFrame(url_entries)
            if not os.path.exists(OUTPUT_FILE):
                df_urls.to_csv(OUTPUT_FILE, index=False, mode="w")
            else:
                df_urls.to_csv(OUTPUT_FILE, index=False, mode="a", header=False)
        else:
            print(f"⚠️ No URLs found in sitemap: {sm}")

        stop_current_sitemap = False
        for idx, entry in enumerate(url_entries, 1):
            url = entry["URL"]
            lastmod = entry.get("LastMod", "")

            # Stop if sitemap lastmod is old
            if lastmod:
                try:
                    article_date = None
                    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            article_date = datetime.strptime(lastmod[:19], fmt)
                            break
                        except ValueError:
                            continue
                    if article_date and article_date < two_months_ago:
                        print(f"⏭️ Old article ({lastmod}) → Skipping rest of sitemap {sm}")
                        stop_current_sitemap = True
                        break
                except Exception:
                    pass

            print(f"[Sitemap {sm_idx} | {idx}/{len(url_entries)}] Scraping: {url}")
            result = scrape_article_selenium(url)

            scraped_date = result.get("Date", "")
            if scraped_date:
                try:
                    sd = None
                    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                        try:
                            sd = datetime.strptime(scraped_date[:19], fmt)
                            break
                        except ValueError:
                            continue
                    if sd and sd < two_months_ago:
                        print(f"⏭️ Old article ({scraped_date}) → Skipping rest of sitemap {sm}")
                        stop_current_sitemap = True
                        break
                except Exception:
                    pass

            df_row = pd.DataFrame([result], columns=columns)
            if not os.path.exists(SCRAPED_OUTPUT_FILE):
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="w")
            else:
                df_row.to_csv(SCRAPED_OUTPUT_FILE, index=False, mode="a", header=False)

            print(f"    → Done: Title length={len(result['Title'])}, Body length={len(result['Body'])}, Date={result['Date']}")

        if stop_current_sitemap:
            continue

    print(f"✅ Scraping complete.")
    print(f"📂 Sitemap URLs saved to: {OUTPUT_FILE}")
    print(f"📝 Articles saved to: {SCRAPED_OUTPUT_FILE}")


if __name__ == "__main__":
    main()
