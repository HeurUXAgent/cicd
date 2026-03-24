import os
import json
import requests
from pymongo import MongoClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Configuration
MONGO_URI = os.getenv("MONGODB_URI")
DB_NAME = "heuruxagent_db"
COLLECTION_NAME = "expert_validation_dataset" # Updated collection
OUTPUT_DIR = Path("data")
IMAGES_DIR = OUTPUT_DIR / "images"
JSONL_FILE = OUTPUT_DIR / "tuning_data.jsonl"

# Create directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def download_image(url, target_path):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        with open(target_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def main():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]

    # Query all records from the expert validation dataset
    cursor = collection.find()
    
    examples = []
    count = 0

    print("Starting data extraction from expert_validation_dataset...")
    for doc in cursor:
        ui_id = doc.get("ui_id", "unknown")
        image_url = doc.get("image_url")
        expert_report = doc.get("expert_report")

        if not image_url or not expert_report:
            continue

        # Download image
        image_name = f"{ui_id}.png"
        image_path = IMAGES_DIR / image_name
        
        if not image_path.exists():
            print(f"Downloading image for {ui_id}...")
            if not download_image(image_url, image_path):
                continue
        
        # Format for Vertex AI Multimodal SFT
        # Target is the structured expert report as a JSON string
        example = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Analyze this interface screenshot and generate a detailed UI/UX report including feedback items, UX score, and a summary."},
                        {"fileData": {"mimeType": "image/png", "fileUri": str(image_path)}} 
                    ]
                },
                {
                    "role": "model",
                    "parts": [
                        {"text": json.dumps(expert_report, indent=2)}
                    ]
                }
            ]
        }
        examples.append(example)
        count += 1
        if count % 10 == 0:
            print(f"Processed {count} examples...")

    # Write to JSONL
    with open(JSONL_FILE, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

    print(f"Extraction complete. Total examples: {count}")
    print(f"Dataset saved to {JSONL_FILE}")

if __name__ == "__main__":
    main()
