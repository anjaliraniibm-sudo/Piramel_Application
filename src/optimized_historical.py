import csv
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# -------------------- Suppress Selenium Logs --------------------
logging.getLogger('selenium').setLevel(logging.CRITICAL)

# -------------------- Speed up WebDriver Manager ----------------
os.environ['WDM_LOCAL'] = '1'  # use cached driver if available

# -------------------- Setup Chrome Options ----------------------
chrome_options = Options()
# Uncomment below to run in headless mode
# chrome_options.add_argument("--headless=new")
# chrome_options.add_argument("--disable-gpu")
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--log-level=3")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

# -------------------- Scraper Function --------------------------
def scrape_articles_from_url(driver, url, keywords, csv_file_path, write_headers=False):
    print(f"\n🔍 Scraping: {url} with keywords: {keywords}")

    def safe_get(link, timeout=10):
        """Try to load a link, restart driver if session crashes."""
        nonlocal driver
        for attempt in range(2):
            try:
                driver.get(link)
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                return True
            except Exception as e:
                if "no such window" in str(e) or "invalid session id" in str(e):
                    print("⚠️ Driver crashed, restarting...")
                    try:
                        driver.quit()
                    except:
                        pass
                    service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
                    driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    print(f"⚠️ Attempt {attempt+1} failed for {link}: {e}")
        return False

    try:
        if not safe_get(url):
            print(f"❌ Could not load {url}")
            return driver

        # Collect all links on the page
        all_links = driver.find_elements(By.XPATH, "//a[@href]")

        # Filter links based on keywords
        matching_links = []
        for link in all_links:
            try:
                text = link.text.strip()
                if any(keyword.lower() in text.lower() for keyword in keywords):
                    href = link.get_attribute("href")
                    if href and href.startswith("http"):
                        matching_links.append(href)
            except Exception as e:
                print(f"⚠️ Error while processing a link: {e}") 

        with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file, quoting=csv.QUOTE_ALL)  # ✅ force quoting
            if write_headers:
                writer.writerow(["link", "title", "body", "date"])

            for link in matching_links:
                if not safe_get(link):
                    print(f"❌ Skipping link after 2 failed attempts: {link}")
                    continue

                # Title
                try:
                    title = driver.title.strip()
                except:
                    title = ""

                # Body (lighter version: only key tags)
                body_texts = []
                candidate_tags = ["p", "article", "section"]

                try:
                    for tag in candidate_tags:
                        elements = driver.find_elements(By.TAG_NAME, tag)
                        for el in elements:
                            text = el.text.strip()
                            if text and len(text) > 30:
                                body_texts.append(text)

                    seen = set()
                    body = "||".join([t for t in body_texts if not (t in seen or seen.add(t))])

                    if not body:  # fallback to <body>
                        try:
                            body_elem = driver.find_element(By.TAG_NAME, "body")
                            body = body_elem.text.strip()
                        except:
                            body = ""
                except:
                    body = ""

                # ✅ Clean body text
                body = body.replace("\n", " ").replace("\r", " ").strip()

                # Date
                date = ""
                try:
                    date_elem = driver.find_element(By.XPATH, "//time")
                    date = date_elem.get_attribute("datetime") or date_elem.text.strip()
                except:
                    try:
                        date_elem = driver.find_element(
                            By.XPATH,
                            "//span[contains(@class,'date') or contains(@class,'Date')]"
                        )
                        date = date_elem.text.strip()
                    except:
                        date = "Date not found"

                writer.writerow([link, title, body, date])

    except Exception as e:
        print(f"❌ Could not process {url}: {e}")

    print(f"✅ Done scraping {url} ({len(matching_links)} links checked)")
    return driver

# -------------------- Historical File Update --------------------
def update_historical_file(scraped_file, historical_file="historical_articles.csv"):
    """Append scraped data to a historical file with timestamp."""
    if not os.path.exists(scraped_file):
        print(f"⚠️ No scraped file found at {scraped_file}, skipping history update.")
        return

    try:
        with open(scraped_file, mode="r", newline="", encoding="utf-8") as infile:
            reader = csv.reader(infile)
            rows = list(reader)

        if not rows:
            print("⚠️ Scraped file is empty, nothing to append.")
            return

        header, data_rows = rows[0], rows[1:]
        if "scraped_at" not in header:
            header.append("scraped_at")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated_rows = [row + [timestamp] for row in data_rows]

        file_exists = os.path.exists(historical_file)

        with open(historical_file, mode="a", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile, quoting=csv.QUOTE_ALL)  # ✅ force quoting
            if not file_exists:
                writer.writerow(header)
            writer.writerows(updated_rows)

        print(f"📌 Appended {len(updated_rows)} rows to {historical_file}")

    except Exception as e:
        print(f"❌ Failed to update historical file: {e}")

# -------------------- Main Function -----------------------------
def main():
    print("🚀 Starting the scraping process...")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, "input_sites.csv")
    output_csv = os.path.join(script_dir, "scraped_articles.csv")

    if os.path.exists(output_csv):
        os.remove(output_csv)

    # Initialize driver once
    service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    first_site = True

    try:
        with open(input_csv, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                url = row["website_url"].strip()
                keyword_str = row["keywords"]
                keywords = [kw.strip() for kw in keyword_str.split(",")]
                driver = scrape_articles_from_url(
                    driver=driver,
                    url=url,
                    keywords=keywords,
                    csv_file_path=output_csv,
                    write_headers=first_site
                )
                first_site = False
    except FileNotFoundError:
        print(f"❌ Input CSV not found at: {input_csv}")
    finally:
        try:
            driver.quit()
        except:
            pass

    # Update historical file
    historical_csv = os.path.join(script_dir, "historical_articles.csv")
    update_historical_file(output_csv, historical_csv)

    print(f"\n📁 Scraping complete. Output saved to: {output_csv}")
    print(f"🗂 Historical data updated at: {historical_csv}")

# -------------------- Entry Point -------------------------------
if __name__ == "__main__":
    main()
