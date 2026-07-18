import os
import sys
import time
import requests
from pymongo import MongoClient
import threading
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
FPT_API_KEY = os.getenv("FPT_API_KEY", "705ff7cc59b841a1ba3a9482f567b45c")
LOG_FILE = "embedding_progress.log"
BATCH_SIZE = 20

client = MongoClient(MONGO_URI)
db = client["dienmayxanh_db"]
prod_col = db["products"]

def get_embeddings_safe(text_list):
    url = os.getenv("EMBEDDING_API_URL", "https://mkp-api.fptcloud.com/v1/embeddings")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FPT_API_KEY}"
    }
    data = {
        "input": text_list,
        "model": "fpt-ai-embedding-v1"
    }
    while True:
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            if response.status_code == 200:
                resp_json = response.json()
                embeddings = []
                for item in resp_json.get("data", []):
                    embeddings.append(item.get("embedding", []))
                return embeddings
            elif response.status_code == 429:
                print("Hit Rate Limit (429). Sleeping for 60 seconds...")
                time.sleep(60)
            else:
                print(f"API Error: {response.status_code}. Sleeping 10s...")
                time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}. Sleeping 10s...")
            time.sleep(10)

def progress_logger(total):
    while True:
        try:
            embedded = prod_col.count_documents({"embedding": {"$exists": True}})
            progress = (embedded / total) * 100 if total > 0 else 0
            log_line = f"[{datetime.now().strftime('%H:%M:%S')}] Total: {total} | Embedded: {embedded} | Progress: {progress:.2f}%\n"
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_line)
            if embedded >= total:
                break
        except Exception:
            pass
        time.sleep(60)

def main():
    print("Fetching documents without embeddings...")
    products_to_embed = list(prod_col.find({"embedding": {"$exists": False}}, {"_id": 1, "name": 1, "category": 1, "brand": 1, "specs": 1}))
    total_docs = prod_col.count_documents({})
    
    if not products_to_embed:
        print("All documents embedded!")
        return

    print(f"Starting Safe Mode embedding for remaining {len(products_to_embed)} products...")
    
    logger_thread = threading.Thread(target=progress_logger, args=(total_docs,), daemon=True)
    logger_thread.start()
    
    success_count = 0
    for i in range(0, len(products_to_embed), BATCH_SIZE):
        batch = products_to_embed[i:i+BATCH_SIZE]
        texts = []
        for p in batch:
            text = f"{p.get('category', '')} {p.get('name', '')} {p.get('brand', '')} "
            specs = p.get('specs', {})
            for k, v in specs.items():
                text += f"{k} {v} "
            texts.append(text[:2000])
        
        embeddings = get_embeddings_safe(texts)
        if embeddings and len(embeddings) == len(batch):
            for j, p in enumerate(batch):
                prod_col.update_one({"_id": p["_id"]}, {"$set": {"embedding": embeddings[j]}})
            success_count += len(batch)

    print(f"Finished. Success items: {success_count}")

if __name__ == '__main__':
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\nKhởi động lại trình nạp an toàn (Safe Mode)...\n")
    main()
