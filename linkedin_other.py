from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import time
import os
from datetime import datetime
from selenium.webdriver.common.keys import Keys
import re

def save_urls(urls_by_page, filename='connections.json'):
    """Helper function to save URLs to a JSON file with page information"""
    # Add timestamp to the save
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_profiles": sum(len(urls) for urls in urls_by_page.values()),
        "pages": urls_by_page
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Saved {data['total_profiles']} URLs across {len(urls_by_page)} pages to {filename}")

def extract_profile_urls(driver, page_number):
    print(f"\n🔍 Scanning page {page_number} for profile URLs...")
    
    # Wait for the first profile container to be present
    try:
        # First wait for the search results container
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.search-results-container'))
        )
        
        # Then wait for profile containers
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-chameleon-result-urn]'))
        )
        
        # Additional wait to ensure all containers are loaded
        time.sleep(2)  # Short sleep to let any remaining profiles load
        
    except TimeoutException:
        print("   No profile containers found")
        return set()
    
    # Get all containers at once
    containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
    expected_count = 10  # LinkedIn typically shows 10 results per page
    
    # If we don't see enough results, wait a bit more
    if len(containers) < expected_count:
        print(f"   Found only {len(containers)} containers, waiting for more...")
        time.sleep(2)
        containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
    
    print(f"   Found {len(containers)} potential profile containers")
    
    profile_urls = set()
    for i, container in enumerate(containers, 1):
        try:
            link = container.find_element(By.CSS_SELECTOR, 'a[href*="linkedin.com/in/"]')
            url = link.get_attribute('href').split('?')[0]  # Clean URL immediately
            profile_urls.add(url)
            print(f"   ✅ [{i}/{len(containers)}] Found: {url}")
        except:
            continue
    
    print(f"\n📊 Successfully extracted {len(profile_urls)} unique URLs from page {page_number}")
    return profile_urls

def get_next_page_url(current_url, page_number):
    """Generate URL for the next page by modifying the page parameter"""
    # If page parameter exists, replace it with new page number
    if 'page=' in current_url:
        # Use regex to replace any page number after 'page=' with the new page number
        return re.sub(r'page=\d+', f'page={page_number}', current_url)
    else:
        # If no page parameter exists, add it
        return f"{current_url}&page={page_number}"

def main():
    print("\n🔗 LinkedIn Profile URL Extractor 🔗")
    url = input("\nPlease enter the LinkedIn URL: ")
    if not url.startswith(('https://www.linkedin.com/', 'https://linkedin.com/')):
        print("❌ Please provide a valid LinkedIn URL")
        return
    
    # Setup Chrome options
    print("\n🌐 Setting up Chrome browser in headless mode...")
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')  # New headless mode
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1920,1080')  # Set a good default window size
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')  # Recommended for headless
    options.add_argument('--no-sandbox')  # Required for some systems
    
    # Use existing Chrome profile
    profile_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default')
    options.add_argument(f'user-data-dir={profile_dir}')
    
    try:
        print("   Starting Chrome in headless mode...")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        # Since we're headless, no need to wait for manual navigation
        print("\n⚡ Starting scraping immediately...")
        
        urls_by_page = {}
        page_number = 1
        
        try:
            while True:
                print(f"\n📄 Processing page {page_number}...")
                
                # Navigate to next page
                if page_number > 1:
                    next_url = get_next_page_url(driver.current_url, page_number)
                    print(f"\n⏭️ Moving to page {page_number}...")
                    print(f"   URL: {next_url}")
                    driver.get(next_url)
                
                # Extract URLs from current page
                new_urls = extract_profile_urls(driver, page_number)
                
                # If no URLs found, we've reached the end
                if not new_urls:
                    print("\n🏁 No more profiles found - reached the last page!")
                    break
                
                urls_by_page[f"page_{page_number}"] = list(new_urls)
                save_urls(urls_by_page)
                page_number += 1
                
        except Exception as e:
            print(f"\n❌ Scraping interrupted: {e}")
        finally:
            if urls_by_page:
                save_urls(urls_by_page)
        
        total_urls = sum(len(urls) for urls in urls_by_page.values())
        print(f"\n✨ Scraping complete!")
        print(f"   Total pages processed: {len(urls_by_page)}")
        print(f"   Total unique profiles found: {total_urls}")
        input("\n👋 Press Enter to close the browser...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        try:
            driver.quit()
            print("\n🔒 Browser closed successfully")
        except:
            print("\n⚠️ Browser already closed")

if __name__ == "__main__":
    main() 