from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import json
import time
import os

def save_urls(urls, filename=None):
    """Helper function to save URLs to a JSON file"""
    if filename is None:
        filename = input("\nEnter filename to save URLs (e.g. 'linkedin_urls.json'): ")
        if not filename.endswith('.json'):
            filename += '.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({"profile_urls": list(urls)}, f, indent=2)
    print(f"\nSaved {len(urls)} URLs to {filename}")

def extract_profile_urls(driver):
    # Wait a bit for JavaScript content to load
    time.sleep(2)
    
    # First find all search result containers
    # Looking for the container divs with data-chameleon-result-urn attribute
    containers = driver.find_elements(By.CSS_SELECTOR, 'div[data-chameleon-result-urn]')
    
    # Extract LinkedIn profile URLs
    profile_urls = set()
    for container in containers:
        try:
            # Find the link within this container
            link = container.find_element(By.CSS_SELECTOR, 'a[href*="linkedin.com/in/"]')
            url = link.get_attribute('href')
            if url:
                profile_urls.add(url)
                print(f"Found profile: {url}")
        except:
            continue
    
    return profile_urls

def main():
    url = input("Please enter the LinkedIn URL: ")
    if not url.startswith(('https://www.linkedin.com/', 'https://linkedin.com/')):
        print("Please provide a valid LinkedIn URL")
        return
    
    # Setup Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    
    # Use existing Chrome profile
    profile_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default')
    options.add_argument(f'user-data-dir={profile_dir}')
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        
        print("\nNavigate to the connections page, then type 'scrape!' and press Enter to start scraping...")
        while input().lower().strip() != "scrape!":
            print("Type 'scrape!' to begin...")
        
        # Get filename for saving results
        filename = input("\nEnter filename to save URLs (e.g. 'linkedin_urls.json'): ")
        if not filename.endswith('.json'):
            filename += '.json'
        
        all_urls = set()
        page_number = 1
        
        try:
            while True:
                print(f"\nScraping page {page_number}...")
                
                # Extract URLs from current page
                new_urls = extract_profile_urls(driver)
                all_urls.update(new_urls)
                
                print(f"Found {len(new_urls)} new URLs on this page. Total unique URLs: {len(all_urls)}")
                save_urls(all_urls, filename)
                
                # Look for and click next button if available
                try:
                    next_button = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'button[aria-label="Next"]'))
                    )
                    if not next_button.is_enabled():
                        print("\nReached the last page!")
                        break
                    next_button.click()
                    page_number += 1
                    time.sleep(2)  # Wait for page transition
                except TimeoutException:
                    print("\nNo more pages available!")
                    break
                
        except Exception as e:
            print(f"\nScraping interrupted: {e}")
        finally:
            if all_urls:
                save_urls(all_urls, filename)
        
        print(f"\nTotal unique profile URLs found: {len(all_urls)}")
        input("\nPress Enter to close the browser...")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            driver.quit()
        except:
            print("Browser already closed")

if __name__ == "__main__":
    main() 