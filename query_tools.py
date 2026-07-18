import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import re
import numpy as np
import asyncio
from functools import wraps
from typing import List, Dict, Any, Tuple
from data_preprocessor import DataPreprocessor

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False

# Thuật toán LRU Cache (Async) - Đáp ứng yêu cầu tối ưu độ trễ
def async_lru_cache(maxsize=2000):
    cache = {}
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Tạo key từ arguments để hash
            key = (args[1:], frozenset(kwargs.items())) # Bỏ self
            if key in cache:
                return cache[key]
            if len(cache) >= maxsize:
                cache.pop(next(iter(cache)))
            result = await func(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator


class AsyncQueryEngine:
    """
    BỘ CÔNG CỤ TRUY VẤN MONGODB TỐI ƯU HÓA CLOUD (Async I/O + Vector HNSW + LRU Cache)
    """
    def __init__(self, db_path: str, mongo_uri: str = None):
        self.preprocessor = DataPreprocessor(db_path, mongo_uri)
        self.use_mock = self.preprocessor.use_mock_db
        
        self.id_to_idx = {p.get("sku", str(p.get("_id", idx))): idx for idx, p in enumerate(self.preprocessor.products)}
        self.faq_id_to_idx = {str(f.get("_id", idx)): idx for idx, f in enumerate(self.preprocessor.faq)}
        
        # Async DB Client setup bằng Motor
        self.motor_client = None
        self.async_db = None
        if not self.use_mock and MOTOR_AVAILABLE:
            mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb+srv://databasetest:Nam10122007@cluster0.jtcycnl.mongodb.net/?appName=Cluster0")
            self.motor_client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=3000)
            self.async_db = self.motor_client["dienmayxanh_db"]
            print("[AsyncQueryEngine] Khởi tạo kết nối Motor AsyncIO tới MongoDB thành công.")
        elif not self.use_mock and not MOTOR_AVAILABLE:
            print("[AsyncQueryEngine] CẢNH BÁO: Không tìm thấy thư viện motor. Hãy cài đặt: pip install motor")
            self.use_mock = True
        
        # Load data tĩnh vào RAM
        self.policy_docs = []
        self.policy_tfidf_matrix = None
        if not self.use_mock and self.preprocessor.db is not None:
            # Sync load lúc khởi tạo cho policy vì data rất nhỏ (cache on RAM)
            self.policy_docs = list(self.preprocessor.db["policy_documents"].find({}))
            if self.policy_docs and "embedding" in self.policy_docs[0]:
                self.policy_tfidf_matrix = np.array([d["embedding"] for d in self.policy_docs if "embedding" in d])

    @async_lru_cache(maxsize=2000)
    async def _get_cached_embedding(self, text: str) -> List[float]:
        """Gọi API Embedding (Chạy trong thread pool để không block event loop, kết hợp Async LRU Cache)"""
        embeddings = await asyncio.to_thread(self.preprocessor._call_embedding_api, [text])
        return embeddings[0] if embeddings else [0.0] * 1024

    @property
    def products(self) -> List[Dict[str, Any]]:
        return self.preprocessor.products

    @property
    def faq(self) -> List[Dict[str, Any]]:
        return self.preprocessor.faq

    @property
    def scenarios(self) -> List[Dict[str, Any]]:
        return self.preprocessor.scenarios

    async def refresh_local_cache(self):
        if not self.use_mock and self.async_db is not None:
            self.preprocessor.products = await self.async_db["products"].find({}, {"_id": 0, "embedding": 0}).to_list(length=None)
            self.preprocessor.faq = await self.async_db["faq"].find({}, {"_id": 0, "embedding": 0}).to_list(length=None)
        self.id_to_idx = {p.get("sku", str(p.get("_id", idx))): idx for idx, p in enumerate(self.preprocessor.products)}

    def _normalize_category(self, category: str) -> str:
        if not category: return category
        cat_map = {
            "điện thoại": "Điện thoại", "smartphone": "Điện thoại",
            "máy lạnh": "Máy lạnh", "điều hòa": "Máy lạnh",
            "tủ lạnh": "Tủ lạnh", 
            "laptop": "Laptop", "máy tính xách tay": "Laptop", "máy tính": "Laptop", "pc": "Laptop", 
            "tivi": "Tivi", "tv": "Tivi",
            "tai nghe": "Loa, Tai nghe", "loa": "Loa, Tai nghe",
            "phụ kiện": "Phụ kiện", "ốp lưng": "Phụ kiện ốp lưng",
            "máy giặt": "Máy giặt", "máy nước nóng": "Máy nước nóng"
        }
        category = cat_map.get(category.lower().strip(), category.strip())
        all_cats = set(p.get("category", "") for p in self.preprocessor.products if p.get("category"))
        return next((c for c in all_cats if category.lower() in c.lower()), category)

    # ==================== 1. CÁC TOOL TÌM KIẾM NGỮ NGHĨA (HYBRID & VECTOR) ====================

    async def tool_query_products(self, category: str, 
                             budget: float = None, 
                             room_area: float = None, 
                             usage_need: str = None, 
                             raw_query: str = "") -> List[Tuple[Dict[str, Any], float]]:
        """
        [TOOL TƯ VẤN SẢN PHẨM - TỐI ƯU HÓA BẰNG HYBRID SEARCH & HNSW]
        """
        candidates = []
        
        category = self._normalize_category(category)

        if not self.use_mock and self.async_db is not None:
            if raw_query:
                query_vector = await self._get_cached_embedding(raw_query.lower())
                
                # CÁCH 2: ÁP DỤNG PRE-FILTERING (LỌC TRƯỚC KHI TÌM KIẾM VECTOR HNSW)
                filter_doc = {"category": category}
                if budget:
                    filter_doc["sale_price"] = {"$lte": budget}
                
                if category == "Máy lạnh" and room_area:
                    if room_area <= 15: filter_doc["specs.room_area_numeric"] = {"$lte": 15}
                    elif room_area <= 20: filter_doc["specs.room_area_numeric"] = {"$gt": 15, "$lte": 20}
                    elif room_area <= 30: filter_doc["specs.room_area_numeric"] = {"$gt": 20, "$lte": 30}
                    else: filter_doc["specs.room_area_numeric"] = {"$gt": 30}
                
                try:
                    if not any(query_vector):
                        raise Exception("Vector rỗng do timeout")
                    
                    # Thuật toán Hybrid: Sử dụng $vectorSearch (HNSW) kết hợp Pre-filter
                    pipeline = [
                        {
                            "$vectorSearch": {
                                "index": "default",
                                "path": "embedding",
                                "queryVector": query_vector,
                                "numCandidates": 150, # Mở rộng không gian tìm kiếm
                                "limit": 15,
                                "filter": filter_doc,
                                "exact": False # Kích hoạt ANN/HNSW
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "embedding": 0,
                                "score": { "$meta": "vectorSearchScore" }
                            }
                        }
                    ]
                    
                    db_candidates = await self.async_db["products"].aggregate(pipeline).to_list(length=15)
                    results = []
                    
                    # Mô phỏng thuật toán RRF (Reciprocal Rank Fusion) và Keyword Boost (BM25 local)
                    for idx, p in enumerate(db_candidates):
                        # Đã lược bỏ Post-filtering ở đây vì áp dụng Pre-filtering vào HNSW
                        
                        # Điểm Vector HNSW base
                        score = p.get("score", 0.0) 
                        
                        # BM25 Keyword Boosting (Hybrid thủ công)
                        boost = 0.0
                        raw_lower = raw_query.lower()
                        if "inverter" in raw_lower and "inverter" in p.get("name", "").lower(): boost += 0.05
                        if "êm" in raw_lower and "êm" in p.get("specs", {}).get("noise_level", "").lower(): boost += 0.05
                        
                        results.append((p, score + boost))
                    
                    results.sort(key=lambda x: x[1], reverse=True)
                    return results[:5]
                except Exception as e:
                    print(f"[Vector Search Fallback] Lỗi Atlas Async: {e}. Chuyển sang Numpy/Local Search.")
            else:
                mongo_query = {"category": category}
                if budget: mongo_query["sale_price"] = {"$lte": budget}
                db_candidates = await self.async_db["products"].find(mongo_query, {"_id": 0, "embedding": 0}).to_list(length=100)
                for p in db_candidates:
                    if category == "Máy lạnh" and room_area:
                        capacity = p.get("specs", {}).get("room_area", "")
                        if "Dưới 15" in capacity and room_area > 15: continue
                        if "15 đến 20" in capacity and (room_area < 15 or room_area > 20): continue
                        if "20 đến 30" in capacity and (room_area < 20 or room_area > 30): continue
                    candidates.append((p, 1.0))
                
                if not raw_query: return candidates[:5]

        # FALLBACK MOCK DB
        if not candidates:
            for idx, p in enumerate(self.preprocessor.products):
                if p.get("category") != category: continue
                if budget and p.get("sale_price", 0) > budget: continue
                if category == "Máy lạnh" and room_area:
                    capacity = p.get("specs", {}).get("room_area", "")
                    if "Dưới 15" in capacity and room_area > 15: continue
                    if "15 đến 20" in capacity and (room_area < 15 or room_area > 20): continue
                    if "20 đến 30" in capacity and (room_area < 20 or room_area > 30): continue
                candidates.append((p, idx))

        if not raw_query: return [(c[0], 1.0) for c in candidates[:5]]

        query_vector = np.array(await self._get_cached_embedding(raw_query.lower()))
        results = []
        for cand, orig_idx in candidates:
            if getattr(self.preprocessor, 'product_tfidf_matrix', None) is not None:
                cand_vector = self.preprocessor.product_tfidf_matrix[orig_idx]
                norm_q = np.linalg.norm(query_vector)
                norm_c = np.linalg.norm(cand_vector)
                sim_score = float(np.dot(query_vector, cand_vector) / (norm_q * norm_c)) if norm_q > 0 and norm_c > 0 else 0.0
            else:
                sim_score = 0.0
            
            boost = 0.0
            if category == "Điện thoại" and usage_need:
                if usage_need == "chơi game" and any(x in cand.get("promotion", "").lower() or x in cand.get("specs", {}).get("chip", "").lower() for x in ["game", "a17 pro", "hiệu năng"]):
                    boost += 0.25
                elif usage_need == "chụp ảnh" and any(x in cand.get("promotion", "").lower() or x in cand.get("specs", {}).get("camera", "").lower() for x in ["chụp ảnh", "camera", "zoom"]):
                    boost += 0.25
                    
            final_score = sim_score + boost
            results.append((cand, final_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:5]

    @async_lru_cache(maxsize=500)
    async def tool_query_faq(self, raw_query: str) -> List[Tuple[Dict[str, Any], float]]:
        """
        [TOOL TRA CỨU FAQ - CÓ CACHING]
        Tích hợp Async LRU Cache giúp thời gian trả lời giảm < 10ms nếu câu hỏi lặp lại.
        """
        query_vector = np.array(await self._get_cached_embedding(raw_query.lower()))
        
        if not self.use_mock and self.async_db is not None:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index_faq",
                        "path": "embedding",
                        "queryVector": query_vector.tolist(),
                        "numCandidates": 50,
                        "limit": 3,
                        "exact": False
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "embedding": 0,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
            try:
                db_faq = await self.async_db["faq"].aggregate(pipeline).to_list(length=3)
                results = [(f, f.get("score", 0.0)) for f in db_faq]
                if results: return results
            except Exception as e:
                print(f"[Vector Search Error] Lỗi Atlas FAQ: {e}. Fallback về Numpy.")

        # Fallback Numpy
        norm_q = np.linalg.norm(query_vector)
        results = []
        for idx, f in enumerate(self.preprocessor.faq):
            if getattr(self.preprocessor, 'faq_tfidf_matrix', None) is not None:
                faq_vector = self.preprocessor.faq_tfidf_matrix[idx]
                norm_c = np.linalg.norm(faq_vector)
                sim_score = float(np.dot(query_vector, faq_vector) / (norm_q * norm_c)) if norm_q > 0 and norm_c > 0 else 0.0
            else:
                sim_score = 0.0
            results.append((f, sim_score))
            
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:3]

    async def tool_search_policy_documents(self, query: str) -> List[Dict[str, Any]]:
        """
        [TOOL TÌM CHÍNH SÁCH - HNSW VECTOR]
        """
        if self.use_mock or self.async_db is None:
            # Nếu Offline, tra cứu trên mảng RAM policy_docs
            pass
        else:
            print(f"  [Tool] Gọi API lấy Vector cho câu hỏi chính sách: '{query}'")
            
        try:
            query_vector = await self._get_cached_embedding(query)
            if not any(query_vector):
                return [{"error": "Vector rỗng do timeout"}]
        except Exception as e:
            return [{"error": f"Lỗi API embedding: {e}"}]

        if not self.use_mock and self.async_db is not None:
            try:
                mongo_query = [
                    {
                        "$vectorSearch": {
                            "index": "default",
                            "path": "embedding",
                            "queryVector": query_vector,
                            "numCandidates": 50,
                            "limit": 2,
                            "exact": False
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "embedding": 0,
                            "score": {"$meta": "vectorSearchScore"}
                        }
                    }
                ]
                
                results = await self.async_db["policy_documents"].aggregate(mongo_query).to_list(length=2)
                if results: return results
                raise Exception("Không tìm thấy bằng Atlas")
            except Exception as e:
                pass

        # Thực thi bằng Numpy (RAM)
        if self.policy_tfidf_matrix is not None:
            norm_q = np.linalg.norm(query_vector)
            results = []
            for idx, doc in enumerate(self.policy_docs):
                doc_vector = self.policy_tfidf_matrix[idx]
                norm_c = np.linalg.norm(doc_vector)
                sim_score = float(np.dot(query_vector, doc_vector) / (norm_q * norm_c)) if norm_q > 0 and norm_c > 0 else 0.0
                clean_doc = {k: v for k, v in doc.items() if k != "embedding" and k != "_id"}
                results.append((clean_doc, sim_score))
            results.sort(key=lambda x: x[1], reverse=True)
            return [{"doc": r[0], "score": r[1]} for r in results[:2]]
            
        return [{"error": "Không thể truy xuất Policy Documents."}]

    async def tool_query_similar_products(self, product_id: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        if not self.use_mock and self.async_db is not None:
            target_product = await self.async_db["products"].find_one({"sku": product_id})
            if not target_product or "embedding" not in target_product:
                return []
            
            target_vector = target_product["embedding"]
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "default",
                        "path": "embedding",
                        "queryVector": target_vector,
                        "numCandidates": 50,
                        "limit": top_k + 1,
                        "filter": {"category": target_product.get("category", "")},
                        "exact": False
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "embedding": 0,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
            
            try:
                db_results = await self.async_db["products"].aggregate(pipeline).to_list(length=top_k + 1)
                results = []
                for p in db_results:
                    if p.get("sku", str(p.get("_id"))) == product_id: continue
                    results.append((p, p.get("score", 0.0)))
                return results[:top_k]
            except Exception as e:
                print(f"[Vector Search Error] Lỗi Atlas Similar Products: {e}. Fallback về Numpy.")

        # Fallback Numpy
        orig_idx = self.id_to_idx.get(product_id)
        if orig_idx is None:
            return []

        target_product = self.preprocessor.products[orig_idx]
        if getattr(self.preprocessor, 'product_tfidf_matrix', None) is None:
            return []
            
        target_vector = self.preprocessor.product_tfidf_matrix[orig_idx]
        results = []
        for idx, p in enumerate(self.preprocessor.products):
            if idx == orig_idx: continue
            if p["category"] != target_product["category"]: continue
                
            cand_vector = self.preprocessor.product_tfidf_matrix[idx]
            norm_q = np.linalg.norm(target_vector)
            norm_c = np.linalg.norm(cand_vector)
            sim_score = float(np.dot(target_vector, cand_vector) / (norm_q * norm_c)) if norm_q > 0 and norm_c > 0 else 0.0
            results.append((p, sim_score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    # ==================== 2. CÁC TOOL TÌM KIẾM CHÍNH XÁC & BỘ LỌC (COMPOUND INDEX) ====================

    @async_lru_cache(maxsize=1000)
    async def tool_get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        [TOOL EXACT MATCH - CÓ CACHE]
        """
        if not self.use_mock and self.async_db is not None:
            doc = await self.async_db["products"].find_one({"sku": product_id}, {"_id": 0, "embedding": 0})
            return doc if doc else {}
        else:
            for p in self.preprocessor.products:
                if p.get("sku", str(p.get("_id"))) == product_id:
                    return p
        return {}

    async def tool_query_products_by_spec_range(self, category: str, spec_name: str, min_val: float, max_val: float) -> List[Dict[str, Any]]:
        """
        [TOOL LỌC RANGE - TỐI ƯU COMPOUND INDEX]
        """
        category = self._normalize_category(category)
        results = []
        numeric_spec_name = f"{spec_name}_numeric"
        
        if not self.use_mock and self.async_db is not None:
            mongo_query = {
                "category": {"$regex": f"^{category}$", "$options": "i"},
                f"specs.{numeric_spec_name}": {"$gte": min_val, "$lte": max_val}
            }
            # Áp dụng chuẩn ESR, giả định đã có index dạng {"category": 1, "specs.xxx": 1}
            cursor = self.async_db["products"].find(mongo_query, {"_id": 0, "embedding": 0})
            results = await cursor.to_list(length=50)
        else:
            for p in self.preprocessor.products:
                if p["category"] != category:
                    continue
                val = p["specs"].get(numeric_spec_name)
                if val is not None:
                    if min_val <= val <= max_val:
                        results.append(p)
        return results

    async def tool_query_products_by_brand(self, category: str, brand: str) -> List[Dict[str, Any]]:
        category = self._normalize_category(category)
        if not self.use_mock and self.async_db is not None:
            return await self.async_db["products"].find({"category": {"$regex": f"^{category}$", "$options": "i"}, "brand": {"$regex": f"^{brand}$", "$options": "i"}}, {"_id": 0, "embedding": 0}).to_list(length=50)
        else:
            return [p for p in self.preprocessor.products if p["category"] == category and p["brand"].lower() == brand.lower()]

    async def tool_query_by_features(self, category: str, features: List[str]) -> List[Dict[str, Any]]:
        """
        [TOOL LỌC FEATURES - TỐI ƯU INDEX HINT]
        """
        category = self._normalize_category(category)
        results = []
        if not self.use_mock and self.async_db is not None:
            mongo_query = {"category": {"$regex": f"^{category}$", "$options": "i"}}
            if features:
                mongo_query["$and"] = [{"specs.special_features": {"$regex": feat, "$options": "i"}} for feat in features]
            
            # Sử dụng hint để ép query planner dùng index category (chuẩn ESR: Equality first)
            cursor = self.async_db["products"].find(mongo_query, {"_id": 0, "embedding": 0}).hint("category_1_price_1")
            return await cursor.to_list(length=50)
        else:
            for p in self.preprocessor.products:
                if p["category"] != category:
                    continue
                special_features = p["specs"].get("special_features", "").lower()
                if all(feat.lower() in special_features for feat in features):
                    results.append(p)
            return results

    async def tool_search_product_by_name(self, query_name: str) -> List[Dict[str, Any]]:
        if not self.use_mock and self.async_db is not None:
            try:
                pipeline = [
                    {
                        "$search": {
                            "index": "default",
                            "text": {
                                "query": query_name,
                                "path": "name"
                            }
                        }
                    },
                    {"$limit": 10},
                    {"$project": {"_id": 0, "embedding": 0}}
                ]
                return await self.async_db["products"].aggregate(pipeline).to_list(length=10)
            except Exception as e:
                print(f"[Atlas Search Error] tool_search_product_by_name: {e}. Fallback to regex.")
                return await self.async_db["products"].find(
                    {"name": {"$regex": query_name, "$options": "i"}}, 
                    {"_id": 0, "embedding": 0}
                ).to_list(length=10)
        else:
            return [p for p in self.preprocessor.products if query_name.lower() in p["name"].lower()]

    # ==================== 3. CÁC TOOL CHỐT SALE & CẢNH BÁO ====================

    async def tool_query_discount_products(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        category = self._normalize_category(category)
        results = []
        if not self.use_mock and self.async_db is not None:
            pipeline = [
                { "$match": { "category": {"$regex": f"^{category}$", "$options": "i"}, "discount_amount": { "$exists": True } } },
                { "$sort": { "discount_amount": -1 } },
                { "$limit": limit },
                { "$project": { "_id": 0, "embedding": 0 } }
            ]
            results = await self.async_db["products"].aggregate(pipeline).to_list(length=limit)
        else:
            for p in self.preprocessor.products:
                if p["category"] == category and "discount_amount" in p:
                    results.append(p)
            results.sort(key=lambda x: x.get("discount_amount", 0), reverse=True)
            results = results[:limit]
            
        return results

    async def tool_query_best_promotions(self, category: str) -> List[Dict[str, Any]]:
        category = self._normalize_category(category)
        results = []
        promo_keywords = ["tặng máy hút bụi", "giảm ngay 500", "tặng combo vật tư", "1 đổi 1", "trợ giá đến 2,000,000đ"]
        
        if not self.use_mock and self.async_db is not None:
            try:
                pipeline = [
                    {
                        "$search": {
                            "index": "default",
                            "text": {
                                "query": " ".join(promo_keywords),
                                "path": "promotion"
                            }
                        }
                    },
                    {"$match": filter_doc if 'filter_doc' in locals() else {}},
                    {"$limit": 10},
                    {"$project": {"_id": 0, "embedding": 0}}
                ]
                if category:
                    pipeline[0]["$search"]["compound"] = {
                        "must": [{"text": {"query": " ".join(promo_keywords), "path": "promotion"}}],
                        "filter": [{"text": {"query": category, "path": "category"}}]
                    }
                    del pipeline[0]["$search"]["text"]
                results = await self.async_db["products"].aggregate(pipeline).to_list(length=10)
            except Exception as e:
                regex_pattern = "|".join(promo_keywords)
                filter_doc = {}
                if category:
                    filter_doc["category"] = category
                filter_doc["promotion"] = {"$regex": regex_pattern, "$options": "i"}
                results = await self.async_db["products"].find(filter_doc, {"_id": 0, "embedding": 0}).to_list(length=10)
        else:
            for p in self.preprocessor.products:
                if p["category"] == category:
                    promo = p.get("promotion") or ""
                    if any(kw in promo.lower() for kw in promo_keywords):
                        results.append(p)
        return results

    async def tool_sort_products_by_price(self, category: str, sort_order: str = "asc", limit: int = 5) -> List[Dict[str, Any]]:
        category = self._normalize_category(category)
        results = []
        sort_dir = 1 if sort_order.lower() == "asc" else -1
        if not self.use_mock and self.async_db is not None:
            pipeline = [
                { "$match": { "category": {"$regex": f"^{category}$", "$options": "i"}, "sale_price": { "$exists": True } } },
                { "$sort": { "sale_price": sort_dir } },
                { "$limit": limit },
                { "$project": { "_id": 0, "embedding": 0 } }
            ]
            results = await self.async_db["products"].aggregate(pipeline).to_list(length=limit)
        else:
            for p in self.preprocessor.products:
                if p["category"] == category and "sale_price" in p:
                    results.append(p)
            results.sort(key=lambda x: x.get("sale_price", 0), reverse=(sort_dir == -1))
            results = results[:limit]
            
        return results

    async def tool_query_out_of_stock(self) -> List[Dict[str, Any]]:
        if not self.use_mock and self.async_db is not None:
            return await self.async_db["products"].find({"stock": {"$lte": 0}}, {"_id": 0, "embedding": 0}).to_list(length=100)
        else:
            return [p for p in self.preprocessor.products if p.get("stock", 0) <= 0]
