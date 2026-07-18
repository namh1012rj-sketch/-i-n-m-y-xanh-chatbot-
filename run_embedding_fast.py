import os
import sys
import time
import requests
import concurrent.futures
from pymongo import MongoClient
import threading
from datetime import datetime

MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
FPT_API_KEY = os.getenv("FPT_API_KEY", "705ff7cc59b841a1ba3a9482f567b45c")
LOG_FILE = "embedding_progress.log"
BATCH_SIZE = 20
MAX_WORKERS = 5 # Chạy song song 5 luồng để tăng tốc gấp 5 lần

client = MongoClient(MONGO_URI)
db = client["dienmayxanh_db"]
prod_col = db["products"]

def get_embeddings_with_retry(text_list, retries=3):
    url = "https://mkp-api.fptcloud.com/ai/genai-api/api/v1/embedding"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {FPT_API_KEY}"
    }
    data = {
        "input": text_list,
        "model": "fpt-ai-embedding-v1"
    }
    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30) # Tăng timeout lên 30s
            if response.status_code == 200:
                resp_json = response.json()
                embeddings = []
                for item in resp_json.get("data", []):
                    embeddings.append(item.get("embedding", []))
                return embeddings
            else:
                time.sleep(2)
        except requests.exceptions.RequestException as e:
            time.sleep(2)
    return None

def process_batch(batch):
    texts = []
    for p in batch:
        text = f"{p.get('category', '')} {p.get('name', '')} {p.get('brand', '')} "
        specs = p.get('specs', {})
        for k, v in specs.items():
            text += f"{k} {v} "
        texts.append(text[:2000]) # Giới hạn độ dài text tránh quá tải
    
    embeddings = get_embeddings_with_retry(texts)
    if embeddings and len(embeddings) == len(batch):
        for i, p in enumerate(batch):
            try:
                prod_col.update_one({"_id": p["_id"]}, {"$set": {"embedding": embeddings[i]}})
            except Exception:
                pass
        return len(batch)
    return 0

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
        time.sleep(60) # Ghi log mỗi 1 phút

def main():
    print("Fetching documents without embeddings...")
    products_to_embed = list(prod_col.find({"embedding": {"$exists": False}}, {"_id": 1, "name": 1, "category": 1, "brand": 1, "specs": 1}))
    total_docs = prod_col.count_documents({})
    
    if not products_to_embed:
        print("All documents embedded!")
        return

    print(f"Starting multi-threaded embedding for {len(products_to_embed)} products...")
    
    # Mở thread ghi log
    logger_thread = threading.Thread(target=progress_logger, args=(total_docs,), daemon=True)
    logger_thread.start()
    
    # Chia batch
    batches = [products_to_embed[i:i+BATCH_SIZE] for i in range(0, len(products_to_embed), BATCH_SIZE)]
    
    success_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_batch, b): b for b in batches}
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result()
                success_count += res
            except Exception as e:
                pass

    print(f"Finished embedding run. Success items in this run: {success_count}")

if __name__ == '__main__':
    # Xóa file log cũ nếu có
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("Bắt đầu tiến trình nhúng dữ liệu (Multi-threading Fast Mode)...\n")
    main()
