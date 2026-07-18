import os
from pymongo import MongoClient

def main():
    mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
    print("Connecting to MongoDB Atlas...")
    client = MongoClient(mongo_uri)
    db = client["dienmayxanh_db"]
    products_col = db["products"]
    
    print("1. Creating Compound Index for Category & Sale Price...")
    products_col.create_index([("category", 1), ("sale_price", -1)])
    
    print("2. Creating Compound Index for Category & Discount Amount...")
    products_col.create_index([("category", 1), ("discount_amount", -1)])
    
    print("3. Updating existing documents to add 'discount_amount' field...")
    # Update all documents that don't have discount_amount (or update all just to be safe)
    # Since we need to subtract fields, we use an aggregation pipeline in update_many (MongoDB 4.2+)
    pipeline = [
        {"$set": {
            "discount_amount": {
                "$subtract": [
                    {"$ifNull": ["$original_price", 0]}, 
                    {"$ifNull": ["$sale_price", 0]}
                ]
            }
        }}
    ]
    
    result = products_col.update_many({}, pipeline)
    print(f"Successfully updated {result.modified_count} documents.")
    print("Database Optimization Complete!")

if __name__ == "__main__":
    main()
