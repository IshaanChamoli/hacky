from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
from dotenv import load_dotenv
import time
import os
import base64
import json
from datetime import datetime
from multiprocessing import Pool, Lock
from functools import partial

# Load environment variables from .env file
load_dotenv()

# Create a lock for file writing
json_lock = Lock()

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_message(message, is_error=False):
    timestamp = get_timestamp()
    prefix = "❌" if is_error else "📝"
    print(f"\n[{timestamp}] {prefix} {message}")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analyze_profile_with_gpt4v(image_paths, profile_url):
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    # Prepare content with multiple images
    content = [
        {
            "type": "text",
            "text": """Please analyze these LinkedIn profile screenshots and extract information in the following JSON format:
            {
                "url": "LinkedIn profile URL",
                "name": "Full name of the person",
                "important": ["List of key achievements, associations, and important keywords", "e.g. Software Engineer", "Google", "Stanford", "YC"],
                "all_details": "A 200-300 word comprehensive summary of the person's profile, including their main roles, career highlights, education, notable achievements, intentions, interests, etc."
            }
            
            Return ONLY the JSON object with no additional text. Make sure the summary is as informative as possible, doesnt even have to be full proper sentences, focus on words that would be useful to a RAG database. Cover AS MUCH as possible in the word count."""
        }
    ]
    
    # Add all images to content
    for image_path in image_paths:
        base64_image = encode_image(image_path)
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{base64_image}",
                "detail": "high"
            }
        })
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": content
            }],
            max_tokens=4096,
            temperature=0
        )
        
        try:
            response_text = response.choices[0].message.content
            
            # Clean up the response text if it contains markdown code blocks
            if response_text.startswith('```'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            # Parse the JSON response
            profile_data = json.loads(response_text)
            
            # Ensure URL is included
            profile_data["url"] = profile_url
            
            return profile_data
            
        except json.JSONDecodeError as e:
            print(f"\n❌ Error parsing JSON response: {str(e)}")
            print("Raw response:", response.choices[0].message.content)
            return None
        
    except Exception as e:
        print(f"\n❌ Error calling OpenAI API: {str(e)}")
        return None

def process_single_profile(url, output_file):
    try:
        log_message(f"Starting processing for: {url}")
        
        # Create a unique profile directory for this process
        process_id = os.getpid()
        base_profile_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default')
        new_profile_dir = os.path.expanduser(f'~/Library/Application Support/Google/Chrome/Profile_{process_id}')
        
        # Copy the default profile to a new directory if it doesn't exist
        if not os.path.exists(new_profile_dir):
            try:
                import shutil
                shutil.copytree(base_profile_dir, new_profile_dir)
                log_message(f"Created new Chrome profile for process {process_id}")
            except Exception as e:
                log_message(f"Warning: Could not copy Chrome profile: {str(e)}", True)
        
        # Setup Chrome with optimized options
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--start-maximized')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-web-security')
        options.add_argument('--dns-prefetch-disable')
        options.add_argument('--disable-javascript')
        options.page_load_strategy = 'eager'
        
        # Use the unique profile directory
        options.add_argument(f'user-data-dir={new_profile_dir}')
        
        # Add a unique debugging port
        options.add_argument(f'--remote-debugging-port={9222 + process_id % 1000}')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        profile_name = url.strip('/').split('/')[-1]
        screenshots_dir = f"{profile_name}_screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)
        
        try:
            driver.get(url)
        except Exception as e:
            log_message(f"Error loading page, retrying once: {str(e)}", True)
            driver.refresh()
        
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            log_message("Warning: Page load timeout, proceeding anyway")
        
        time.sleep(1)
        
        # Take screenshots
        viewport_height = driver.execute_script("return window.innerHeight")
        total_height = driver.execute_script("return document.body.scrollHeight")
        
        screenshot_paths = []
        current_position = 0
        screenshot_number = 1
        
        while current_position < total_height:
            driver.execute_script(f"window.scrollTo(0, {current_position});")
            time.sleep(0.5)
            
            screenshot_path = os.path.join(screenshots_dir, f"screenshot_{screenshot_number}.png")
            driver.save_screenshot(screenshot_path)
            screenshot_paths.append(screenshot_path)
            
            log_message(f"Captured screenshot {screenshot_number} for {profile_name}")
            
            current_position += viewport_height
            screenshot_number += 1
        
        # Analyze with GPT-4V
        log_message(f"Analyzing profile with GPT-4 Vision: {profile_name}")
        profile_data = analyze_profile_with_gpt4v(screenshot_paths, url)
        
        if profile_data:
            # Update the JSON file with lock to prevent concurrent writes
            with json_lock:
                try:
                    # Read existing data
                    existing_data = []
                    if os.path.exists(output_file):
                        with open(output_file, 'r', encoding='utf-8') as f:
                            existing_data = json.load(f)
                    
                    # Add new profile
                    existing_data.append(profile_data)
                    
                    # Write back to file
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(existing_data, f, indent=2, ensure_ascii=False)
                    log_message(f"Updated {output_file} with profile: {profile_name}")
                except Exception as e:
                    log_message(f"Error updating JSON file: {str(e)}", True)
        
        # Clean up screenshots
        try:
            import shutil
            shutil.rmtree(screenshots_dir)
            log_message(f"Cleaned up directory: {screenshots_dir}")
        except Exception as e:
            log_message(f"Warning: Could not delete screenshots directory: {str(e)}", True)
        
    except Exception as e:
        log_message(f"Error processing profile {url}: {str(e)}", True)
    finally:
        if 'driver' in locals():
            driver.quit()
            log_message(f"Browser closed for {profile_name}")
            
            # Clean up the temporary profile directory
            try:
                import shutil
                shutil.rmtree(new_profile_dir)
                log_message(f"Cleaned up Chrome profile directory: {new_profile_dir}")
            except Exception as e:
                log_message(f"Warning: Could not delete Chrome profile: {str(e)}", True)

def process_profiles():
    output_file = "ishaan.json"
    
    try:
        # Read URLs from file
        with open('ishaan.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        total_urls = len(urls)
        log_message(f"Found {total_urls} profiles to process")
        
        # Process URLs in parallel with 5 workers
        with Pool(5) as pool:
            # Use partial to pass output_file to process_single_profile
            process_func = partial(process_single_profile, output_file=output_file)
            
            # Map URLs to workers
            pool.map(process_func, urls)
        
        log_message(f"✅ Processing complete!")
        log_message(f"Results saved to: {output_file}")
        
    except Exception as e:
        log_message(f"Fatal error: {str(e)}", True)

def main():
    log_message("Starting LinkedIn Profile Processor (Parallel Version)")
    process_profiles()

if __name__ == "__main__":
    main() 