import requests
from bs4 import BeautifulSoup
import csv

# Step 1: Define the target URL
url = "https://www.fiercepharma.com/"

# Step 2: Send a GET request
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# Step 3: Find all anchor tags that link to articles
article_links = soup.find_all('a', href=True)

# Step 4: Filter for the specific article
target_text = "Moderna says updated mNEXSPIKE induces strong immune response"
found = False

for tag in article_links:
    if target_text.lower() in tag.text.strip().lower():
        title = tag.text.strip()
        full_link = f"https://www.fiercepharma.com{tag['href']}"
        found = True
        break

# Step 5: Save to CSV
if found:
    with open("fiercepharma_article.csv", mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Title", "Link"])
        writer.writerow([title, full_link])
    print("✅ Article saved to fiercepharma_article.csv")
else:
    print("❌ Article not found on the homepage.")
