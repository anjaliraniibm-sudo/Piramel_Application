import csv
import os
import time
import logging
from selenium import webdriver
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
# chrome_options.add_argument("--disable-gpu")
# chrome_options.add_argument("--no-sandbox")
# chrome_options.add_argument("--disable-dev-shm-usage")
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
def scrape_articles_from_url(url, keywords, csv_file_path, write_headers=False):
    print(f"\n🔍 Scraping: {url} with keywords: {keywords}")

    # Step 1: Load page
    try:
        driver.get(url)
        time.sleep(5)
    except Exception as e:
        print(f"❌ Could not load {url}: {e}")
        return

    # Step 2: Find all <a> tags
    try:
        all_links = driver.find_elements(By.XPATH, "//a")
    except Exception as e:
        print(f"❌ Failed to find links on {url}: {e}")
        return

    matching_links = []

    # Step 3: Filter links based on keywords
    for link in all_links:
        try:
            text = link.text.strip()
            if any(keyword.lower() in text.lower() for keyword in keywords):
                href = link.get_attribute("href")
                if href and href.startswith("http"):
                    matching_links.append((text, href))
        except Exception as e:
            print(f"⚠️ Error while processing a link: {e}")

    # Step 4: Write to CSV
    try:
        with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            if write_headers:
                writer.writerow(["title", "link", "date", "country"])

            for title, link in matching_links:
                try:
                    driver.get(link)
                    time.sleep(3)
                except Exception as e:
                    print(f"⚠️ Skipping link (load error): {link} - {e}")
                    continue

                # Try to extract the date
                try:
                    date_element = driver.find_element(By.XPATH, "//span[contains(@class, 'date') or contains(@class, 'Date')]")
                    date = date_element.text.strip()
                except:
                    print(f"⚠️ Date not found for link: {link}")
                    date = "Date not found"

                country = "USA"  # Default placeholder
                writer.writerow([title, link, date, country])
    except Exception as e:
        print(f"❌ Failed to write to CSV: {e}")
        return

    print(f"✅ Done scraping {url} ({len(matching_links)} matches)")

# -------------------- Main Function --------------------
def main():
    print("🚀 Starting the scraping process...")

    # Get the directory where this script is located
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
    except Exception as e:
        print(f"❌ Failed to determine script directory: {e}")
        return

    # Build the full path to the input CSV file in the same folder
    input_csv = os.path.join(script_dir, "input_sites.csv")

    # Output CSV will also be saved in the same folder
    output_csv = os.path.join(script_dir, "scraped_articles.csv")

    # Delete output file if it exists
    if os.path.exists(output_csv):
        try:
            os.remove(output_csv)
        except Exception as e:
            print(f"❌ Failed to delete existing output CSV: {e}")
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

                    scrape_articles_from_url(
                        url=url,
                        keywords=keywords,
                        csv_file_path=output_csv,
                        write_headers=first_site
                    )
                    first_site = False  # Only write headers once
                except KeyError as e:
                    print(f"❌ Missing expected column in CSV: {e}")
                except Exception as e:
                    print(f"❌ Failed to process row: {e}")
    except FileNotFoundError:
        print(f"❌ Input CSV not found at: {input_csv}")
        return
    except Exception as e:
        print(f"❌ Error reading input CSV: {e}")
        return

    driver.quit()
    print(f"\n📁 Scraping complete. Output saved to: {output_csv}")

# -------------------- Entry Point --------------------
if __name__ == "__main__":
    main()
