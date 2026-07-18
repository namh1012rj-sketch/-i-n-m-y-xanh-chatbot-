import sys
import time
import asyncio
from llm_agent import DMXAgent

async def main():
    print("="*60)
    print("🤖 ĐIỆN MÁY XANH AI AGENT (ReAct Loop Custom + Streaming + Async)")
    print("="*60)
    print("Đang khởi tạo Agent và kết nối Database... (Vui lòng đợi 2-3s)")
    
    try:
        agent = DMXAgent()
    except Exception as e:
        print(f"Lỗi khởi tạo Agent: {e}")
        return

    print("Khởi tạo thành công! (Gõ 'exit' hoặc 'quit' để thoát)")
    print("-" * 60)
    
    while True:
        try:
            # Dùng asyncio.to_thread để không block event loop khi dùng lệnh input
            user_input = await asyncio.to_thread(input, "\nKhách hàng: ")
            if user_input.strip().lower() in ['exit', 'quit']:
                print("Tạm biệt!")
                break
                
            if not user_input.strip():
                continue
                
            print(f"Nhân viên ĐMX: ", end="", flush=True)
            
            t0 = time.time()
            first_token_time = None
            
            # Thay vòng lặp for đồng bộ thành async for vì stream giờ là Async Generator
            async for chunk in agent.send_message_stream(user_input):
                if first_token_time is None and chunk.strip():
                    first_token_time = time.time()
                print(chunk, end="", flush=True)
                
            t1 = time.time()
            ttft = (first_token_time - t0) if first_token_time else (t1 - t0)
            
            print(f"\n\n[Debug] Time to First Token (TTFT): {ttft:.2f}s | Total Latency: {t1 - t0:.2f}s")
            
        except KeyboardInterrupt:
            print("\nTạm biệt!")
            break
        except EOFError:
            print("\nTạm biệt!")
            break
        except Exception as e:
            print(f"\n[Lỗi trong quá trình xử lý]: {e}")

if __name__ == "__main__":
    asyncio.run(main())
