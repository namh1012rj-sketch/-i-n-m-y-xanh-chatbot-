# KẾ HOẠCH TRIỂN KHAI LLM AGENT ĐÁP ỨNG TIÊU CHÍ VĂN HÓA & NGÔN NGỮ

Dựa trên bảng tiêu chí (Rubric) cực kỳ chi tiết về ngôn ngữ, văn hóa địa phương (Việt Nam) và tư duy ngành hàng, mình đề xuất kế hoạch triển khai (Implementation Plan) sau:

## 1. Nâng cấp `system_prompt_template.txt`

Cần tiêm (inject) các ràng buộc cực kỳ cụ thể từ bảng Tiêu chí vào Prompt:

*   **Về Ngôn ngữ (Language):**
    *   Hỗ trợ hiểu tiếng Việt không dấu, viết tắt (VD: "sp", "đt", "kh", "k" = nghìn).
    *   Hiểu Code-switching Việt-Anh (VD: "RAM xịn", "chơi game mượt", "camera nét").
    *   Hiểu các đơn vị đo đặc thù ngành: m2 (diện tích), HP/BTU (công suất lạnh), GB/TB (bộ nhớ), Lít (dung tích).
*   **Về Văn hóa (Culture & Tone):**
    *   Giao tiếp lịch sự, gần gũi, xưng "Em" gọi "Anh/Chị".
    *   **TUYỆT ĐỐI KHÔNG ÉP MUA (No hard-selling):** Không dùng các từ ngữ chèo kéo quá đà kiểu "Mua ngay kẻo lỡ", "Anh phải chốt con này".
*   **Về Logic Tư duy Ngành hàng (Domain Logic):**
    *   Máy lạnh: Hỏi diện tích, hướng phòng (có bị nắng chiếu không).
    *   Tủ lạnh: Hỏi số người trong gia đình (để tính dung tích Lít).
    *   Điện thoại: Hỏi nhu cầu chụp ảnh, pin, chơi game.
    *   Laptop: Hỏi nhu cầu công việc (Văn phòng, Đồ họa, Gaming).

## 2. Tích hợp LLM Workflow (ReAct & Latency Optimization)
- **Workflow cốt lõi (ReAct):** Nhận diện Ý định (Intent) -> Chọn Hành động (Hỏi ngược hoặc Gọi Tool) -> Lọc dữ liệu -> Trả lời khách hàng.
- **Quản lý Ngữ cảnh (Memory):** Dùng kỹ thuật Cửa sổ trượt (Sliding Window), nạp 5-7 câu chat gần nhất để tránh mất ngữ cảnh.
- **Tối ưu tốc độ (< 3s & < 5s):** 
  - Kịch bản hỏi ngược, Chit-chat, Lạc đề: Bắt LLM trả lời trực tiếp ngay, KHÔNG gọi Tool (để đạt < 3s).
  - So sánh Top 3: Ép output ngắn gọn dưới 150 từ (để đạt < 5s). Cấu hình max_iterations = 3 để tránh vòng lặp chết (Infinite Loop).

## 3. Xây dựng Code Core LLM (`llm_agent.py`)

Để biến 13 Tools trong `query_tools.py` thành một con Agent tự động suy nghĩ (ReAct), chúng ta cần viết một file `llm_agent.py`.

### Kiến trúc dự kiến:
*   **Framework:** Sử dụng **Google GenAI SDK (Gemini)** hoặc **OpenAI SDK** vì hỗ trợ Function Calling (gọi hàm) cực tốt và rất dễ thiết lập cho Hackathon.
*   **Function Calling:** Bind (Gắn) 13 hàm từ `QueryEngine` vào LLM. Khi LLM nhận câu hỏi, nó sẽ tự động phân tích và trả về tên hàm + tham số cần gọi.
*   **Conversation Memory:** Lưu trữ 5 lượt chat gần nhất để truyền vào LLM.

## 3. Các bước thực thi

1.  [MODIFY] `system_prompt_template.txt`: Viết lại prompt bám sát 100% các tiêu chí từ hình ảnh.
2.  [NEW] `llm_agent.py`: Khởi tạo class `Agent` kết nối API của LLM, nạp System Prompt và 13 Tools.
3.  [NEW] `test_agent.py`: Script giả lập khung chat Terminal để test thử vòng lặp ReAct của Agent với các câu hỏi thực tế (có viết tắt, không dấu, chit-chat).

## User Review Required
> [!IMPORTANT]
> Mình sẽ code phần `llm_agent.py`. Bạn muốn mình sử dụng model của hãng nào cho Hackathon này?
> 1. **Google Gemini (Gemini 1.5 Flash/Pro)** - Đang miễn phí và tốc độ cực nhanh, hỗ trợ tiếng Việt xuất sắc.
> 2. **OpenAI (GPT-4o-mini)** - Rất thông minh nhưng cần thẻ tín dụng nạp tiền.
> 
> Bạn hãy phản hồi chọn Model, sau đó bấm **Proceed (Xác nhận)** để mình bắt đầu Code nhé!
