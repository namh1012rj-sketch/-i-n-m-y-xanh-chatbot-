import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import re
import numpy as np
from typing import List, Dict, Any, Tuple
from data_preprocessor import DataPreprocessor

class QueryEngine:
    """
    BỘ CÔNG CỤ TRUY VẤN MONGODB TỐI ƯU HÓA (MongoDB Runtime Query Tools Suite)
    Nhiệm vụ:
    1. Kết nối với DataPreprocessor để truy xuất thông tin từ MongoDB (hoặc Mock DB).
    2. Cung cấp các hàm tìm kiếm lai (Hybrid Search) sử dụng MongoDB Find + Python Vector Cosine Similarity.
    3. Hỗ trợ các chỉ mục tối ưu và các hàm thao tác kho/khuyến mãi thực tế.
    """
    def __init__(self, db_path: str, mongo_uri: str = None):
        self.preprocessor = DataPreprocessor(db_path, mongo_uri)
        self.use_mock = self.preprocessor.use_mock_db
        
        # Ánh xạ nhanh ID sản phẩm -> vị trí index trong ma trận Vector TF-IDF để tăng tốc độ truy xuất
        self.id_to_idx = {p.get("sku", str(p.get("_id", idx))): idx for idx, p in enumerate(self.preprocessor.products)}
        self.faq_id_to_idx = {str(f.get("_id", idx)): idx for idx, f in enumerate(self.preprocessor.faq)}

    @property
    def products(self) -> List[Dict[str, Any]]:
        return self.preprocessor.products

    @property
    def faq(self) -> List[Dict[str, Any]]:
        return self.preprocessor.faq

    @property
    def scenarios(self) -> List[Dict[str, Any]]:
        return self.preprocessor.scenarios

    def refresh_local_cache(self):
        """Đồng bộ lại bộ nhớ đệm sau khi cập nhật dữ liệu (ghi/sửa) xuống database"""
        if not self.use_mock and self.preprocessor.db is not None:
            self.preprocessor.products = list(self.preprocessor.db["products"].find({}, {"_id": 0}))
            self.preprocessor.faq = list(self.preprocessor.db["faq"].find({}, {"_id": 0}))
        self.id_to_idx = {p.get("sku", str(p.get("_id", idx))): idx for idx, p in enumerate(self.preprocessor.products)}

    # ==================== 1. CÁC TOOL CHÍNH TRONG CHATBOT TƯ VẤN VÀ BẢO VỆ ====================

    def tool_query_products(self, category: str, 
                             budget: float = None, 
                             room_area: float = None, 
                             usage_need: str = None, 
                             raw_query: str = "") -> List[Tuple[Dict[str, Any], float]]:
        """
        [TOOL TƯ VẤN SẢN PHẨM MONGODB ATLAS]
        Kết hợp lọc bằng MongoDB Query và xếp hạng Vector RAG ($vectorSearch).
        """
        candidates = []

        if not self.use_mock and self.preprocessor.db is not None:
            # Nhánh 1: Sử dụng MongoDB Atlas Vector Search
            if raw_query:
                query_vector = self.preprocessor._call_embedding_api([raw_query.lower()])[0]
                
                # Tạo bộ lọc cứng cho Vector Search
                filter_doc = {"category": category}
                if budget:
                    filter_doc["sale_price"] = {"$lte": budget}
                
                try:
                    # Nếu API timeout trả về vector toàn 0, Atlas sẽ báo lỗi. Chủ động ngắt sớm.
                    if not any(query_vector):
                        raise Exception("Vector rỗng do timeout")
                        
                    pipeline = [
                        {
                            "$vectorSearch": {
                                "index": "vector_index",
                                "path": "embedding",
                                "queryVector": query_vector,
                                "numCandidates": 100,
                                "limit": 10,
                                "filter": filter_doc
                            }
                        },
                        {
                            "$project": {
                                "embedding": 0,
                                "score": { "$meta": "vectorSearchScore" }
                            }
                        }
                    ]
                    db_candidates = list(self.preprocessor.db["products"].aggregate(pipeline))
                    results = []
                    for p in db_candidates:
                        if category == "Máy lạnh" and room_area:
                            capacity = p.get("specs", {}).get("room_area", "")
                            if "Dưới 15" in capacity and room_area > 15: continue
                            if "15 đến 20" in capacity and (room_area < 15 or room_area > 20): continue
                            if "20 đến 30" in capacity and (room_area < 20 or room_area > 30): continue
                        
                        score = p.get("score", 0.0)
                        boost = 0.0
                        if "inverter" in raw_query.lower() and "inverter" in p.get("name", "").lower(): boost += 0.05
                        if "êm" in raw_query.lower() and "êm" in p.get("specs", {}).get("noise_level", "").lower(): boost += 0.05
                        
                        results.append((p, score + boost))
                    
                    results.sort(key=lambda x: x[1], reverse=True)
                    return results[:5]
                except Exception as e:
                    print(f"[Vector Search Fallback] {e}. Chuyển sang Numpy/Local Search.")
            else:
                # Nếu không có raw_query, chỉ dùng MongoDB find bình thường
                mongo_query = {"category": category}
                if budget: mongo_query["sale_price"] = {"$lte": budget}
                db_candidates = list(self.preprocessor.db["products"].find(mongo_query))
                for p in db_candidates:
                    if category == "Máy lạnh" and room_area:
                        capacity = p.get("specs", {}).get("room_area", "")
                        if "Dưới 15" in capacity and room_area > 15: continue
                        if "15 đến 20" in capacity and (room_area < 15 or room_area > 20): continue
                        if "20 đến 30" in capacity and (room_area < 20 or room_area > 30): continue
                    candidates.append((p, self.preprocessor.products.index(p) if p in self.preprocessor.products else 0))
                
                if not raw_query: return [(c[0], 1.0) for c in candidates[:5]]

        # FALLBACK: Nếu đang chạy Mock DB hoặc bị lỗi Atlas Vector Search
        if not candidates:
            # Lọc thô trên RAM
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

        # Xếp hạng Vector RAG bằng Numpy (Fallback)
        query_vector = np.array(self.preprocessor._call_embedding_api([raw_query.lower()])[0])
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
        return results

    def tool_query_faq(self, raw_query: str) -> List[Tuple[Dict[str, Any], float]]:
        """
        [TOOL TRA CỨU FAQ MONGODB ATLAS]
        Truy xuất câu trả lời chính sách bằng Vector Search (Cloud API).
        """
        query_vector = np.array(self.preprocessor._call_embedding_api([raw_query.lower()])[0])
        
        if not self.use_mock and self.preprocessor.db is not None:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index_faq",
                        "path": "embedding",
                        "queryVector": query_vector.tolist(),
                        "numCandidates": 50,
                        "limit": 3
                    }
                },
                {
                    "$project": {
                        "embedding": 0,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
            try:
                db_faq = list(self.preprocessor.db["faq"].aggregate(pipeline))
                results = [(f, f.get("score", 0.0)) for f in db_faq]
                if results: return results
            except Exception as e:
                print(f"[Vector Search Error] Lỗi Atlas FAQ (Chưa tạo Index?): {e}. Fallback về Numpy.")

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

    # ==================== 2. CÁC TRUY VẤN MỚI BỔ SUNG & TỐI ƯU (NEW OPTIMIZED TOOLS) ====================

    def tool_query_products_by_spec_range(self, category: str, spec_name: str, min_val: float, max_val: float) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - MONGODB RANGE QUERY] 
        Tìm kiếm các sản phẩm trong khoảng thông số kỹ thuật (ví dụ: diện tích phòng, dung tích tủ lạnh).
        Sử dụng Chỉ mục kép specs trong MongoDB để tối ưu hóa hiệu năng.
        """
        results = []
        numeric_spec_name = f"{spec_name}_numeric"
        
        if not self.use_mock and self.preprocessor.db is not None:
            # Lọc trực tiếp trên MongoDB bằng trường số tối ưu
            mongo_query = {
                "category": category,
                f"specs.{numeric_spec_name}": {"$gte": min_val, "$lte": max_val}
            }
            results = list(self.preprocessor.db["products"].find(mongo_query, {"_id": 0}))
        else:
            # Fallback lọc bằng bộ nhớ sử dụng trường số mới tạo
            for p in self.preprocessor.products:
                if p["category"] != category:
                    continue
                val = p["specs"].get(numeric_spec_name)
                if val is not None:
                    if min_val <= val <= max_val:
                        results.append(p)
        return results

    def tool_query_products_by_brand(self, category: str, brand: str) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - BRAND FILTER]
        Tìm kiếm sản phẩm theo Thương hiệu và ngành hàng cụ thể.
        """
        if not self.use_mock and self.preprocessor.db is not None:
            return list(self.preprocessor.db["products"].find({"category": category, "brand": brand}, {"_id": 0}))
        else:
            return [p for p in self.preprocessor.products if p["category"] == category and p["brand"].lower() == brand.lower()]

    def tool_query_best_promotions(self, category: str) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - PROMOTIONS SEARCH]
        Tìm kiếm các sản phẩm thuộc ngành hàng đang có chính sách khuyến mãi cao nhất hoặc quà tặng lớn.
        """
        results = []
        # Định nghĩa các từ khóa khuyến mãi lớn để lọc
        promo_keywords = ["tặng máy hút bụi", "giảm ngay 500", "tặng combo vật tư", "1 đổi 1", "trợ giá đến 2,000,000đ"]
        
        if not self.use_mock and self.preprocessor.db is not None:
            # 2. Xây dựng B-Tree Filter
            filter_doc = {}
            if category:
                cat_map = {
                    "điện thoại": "Điện thoại",
                    "máy lạnh": "Máy lạnh",
                    "tủ lạnh": "Tủ lạnh"
                }
                exact_cat = cat_map.get(category.lower().strip(), category)
                filter_doc["category"] = exact_cat
            regex_pattern = "|".join(promo_keywords)
            filter_doc["promotion"] = {"$regex": regex_pattern, "$options": "i"}
            results = list(self.preprocessor.db["products"].find(filter_doc, {"_id": 0}))
        else:
            for p in self.preprocessor.products:
                if p["category"] == category:
                    promo = p.get("promotion") or ""
                    if any(kw in promo.lower() for kw in promo_keywords):
                        results.append(p)
        return results



    def tool_query_out_of_stock(self) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - OUT OF STOCK ALERT]
        Liệt kê toàn bộ các sản phẩm đã hết hàng (stock = 0) để thông báo cho nhân viên tư vấn.
        """
        if not self.use_mock and self.preprocessor.db is not None:
            return list(self.preprocessor.db["products"].find({"stock": {"$lte": 0}}, {"_id": 0}))
        else:
            return [p for p in self.preprocessor.products if p["stock"] <= 0]

    def tool_get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        [NEW TOOL - EXACT MATCH]
        Lấy thông tin chi tiết của một sản phẩm cụ thể qua ID.
        """
        if not self.use_mock and self.preprocessor.db is not None:
            return self.preprocessor.db["products"].find_one({"sku": product_id}, {"_id": 0})
        else:
            for p in self.preprocessor.products:
                if p.get("sku", str(p.get("_id"))) == product_id:
                    return p
        return {}

    def tool_query_by_features(self, category: str, features: List[str]) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - FEATURE SEARCH]
        Tìm kiếm sản phẩm theo các tính năng đặc biệt (VD: Inverter, Lọc bụi, Khử mùi).
        """
        results = []
        if not self.use_mock and self.preprocessor.db is not None:
            mongo_query = {"category": category}
            if features:
                mongo_query["$and"] = [{"specs.special_features": {"$regex": feat, "$options": "i"}} for feat in features]
            return list(self.preprocessor.db["products"].find(mongo_query, {"_id": 0}))
        else:
            for p in self.preprocessor.products:
                if p["category"] != category:
                    continue
                special_features = p["specs"].get("special_features", "").lower()
                if all(feat.lower() in special_features for feat in features):
                    results.append(p)
            return results

    def tool_query_similar_products(self, product_id: str, top_k: int = 3) -> List[Tuple[Dict[str, Any], float]]:
        """
        [NEW TOOL - SIMILARITY SEARCH MONGODB ATLAS]
        Tìm kiếm các sản phẩm tương đồng với một sản phẩm cụ thể (để gợi ý thay thế).
        """
        # Nếu dùng MongoDB thực tế
        if not self.use_mock and self.preprocessor.db is not None:
            target_product = self.preprocessor.db["products"].find_one({"sku": product_id})
            if not target_product or "embedding" not in target_product:
                return []
            
            target_vector = target_product["embedding"]
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": target_vector,
                        "numCandidates": 50,
                        "limit": top_k + 1,
                        "filter": {"category": target_product.get("category")}
                    }
                },
                {
                    "$project": {
                        "embedding": 0,
                        "score": { "$meta": "vectorSearchScore" }
                    }
                }
            ]
            
            try:
                db_results = list(self.preprocessor.db["products"].aggregate(pipeline))
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

    def tool_search_product_by_name(self, query_name: str) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - NAME/SKU SEARCH]
        Tìm kiếm đích danh sản phẩm theo tên hoặc mã SKU. 
        Phục vụ cho kịch bản người dùng yêu cầu: "So sánh máy X và máy Y".
        """
        if not self.use_mock and self.preprocessor.db is not None:
            return list(self.preprocessor.db["products"].find(
                {"name": {"$regex": query_name, "$options": "i"}}, 
                {"_id": 0}
            ))
        else:
            return [p for p in self.preprocessor.products if query_name.lower() in p["name"].lower()]

    def tool_query_discount_products(self, category: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - DISCOUNT SEARCH]
        Tìm kiếm các sản phẩm đang có mức giảm giá cao nhất (dựa trên original_price và sale_price).
        """
        results = []
        if not self.use_mock and self.preprocessor.db is not None:
            pipeline = [
                { "$match": { "category": category, "original_price": { "$exists": True }, "sale_price": { "$exists": True } } },
                { "$addFields": { "discount_amount": { "$subtract": ["$original_price", "$sale_price"] } } },
                { "$sort": { "discount_amount": -1 } },
                { "$limit": limit },
                { "$project": { "_id": 0, "embedding": 0 } }
            ]
            results = list(self.preprocessor.db["products"].aggregate(pipeline))
        else:
            for p in self.preprocessor.products:
                if p["category"] == category and "original_price" in p and "sale_price" in p:
                    p["discount_amount"] = p["original_price"] - p["sale_price"]
                    results.append(p)
            results.sort(key=lambda x: x.get("discount_amount", 0), reverse=True)
            results = results[:limit]
            
        return results

    def tool_sort_products_by_price(self, category: str, sort_order: str = "asc", limit: int = 5) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - PRICE SORT]
        Lấy danh sách các sản phẩm có giá rẻ nhất (asc) hoặc đắt nhất (desc).
        """
        results = []
        sort_dir = 1 if sort_order.lower() == "asc" else -1
        if not self.use_mock and self.preprocessor.db is not None:
            pipeline = [
                { "$match": { "category": category, "sale_price": { "$exists": True } } },
                { "$sort": { "sale_price": sort_dir } },
                { "$limit": limit },
                { "$project": { "_id": 0, "embedding": 0 } }
            ]
            results = list(self.preprocessor.db["products"].aggregate(pipeline))
        else:
            for p in self.preprocessor.products:
                if p["category"] == category and "sale_price" in p:
                    results.append(p)
            results.sort(key=lambda x: x.get("sale_price", 0), reverse=(sort_dir == -1))
            results = results[:limit]
            
        return results

    def tool_search_policy_documents(self, query: str) -> List[Dict[str, Any]]:
        """
        [NEW TOOL - POLICY VECTOR SEARCH]
        Tìm kiếm thông tin trong các văn bản chính sách, điều khoản, nội quy, bảo hành.
        Chỉ dùng khi người dùng hỏi các câu hỏi về chính sách dài hoặc phức tạp.
        """
        if self.use_mock or self.preprocessor.db is None:
            return [{"error": "Tool này chỉ hoạt động khi kết nối với MongoDB Atlas."}]
            
        print(f"  [Tool] Gọi API lấy Vector cho câu hỏi chính sách: '{query}'")
        try:
            query_vector_list = self.preprocessor._call_embedding_api([query])
            if not query_vector_list:
                return [{"error": "Lỗi API embedding"}]
            query_vector = query_vector_list[0]
            if not any(query_vector):
                return [{"error": "Vector rỗng do timeout"}]
                
            mongo_query = [
                {
                    "$vectorSearch": {
                        "index": "default",
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": 20,
                        "limit": 2
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
            
            results = list(self.preprocessor.db["policy_documents"].aggregate(mongo_query))
            return results
        except Exception as e:
            return [{"error": f"Lỗi truy vấn Vector Policy: {e}"}]
