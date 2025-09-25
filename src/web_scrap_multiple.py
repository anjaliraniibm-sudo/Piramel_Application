from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import os
import logging

# -------------------- Setup Chrome Driver --------------------
logging.getLogger('selenium').setLevel(logging.CRITICAL)

chrome_options = Options()
# chrome_options.add_argument("--headless")               
# chrome_options.add_argument("--disable-gpu") 
chrome_options.add_argument("--log-level=3")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
driver = webdriver.Chrome(service=service, options=chrome_options)

# -------------------- Scraper Function --------------------
def scrape_articles_from_url(url, keywords, csv_file_path, write_headers=False):
    print(f"\n🔍 Scraping: {url} with keywords: {keywords}")
    
    try:
        driver.get(url)
        time.sleep(5)  # Wait for page to load
    except Exception as e:
        print(f"❌ Failed to load {url}: {e}")
        return

    all_links = driver.find_elements(By.XPATH, "//a")
    matching_links = []

    for link in all_links:
        text = link.text.strip()
        if any(keyword.lower() in text.lower() for keyword in keywords):
            href = link.get_attribute("href")
            if href and href.startswith("http"):
                matching_links.append((text, href))

    with open(csv_file_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if write_headers:
            writer.writerow(["title", "link", "date", "country"])

        for title, link in matching_links:
            try:
                driver.get(link)
                time.sleep(3)
            except:
                print(f"⚠️ Skipping broken link: {link}")
                continue

            # Try extracting the publication date
            try:
                date_element = driver.find_element(By.XPATH, "//span[contains(@class, 'date') or contains(@class, 'Date')]")
                date = date_element.text.strip()
            except:
                date = ""

            country = "USA"

            writer.writerow([title, link, date, country])

    print(f"✅ Scraped {len(matching_links)} articles from {url}")

# -------------------- Main Function --------------------
def main():
    csv_file = "fiercepharma_article.csv"

    # Remove file if it already exists
    if os.path.exists(csv_file):
        os.remove(csv_file)

    # Scrape from FiercePharma
    scrape_articles_from_url(
        url="https://www.fiercepharma.com/",
        keywords=["Moderna", "mRNA", "vaccine", "COVID"],
        csv_file_path=csv_file,
        write_headers=True  # Write headers only once
    )

    # Scrape from ContractPharma
    scrape_articles_from_url(
        url="https://www.contractpharma.com/",
        keywords=["streamline", "partner", "archiving"],
        csv_file_path=csv_file,
        write_headers=False
    )

    # Close the browser
    driver.quit()
    print(f"\n📁 All data saved to: {csv_file}")

# -------------------- Entry Point --------------------
if __name__ == "__main__":
    main()
