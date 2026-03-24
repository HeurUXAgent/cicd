import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri)
db = client['heuruxagent_db']
evaluations = db['evaluations']

print("Sampling 5 documents...")
for doc in evaluations.find({"status": "completed"}).limit(5):
    print(f"\nID: {doc.get('evaluation_id')}")
    print(f"URL: {doc.get('input', {}).get('screenshot_url')}")
