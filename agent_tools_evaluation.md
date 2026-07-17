# BÁO CÁO CÔNG CỤ CHO AI AGENT (AGENT TOOLS)

Tài liệu này đánh giá chi tiết 13 công cụ (Tools) (đã loại bỏ các tool cập nhật dữ liệu để đảm bảo an toàn Read-Only) cung cấp cho AI Agent. Các số liệu đánh giá bao gồm đầu vào, đầu ra, và thời gian chạy thực tế đã bao gồm độ trễ mạng (Network Latency) tới MongoDB Atlas và thời gian truy vấn.

> [!NOTE]
> **Về thời gian phản hồi (Latency):** 
> Các con số ước tính bên dưới được đo trực tiếp từ môi trường thực tế với kết nối qua mạng Internet tới cụm máy chủ Cloud. 

---

## 1. NHÓM TÌM KIẾM & GỢI Ý VECTOR (ATLAS VECTOR SEARCH / RAG)
Đặc điểm chung: Kết hợp truy vấn Atlas Vector Search với bộ lọc thông minh. Phù hợp cho các câu hỏi mở, không cố định cấu hình.

### 1.1. `tool_query_products` (Tìm kiếm sản phẩm lai)
*   **Đầu vào (Inputs):**
    *   `category` (str): Danh mục sản phẩm (Bắt buộc).
    *   `budget` (float): Ngân sách tối đa (Tùy chọn).
    *   `room_area` (float): Diện tích phòng (Tùy chọn, cho Máy lạnh).
    *   `usage_need` (str): Nhu cầu sử dụng, ví dụ: "chơi game", "chụp ảnh" (Tùy chọn).
    *   `raw_query` (str): Câu lệnh tự nhiên gốc (Tùy chọn).
*   **Đầu ra (Outputs):** `List[Tuple[Dict, float]]` - Danh sách Top 5 sản phẩm khớp nhất và Điểm Vector.
*   **Thời gian chạy thực tế:** `~0.9s` (Gồm độ trễ gọi API Embedding và quét Vector Atlas).

### 1.2. `tool_query_similar_products` (Tìm sản phẩm tương đồng)
*   **Đầu vào (Inputs):**
    *   `product_id` (str): Mã sản phẩm.
    *   `top_k` (int): Số lượng kết quả trả về mặc định là 3.
*   **Đầu ra (Outputs):** `List[Tuple[Dict, float]]` - Sản phẩm giống nhất với sản phẩm gốc, lý tưởng để Upsell/Thay thế.
*   **Thời gian chạy thực tế:** `~0.15s - 0.2s` (Chỉ lấy Vector nội bộ và quét Atlas).

### 1.3. `tool_query_faq` (Trả lời câu hỏi thường gặp)
*   **Đầu vào (Inputs):** `raw_query` (str) - Câu hỏi FAQ.
*   **Đầu ra (Outputs):** `List[Tuple[Dict, float]]` - Câu trả lời phù hợp.
*   **Thời gian chạy thực tế:** `~0.9s`.

### 1.4. `tool_search_policy_documents` (Tra cứu Quy định, Chính sách Dài)
*   **Đầu vào (Inputs):** `query` (str) - Câu hỏi hoặc chủ đề cần tra cứu (VD: "Bảo hành iPhone khui hộp", "Chính sách đổi trả máy lạnh").
*   **Đầu ra (Outputs):** `List[Dict]` - Các đoạn văn bản chính sách liên quan nhất trích xuất từ dữ liệu Markdown phi cấu trúc.
*   **Thời gian chạy thực tế:** `~0.9s`. (Gồm độ trễ gọi API Embedding và quét Atlas).

---

## 2. NHÓM TRUY XUẤT CẤU HÌNH & THUỘC TÍNH (EXACT MATCH & FILTER)
Đặc điểm chung: Dùng các bộ lọc (B-Tree Index) trực tiếp trên cơ sở dữ liệu MongoDB. Tốc độ truy xuất siêu nhanh qua mạng.

### 2.1. `tool_get_product_details` (Lấy chi tiết 1 sản phẩm)
*   **Đầu vào (Inputs):** `product_id` (str).
*   **Đầu ra (Outputs):** `Dict[str, Any]` - Toàn bộ thông số kỹ thuật chi tiết của sản phẩm.
*   **Thời gian chạy thực tế:** `< 0.1s`.

### 2.2. `tool_search_product_by_name` (Tìm tên/Mã SKU)
*   **Đầu vào (Inputs):** `query_name` (str) - Tên hoặc mã SKU (Ví dụ: "iPhone 14").
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Các sản phẩm có tên khớp với từ khóa (Regex search). Dùng tốt để lấy data cho mục đích "So sánh".
*   **Thời gian chạy thực tế:** `< 0.1s`.

### 2.3. `tool_query_products_by_spec_range` (Lọc theo khoảng thông số)
*   **Đầu vào (Inputs):**
    *   `category` (str): Danh mục.
    *   `spec_name` (str): Tên thông số (ví dụ: "room_area", "capacity").
    *   `min_val`, `max_val` (float): Khoảng giá trị.
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Sản phẩm thỏa mãn khoảng (Range) kỹ thuật (VD: máy lạnh từ 15-20m2).
*   **Thời gian chạy thực tế:** `< 0.05s`.

### 2.4. `tool_query_products_by_brand` (Lọc theo thương hiệu)
*   **Đầu vào (Inputs):** `category` (str), `brand` (str).
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Danh sách các sản phẩm của một thương hiệu.
*   **Thời gian chạy thực tế:** `< 0.07s`.

### 2.5. `tool_query_by_features` (Lọc tính năng đặc biệt)
*   **Đầu vào (Inputs):** `category` (str), `features` (List[str]).
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Khớp các tính năng (VD: "Inverter", "Lọc không khí").
*   **Thời gian chạy thực tế:** `< 0.05s`.

### 2.6. `tool_sort_products_by_price` (Lấy sản phẩm Rẻ/Đắt nhất)
*   **Đầu vào (Inputs):** 
    *   `category` (str): Danh mục.
    *   `sort_order` (str): "asc" (rẻ nhất) hoặc "desc" (đắt nhất).
    *   `limit` (int): Số lượng kết quả.
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Danh sách đã được xếp hạng cứng (Hard Sort) trên DB.
*   **Thời gian chạy thực tế:** `< 0.06s`.

---

## 3. NHÓM CHỐT SALE & KHUYẾN MÃI
Phục vụ nhu cầu chốt sale nhanh và làm khách hàng hài lòng bằng giá tốt.

### 3.1. `tool_query_discount_products` (Sản phẩm giảm giá sâu nhất)
*   **Đầu vào (Inputs):** `category` (str), `limit` (int).
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Top sản phẩm có `original_price - sale_price` lớn nhất.
*   **Thời gian chạy thực tế:** `< 0.05s`.

### 3.2. `tool_query_best_promotions` (Khuyến mãi, Quà tặng khủng)
*   **Đầu vào (Inputs):** `category` (str).
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Sản phẩm chứa các từ khóa quà tặng (hút bụi, vật tư, 1 đổi 1).
*   **Thời gian chạy thực tế:** `< 0.05s`.

---

## 4. NHÓM NGHIỆP VỤ (CẢNH BÁO)

### 4.1. `tool_query_out_of_stock` (Kiểm tra hết hàng)
*   **Đầu vào (Inputs):** Không cần.
*   **Đầu ra (Outputs):** `List[Dict[str, Any]]` - Danh sách sản phẩm có số lượng <= 0.
*   **Thời gian chạy thực tế:** `< 0.1s`.
