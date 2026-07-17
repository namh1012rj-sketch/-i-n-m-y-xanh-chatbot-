# TỔNG HỢP KIẾN TRÚC XỬ LÝ DỮ LIỆU VÀ THUẬT TOÁN TRUY VẤN (MONGODB ATLAS RAG)

Tài liệu này là đặc tả chi tiết về Định dạng dữ liệu, Các bước Chuẩn hóa (`DataPreprocessor`), và thuật toán vận hành của 12 công cụ tìm kiếm (`QueryEngine`). Hệ thống đã được thiết kế hoàn toàn Read-only để đảm bảo an toàn tuyệt đối khi kết hợp với LLM.

---

## 1. ĐỊNH DẠNG & CÁC BƯỚC CHUẨN HÓA DỮ LIỆU (DATA NORMALIZATION)

`DataPreprocessor` là thành phần xử lý đầu vào, tự động phân tích và nhúng Vector lên MongoDB.

### 1.1 Khối lượng và Cấu trúc Dữ liệu (Data Formats)
*   **Sản phẩm (Products):** Tổng cộng **5198** sản phẩm được lưu dưới định dạng **JSON Dictionaries**.
    *   *Các trường (Fields) chính:* Tên, Mã SKU (chuỗi), Thương hiệu, Giá gốc (`float`), Giá khuyến mãi (`float`), Danh mục (Máy lạnh, Tủ lạnh, v.v.), Quà tặng/Khuyến mãi (chuỗi), và bảng Cấu hình (`specs` - dạng Dictionary JSON lồng nhau).
*   **Câu hỏi chính sách (FAQ):** Dữ liệu câu hỏi đáp chuyên sâu định dạng JSON.
    *   *Các trường chính:* Câu hỏi, Nội dung câu trả lời, Nhãn danh mục (Category).
*   **Vector Embeddings:** Mảng số thực độ dài cố định **1024 chiều** (`List[float]`) được sinh ra từ mô hình `Vietnamese_Embedding`.

### 1.2 Các bước Chuẩn hóa dữ liệu (Normalization Steps)
1.  **Chuyển đổi kiểu dữ liệu (Data Casting & RegEx):**
    *   Hệ thống quét toàn bộ `specs` (thông số kỹ thuật). Bất cứ trường nào là dạng chuỗi văn bản chứa số (VD: `"1.5 HP"`, `"15 kg"`) đều được dùng Regex `r'(\d+[\.\d]*)'` để tách phần số thực (`float`/`int`).
    *   Giá trị số này được lưu vào field mới mang tên gốc kèm hậu tố `_numeric` (VD: `capacity_numeric: 1.5`). Bắt buộc để MongoDB có thể chạy thuật toán tính toán `<, >, =, <=`.
2.  **Gán nhãn Phân khúc giá (Price Bucketing):**
    *   Thay vì chỉ nhúng con số khô khan, hệ thống phân loại giá thành ngôn ngữ tự nhiên. 
    *   VD: < 5tr -> `"phân khúc giá siêu rẻ dưới 5 triệu"`; > 20tr -> `"phân khúc giá cao cấp trên 20 triệu"`.
    *   Bước này giúp LLM và API nhúng hiểu được ngữ nghĩa về "sự đắt/rẻ" chứ không đơn thuần là xử lý con số.
3.  **Tạo Vector Nhúng (Embedding Generation):**
    *   Nối (concatenate) tất cả thông tin thành một cụm văn bản lớn (Tên, Giá, Phân khúc, Khuyến mãi, Cấu hình).
    *   Gửi từng batch qua FPT Cloud API để lấy Vector 1024 chiều và gán ngược lại field `"embedding"` trên MongoDB Atlas. Tránh việc LLM phải tự sinh Vector gây chậm trễ.

---

## 2. THUẬT TOÁN CỦA CÁC QUERY TOOLS (QUERY ENGINE)

Bộ 12 công cụ truy vấn (đã loại trừ công cụ ghi chú) được chia thành 3 thuật toán chính.

### 2.1 Thuật toán Tìm kiếm Lai (Hybrid Search / Atlas Vector Search)
Hoạt động trên cơ sở so sánh độ đo Cosine Similarity giữa Vector câu hỏi và Vector trong Database.
*   **`tool_query_products` (Tìm sản phẩm theo nhu cầu mềm):**
    *   *Bước 1:* Dùng API dịch `raw_query` thành Vector 1024 chiều $Q$. (Short-circuit: Nếu API rớt mạng trả về toàn số 0, thuật toán sẽ bỏ qua Bước 2 để tránh crash DB).
    *   *Bước 2:* Dùng thuật toán `$vectorSearch` của Atlas. Kết hợp **Pre-filtering** (Lọc thô các sản phẩm vi phạm bộ lọc cứng như: sai danh mục, vượt `budget`, hoặc sai `room_area`).
    *   *Bước 3:* MongoDB tính điểm Cosine góc giữa $Q$ với các sản phẩm qua vòng lọc để lấy ra Top 5 sát nhất.
    *   *Bước 4:* Tính điểm Boost cứng (Cộng dồn tay 0.05 điểm) nếu truy vấn có chữ "inverter" và tên máy có chữ "inverter".
*   **`tool_query_similar_products` (Tìm thay thế):**
    *   Trích xuất trực tiếp Vector $T$ của sản phẩm gốc có sẵn trong DB để tìm các sản phẩm lân cận nhất trong không gian Vector. Tốc độ rất nhanh vì không phải gọi API nhúng văn bản.
*   **`tool_query_faq` (Tìm chính sách):**
    *   Dịch truy vấn thành Vector và quét trên tập CSDL `faq`.

### 2.2 Thuật toán Lọc Thông số chính xác (Exact Range & Match)
Không dùng Vector, hoàn toàn dùng sức mạnh của thuật toán dò tìm B-Tree Index trên MongoDB để đạt tốc độ <0.05s.
*   **`tool_get_product_details`:** Tìm theo ID duy nhất với tốc độ O(log n).
*   **`tool_search_product_by_name`:** Dùng thuật toán biểu thức chính quy Regex (`$regex`, option `i` - ignore case) để quét chuỗi ký tự.
*   **`tool_query_products_by_spec_range`:** Dùng thuật toán so sánh `$gte` (Lớn hơn bằng) và `$lte` (Nhỏ hơn bằng) duyệt qua các trường số học `_numeric` đã chuẩn hóa ở phần DataPreprocessor.
*   **`tool_query_products_by_brand`:** Khớp nhãn cứng (Hard Match).

### 2.3 Thuật toán Aggregation, Sắp xếp và Khuyến mãi (Sorting & Keyword Matching)
Sử dụng Aggregation Pipeline của MongoDB để xử lý tính toán ngay trên Server DB.
*   **`tool_sort_products_by_price`:** 
    *   Dùng Pipeline: `$match` (Lọc danh mục) -> `$sort` (Sắp xếp `sale_price`) -> `$limit` (Cắt Top đầu). 
*   **`tool_query_discount_products`:**
    *   Dùng thuật toán `$subtract` để tạo trường tính toán ảo `$discount_amount` = `original_price - sale_price`.
    *   Sau đó `$sort` giảm dần theo phần chênh lệch này.
*   **`tool_query_best_promotions`:**
    *   Dùng vòng lặp `$regex` quét qua trường `promotion` kết hợp mảng tĩnh chứa từ khóa vàng `["tặng máy hút bụi", "1 đổi 1", ...]`.
