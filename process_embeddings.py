import json
import os
from time import sleep
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_embedding(text):
    """Get embedding for a text using OpenAI's API"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            encoding_format="float"
        )
        # Print just first 5 values of embedding
        embedding = response.data[0].embedding
        print("\n📊 First 5 values of embedding:")
        print(embedding[:5])
        return embedding
    except Exception as e:
        print(f"⚠️ Error getting embedding: {str(e)}")
        return None

def process_profile(profile):
    """Process a single profile and get its embedding"""
    # Combine important points and details
    important_text = " ".join(profile.get('important', []))
    all_details = profile.get('all_details', '')
    combined_text = f"{important_text} {all_details}".strip()
    
    # Print the combined text
    print("\n📝 Combined text being sent to OpenAI:")
    print(combined_text)
    print("\n" + "-"*80)
    
    # Get embedding
    embedding = get_embedding(combined_text)
    
    return {
        'url': profile['url'],
        'name': profile['name'],
        'embedding': embedding
    }

def main():
    print("\n🔄 Starting profile embedding process...")
    
    # Load JSON data
    try:
        with open('ishaan.json', 'r', encoding='utf-8') as f:
            profiles = json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON: {str(e)}")
        return

    print(f"📚 Loaded {len(profiles)} profiles")
    
    # Process each profile
    embeddings = []
    for i, profile in enumerate(profiles, 1):
        print(f"\n[{i}/{len(profiles)}] 🔍 Processing: {profile['name']}")
        
        result = process_profile(profile)
        if result['embedding']:
            embeddings.append(result)
            print(f"✅ Successfully created embedding for {profile['name']}")
        else:
            print(f"❌ Failed to create embedding for {profile['name']}")
            
        # Add a small delay to avoid rate limits
        sleep(0.5)
        
        # Optional: Process only first few profiles for testing
        if i == 3:  # Change this number to process more/fewer profiles
            break
    
    print(f"\n✨ Complete! Processed {len(embeddings)} embeddings successfully")
    
    # Optionally save embeddings to file
    try:
        with open('profile_embeddings.json', 'w', encoding='utf-8') as f:
            json.dump(embeddings, f, ensure_ascii=False, indent=2)
        print("💾 Saved embeddings to profile_embeddings.json")
    except Exception as e:
        print(f"⚠️ Error saving embeddings: {str(e)}")

if __name__ == "__main__":
    main() 