import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import json
import os
import re
import requests
import time
import numpy as np
from typing import Dict, Any, List

# Thông số kết nối API Cloud Embedding
EMBEDDING_API_KEY = "sk-8sWyb2aQoafIyW91kzGGXz-FANr4ql-jciS5zNPYzhs="
# Thay thế URL này bằng Endpoint thực tế của nền tảng bạn đang sử dụng (Dưới đây là một ví dụ chuẩn OpenAI)
EMBEDDING_API_URL = os.getenv("EMBEDDING_API_URL", "https://mkp-api.fptcloud.com/v1/embeddings") 
EMBEDDING_MODEL_NAME = "Vietnamese_Embedding"

try:
    from pymongo import MongoClient
    from pymongo.errors import ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

class DataPreprocessor:
    """
    BỘ TIỀN XỬ LÝ DỮ LIỆU & INDEXING MONGODB
    Nhiệm vụ:
    1. Kết nối tới MongoDB (Cloud Atlas hoặc Local). Tự động dùng Mock DB nếu offline.
    2. Đồng bộ hóa dữ liệu từ mock_db.json vào MongoDB (Tự khởi tạo).
    3. Tạo các chỉ mục (Indexes) để tối ưu hóa truy vấn.
    4. Xây dựng Vector Index (RAG) offline để xếp hạng ngữ nghĩa.
    """
    def __init__(self, db_path: str, mongo_uri: str = None):
        self.db_path = db_path
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
        self.use_mock_db = False
        
        # Kết nối MongoDB
        self.client = None
        self.db = None
        self.init_mongodb_connection()
        
        # Đọc dữ liệu ban đầu từ mock_db.json
        self.raw_data = self.load_json_db()
        
        # Tiền xử lý chuyển các spec có dạng text số thành số thực để tối ưu bộ lọc RAG/SQL
        for p in self.raw_data.get("products", []):
            for k, v in list(p["specs"].items()):
                if isinstance(v, str):
                    num_match = re.search(r'(\d+[\.\d]*)', v)
                    if num_match:
                        try:
                            val_str = num_match.group(1)
                            val = float(val_str) if "." in val_str else int(val_str)
                            p["specs"][k + "_numeric"] = val
                        except ValueError:
                            pass
        
        # Nạp dữ liệu và đồng bộ vào MongoDB (nếu khả dụng) hoặc dùng bộ nhớ đệm
        self.products = []
        self.faq = []
        self.scenarios = []
        self.sync_data()

        # Chỉ mục Vector cho RAG
        self.embedding_model = None
        self.product_tfidf_matrix = None
        self.faq_tfidf_matrix = None
        self.build_vector_indices()

    def _get_price_bucket(self, price: float) -> str:
        if not price: return "giá chưa cập nhật"
        if price < 5000000: return "phân khúc giá siêu rẻ dưới 5 triệu"
        if price < 10000000: return "phân khúc giá rẻ từ 5 đến 10 triệu"
        if price < 15000000: return "phân khúc giá tầm trung từ 10 đến 15 triệu"
        if price < 20000000: return "phân khúc giá cận cao cấp từ 15 đến 20 triệu"
        return "phân khúc giá cao cấp trên 20 triệu"

    def init_mongodb_connection(self):
        """Khởi tạo kết nối tới MongoDB với cơ chế mạng dự phòng"""
        if not PYMONGO_AVAILABLE or os.getenv("USE_MOCK_DB") == "1":
            print("[Hệ thống dữ liệu] Hệ thống được cấu hình chạy Offline (MOCK DB).")
            self.use_mock_db = True
            return

        try:
            # Thiết lập timeout ngắn (3 giây) để phát hiện nhanh nếu MongoDB không chạy cục bộ
            self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=3000)
            # Kích hoạt kiểm tra kết nối thực tế
            self.client.server_info()
            self.db = self.client["dienmayxanh_db"]
            print(f"[Hệ thống dữ liệu] Đã kết nối thành công tới MongoDB: {self.mongo_uri}")
        except (ServerSelectionTimeoutError, Exception) as e:
            print(f"[Hệ thống dữ liệu] CẢNH BÁO: Không thể kết nối tới MongoDB thực tế. Hệ thống tự động chuyển sang MOCK DB. (Chi tiết lỗi: {e})")
            self.use_mock_db = True
            self.client = None
            self.db = None

    def load_json_db(self) -> Dict[str, Any]:
        base_dir = os.path.dirname(self.db_path) if self.db_path else "."
        products_path = os.path.join(base_dir, "cleaned_data.json")
        faq_path = os.path.join(base_dir, "policy_faq.json")
        scen_path = os.path.join(base_dir, "customer_need_scenarios.jsonl")
        
        products = []
        if os.path.exists(products_path):
            with open(products_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    products = data.get("products", [])
                else:
                    products = data
                    
        # Inject default stock if missing
        for p in products:
            if "stock" not in p:
                p["stock"] = 10
                
        faq = []
        if os.path.exists(faq_path):
            with open(faq_path, 'r', encoding='utf-8') as f:
                faq = json.load(f)
                
        scenarios = []
        if os.path.exists(scen_path):
            with open(scen_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        scenarios.append(json.loads(line))
        
        return {
            "products": products,
            "faq": faq,
            "scenarios": scenarios
        }

    def sync_data(self):
        """Đồng bộ hóa dữ liệu từ JSON vào MongoDB và tối ưu hóa các Indexes"""
        if self.use_mock_db:
            # Chế độ Mock DB: lấy dữ liệu trực tiếp từ file JSON trong bộ nhớ
            self.products = self.raw_data.get("products", [])
            self.faq = self.raw_data.get("faq", [])
            self.scenarios = self.raw_data.get("scenarios", [])
            return

        # Chế độ MongoDB thực: nạp dữ liệu và tạo chỉ mục tối ưu
        try:
            prod_col = self.db["products"]
            faq_col = self.db["faq"]
            scen_col = self.db["scenarios"]

            if prod_col.count_documents({}) == 0:
                prod_col.insert_many(self.raw_data["products"])
                print("[MongoDB] Đã tự động import bảng 'products' từ file JSON vào Database.")
            
            # Tạo các chỉ mục tối ưu truy vấn (Optimized Indexes)
            # Chỉ mục kép: tối ưu việc lọc theo Category và Giá
            prod_col.create_index([("category", 1), ("price", 1)])
            # Chỉ mục kép: tối ưu lọc theo Category và diện tích phòng máy lạnh
            prod_col.create_index([("category", 1), ("specs.room_area", 1)])
            
            # 2. Ghi FAQ
            if faq_col.count_documents({}) == 0:
                faq_col.insert_many(self.raw_data["faq"])
                print("[MongoDB] Đã tự động import bảng 'faq' vào Database.")
            faq_col.create_index("category")

            # 3. Ghi Scenarios
            if scen_col.count_documents({}) == 0:
                scen_col.insert_many(self.raw_data["scenarios"])
                print("[MongoDB] Đã tự động import bảng 'scenarios' vào Database.")

            # Lấy dữ liệu thực tế từ MongoDB ra bộ nhớ để chạy runtime (KHÔNG tải Vector để tiết kiệm RAM)
            self.products = list(prod_col.find({}, {"embedding": 0}))
            self.faq = list(faq_col.find({}, {"embedding": 0}))
            self.scenarios = list(scen_col.find({}, {"embedding": 0}))
            
        except Exception as e:
            print(f"[Hệ thống dữ liệu] Lỗi khi đồng bộ dữ liệu MongoDB: {e}. Chuyển sang MOCK DB dự phòng.")
            self.use_mock_db = True
            self.products = self.raw_data.get("products", [])
            self.faq = self.raw_data.get("faq", [])
            self.scenarios = self.raw_data.get("scenarios", [])

    def _call_embedding_api(self, text_list: List[str]) -> List[List[float]]:
        """Gửi văn bản lên Cloud API để lấy Vector Embeddings"""
        if not text_list:
            return []
            
        headers = {
            "Authorization": f"Bearer {EMBEDDING_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Batching để tránh quá tải API (ví dụ 10 docs/lần)
        all_embeddings = []
        batch_size = 10
        for i in range(0, len(text_list), batch_size):
            batch = text_list[i:i+batch_size]
            payload = {
                "input": batch,
                "model": EMBEDDING_MODEL_NAME
            }
            try:
                # time.sleep(1.5) # Removed sleep to optimize speed
                response = requests.post(EMBEDDING_API_URL, json=payload, headers=headers, timeout=5)
                response.raise_for_status()
                data = response.json()
                # Phân tích cú pháp trả về theo chuẩn OpenAI
                if "data" in data:
                    embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x.get("index", 0))]
                    all_embeddings.extend(embeddings)
                else:
                    raise Exception(f"Phản hồi API không có trường 'data': {data}")
            except Exception as e:
                print(f"[API Error] Lỗi khi gọi Embedding API: {e}")
                # Fallback: Trả về vector 0 nếu lỗi để hệ thống không bị crash (Giả định 1024 chiều)
                all_embeddings.extend([[0.0] * 1024 for _ in batch])
                
        return all_embeddings

    def build_vector_indices(self):
        """Xây dựng chỉ mục vector bằng Cloud API Embeddings và đẩy lên MongoDB Atlas"""
        print(f"[Hệ thống dữ liệu] Đang kiểm tra và khởi tạo Vector trên Atlas ({EMBEDDING_MODEL_NAME})...")
        
        # 1. Vector hóa sản phẩm và ĐẨY LÊN ATLAS TỪNG PHẦN (Progressive)
        if not self.use_mock_db and self.db is not None:
            products_to_embed = list(self.db["products"].find({"embedding": {"$exists": False}}))
            total_products = len(products_to_embed)
            if total_products > 0:
                print(f"[Hệ thống dữ liệu] Phát hiện {total_products} sản phẩm chưa có Vector. Bắt đầu tiến trình tạo và nạp (Lưu dần dần)...")
                
                batch_size = 10
                for i in range(0, total_products, batch_size):
                    batch_products = products_to_embed[i:i+batch_size]
                    docs = []
                    for p in batch_products:
                        spec_str = " ".join([f"{k}: {v}" for k, v in p.get('specs', {}).items()])
                        price_bucket = self._get_price_bucket(p.get("sale_price", 0))
                        doc = f"Sản phẩm {p.get('category', '')} thương hiệu {p.get('brand', '')} tên gọi {p.get('name', '')}. {price_bucket}. Chi tiết: {p.get('promotion', '')} {spec_str}".lower()
                        docs.append(doc)
                    
                    # Gọi API cho batch này
                    embeddings = self._call_embedding_api(docs)
                    
                    # Lưu ngay xuống MongoDB
                    for j, p in enumerate(batch_products):
                        self.db["products"].update_one({"_id": p["_id"]}, {"$set": {"embedding": embeddings[j]}})
                        
                    print(f"[Tiến trình] Đã xử lý và lưu thành công {min(i+batch_size, total_products)} / {total_products} sản phẩm...")
                
                print("[Hệ thống dữ liệu] Đã nạp xong toàn bộ Vector Sản phẩm vào MongoDB Atlas!")
                
                # Cập nhật lại list trên RAM
                self.products = list(self.db["products"].find({}, {"embedding": 0}))
        
        # 2. Vector hóa FAQ và ĐẨY LÊN ATLAS TỪNG PHẦN (Progressive)
        if not self.use_mock_db and self.db is not None:
            faq_to_embed = list(self.db["faq"].find({"embedding": {"$exists": False}}))
            total_faq = len(faq_to_embed)
            if total_faq > 0:
                print(f"[Hệ thống dữ liệu] Phát hiện {total_faq} FAQ chưa có Vector. Bắt đầu tạo và nạp...")
                
                batch_size = 10
                for i in range(0, total_faq, batch_size):
                    batch_faq = faq_to_embed[i:i+batch_size]
                    docs = []
                    for f in batch_faq:
                        doc = f"{f.get('category', '')} {f.get('question', '')} {f.get('policy_content', '')}".lower()
                        docs.append(doc)
                    
                    embeddings = self._call_embedding_api(docs)
                    for j, f in enumerate(batch_faq):
                        self.db["faq"].update_one({"_id": f["_id"]}, {"$set": {"embedding": embeddings[j]}})
                        
                    print(f"[Tiến trình] Đã xử lý và lưu thành công {min(i+batch_size, total_faq)} / {total_faq} FAQ...")
                    
                print("[Hệ thống dữ liệu] Đã nạp thành công toàn bộ Vector FAQ vào MongoDB Atlas!")
                
                # Cập nhật lại list trên RAM
                self.faq = list(self.db["faq"].find({}, {"embedding": 0}))

        # FALLBACK: Nếu phải dùng MOCK_DB offline, tính ma trận Numpy như cũ để code chạy được
        if self.use_mock_db:
            print("[Hệ thống dữ liệu] Fallback RAM: Đang gọi API nhúng dữ liệu MOCK...")
            p_docs = []
            for p in self.products:
                spec_str = " ".join([f"{k}: {v}" for k, v in p.get('specs', {}).items()])
                price_bucket = self._get_price_bucket(p.get("sale_price", 0))
                p_docs.append(f"Sản phẩm {p.get('category', '')} thương hiệu {p.get('brand', '')} tên gọi {p.get('name', '')}. {price_bucket}. Chi tiết: {p.get('promotion', '')} {spec_str}".lower())
            
            self.product_tfidf_matrix = np.array(self._call_embedding_api(p_docs)) if p_docs else None
            
            f_docs = [f"{f.get('category', '')} {f.get('question', '')} {f.get('policy_content', '')}".lower() for f in self.faq]
            self.faq_tfidf_matrix = np.array(self._call_embedding_api(f_docs)) if f_docs else None
            print("[Hệ thống dữ liệu] Đã tạo xong Vector Matrix cục bộ trên RAM.")
