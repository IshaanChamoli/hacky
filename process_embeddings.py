import json
import os
from time import sleep
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index_name = "hacky"

def init_pinecone():
    """Connect to existing Pinecone index"""
    try:
        index = pc.Index(index_name)
        print(f"\n📌 Connected to Pinecone index: {index_name}")
        return index
    except Exception as e:
        print(f"❌ Error connecting to Pinecone: {str(e)}")
        return None

def get_embedding(text):
    """Get embedding for a text using OpenAI's API"""
    try:
        response = client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
            encoding_format="float"
        )
        embedding = response.data[0].embedding
        print("\n📊 Embedding generated successfully")
        return embedding
    except Exception as e:
        print(f"⚠️ Error getting embedding: {str(e)}")
        return None

def process_profiles_batch(profiles, index, batch_size=100):
    """Process profiles in batches and upload embeddings to Pinecone"""
    successful_uploads = 0
    vectors_batch = []
    
    for i, profile in enumerate(profiles, 1):
        print(f"\n[{i}/{len(profiles)}] 🔍 Processing: {profile['name']}")
        
        # Combine important points and details
        important_text = " ".join(profile.get('important', []))
        all_details = profile.get('all_details', '')
        combined_text = f"{important_text} {all_details}".strip()
        
        # Get embedding
        embedding = get_embedding(combined_text)
        
        if embedding:
            # Create vector object
            vector = {
                'id': profile['url'].split('/')[-2],  # Use LinkedIn handle as ID
                'values': embedding,
                'metadata': {
                    'url': profile['url'],
                    'name': profile['name'],
                    'text': combined_text
                }
            }
            vectors_batch.append(vector)
            successful_uploads += 1
            
            # Upload batch when it reaches batch_size
            if len(vectors_batch) >= batch_size:
                try:
                    index.upsert(vectors=vectors_batch)
                    print(f"✅ Successfully uploaded batch of {len(vectors_batch)} vectors to Pinecone")
                    vectors_batch = []  # Clear batch after upload
                except Exception as e:
                    print(f"❌ Error uploading batch to Pinecone: {str(e)}")
                    successful_uploads -= len(vectors_batch)
                    vectors_batch = []
        
        # Add a small delay to avoid rate limits
        sleep(0.5)
    
    # Upload any remaining vectors
    if vectors_batch:
        try:
            index.upsert(vectors=vectors_batch)
            print(f"✅ Successfully uploaded final batch of {len(vectors_batch)} vectors to Pinecone")
        except Exception as e:
            print(f"❌ Error uploading final batch to Pinecone: {str(e)}")
            successful_uploads -= len(vectors_batch)
    
    return successful_uploads

def main():
    print("\n🔄 Starting profile embedding process...")
    
    # Initialize Pinecone
    index = init_pinecone()
    if not index:
        print("❌ Failed to initialize Pinecone. Exiting...")
        return
    
    # Load JSON data
    try:
        with open('sangeet.json', 'r', encoding='utf-8') as f:
            profiles = json.load(f)
    except Exception as e:
        print(f"❌ Error loading JSON: {str(e)}")
        return

    print(f"📚 Loaded {len(profiles)} profiles")
    
    # Process profiles in batches
    successful_uploads = process_profiles_batch(profiles, index)
    
    print(f"\n✨ Complete! Successfully uploaded {successful_uploads} embeddings to Pinecone")

if __name__ == "__main__":
    main() 