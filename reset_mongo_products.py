import os
from pymongo import MongoClient

def main():
    mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
    print("Connecting to MongoDB...")
    client = MongoClient(mongo_uri)
    db = client["dienmayxanh_db"]
    
    print("Dropping 'products' collection...")
    db.products.drop()
    print("Successfully dropped 'products' collection.")
    
    # We don't drop faq and scenarios because they are not being replaced right now, 
    # but we can optionally drop them if we want a full reset. For now, just products.

if __name__ == "__main__":
    main()
