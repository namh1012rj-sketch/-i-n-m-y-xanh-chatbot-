import os
import sys
import numpy as np

# Thêm đường dẫn để có thể import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_preprocessor import DataPreprocessor

def main():
    print("Khởi tạo DataPreprocessor để lấy dữ liệu FAQ và Scenarios...")
    
    # Kế thừa để không tự động chạy MongoDB logic của DataPreprocessor
    class ExtraDataPreprocessor(DataPreprocessor):
        def init_mongodb_connection(self):
            # Không kết nối ở đây, ta sẽ tự kết nối
            self.use_mock_db = True
            pass
        def sync_data(self):
            pass
        def build_vector_indices(self):
            pass

    # Chạy khởi tạo với mock_db.json / cleaned_data.json
    dp = ExtraDataPreprocessor('.')
    
    # Kết nối thật
    from pymongo import MongoClient
    mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
    client = MongoClient(mongo_uri)
    db = client["dienmayxanh_db"]
    
    # 1. ĐẨY SCENARIOS (Không cần vector)
    scen_col = db["scenarios"]
    scen_col.delete_many({})
    scenarios = dp.raw_data.get("scenarios", [])
    if scenarios:
        scen_col.insert_many(scenarios)
        print(f"[Scenarios] Đã đẩy {len(scenarios)} kịch bản lên MongoDB.")
        
    # 2. ĐẨY FAQ (Cần Vector)
    faq_col = db["faq"]
    faq_col.delete_many({})
    faqs = dp.raw_data.get("faq", [])
    if faqs:
        print(f"[FAQ] Tìm thấy {len(faqs)} FAQ. Đang tiến hành tạo Vector (nhúng)...")
        docs = []
        for f in faqs:
            doc = f"{f.get('category', '')} {f.get('question', '')} {f.get('policy_content', '')}".lower()
            docs.append(doc)
            
        # Gọi API lấy embedding (mượn phương thức của DataPreprocessor gốc)
        dp_original = DataPreprocessor.__new__(DataPreprocessor)
        embeddings = dp_original._call_embedding_api(docs)
        
        for i, f in enumerate(faqs):
            f["embedding"] = embeddings[i]
            
        faq_col.insert_many(faqs)
        faq_col.create_index("category")
        print(f"[FAQ] Đã nhúng và đẩy {len(faqs)} FAQ lên MongoDB.")

if __name__ == '__main__':
    main()
