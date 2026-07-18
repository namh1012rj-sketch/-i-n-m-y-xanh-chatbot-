import os
import json
import inspect
import asyncio
from openai import OpenAI
from query_tools import AsyncQueryEngine
from dotenv import load_dotenv

load_dotenv()

FPT_API_KEY = os.environ.get("FPT_API_KEY")
if not FPT_API_KEY:
    print("WARNING: Chưa có FPT_API_KEY trong file .env.")

# Khởi tạo OpenAI client trỏ đến server FPT
client = OpenAI(
    api_key=FPT_API_KEY,
    base_url="https://mkp-api.fptcloud.com/v1"
)

engine = AsyncQueryEngine('cleaned_data.json')

async def tool_query_products(category: str = "", budget: float = 0.0, raw_query: str = "") -> list:
    """[CÔNG CỤ TÌM KIẾM CHÍNH - DÙNG TRONG 90% TRƯỜNG HỢP] Dùng công cụ này khi khách có nhiều yêu cầu kết hợp (thương hiệu + ngân sách + tính năng + nhu cầu). Gộp tất cả yêu cầu mềm, thương hiệu, tính năng vào tham số raw_query."""
    return await engine.tool_query_products(category, budget, raw_query=raw_query)

async def tool_query_similar_products(product_id: str, top_k: int = 3) -> list:
    """Tìm các sản phẩm thay thế gần giống nhất."""
    return await engine.tool_query_similar_products(product_id, top_k)

async def tool_query_faq(raw_query: str) -> list:
    """Tra cứu câu hỏi thường gặp về chính sách."""
    return await engine.tool_query_faq(raw_query)

async def tool_get_product_details(product_id: str) -> dict:
    """Lấy thông tin chi tiết (Specs) bằng ID/SKU."""
    return await engine.tool_get_product_details(product_id)

async def tool_search_product_by_name(query_name: str) -> list:
    """Tìm kiếm bằng đích danh tên (vd: 'iPhone 15', 'SingPC'). Dùng xử lý Link URL."""
    return await engine.tool_search_product_by_name(query_name)

async def tool_query_products_by_brand(category: str, brand: str) -> list:
    """Lọc danh sách theo Thương hiệu."""
    return await engine.tool_query_products_by_brand(category, brand)

async def tool_query_products_by_spec_range(category: str, spec_name: str, min_val: float, max_val: float) -> list:
    """Lọc sản phẩm theo khoảng thông số (vd: room_area từ 15-20)."""
    return await engine.tool_query_products_by_spec_range(category, spec_name, min_val, max_val)

async def tool_query_by_features(category: str, features: list) -> list:
    """Lọc theo danh sách tính năng ('Inverter', 'Lọc không khí')."""
    return await engine.tool_query_by_features(category, features)

async def tool_sort_products_by_price(category: str, sort_order: str = "asc", limit: int = 3) -> list:
    """Lọc theo Giá (asc/desc)."""
    return await engine.tool_sort_products_by_price(category, sort_order, limit)

async def tool_query_discount_products(category: str, limit: int = 3) -> list:
    """Tìm sản phẩm đang giảm giá sâu nhất."""
    return await engine.tool_query_discount_products(category, limit)

async def tool_query_best_promotions(category: str) -> list:
    """Tìm sản phẩm có khuyến mãi/quà tặng tốt nhất."""
    return await engine.tool_query_best_promotions(category)

async def tool_query_out_of_stock() -> list:
    """Kiểm tra sản phẩm hết hàng."""
    return await engine.tool_query_out_of_stock()

async def tool_search_policy_documents(query: str) -> list:
    """Tra cứu văn bản chính sách/bảo hành chi tiết."""
    return await engine.tool_search_policy_documents(query)

ALL_TOOLS = [
    tool_query_products, tool_query_similar_products, tool_query_faq, 
    tool_get_product_details, tool_search_product_by_name, tool_query_products_by_brand,
    tool_query_products_by_spec_range, tool_query_by_features, tool_sort_products_by_price,
    tool_query_discount_products, tool_query_best_promotions, tool_query_out_of_stock,
    tool_search_policy_documents
]

PARAM_DESCRIPTIONS = {
    "category": "BẮT BUỘC. Danh mục sản phẩm chung (vd: 'Máy lạnh', 'Tủ lạnh', 'Tivi', 'Laptop', 'Điện thoại', 'Máy tính để bàn'). KHÔNG điền thương hiệu, tính năng hay nhu cầu vào đây.",
    "budget": "Ngân sách tối đa của khách (VNĐ, vd: 15 triệu = 15000000). Điền 0 nếu khách không đề cập ngân sách.",
    "raw_query": "QUAN TRỌNG: Câu truy vấn để tìm kiếm Vector. Hãy gộp TẤT CẢ thương hiệu, tính năng, và nhu cầu mềm của khách vào đây (vd: 'Tủ lạnh side by side Samsung cho 5 người', 'Laptop SingPC chơi game').",
    "brand": "Tên thương hiệu (vd: 'Samsung', 'SingPC'). CHỈ dùng cho tool lọc theo brand thuần túy.",
    "features": "Danh sách tính năng (vd: ['Inverter']). CHỈ dùng cho tool lọc theo tính năng.",
    "product_id": "Mã ID của sản phẩm.",
    "query_name": "Tên đích danh của một model (vd: 'iPhone 15 Pro Max 256GB').",
    "spec_name": "Tên thông số kỹ thuật muốn lọc (vd: 'room_area', 'capacity').",
    "min_val": "Giá trị nhỏ nhất.",
    "max_val": "Giá trị lớn nhất.",
    "sort_order": "Thứ tự ('asc' = rẻ nhất, 'desc' = đắt nhất).",
    "limit": "Số lượng kết quả trả về."
}

def _get_openai_tools_schema(tools_list):
    """Tự động sinh OpenAI Tool Schema từ Python functions"""
    tools_schema = []
    for func in tools_list:
        sig = inspect.signature(func)
        schema = {
            "type": "function",
            "function": {
                "name": func.__name__,
                "description": func.__doc__ or "",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        }
        for name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int: param_type = "integer"
            elif param.annotation == float: param_type = "number"
            elif param.annotation == list or str(param.annotation).startswith("list"): param_type = "array"
            elif param.annotation == bool: param_type = "boolean"
            
            prop = {"type": param_type}
            if name in PARAM_DESCRIPTIONS:
                prop["description"] = PARAM_DESCRIPTIONS[name]
                
            if param_type == "array":
                prop["items"] = {"type": "string"}
                
            schema["function"]["parameters"]["properties"][name] = prop
            
            if param.default == inspect.Parameter.empty:
                schema["function"]["parameters"]["required"].append(name)
        
        tools_schema.append(schema)
    return tools_schema

OPENAI_TOOLS = _get_openai_tools_schema(ALL_TOOLS)

class DMXAgent:
    def __init__(self):
        try:
            with open('system_prompt_template.txt', 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except:
            system_prompt = "Bạn là AI."
            
        self.model_name = "DeepSeek-V4-Flash"
        self.history = [{"role": "system", "content": system_prompt}]
        self.max_history_len = 6 # Giới hạn bộ nhớ 3 lượt chat gần nhất

    async def send_message_stream(self, user_text: str):
        # 1. Truncate history (Sliding Window an toàn với Tool calls)
        self.history.append({"role": "user", "content": user_text})
        
        # Đếm số lượng message (không tính system prompt). Xóa dần từ cũ đến mới.
        # Lưu ý: Không được cắt rời 'tool_call' và 'tool' message
        while len(self.history) > self.max_history_len + 1: # +1 cho system prompt
            # Tìm vị trí an toàn để xóa
            if self.history[1]["role"] == "user" or self.history[1]["role"] == "assistant":
                if "tool_calls" not in self.history[1]:
                    self.history.pop(1)
                    continue
            # Nếu tin nhắn thứ 1 có gọi tool, ta phải xóa nguyên cụm tool call
            self.history.pop(1)

        # 2. ReAct Loop
        iterations = 0
        while iterations < 5:
            try:
                # LLM API call
                response_stream = client.chat.completions.create(
                    model=self.model_name,
                    messages=self.history,
                    tools=OPENAI_TOOLS,
                    stream=True,
                    temperature=0.3,
                    max_tokens=800
                )
            except Exception as e:
                yield f"\n[Lỗi kết nối FPT API: {str(e)}]\n"
                break
            
            full_text = ""
            tool_calls_accumulator = {}
            
            for chunk in response_stream:
                if len(chunk.choices) == 0:
                    continue
                delta = chunk.choices[0].delta
                
                # Stream chữ ra Frontend
                if delta.content:
                    full_text += delta.content
                    yield delta.content
                    
                # Góp nhặt thông tin Tool Call
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.index not in tool_calls_accumulator:
                            tool_calls_accumulator[tc.index] = {
                                "id": tc.id,
                                "type": "function",
                                "function": {"name": tc.function.name, "arguments": tc.function.arguments or ""}
                            }
                        else:
                            if tc.function.arguments:
                                tool_calls_accumulator[tc.index]["function"]["arguments"] += tc.function.arguments

            if tool_calls_accumulator:
                # LLM đã gọi tool
                tool_calls = list(tool_calls_accumulator.values())
                
                # Lưu vào history
                assistant_msg = {"role": "assistant", "tool_calls": tool_calls}
                if full_text:
                    assistant_msg["content"] = full_text
                self.history.append(assistant_msg)
                
                func_map = {f.__name__: f for f in ALL_TOOLS}
                tasks = []
                valid_tcs = []
                
                for tc in tool_calls:
                    name = tc["function"]["name"]
                    args_str = tc["function"]["arguments"]
                    try:
                        args = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        args = {}
                        
                    if name in func_map:
                        if iterations >= 2 and name.startswith("tool_"):
                            yield f"\n[Hệ thống ép dừng lặp Tool ({name})]\n"
                            
                            # Tự động chèn câu trả lời cứu vãn và ép ngắt luồng hoàn toàn
                            fallback_msg = "\nDạ, hiện tại hệ thống bên em không tìm thấy mẫu sản phẩm nào đáp ứng đúng hoàn toàn tiêu chí (hoặc mức giá) vừa rồi. Anh/chị có muốn tham khảo sang các mẫu khác hoặc điều chỉnh lại ngân sách không ạ?\n"
                            yield fallback_msg
                            self.history.append({"role": "assistant", "content": fallback_msg})
                            
                            return # Kết thúc generator ngay lập tức
                            
                        else:
                            yield f"\n[Agent đang tra cứu Database ({name})]\n"
                            tasks.append(func_map[name](**args))
                            valid_tcs.append(tc)
                    else:
                        async def dummy_err(): return {"error": "Tool not found"}
                        tasks.append(dummy_err())
                        valid_tcs.append(tc)
                        
                # Thực thi song song tất cả các tool calls
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for tc, result in zip(valid_tcs, results):
                        if isinstance(result, Exception):
                            result = {"error": str(result)}
                        # Lưu kết quả về LLM
                        self.history.append({
                            "tool_call_id": tc["id"],
                            "role": "tool",
                            "name": tc["function"]["name"],
                            "content": json.dumps({"result": result}, ensure_ascii=False, default=str)
                        })
                iterations += 1
            else:
                # Trả lời bình thường bằng chữ
                self.history.append({"role": "assistant", "content": full_text})
                break
                
        if iterations >= 5:
            msg = "\n[Hệ thống quá tải, tự ngắt Tool để đảm bảo độ trễ < 5s]"
            yield msg
            self.history.append({"role": "assistant", "content": msg})

if __name__ == "__main__":
    pass
