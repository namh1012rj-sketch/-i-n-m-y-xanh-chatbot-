import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict

# Import class DMXAgent đã được viết sẵn
from llm_agent import DMXAgent

app = FastAPI(title="Điện Máy Xanh AI Agent API")

# Cấu hình CORS để Frontend (React/Vue/HTML) gọi được API mà không bị lỗi chéo domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Trong thực tế nên đổi thành domain cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# [CÁCH 1]: Quản lý Session In-Memory
# Dictionary lưu trữ các object Agent, key là session_id
# Lưu ý: Cách này sẽ mất session nếu restart server.
active_sessions: Dict[str, DMXAgent] = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    # 1. Khởi tạo Agent mới nếu session_id chưa tồn tại
    if req.session_id not in active_sessions:
        active_sessions[req.session_id] = DMXAgent()
    
    agent = active_sessions[req.session_id]

    # 2. Hàm Generator bọc lại hàm send_message_stream của Agent
    async def event_stream():
        # Duyệt qua các chunk text được sinh ra từ Agent
        async for chunk in agent.send_message_stream(req.message):
            # Format trả về theo chuẩn Server-Sent Events (SSE) để frontend dễ xử lý stream
            # Xử lý an toàn nếu chunk có chứa ký tự xuống dòng
            chunk_safe = chunk.replace('\n', '\\n')
            yield f"data: {chunk_safe}\n\n"

    # 3. Trả về StreamingResponse với chuẩn Server-Sent Events
    return StreamingResponse(event_stream(), media_type="text/event-stream")
