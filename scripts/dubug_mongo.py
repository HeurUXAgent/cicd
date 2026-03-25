"""Debug script to inspect MongoDB evaluations collection."""
import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

try:
    uri = os.getenv("MONGODB_URI")
    print(f"Connecting to MongoDB...")
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    
    # Force connection test
    server_info = client.server_info()
    print(f"Connected! MongoDB version: {server_info.get('version', 'unknown')}")
    
    # List databases
    dbs = client.list_database_names()
    print(f"Databases: {dbs}")
    
    db = client["heuruxagent_db"]
    colls = db.list_collection_names()
    print(f"Collections in heuruxagent_db: {colls}")
    
    total = db["evaluations"].count_documents({})
    print(f"\nTotal evaluations: {total}")
    
    if total > 0:
        completed = db["evaluations"].count_documents({"status": "completed"})
        reviewed = db["evaluations"].count_documents({"hitl_feedback.review_status": "reviewed"})
        has_url = db["evaluations"].count_documents({"input.screenshot_url": {"$exists": True}})
        print(f"Completed: {completed}")
        print(f"Reviewed: {reviewed}")
        print(f"Has screenshot_url: {has_url}")
        
        # Print first doc's relevant fields
        doc = db["evaluations"].find_one()
        if doc:
            print(f"\nSample doc keys: {list(doc.keys())}")
            print(f"status: {doc.get('status')}")
            hitl = doc.get("hitl_feedback", {})
            if isinstance(hitl, dict):
                print(f"hitl_feedback.review_status: {hitl.get('review_status')}")
            inp = doc.get("input", {})
            if isinstance(inp, dict):
                print(f"input.screenshot_url: {str(inp.get('screenshot_url', 'N/A'))[:80]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)