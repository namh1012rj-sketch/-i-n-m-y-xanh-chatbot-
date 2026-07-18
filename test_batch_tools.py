import sys
import time
import asyncio
from llm_agent import DMXAgent

PROMPTS = [
    "Xin chào shop",
    "Tư vấn cho mình cái máy lạnh",
    "Mình muốn mua máy tính để chơi game Genshin Impact mượt mà",
    "Cho mình xin thông tin con SingPC",
    "Mình thích máy lạnh của hãng Daikin",
    "Cho xem top 3 điện thoại rẻ nhất",
    "Laptop nào đang giảm giá sâu nhất",
    "Tủ lạnh có làm đá tự động không",
    "Máy lạnh cho phòng khoảng 15 mét vuông",
    "Chính sách bảo hành tivi bên mình như nào",
    "Có sản phẩm nào đang hết hàng không",
    "Tìm cho mình các sản phẩm tương tự con điện thoại mã IPH-15-PRO-MAX-1T-TITAN"
]

MEMORY_TEST_SEQ = [
    "Tư vấn cho mình cái tủ lạnh",
    "Mình mua cho gia đình 4 người dùng",
    "Ngân sách của mình là dưới 15 triệu",
    "Cho mình lấy con thứ 2 nhé"
]

async def run_batch_test():
    log_file = open("fpt_test_session.log", "w", encoding="utf-8")
    original_stdout = sys.stdout
    sys.stdout = log_file

    print("="*60)
    print("BẮT ĐẦU CHẠY BATCH TEST & MEMORY TEST (DeepSeek-V4-Flash)")
    print("="*60)
    
    try:
        agent = DMXAgent()
        system_prompt = agent.history[0]
    except Exception as e:
        print("Lỗi khởi tạo Agent:", e)
        sys.stdout = original_stdout
        log_file.close()
        return

    # 1. BATCH TEST (Không liên kết bộ nhớ)
    print("\n--- 1. BATCH TEST TOOL COVERAGE ---")
    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\n[{i}/{len(PROMPTS)}] Khách: {prompt}")
        print("Agent: ", end="")
        
        start_time = time.time()
        try:
            agent.history = [system_prompt] # Xóa context
            async for chunk in agent.send_message_stream(prompt):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n[LỖI]: {e}")
            
        end_time = time.time()
        print(f"--> [Thời gian xử lý: {end_time - start_time:.2f}s]")
        await asyncio.sleep(1)

    # 2. MEMORY TEST (Liên kết bộ nhớ)
    print("\n\n--- 2. SESSION MEMORY TEST (MULTI-TURN) ---")
    agent.history = [system_prompt]
    
    for i, prompt in enumerate(MEMORY_TEST_SEQ, 1):
        print(f"\n[Turn {i}] Khách: {prompt}")
        print("Agent: ", end="")
        
        start_time = time.time()
        try:
            # Không xóa history
            async for chunk in agent.send_message_stream(prompt):
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            print(f"\n[LỖI]: {e}")
            
        end_time = time.time()
        print(f"--> [Thời gian xử lý: {end_time - start_time:.2f}s]")
        await asyncio.sleep(1)
        
    sys.stdout = original_stdout
    log_file.close()
    print("Đã hoàn thành Batch Test và Memory Test. Hãy xem file fpt_test_batch.log")

if __name__ == "__main__":
    asyncio.run(run_batch_test())
