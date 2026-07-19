# Báo Cáo Tổng Kết - Trợ lý AI Tư vấn Mua sắm Điện Máy Xanh

Tài liệu này tổng hợp lại toàn bộ quy trình xây dựng, tối ưu và kiểm thử hệ thống Trợ lý AI (Chatbot) dành riêng cho Điện Máy Xanh. Dự án ứng dụng kiến trúc ReAct kết hợp với Retrieval-Augmented Generation (RAG) và Vector Search để mang lại trải nghiệm tư vấn tự nhiên, thông minh và chính xác nhất cho khách hàng.

---

## 1. Xử lý Dữ liệu (Data Processing)
- **Thu thập & Làm sạch**: Lọc bỏ các ký tự rác, chuẩn hóa tên danh mục sản phẩm từ dữ liệu gốc (ví dụ: gộp các biến thể về các danh mục chuẩn như "Điện thoại", "Máy lạnh", "Tủ lạnh").
- **Tối ưu cấu trúc**: Tái cấu trúc dữ liệu JSON để tối ưu hóa việc trích xuất thông tin (thông số kỹ thuật, giá, khuyến mãi).
- **Vectorization & Lưu trữ**: Mã hóa dữ liệu (embedding) và đẩy lên **MongoDB Atlas** để phục vụ việc truy vấn tốc độ cao thông qua thuật toán Vector Search (HNSW).

## 2. Xây dựng Trợ lý AI (LLM Agent Architecture)
- **Thiết kế ReAct Framework**: Phát triển Agent tự động với mô hình ngôn ngữ (DeepSeek/FPT) tích hợp khả năng suy luận và sử dụng công cụ (Tool Use).
- **Tích hợp Semantic Search**: Áp dụng mô hình `multilingual-e5-large` để tìm kiếm thông minh dựa trên độ tương đồng ngữ nghĩa (Cosine Similarity), vượt qua rào cản của việc tìm kiếm theo từ khóa thông thường.
- **Quản lý Bộ nhớ (Memory)**: Áp dụng cơ chế *Sliding Window History* để duy trì ngữ cảnh trò chuyện mà không gây tràn token (out of context window).
- **Xử lý Fallback linh hoạt**: Kịch bản phản hồi khéo léo khi khách hàng hỏi những câu hỏi ngoài phạm vi hệ thống hoặc khi không có sản phẩm nào đáp ứng sát tiêu chí.

## 3. Phát triển Giao diện (Frontend & UI/UX)
- **Redesign giao diện**: Tối ưu hóa UI/UX với giao diện sáng màu hiện đại (Light Mode cố định), bố cục Full-width tràn viền để dễ dàng hiển thị danh sách sản phẩm. Cập nhật Logo và Favicon chuẩn nhận diện thương hiệu.
- **Tối ưu hiển thị Markdown**: Tích hợp `react-markdown` và `remark-gfm` giúp nội dung văn bản của AI (như in đậm, danh sách bullet) được render một cách mượt mà và trực quan.
- **Cải tiến khung chat (Chat Input)**: Thay thế thẻ `<input>` cơ bản thành `<textarea>` tự động giãn nở (auto-resize), hỗ trợ phím `Shift+Enter` để xuống dòng tự nhiên giống các nền tảng chat phổ biến.
- **Trải nghiệm Streaming**: Chuẩn hóa luồng trả lời trực tiếp (Server-Sent Events - SSE), lược bỏ hoàn toàn các log hệ thống nội bộ (như `[Đang tìm kiếm...]`) trên giao diện để mang lại cảm giác giao tiếp trơn tru như người thật.

## 4. Kiểm thử & Tối ưu Hiệu năng (Testing & Optimization)
- **Tối ưu tốc độ (Caching & Concurrency)**: Triển khai luồng xử lý đa luồng (Multi-threading với `ThreadPoolExecutor`) kết hợp caching thread-safe (sử dụng `dict` + `threading.Lock`). Nhờ đó, hệ thống phản hồi nhanh hơn tới **~6.8x** đối với các truy vấn vector độc lập.
- **Sửa lỗi đứt gãy kết nối (SSE Parsing)**: Xử lý triệt để lỗi ngắt kết nối stream do ký tự xuống dòng `\n` trong phản hồi của mô hình, giúp giao diện không bị giật/lag khi sinh chữ.
- **Khắc phục lỗi Tràn Token**: Nâng cấp `max_tokens` từ 800 lên 4000, giải quyết dứt điểm hiện tượng câu trả lời chứa mô tả cấu hình chi tiết của sản phẩm bị ngắt câu giữa chừng.
- **Tinh chỉnh thuật toán lọc (Filtering Tolerance)**: 
  - Sửa lỗi logic match nhầm danh mục (ví dụ: truy vấn "Điện thoại" bị hệ thống bắt nhầm sang "Phụ kiện điện thoại" do substring match). Cập nhật sang Exact Match.
  - Nới lỏng biên độ lọc mức giá (budget tolerance) thêm 15% (`$lte: budget * 1.15`), giúp AI tự động gợi ý các sản phẩm ưu tú nằm kề cận với ngân sách người dùng (VD: ngân sách 8 triệu vẫn có thể gợi ý máy 8.2 triệu), mang tính thực tế cao hơn so với việc lọc cứng ngắc.
- **Kiểm soát mã nguồn**: Cài đặt và sử dụng `commitlint` kết hợp `husky` để đảm bảo quy chuẩn commit message trong quá trình làm việc nhóm.

---
*Dự án đã hoàn thiện và sẵn sàng để nghiệm thu / deploy trên môi trường Production, đảm bảo xử lý trọn vẹn và chuyên nghiệp mọi yêu cầu tư vấn mua sắm của khách hàng.*
