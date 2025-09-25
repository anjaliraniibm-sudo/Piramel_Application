import csv
import os
import time
import logging
from selenium import webdriver
from urllib.parse import urlparse
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# -------------------- Suppress Selenium Logs --------------------
logging.getLogger('selenium').setLevel(logging.CRITICAL)

# -------------------- Setup Chrome Options --------------------
chrome_options = Options()
# Uncomment below to run in headless mode
# chrome_options.add_argument("--headless")
chrome_options.add_argument("--log-level=3")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

# -------------------- Setup WebDriver --------------------
try:
    service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
    driver = webdriver.Chrome(service=service, options=chrome_options)
except Exception as e:
    print(f"❌ Failed to initialize WebDriver: {e}")
    exit(1)


# -------------------- Scraper Function --------------------
def scrape_articles_from_url(driver, url,keywords,csv_file_path, write_headers=False):
    print(f"\n🔍 Scraping: {url} with keywords: {keywords}")

    def safe_get(link):
        """Try to load a link, restart driver if session crashes."""
        nonlocal driver
        for attempt in range(2):
            try:
                driver.get(link)
                time.sleep(3)
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
            return driver  # return driver so session continues

        # Collect all links on the page
        all_links = driver.find_elements(By.XPATH, "//a[@href]")
        # matching_links = list(set([
        #     link.get_attribute("href")
        #     for link in all_links
        #     if link.get_attribute("href") and link.get_attribute("href").startswith("http")
        # ]))

        # Step 3: Filter links based on keywords

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
            writer = csv.writer(file)
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

                # Body (collect from multiple tags)
                body_texts = []
                candidate_tags = ["p", "div", "span", "section", "article", "main"]

                try:
                    for tag in candidate_tags:
                        elements = driver.find_elements(By.TAG_NAME, tag)
                        for el in elements:
                            text = el.text.strip()
                            if text and len(text) > 30:  # filter out short junk
                                body_texts.append(text)

                    # Deduplicate while preserving order
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

                # Date
                date = ""
                try:
                    date_elem = driver.find_element(By.XPATH, "//time")  ##needs modification.can be other date formats as well
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
    return driver  # return driver so main() keeps using same instance


# -------------------- Main Function --------------------
def main():
    print("🚀 Starting the scraping process...")
    

    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except Exception as e:
        print(f"❌ Failed to determine script directory: {e}")
        return

    input_csv = os.path.join(script_dir, "input_sites.csv")
    output_csv = os.path.join(script_dir, "scraped_articles.csv")

    # Delete old output file
    if os.path.exists(output_csv):
        try:
            os.remove(output_csv)
        except Exception as e:
            print(f"❌ Failed to delete existing output CSV: {e}")
            return

    # Initialize driver once
    try:
        service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        print(f"❌ Failed to initialize WebDriver: {e}")
        return

    first_site = True

    # Read input CSV

    try:
        with open(input_csv, mode="r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                try:
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
                except KeyError as e:
                    print(f"❌ Missing expected column in CSV: {e}")
                except Exception as e:
                    print(f"❌ Failed to process row: {e}")
    except FileNotFoundError:
        print(f"❌ Input CSV not found at: {input_csv}")
    except Exception as e:
        print(f"❌ Error reading input CSV: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass

    print(f"\n📁 Scraping complete. Output saved to: {output_csv}")


# -------------------- Entry Point --------------------
if __name__ == "__main__":
    main()
