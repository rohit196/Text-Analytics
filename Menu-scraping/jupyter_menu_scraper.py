import requests
from bs4 import BeautifulSoup
import json
import csv
import time
import random
import sys
import argparse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import os
import logging
import subprocess
from datetime import datetime

# Clear sys.argv to avoid Jupyter/IPython argument conflicts
sys.argv = [sys.argv[0]]

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

class MenuScraper:
    def __init__(self, headless=True, use_proxy=False, proxy=None):
        self.use_proxy = use_proxy
        self.proxy = proxy
        self.headless = headless
        self.setup_driver()
        
    def find_chrome_binary(self):
        """Find Chrome binary location on various operating systems"""
        # First check if Chrome is in common locations
        chrome_paths = [
            # Linux paths
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            # Mac paths
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            # Windows paths
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        
        for path in chrome_paths:
            if os.path.exists(path):
                logger.info(f"Found Chrome binary at {path}")
                return path
                
        # If not found, try to find via 'which' command on Unix systems
        try:
            chrome_path = subprocess.check_output(["which", "google-chrome"], text=True).strip()
            if chrome_path:
                logger.info(f"Found Chrome binary via 'which' at {chrome_path}")
                return chrome_path
        except (subprocess.SubprocessError, FileNotFoundError):
            try:
                chrome_path = subprocess.check_output(["which", "google-chrome-stable"], text=True).strip()
                if chrome_path:
                    logger.info(f"Found Chrome binary via 'which' at {chrome_path}")
                    return chrome_path
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
        
        logger.warning("Could not find Chrome binary. Using default webdriver configuration.")
        return None
        
    def setup_driver(self):
        """Set up the Selenium WebDriver with Chrome"""
        try:
            chrome_options = Options()
            
            # Find Chrome binary
            chrome_binary = self.find_chrome_binary()
            if chrome_binary:
                chrome_options.binary_location = chrome_binary
            
            if self.headless:
                # Use the new headless mode syntax for newer Chrome versions
                chrome_options.add_argument("--headless=new")
            
            # Add common options to make Chrome more stable in Codespace/Docker environments
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            
            # Add user agent
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            chrome_options.add_argument(f"user-agent={user_agent}")
            
            if self.use_proxy and self.proxy:
                chrome_options.add_argument(f'--proxy-server={self.proxy}')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Error setting up WebDriver: {str(e)}")
            raise
    
    def random_delay(self, min_sec=1, max_sec=5):
        """Add a random delay to mimic human behavior and avoid detection"""
        delay = random.uniform(min_sec, max_sec)
        time.sleep(delay)
    
    def scrape_aw(self):
        """Scrape A&W menu"""
        try:
            logger.info("Starting A&W menu scraping")
            menu_url = "https://web.aw.ca/en/our-menu"
            self.driver.get(menu_url)
            
            # Wait for menu items to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".menu-category-container"))
            )
            
            # Allow time for dynamic content to load
            self.random_delay(2, 4)
            
            # Scroll down to load all content
            self.scroll_page()
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            menu_data = []
            
            # Extract menu categories
            menu_categories = soup.select(".menu-category-container")
            logger.info(f"Found {len(menu_categories)} menu categories")
            
            for category in menu_categories:
                # Get category name
                category_title_elem = category.select_one(".menu-category-title")
                category_name = category_title_elem.get_text(strip=True) if category_title_elem else "Uncategorized"
                logger.info(f"Processing category: {category_name}")
                
                # Extract menu items for this category
                menu_items = category.select(".menu-item")
                for item in menu_items:
                    # Extract item name
                    item_name_elem = item.select_one(".menu-item-title")
                    item_name = item_name_elem.get_text(strip=True) if item_name_elem else "Unknown"
                    
                    # Extract item description
                    item_desc_elem = item.select_one(".menu-item-desc")
                    item_description = item_desc_elem.get_text(strip=True) if item_desc_elem else ""
                    
                    # Extract price (A&W might not show prices directly on the menu page)
                    item_price_elem = item.select_one(".menu-item-price")
                    item_price = item_price_elem.get_text(strip=True) if item_price_elem else "Price not available online"
                    
                    # Extract image URL if available
                    item_image = ""
                    img_tag = item.select_one("img")
                    if img_tag and img_tag.get('src'):
                        item_image = img_tag.get('src')
                        
                        # If it's a relative URL, make it absolute
                        if item_image.startswith('/'):
                            item_image = f"https://web.aw.ca{item_image}"
                    
                    # Add nutritional info if available
                    nutritional_info = {}
                    nutrition_elem = item.select_one(".nutrition-info")
                    if nutrition_elem:
                        nutrition_items = nutrition_elem.select(".nutrition-item")
                        for n_item in nutrition_items:
                            key_elem = n_item.select_one(".nutrition-key")
                            value_elem = n_item.select_one(".nutrition-value")
                            if key_elem and value_elem:
                                key = key_elem.get_text(strip=True)
                                value = value_elem.get_text(strip=True)
                                nutritional_info[key] = value
                    
                    menu_data.append({
                        "restaurant": "A&W",
                        "category": category_name,
                        "name": item_name,
                        "price": item_price,
                        "description": item_description,
                        "image_url": item_image,
                        "nutritional_info": nutritional_info
                    })
            
            logger.info(f"Scraped {len(menu_data)} items from A&W menu")
            return menu_data
        except Exception as e:
            logger.error(f"Error scraping A&W menu: {str(e)}")
            return []
    
    def scrape_mcdonalds(self):
        """Scrape McDonald's menu"""
        try:
            logger.info("Starting McDonald's menu scraping")
            menu_url = "https://www.mcdonalds.com/us/en-us/full-menu.html"
            self.driver.get(menu_url)
            
            # Wait for menu items to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".category-wrapper"))
            )
            
            # Allow time for dynamic content to load
            self.random_delay(2, 4)
            
            # Scroll down to load all content
            self.scroll_page()
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            menu_data = []
            
            # Extract menu categories
            menu_categories = soup.select(".category-wrapper")
            logger.info(f"Found {len(menu_categories)} menu categories")
            
            for category in menu_categories:
                category_name = category.select_one("h2").get_text(strip=True) if category.select_one("h2") else "Uncategorized"
                logger.info(f"Processing category: {category_name}")
                
                # Extract menu items for this category
                menu_items = category.select(".cmp-category-item")
                for item in menu_items:
                    item_name = item.select_one(".item-title").get_text(strip=True) if item.select_one(".item-title") else "Unknown"
                    item_price = item.select_one(".item-price").get_text(strip=True) if item.select_one(".item-price") else "N/A"
                    item_description = item.select_one(".item-description").get_text(strip=True) if item.select_one(".item-description") else ""
                    item_image = ""
                    
                    img_tag = item.select_one("img")
                    if img_tag and img_tag.get('src'):
                        item_image = img_tag.get('src')
                    
                    menu_data.append({
                        "restaurant": "McDonald's",
                        "category": category_name,
                        "name": item_name,
                        "price": item_price,
                        "description": item_description,
                        "image_url": item_image
                    })
            
            logger.info(f"Scraped {len(menu_data)} items from McDonald's menu")
            return menu_data
        except Exception as e:
            logger.error(f"Error scraping McDonald's menu: {str(e)}")
            return []

    def scrape_burger_king(self):
        """Scrape Burger King menu"""
        try:
            logger.info("Starting Burger King menu scraping")
            menu_url = "https://www.bk.com/menu"
            self.driver.get(menu_url)
            
            # Wait for menu items to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".menuPage_menuCategory__Qbda1"))
            )
            
            # Allow time for dynamic content to load
            self.random_delay(2, 4)
            
            # Scroll down to load all content
            self.scroll_page()
            
            # Get page source and parse with BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            menu_data = []
            
            # Extract menu categories
            menu_categories = soup.select(".menuPage_menuCategory__Qbda1")
            logger.info(f"Found {len(menu_categories)} menu categories")
            
            for category in menu_categories:
                category_name = category.select_one("h2").get_text(strip=True) if category.select_one("h2") else "Uncategorized"
                logger.info(f"Processing category: {category_name}")
                
                # Extract menu items for this category
                menu_items = category.select(".menuItem_wrapper__X_zY_")
                for item in menu_items:
                    item_name = item.select_one(".menuItem_name__on_cM").get_text(strip=True) if item.select_one(".menuItem_name__on_cM") else "Unknown"
                    item_price = item.select_one(".menuItem_price__TPsSC").get_text(strip=True) if item.select_one(".menuItem_price__TPsSC") else "N/A"
                    item_description = item.select_one(".menuItem_description__i5zkV").get_text(strip=True) if item.select_one(".menuItem_description__i5zkV") else ""
                    item_image = ""
                    
                    img_tag = item.select_one("img")
                    if img_tag and img_tag.get('src'):
                        item_image = img_tag.get('src')
                    
                    menu_data.append({
                        "restaurant": "Burger King",
                        "category": category_name,
                        "name": item_name,
                        "price": item_price,
                        "description": item_description,
                        "image_url": item_image
                    })
            
            logger.info(f"Scraped {len(menu_data)} items from Burger King menu")
            return menu_data
        except Exception as e:
            logger.error(f"Error scraping Burger King menu: {str(e)}")
            return []
    
    def scroll_page(self, pause_time=1.0):
        """Scroll down the page to ensure all dynamic content is loaded"""
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # Scroll down to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # Wait to load page
            time.sleep(pause_time)
            
            # Calculate new scroll height and compare with last scroll height
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def save_as_json(self, data, filename):
        """Save data as JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as json_file:
                json.dump(data, json_file, indent=4, ensure_ascii=False)
            logger.info(f"Data successfully saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving JSON file: {str(e)}")
            return False
    
    def save_as_csv(self, data, filename):
        """Save data as CSV file"""
        try:
            if not data:
                logger.warning("No data to save to CSV")
                return False
                
            # For CSV, we need to flatten the nutritional_info dictionary if it exists
            flattened_data = []
            for item in data:
                flat_item = item.copy()
                
                # Handle nutritional_info if it exists
                if "nutritional_info" in flat_item and isinstance(flat_item["nutritional_info"], dict):
                    for key, value in flat_item["nutritional_info"].items():
                        flat_item[f"nutrition_{key}"] = value
                    del flat_item["nutritional_info"]
                
                flattened_data.append(flat_item)
            
            # Extract column headers from all items to ensure we include all possible fields
            all_fields = set()
            for item in flattened_data:
                all_fields.update(item.keys())
            
            fieldnames = sorted(list(all_fields))
            
            with open(filename, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(flattened_data)
            logger.info(f"Data successfully saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving CSV file: {str(e)}")
            return False
    
    def scrape_restaurant(self, restaurant_name):
        """Scrape menu based on restaurant name"""
        restaurant_name = restaurant_name.lower().strip()
        
        if "a&w" in restaurant_name or "a & w" in restaurant_name:
            return self.scrape_aw()
        elif "mcdonald" in restaurant_name:
            return self.scrape_mcdonalds()
        elif "burger king" in restaurant_name or "burgerking" in restaurant_name:
            return self.scrape_burger_king()
        else:
            logger.error(f"Unsupported restaurant: {restaurant_name}")
            return []
    
    def close(self):
        """Close the WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            logger.info("WebDriver closed")

# Function to run scraper with parameters (for Jupyter usage)
def run_scraper(restaurants=None, output_dir="menu_data", headless=True, proxy=None):
    """
    Run the scraper with the specified parameters
    
    Parameters:
        restaurants (list): List of restaurant names to scrape. Default: ["A&W", "McDonalds", "Burger King"]
        output_dir (str): Directory to save output files. Default: "menu_data"
        headless (bool): Whether to run in headless mode. Default: True
        proxy (str): Proxy server to use. Default: None
    """
    if restaurants is None:
        restaurants = ["A&W", "McDonalds", "Burger King"]
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup for using a proxy if specified
    use_proxy = proxy is not None
    
    # Initialize the scraper
    scraper = MenuScraper(
        headless=headless,
        use_proxy=use_proxy,
        proxy=proxy
    )
    
    try:
        all_menu_data = []
        
        for restaurant in restaurants:
            logger.info(f"Processing {restaurant} menu")
            menu_data = scraper.scrape_restaurant(restaurant)
            
            if menu_data:
                # Save individual restaurant data
                restaurant_name = restaurant.lower().replace(" ", "_").replace("&", "and")
                output_base = os.path.join(output_dir, restaurant_name)
                
                scraper.save_as_json(menu_data, f"{output_base}_menu.json")
                scraper.save_as_csv(menu_data, f"{output_base}_menu.csv")
                
                # Add to combined data
                all_menu_data.extend(menu_data)
        
        # Save combined data if more than one restaurant was scraped
        if len(restaurants) > 1 and all_menu_data:
            output_base = os.path.join(output_dir, "all_restaurants")
            scraper.save_as_json(all_menu_data, f"{output_base}_menu.json")
            scraper.save_as_csv(all_menu_data, f"{output_base}_menu.csv")
            
        return True
    except Exception as e:
        logger.error(f"Error in execution: {str(e)}")
        return False
    finally:
        scraper.close()