import os
import re
import io
import sys
import json
import asyncio
from openai import OpenAI
from llm_agent import DMXAgent
from dotenv import load_dotenv

load_dotenv()
FPT_API_KEY = os.environ.get("FPT_API_KEY")
if not FPT_API_KEY:
    print("WARNING: Chưa có FPT_API_KEY trong file .env.")

client = OpenAI(api_key=FPT_API_KEY, base_url="https://mkp-api.fptcloud.com/v1")
MODEL_NAME = "DeepSeek-V4-Flash"
PROMPT_FILE = "system_prompt_template.txt"

SCENARIOS = [
    "Tôi muốn mua một chiếc điện thoại giá tầm 10 củ để chơi game nặng. Hãy gợi ý vài mẫu.",
    "Bán cho tôi cái máy lạnh đi shop",
    "Tư vấn máy tính SingPc vừa làm việc văn phòng vừa chơi game, giá cả từ 15 triệu trở xuống",
    "so sánh giúp mình tủ lạnh side by side và tủ nhiều cửa, nhà mình 5 người thì nên mua loại nào",
    "Mình đang tìm tivi 65 inch giá rẻ nhất có thể, nhưng phải xem được Netflix"
]

JUDGE_PROMPT = """Bạn là giám khảo chuyên môn đánh giá chất lượng của trợ lý AI bán hàng Điện Máy Xanh.
Trọng số đánh giá (dựa trên 5 tiêu chí):
1. Hiểu đúng nhu cầu: Phân loại đúng nhu cầu, ngân sách. (10%)
2. Hỏi ngược thông minh: Biết hỏi thêm khi thiếu thông tin quan trọng. (10%)
3. So sánh sản phẩm có trade-off: Không chỉ liệt kê thông số, phải giải thích bằng ngôn ngữ phổ thông ưu/nhược. (10%)
4. Đề xuất top 3: Đề xuất phù hợp nhất. (10%)
5. Tốc độ & Giao tiếp (Rất Quan Trọng): AI tuyệt đối KHÔNG ĐƯỢC chat dài dòng kiểu "Dạ để em kiểm tra..." TRƯỚC KHI gọi Tool. Bắt buộc phải gọi Tool ngay lập tức. (10%)

Hãy đọc CÂU HỎI của khách hàng và PHẢN HỒI của AI. 
Chỉ ra những điểm chưa tốt của AI. Cuối cùng, đánh giá ĐIỂM SỐ CHUNG (từ 1.0 đến 10.0) dựa trên mức độ hoàn thiện của 5 tiêu chí trên.
BẮT BUỘC ở dòng cuối cùng của kết quả, xuất ra đúng định dạng sau: SCORE: X.X (ví dụ SCORE: 8.5)
"""

OPTIMIZER_PROMPT = """Bạn là chuyên gia Prompt Engineering.
Trợ lý AI của Điện Máy Xanh vừa được đánh giá bằng các tiêu chí khắt khe (Hỏi ngược thông minh, So sánh có trade-off, Giới hạn top 3, Không hallucinate) và vẫn chưa đạt điểm tối đa.
Dưới đây là Prompt hiện tại đang được sử dụng. BẠN PHẢI GIỮ NGUYÊN hoặc làm mạnh hơn quy tắc "Tuyệt đối không chat nhảm trước khi gọi tool để tiết kiệm thời gian":
<CURRENT_PROMPT>
{current_prompt}
</CURRENT_PROMPT>

Đây là những lỗi và phản hồi từ giám khảo cho các tình huống thử nghiệm:
<FEEDBACK>
{feedback}
</FEEDBACK>

Nhiệm vụ của bạn: Dựa vào CURRENT_PROMPT và FEEDBACK, hãy VIẾT LẠI TOÀN BỘ nội dung của system prompt. 
- BẮT BUỘC giữ lại toàn bộ cấu trúc và các quy tắc cốt lõi, chỉ thêm hoặc làm rõ các hướng dẫn để sửa các lỗi được giám khảo chỉ ra.
- BẮT BUỘC đầu ra phải là một bản system prompt HOÀN CHỈNH, ĐẦY ĐỦ từ dòng đầu tiên đến dòng cuối cùng. TUYỆT ĐỐI KHÔNG được trả về một câu ngắn hay một đoạn tóm tắt.
- CHỈ output phần text của prompt mới, không bọc trong ```markdown hoặc bất kỳ tag nào khác. Không giải thích gì thêm.
"""

async def evaluate_agent():
    total_score = 0.0
    feedbacks = []
    
    for i, user_text in enumerate(SCENARIOS):
        print(f"  Thử nghiệm kịch bản {i+1}: {user_text}")
        agent = DMXAgent()
        
        # Capture stdout
        old_stdout = sys.stdout
        new_stdout = io.StringIO()
        sys.stdout = new_stdout
        
        try:
            async for chunk in agent.send_message_stream(user_text):
                pass
        except Exception as e:
            print(f"Lỗi khi chạy agent: {e}")
        finally:
            sys.stdout = old_stdout
            
        output_text = new_stdout.getvalue()
        
        ai_response = ""
        for msg in reversed(agent.history):
            if msg["role"] == "assistant" and msg.get("content"):
                ai_response = msg["content"]
                break
        
        if not ai_response:
            ai_response = output_text # Fallback
            
        judge_sys = {"role": "system", "content": JUDGE_PROMPT}
        judge_user = {"role": "user", "content": f"CÂU HỎI KHÁCH HÀNG: {user_text}\n\nAI PHẢN HỒI:\n{ai_response}"}
        
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[judge_sys, judge_user],
            temperature=0.1
        )
        evaluation = resp.choices[0].message.content
        
        score_match = re.search(r'SCORE:\s*([\d\.]+)', evaluation)
        if score_match:
            score = float(score_match.group(1))
        else:
            score = 5.0
            
        total_score += score
        if score < 9.5:
            feedbacks.append(f"- Tình huống: {user_text}\n- Phản hồi của AI:\n{ai_response}\n- Nhận xét giám khảo:\n{evaluation}\n")
            
    return total_score / len(SCENARIOS), feedbacks

async def main():
    max_iters = 30
    best_score = 0
    
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        best_prompt = f.read()

    for iteration in range(1, max_iters + 1):
        print(f"\n[{iteration}/{max_iters}] Bắt đầu vòng tối ưu...")
        avg_score, feedbacks = await evaluate_agent()
        print(f"-> Điểm trung bình vòng {iteration}: {avg_score:.2f} / 10")
        
        if avg_score > best_score:
            best_score = avg_score
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                best_prompt = f.read()
                
        if avg_score >= 9.5:
            print(f"🎉 Đạt ngưỡng điểm mong muốn (>=9.5)! Dừng tối ưu.")
            break
            
        if iteration == max_iters:
            print("Đã đạt số vòng tối đa.")
            break
            
        if feedbacks:
            print(f"Tiến hành sinh prompt mới để cải thiện điểm số...")
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                current_prompt = f.read()
                
            combined_feedback = "\n\n".join(feedbacks)
            
            optimizer_sys = {"role": "system", "content": OPTIMIZER_PROMPT.format(current_prompt=current_prompt, feedback=combined_feedback)}
            
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[optimizer_sys],
                temperature=0.7
            )
            
            new_prompt = resp.choices[0].message.content.strip()
            
            if new_prompt.startswith("```"):
                lines = new_prompt.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                new_prompt = "\n".join(lines).strip()
                
            if len(new_prompt) < 2000:
                print(f"Lỗi: Prompt sinh ra quá ngắn (chỉ có {len(new_prompt)} ký tự). Giữ nguyên prompt cũ để thử lại vòng sau...")
                continue
                
            with open(PROMPT_FILE, "w", encoding="utf-8") as f:
                f.write(new_prompt)
            print("Đã cập nhật file system_prompt_template.txt mới.")

    # Khôi phục best prompt nếu vòng cuối cùng tệ hơn
    print(f"\nKết thúc tối ưu. Điểm cao nhất đạt được: {best_score:.2f}")
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(best_prompt)

if __name__ == "__main__":
    asyncio.run(main())
