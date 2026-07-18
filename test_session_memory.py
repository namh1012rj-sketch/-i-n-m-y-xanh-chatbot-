import time
from llm_agent import DMXAgent

SESSION_PROMPTS = [
    # Câu 1: Bắt đầu thiếu thông tin
    "Tư vấn cho tôi một chiếc máy lạnh nhé",
    # Câu 2: Cung cấp 1 phần thông tin
    "Phòng tôi diện tích khoảng 15m2",
    # Câu 3: Hỏi thêm tính năng (Agent phải nhớ đang mua máy lạnh 15m2)
    "Tôi muốn loại nào tiết kiệm điện một chút",
    # Câu 4: So sánh 
    "Trong các mẫu bạn vừa nêu, hãng nào xài bền hơn?",
    # Câu 5: Lạc đề (Test chống quên)
    "À mà shop có bán tivi màn hình cong không?",
    # Câu 6: Quay lại chủ đề cũ (Phải nhớ mẫu máy lạnh đang nói)
    "Thôi quay lại cái máy lạnh lúc nãy, mẫu tiết kiệm điện rẻ nhất là bao nhiêu?",
    # Câu 7: Hỏi chính sách (FAQ)
    "Bảo hành loại đó thì quy trình như thế nào?",
    # Câu 8: Thay đổi quyết định 
    "Nếu đổi sang phòng lớn hơn 30m2 thì dùng loại nào?",
    # Câu 9: Tính năng cụ thể
    "Loại 30m2 đó có Inverter không?",
    # Câu 10: Chốt
    "Ok, cho tôi xem thông tin chi tiết con rẻ nhất trong số đó."
]

import sys

def run_session_test():
    log_file = open("fpt_test_session.log", "w", encoding="utf-8")
    original_stdout = sys.stdout
    sys.stdout = log_file

    print("="*60)
    print("BẮT ĐẦU CHẠY SESSION TEST (SLIDING WINDOW MEMORY - 10 CÂU) TRÊN FPT API")
    print("="*60)
    
    try:
        agent = DMXAgent()
    except Exception as e:
        print("Lỗi khởi tạo Agent:", e)
        sys.stdout = original_stdout
        log_file.close()
        return

    for i, prompt in enumerate(SESSION_PROMPTS, 1):
        print(f"\n[{i}/10] Khách: {prompt}")
        print("Agent: ", end="")
        
        start_time = time.time()
        try:
            for chunk in agent.send_message_stream(prompt):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n[LỖI]: {e}")
            
        end_time = time.time()
        
        # In độ dài lịch sử chat hiện tại để kiểm tra cơ chế Sliding Window
        print(f"--> [Thời gian xử lý: {end_time - start_time:.2f}s]")
        print(f"--> [Debug] Số lượng tin nhắn trong Context hiện tại: {len(agent.history)}")
        
        time.sleep(1) # Tránh Rate Limit của FPT API

    sys.stdout = original_stdout
    log_file.close()
    print("Đã hoàn thành Session Test. Hãy xem file fpt_test_session.log")

if __name__ == "__main__":
    run_session_test()
