import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Try the one from Downloads just for testing
uri_downloads = "mongodb+srv://buddhimafernando:h2GFRMq4POGODI0z@wpclust.8vibaz2.mongodb.net/?retryWrites=true&w=majority&appName=WPClust"
client = MongoClient(uri_downloads)

try:
    dbs = client.list_database_names()
    print(f"Databases (Downloads URI): {dbs}")
    db_name = 'garage_billing' if 'garage_billing' in dbs else dbs[0]
    db = client[db_name]
    collections = db.list_collection_names()
    print(f"Collections in {db_name}: {collections}")
    doc = db[collections[0]].find_one() if collections else None
    print(f"Sample Document: {doc}")
except Exception as e:
    print(f"Downloads URI failed: {e}")

# Now try the one from the local .env again but with more debug
load_dotenv()
uri_local = os.getenv("MONGODB_URI")
print(f"Trying local URI: {uri_local}")
client_local = MongoClient(uri_local)
try:
    dbs = client_local.list_database_names()
    print(f"Databases (Local URI): {dbs}")
except Exception as e:
    print(f"Local URI failed: {e}")
