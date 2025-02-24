from playwright.sync_api import sync_playwright
import os
import time
import json

def scrape_visible_connections(page, existing_connections=None):
    if existing_connections is None:
        existing_connections = set()
    
    new_connections = []
    
    # Get all connection cards
    connections = page.query_selector_all('div.mn-connection-card__details')
    
    for connection in connections:
        # Get name and occupation
        name_elem = connection.query_selector('.mn-connection-card__name')
        occupation_elem = connection.query_selector('.mn-connection-card__occupation')
        
        if name_elem and occupation_elem:
            name = name_elem.inner_text().strip()
            occupation = occupation_elem.inner_text().strip()
            
            # Only process if this is a new connection
            if name not in existing_connections:
                existing_connections.add(name)
                new_connections.append({
                    "name": name,
                    "occupation": occupation
                })
                print(f"{name} - {occupation}")
    
    return new_connections

def save_connections(connections, filename=None):
    """Helper function to save connections to a JSON file"""
    if filename is None:
        filename = input("\nEnter filename to save connections (e.g. 'connections.json'): ")
        if not filename.endswith('.json'):
            filename += '.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(connections, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(connections)} connections to {filename}")

def scroll_and_scrape(page):
    print("\nStarting to scroll and scrape...")
    last_height = 0
    same_height_count = 0
    all_connections = []
    existing_names = set()
    
    # Ask for filename at the start
    filename = input("\nEnter filename to save connections (e.g. 'connections.json'): ")
    if not filename.endswith('.json'):
        filename += '.json'
    
    try:
        while True:
            # Scrape visible connections
            new_connections = scrape_visible_connections(page, existing_names)
            if new_connections:
                all_connections.extend(new_connections)
                print(f"\nFound {len(new_connections)} new connections. Total: {len(all_connections)}")
                # Save progress after each batch of new connections
                save_connections(all_connections, filename)
            
            # Scroll to bottom
            current_height = page.evaluate('''() => {
                window.scrollTo(0, document.body.scrollHeight);
                return document.body.scrollHeight;
            }''')
            
            # Wait for lazy loading
            time.sleep(2)
            
            # Check if we've hit the bottom
            if current_height == last_height:
                same_height_count += 1
                
                # Check for "Show more results" button
                show_more = page.get_by_text("Show more results", exact=True)
                if show_more.is_visible():
                    print("\nClicking 'Show more results' button...")
                    show_more.click()
                    time.sleep(2)
                    same_height_count = 0  # Reset counter after clicking
                elif same_height_count >= 3:  # If height hasn't changed after 3 attempts
                    print("\nReached the bottom of the page!")
                    break
            else:
                same_height_count = 0
                print("\nScrolling... Looking for more connections...")
            
            last_height = current_height
            
    except Exception as e:
        print(f"\nScraping interrupted: {e}")
    finally:
        # Always save whatever we've collected so far
        if all_connections:
            save_connections(all_connections, filename)
    
    return all_connections

def main():
    # Ask for URL in terminal
    url = input("Please enter the LinkedIn URL: ")
    
    # Validate if it's a LinkedIn URL
    if not url.startswith(('https://www.linkedin.com/', 'https://linkedin.com/')):
        print("Please provide a valid LinkedIn URL")
        return

    # MacOS Chrome profile directory
    base_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome')
    
    # Create a specific profile for automation
    profile_dir = os.path.join(base_dir, 'Playwright_Profile')
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        try:
            # Launch Chrome with specific profile
            browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--start-maximized'
                ]
            )
            
            # Get the default page
            page = browser.pages[0]
            if not page:
                page = browser.new_page()
            
            # Set a more realistic user agent
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            })
            
            # Navigate to the URL
            print(f"Opening: {url}")
            page.goto(url)
            
            # Wait for user to navigate to the right page and type "scrape!"
            print("\nNavigate to the connections page, then type 'scrape!' and press Enter to start scrolling...")
            while input().lower().strip() != "scrape!":
                print("Type 'scrape!' to begin scrolling...")
            
            # Start scrolling and scraping
            connections = scroll_and_scrape(page)
            
            # Wait for user input to close
            input(f"\nScraping complete! Found {len(connections)} connections. Press Enter to close the browser...")
            
        except Exception as e:
            print(f"Error: {e}")
            print("\nTroubleshooting steps:")
            print("1. Make sure Chrome is completely closed")
            print("2. Check if Chrome is installed")
            print("3. Try restarting your computer if the issue persists")
        finally:
            if 'browser' in locals():
                try:
                    browser.close()
                except:
                    print("\nBrowser already closed")

if __name__ == "__main__":
    main() 