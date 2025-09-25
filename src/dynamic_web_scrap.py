from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import os
import logging

# Suppress logs
logging.getLogger('selenium').setLevel(logging.CRITICAL)

# Chrome options
chrome_options = Options()
chrome_options.add_argument("--log-level=3")
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

# Use webdriver-manager to auto-download ChromeDriver
service = Service(executable_path=ChromeDriverManager().install(), log_path=os.devnull)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Open FiercePharma homepage
driver.get("https://www.fiercepharma.com/")
time.sleep(5)  # Wait for page to load

# Define your keywords to search for in article headings
keywords = ["Moderna", "mRNA", "vaccine", "COVID"]

# Find all <a> elements on the page
all_links = driver.find_elements(By.XPATH, "//a")

# Filter links whose text contains any of the keywords
matching_links = []
for link in all_links:
    text = link.text.strip()
    if any(keyword.lower() in text.lower() for keyword in keywords):
        href = link.get_attribute("href")
        # Basic filtering: href exists and starts with http (likely a full URL)
        if href and href.startswith("http"):
            matching_links.append((text, href))

# Open CSV for writing
with open("fiercepharma_article.csv", mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    # Custom headers as requested
    writer.writerow(["company", "event_type", "details", "source URL", "date", "country"])

    for title, link in matching_links:
        # Visit the article page to scrape additional info like date
        driver.get(link)
        time.sleep(3)

        # Scrape date from the article page if available
        try:
            date_element = driver.find_element(By.CSS_SELECTOR, "span.date-display-single")
            date = date_element.text.strip()
        except:
            date = ""

        # Simple company inference based on title keywords (can be improved)
        if "moderna" in title.lower():
            company = "Moderna"
        else:
            company = "Unknown"

        # You can create your own logic to infer event_type from the title or content
        if "launch" in title.lower():
            event_type = "Product Launch"
        elif "approval" in title.lower():
            event_type = "Regulatory Approval"
        elif "trial" in title.lower():
            event_type = "Clinical Trial"
        else:
            event_type = "News"

        details = title
        source_url = link
        country = "USA"  # Static here, or you could infer from content

        writer.writerow([company, event_type, details, source_url, date, country])

driver.quit()
print("✅ Articles matching keywords saved to fiercepharma_article.csv")
