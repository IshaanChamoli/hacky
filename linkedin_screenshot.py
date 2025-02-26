from playwright.sync_api import sync_playwright
from openai import OpenAI
from dotenv import load_dotenv
import time
import os
import base64
import json
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

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

def process_single_profile(page, url, output_file):
    try:
        log_message(f"Starting processing for: {url}")
        
        profile_name = url.strip('/').split('/')[-1]
        screenshots_dir = f"{profile_name}_screenshots"
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Navigate to the URL without waiting
        page.goto(url, wait_until='domcontentloaded')  # Less strict wait
        
        # Wait 2 seconds for content to load before starting screenshots
        time.sleep(2)
        
        # Take initial screenshot
        screenshot_number = 1
        screenshot_paths = []
        
        # Initial viewport height
        viewport_height = page.viewport_size['height']
        
        # Keep scrolling and taking screenshots
        last_height = 0
        same_height_count = 0
        
        while True:
            # Take screenshot of current viewport
            screenshot_path = os.path.join(screenshots_dir, f"screenshot_{screenshot_number}.png")
            page.screenshot(path=screenshot_path)
            screenshot_paths.append(screenshot_path)
            log_message(f"Captured screenshot {screenshot_number} for {profile_name}")
            
            # Scroll down one viewport height
            page.evaluate(f'window.scrollBy(0, {viewport_height})')
            time.sleep(1)  # Small wait for content to load
            
            # Get new scroll height
            current_height = page.evaluate('window.pageYOffset')
            
            # Check if we've reached the bottom
            if current_height == last_height:
                same_height_count += 1
                if same_height_count >= 2:  # If height hasn't changed after 2 attempts
                    break
            else:
                same_height_count = 0
                screenshot_number += 1
            
            last_height = current_height
        
        # Analyze with GPT-4V
        log_message(f"Analyzing profile with GPT-4 Vision: {profile_name}")
        profile_data = analyze_profile_with_gpt4v(screenshot_paths, url)
        
        if profile_data:
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

def process_profiles():
    output_file = "sangeet.json"
    
    try:
        # Read URLs from file
        with open('sangeet.txt', 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        total_urls = len(urls)
        log_message(f"Found {total_urls} profiles to process")
        
        # MacOS Chrome profile directory
        base_dir = os.path.expanduser('~/Library/Application Support/Google/Chrome')
        profile_dir = os.path.join(base_dir, 'Playwright_Profile')
        os.makedirs(profile_dir, exist_ok=True)
        
        with sync_playwright() as p:
            # Launch Chrome with specific profile
            browser = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                channel="chrome",
                headless=True,
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
            
            # Process each URL
            for url in urls:
                process_single_profile(page, url, output_file)
                time.sleep(2)  # Small delay between profiles
            
            # Close browser
            browser.close()
            
        log_message(f"✅ Processing complete!")
        log_message(f"Results saved to: {output_file}")
        
    except Exception as e:
        log_message(f"Fatal error: {str(e)}", True)

def main():
    log_message("Starting LinkedIn Profile Processor")
    process_profiles()

if __name__ == "__main__":
    main() 