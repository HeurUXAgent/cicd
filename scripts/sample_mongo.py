import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load env from .env in the same directory
load_dotenv()

uri = os.getenv("MONGODB_URI")
if not uri:
    print("MONGODB_URI not found in environment")
    exit(1)

client = MongoClient(uri)
# The database name might be different, let's list them
dbs = client.list_database_names()
print(f"Databases: {dbs}")

# Attempt to find the correct database. If not specified, we'll check common names.
db_name = os.getenv("dbName", "garage_billing") # Defaulting to garage_billing if not set
if db_name not in dbs:
    print(f"Database {db_name} not found. Available: {dbs}")
    # Try to guess
    if 'garage_billing' in dbs:
        db_name = 'garage_billing'
    elif 'heurUXAgent' in dbs:
        db_name = 'heurUXAgent'
    else:
        db_name = dbs[0] if dbs else None

if not db_name:
    print("No database found")
    exit(1)

print(f"Using database: {db_name}")
db = client[db_name]

collections = db.list_collection_names()
print(f"Collections: {collections}")

for coll_name in collections:
    print(f"\n--- Sample from {coll_name} ---")
    doc = db[coll_name].find_one()
    print(doc)
