import time
import json
import csv
import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup

# Set up logging
log_directory = "logs"
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(log_directory, f"menu_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def scroll_to_bottom(driver, pause_time=1.0):
    """Scroll to the bottom of the page to ensure all dynamic content is loaded."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def scrape_aw_menu():
    """Scrape A&W menu using Selenium with WebDriver Manager for Firefox"""
    logger.info("Starting A&W menu scraping")
    menu_url = "https://web.aw.ca/en/our-menu"

    # Retry logic for scraping
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Configure Firefox options
            options = Options()
            options.add_argument("--headless")  # Headless mode
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            
            # Use WebDriver Manager to get the correct GeckoDriver version
            service = Service(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
            
            logger.info("WebDriver successfully initialized with the correct GeckoDriver version")
            driver.get(menu_url)
            
            # Wait for the page to fully load
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".category-menu"))
            )
            logger.info("Menu page loaded successfully")
            
            # Scroll to the bottom to load all dynamic content
            scroll_to_bottom(driver)
            
            # Get page source and parse it with BeautifulSoup
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract menu categories
            category_menu = soup.select('.category-menu a')
            menu_categories = [category.get_text(strip=True) for category in category_menu]
            logger.info(f"Found {len(menu_categories)} menu categories: {menu_categories}")
            
            # Extract menu items for each category
            menu_data = []
            for category in menu_categories:
                logger.info(f"Processing category: {category}")
                category_class = category.replace(' ', '-').replace('&', 'and').replace("'", "").lower()
                category_items = soup.select(f".{category_class} .item")
                for item in category_items:
                    item_name_elem = item.select_one(".item-name h3")
                    item_name = item_name_elem.get_text(strip=True) if item_name_elem else "Unknown"
                    
                    # Extract item description
                    item_desc_elem = item.select_one(".item-description")
                    item_description = item_desc_elem.get_text(strip=True) if item_desc_elem else ""
                    
                    # Extract price
                    item_price_elem = item.select_one(".item-price")
                    item_price = item_price_elem.get_text(strip=True) if item_price_elem else "Price not available online"
                    
                    # Extract image URL
                    item_image = ""
                    img_tag = item.select_one("img")
                    if img_tag and img_tag.get('src'):
                        item_image = img_tag.get('src')
                        if item_image.startswith('/'):
                            item_image = f"https://web.aw.ca{item_image}"
                    
                    menu_data.append({
                        "restaurant": "A&W",
                        "category": category,
                        "name": item_name,
                        "price": item_price,
                        "description": item_description,
                        "image_url": item_image
                    })
            
            logger.info(f"Scraped {len(menu_data)} items from A&W menu")
            
            # Close the browser
            driver.quit()
            
            # Save data
            if menu_data:
                os.makedirs("menu_data", exist_ok=True)
                
                # Save as JSON
                with open("menu_data/aw_menu.json", 'w', encoding='utf-8') as json_file:
                    json.dump(menu_data, json_file, indent=4, ensure_ascii=False)
                
                # Save as CSV
                with open("menu_data/aw_menu.csv", 'w', newline='', encoding='utf-8') as csv_file:
                    fieldnames = menu_data[0].keys()
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(menu_data)
                
                logger.info("Menu data saved to menu_data/aw_menu.json and menu_data/aw_menu.csv")
                
            return menu_data
        
        except Exception as e:
            logger.error(f"Error scraping A&W menu: {str(e)}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying... ({attempt + 1}/{max_retries})")
                time.sleep(5)  # Wait before retrying
            else:
                logger.error("Max retries reached. Exiting.")
                return []

# Run the scraper directly if executed as a script
if __name__ == "__main__":
    scrape_aw_menu()