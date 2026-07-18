# KIẾN TRÚC VÀ LUỒNG XỬ LÝ CỦA LLM AGENT (LLM WORKFLOW)

Tài liệu này đặc tả luồng xử lý từ đầu đến cuối (End-to-End Workflow) dành cho Team LLM/Agent, kèm theo chiến thuật tối ưu hóa để **đạt điểm tuyệt đối ở cả 5 tiêu chí đánh giá** của Ban Giám Khảo.

---

## 1. LUỒNG XỬ LÝ TIÊU CHUẨN (STANDARD WORKFLOW)

Khi hệ thống nhận được tin nhắn từ khách hàng (User Input), LLM Agent sẽ chạy qua 4 bước (ReAct Framework: Reason + Act):

### Bước 1: Phân tích Ý định & Nhận diện Nhu cầu (Intent Recognition)
- Agent đọc câu hỏi của khách và lịch sử chat (Memory).
- **Quyết định 1 (Phân loại yêu cầu):**
  - Mua hàng / Tra cứu sản phẩm / Tra cứu Chính sách / Gửi Link.
  - **Giao tiếp ngoài lề (Chit-chat):** (VD: "Xin chào", "Cảm ơn", "Bạn là ai"). Agent phản hồi xã giao ngay lập tức, không gọi Tool.
  - **Nằm ngoài phạm vi (Out-of-domain):** (VD: Hỏi chính trị, mua quần áo, viết code). Khéo léo từ chối và điều hướng khách về mảng điện máy.
- **Quyết định 2 (Kiểm tra độ đầy đủ):** Yêu cầu mua hàng đã đủ thông tin cốt lõi (Ngân sách, Danh mục, Nhu cầu cụ thể) chưa?

### Bước 2: Kích hoạt Công cụ (Tool Calling / Act)
- **Nếu hoàn toàn thiếu thông tin** (VD: chỉ nói "mua máy lạnh"): Agent quyết định **KHÔNG** gọi Tool mà **Trực tiếp Hỏi ngược** khách hàng (VD: hỏi diện tích phòng).
- **Nếu thiếu thông tin NHƯNG đã có 1 vài tiêu chí** (VD: "Tôi muốn mua máy tính SingPC"): Agent **VẪN GỌI TOOL** để tìm các mẫu SingPC tốt nhất hiện có để show cho khách, ĐỒNG THỜI hỏi thêm câu hỏi phụ. (Giúp trải nghiệm mượt mà, tránh tình trạng ép cung khách hàng phải khai báo đủ 100% tiêu chí mới chịu tư vấn).
- **Nếu đủ thông tin:** Agent phân tích và truyền tham số (Arguments) vào đúng Tool trong bộ 13 Tools.

### Bước 3: Đọc hiểu Dữ liệu trả về (Observation & Data Filtering)
- Dữ liệu thô từ Database trả về (thường là JSON chứa thông số kỹ thuật).
- Agent đọc dữ liệu, lọc bỏ các thông số không liên quan, chỉ giữ lại những thông số giải quyết đúng "nỗi đau" (pain-point) của khách.

### Bước 4: Tổng hợp & Trả lời (Response Generation)
- Agent định dạng lại dữ liệu thô thành ngôn ngữ tự nhiên.
- Phiên dịch thông số kỹ thuật sang **lợi ích thực tế**.
- So sánh, giải thích Trade-off (Đánh đổi) và đưa ra kết luận (Call-to-Action).

---

## 2. QUẢN LÝ LỊCH SỬ HỘI THOẠI & VÒNG LẶP REACT (CRITICAL)

Đây là 2 kỹ thuật bắt buộc phải có để Agent không bị "ngu ngơ" và không bị treo (Infinite Loop):

### 2.1 Quản lý Bộ nhớ (Conversation Memory)
- **Vấn đề:** Nếu không có lịch sử, khi Agent hỏi *"Phòng anh bao nhiêu m2?"*, khách đáp *"15m2"*, Agent sẽ quên mất khách đang định mua máy lạnh.
- **Giải pháp:** Phải nhúng lịch sử chat (Conversation Buffer Memory) vào Context của LLM. Tuy nhiên, để tránh "Lost in the Middle" và tiết kiệm Token, **chỉ nên giữ lại 5-7 lượt hội thoại gần nhất** (Sliding Window Memory).

### 2.2 Kiểm soát Vòng lặp ReAct (ReAct Loop & Latency)
- **Cơ chế ReAct:** Agent hoạt động theo chu kỳ `Suy nghĩ (Thought) -> Hành động (Action/Tool) -> Quan sát kết quả (Observation) -> Suy nghĩ tiếp...` cho đến khi có câu trả lời cuối cùng.
- **Rủi ro:** Nếu Tool báo lỗi liên tục, Agent có thể rơi vào vòng lặp vô tận (Infinite Loop), dẫn đến quá thời gian phản hồi (Latency > 10s) và bị trừ điểm nặng.
- **Giải pháp (Max Iterations):** 
  - Đặt cấu hình `max_iterations = 3` (hoặc tối đa 5). Nếu qua 3 vòng lặp mà chưa tìm được kết quả, ép Agent phải thoát vòng lặp và báo lỗi mượt mà: *"Dạ hệ thống bên em đang quá tải, anh chị đợi chút nhé..."*
  - Hướng dẫn Prompt: *"Nếu Tool A trả về rỗng, KHÔNG ĐƯỢC gọi đi gọi lại Tool A. Hãy thử Tool B hoặc dừng lại hỏi khách."*

---

## 3. CHIẾN LƯỢC TỐI ƯU ĐỘ TRỄ (LATENCY OPTIMIZATION)

Dựa trên yêu cầu khắt khe của Ban Giám Khảo: **"Phản hồi gợi ý/hỏi ngược trong < 3 giây; so sánh top 3 sản phẩm trong < 5 giây"**, Team LLM bắt buộc phải áp dụng các kỹ thuật sau:

### 3.1 Đối với Kịch bản Hỏi ngược (< 3s)
- **Không gọi Tool:** Khi LLM nhận diện thiếu thông tin (VD: chưa có diện tích phòng), phải thiết lập cấu trúc ReAct sao cho LLM xuất ra câu trả lời trực tiếp thay vì cố gắng gọi Tool với tham số rỗng. Việc bỏ qua bước gọi Tool sẽ giảm độ trễ xuống chỉ còn **1-2 giây** (thời gian sinh text của LLM).
- **Dùng Model siêu tốc (Fast LLM):** Nên ưu tiên dùng các model nhẹ và siêu nhanh như **Gemini 1.5 Flash**, **GPT-4o-mini**, hoặc **Llama-3 (qua Groq)** cho các tác vụ phân tích Intent ban đầu.

### 3.2 Đối với Kịch bản So sánh Top 3 Sản phẩm (< 5s)
- **Quỹ thời gian:** Tool `tool_query_products` (Vector Search) mất khoảng **0.9s** để chạy. Do đó, LLM chỉ còn khoảng **3-4s** để đọc Data và sinh ra đoạn văn bản so sánh.
- **Giới hạn Output Tokens:** Trong System Prompt, phải ép LLM trả lời ngắn gọn: *"Trình bày so sánh tối đa trong 150 từ"*. Không để LLM lan man sinh ra văn bản quá dài làm lố thời gian 5s.
- **Streaming Response (Bắt buộc):** Ở phía Frontend / Backend, **phải bật chế độ Streaming** (Server-Sent Events). Ngay khi LLM nhả ra chữ đầu tiên (Time to First Token - TTFT thường chỉ mất ~1.5s), giao diện phải hiển thị ngay cho giám khảo xem. Giám khảo sẽ có cảm giác Bot phản hồi tức thì, dù tổng thời gian hoàn thành (hoàn tất câu) có thể là 4-5s.

---

## 4. CHIẾN LƯỢC TỐI ƯU 5 TIÊU CHÍ ĐÁNH GIÁ (SCORING OPTIMIZATION)

Dựa trên bảng Tiêu chí Đánh giá, Team LLM cần thiết lập System Prompt và Logic xử lý như sau để lấy trọn điểm:

### Tiêu chí 1: Hiểu đúng nhu cầu thật từ mô tả tự nhiên
- **Cách tối ưu:** 
  - Sử dụng công cụ `tool_query_products` (Hybrid Search) làm nòng cốt. Khách hàng hiếm khi gõ "RAM 8GB", họ sẽ gõ "máy chạy Excel mượt không lag". Vector Search của chúng ta (qua FPT API) sinh ra để giải quyết vấn đề này. 
  - **Prompt:** *"Luôn phân tích câu hỏi của khách hàng để trích xuất các từ khóa về nhu cầu mềm (như 'tiết kiệm điện', 'chơi game mượt') truyền vào tham số `raw_query` của Tool."*

### Tiêu chí 2: Hỏi ngược khi thiếu thông tin đầu vào
- **Cách tối ưu:** Đây là tiêu chí **dễ mất điểm nhất** nếu AI quá máy móc.
- **Prompt:** Cần đưa Rule "HỎI NGƯỢC" lên đầu System Prompt.
  - *"Nếu khách yêu cầu tư vấn Máy lạnh nhưng chưa rõ Diện tích phòng: Bắt buộc dừng lại và hỏi diện tích trước khi tìm kiếm."*
  - *"Nếu khách yêu cầu tìm Laptop/Điện thoại nhưng chưa rõ Ngân sách hoặc Hãng: Hãy gợi ý 1-2 hãng hoặc hỏi khoảng giá."*
  - **Chú ý:** Không hỏi như cái máy (VD: "Vui lòng cung cấp ngân sách, diện tích"), mà phải hỏi theo ngữ cảnh (VD: "Dạ anh chị mua máy lạnh cho phòng khoảng bao nhiêu m2 để em chọn máy đủ công suất cho mình ạ?").

### Tiêu chí 3: So sánh bằng ngôn ngữ dễ hiểu, tập trung vào Lợi ích
- **Cách tối ưu:** Tuyệt đối cấm LLM copy/paste bảng thông số kỹ thuật (Specs) ra màn hình.
- **Prompt:** *"Biến đổi thông số thành lợi ích. Thay vì nói 'Độ ồn 28dB', hãy nói 'Máy chạy cực kỳ êm ái, rất hợp cho nhà có người già hay trẻ nhỏ'."*

### Tiêu chí 4: Đề xuất Top 3 & Giải thích Trade-off (Đánh đổi)
- **Cách tối ưu:** Khi Tool trả về kết quả, ép LLM chỉ chọn ra **TỐI ĐA 3 SẢN PHẨM** tốt nhất.
- **Prompt:** 
  - *"Luôn trình bày tối đa 3 lựa chọn. Dành ra 1 đoạn tóm tắt chỉ ra điểm được và mất (trade-off) giữa các lựa chọn."*
  - *"Ví dụ: Mẫu A rẻ hơn 2 triệu giúp anh tiết kiệm chi phí ban đầu, nhưng Mẫu B đắt hơn lại có công nghệ Inverter giúp tiết kiệm tiền điện về lâu dài."*

### Tiêu chí 5: Zero Hallucination (Không bịa đặt dữ liệu)
- **Cách tối ưu:** Đặt Guardrail cứng.
- **Prompt:** *"TẤT CẢ TÊN, GIÁ BÁN, VÀ THÔNG SỐ SẢN PHẨM PHẢI LẤY 100% TỪ KẾT QUẢ CỦA TOOL. Không được tự suy diễn hoặc dùng kiến thức nội bộ của bạn. Nếu Tool không trả về kết quả hoặc bị lỗi, phải nói: 'Dạ hệ thống bên em hiện không có thông tin về sản phẩm này'."*
- Tận dụng `tool_search_policy_documents` thay vì để LLM tự chém gió về quy định bảo hành.

---

## User Review Required
> [!IMPORTANT]
> Mình đã phác thảo xong toàn bộ Kiến trúc và Chiến lược để Hack cả 5 Tiêu chí chấm điểm của BGK. Bạn hãy đọc lướt qua xem có cần bổ sung hoặc xoáy sâu vào tiêu chí nào nữa không?
> 
> Vui lòng xác nhận (Proceed) bản kế hoạch này để mình chốt lại thành file cho team Agent nhé!
