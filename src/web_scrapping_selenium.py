from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import csv
import time

# Setup Chrome WebDriver
service = Service('c:/Users/AnjaliRani/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe')
driver = webdriver.Chrome(service=service)

# Open FiercePharma homepage
driver.get("https://www.fiercepharma.com/")
time.sleep(5)  # Wait for page to load

# Find the article by partial text
target_text = "Moderna says updated mNEXSPIKE induces strong immune response"
elements = driver.find_elements(By.XPATH, f"//a[contains(text(), '{target_text}')]")

# Extract and save to CSV
with open("fiercepharma_article.csv", mode="w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["Title", "Link"])
    for el in elements:
        title = el.text.strip()
        link = el.get_attribute("href")
        writer.writerow([title, link])

driver.quit()
print("✅ Article saved to fiercepharma_article.csv")
