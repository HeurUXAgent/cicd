import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("MONGODB_URI")
client = MongoClient(uri)
dbs = client.list_database_names()

# Focus on heurUXAgent or garage_billing
db_name = 'heurUXAgent' if 'heurUXAgent' in dbs else ('garage_billing' if 'garage_billing' in dbs else dbs[0])
db = client[db_name]

print(f"Using DB: {db_name}")

collections = db.list_collection_names()
print(f"Collections: {collections}")

for coll_name in collections:
    print(f"\n--- {coll_name} ---")
    # Find a document that has a URL or an image field
    doc = db[coll_name].find_one({"$or": [{"url": {"$exists": True}}, {"imageUrl": {"$exists": True}}, {"image": {"$exists": True}}]})
    if doc:
        print(f"Found document with image field in {coll_name}:")
        print(doc)
    else:
        # Just print any doc to see structure
        doc = db[coll_name].find_one()
        print(f"Sample document in {coll_name}:")
        print(doc)
