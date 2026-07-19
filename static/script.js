// Tạo một session ID ngẫu nhiên cho mỗi phiên người dùng
const sessionId = Math.random().toString(36).substring(2, 15);

const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

// Cuộn xuống cuối
function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

// Chuyển markdown cơ bản (in đậm, danh sách) thành HTML
function parseMarkdown(text) {
    let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

function appendMessage(content, sender) {
    const msgDiv = document.createElement('div');
    msgDiv.classList.add('message');
    msgDiv.classList.add(sender === 'ai' ? 'ai-message' : 'user-message');
    
    const contentDiv = document.createElement('div');
    contentDiv.classList.add('message-content');
    
    // Nếu là AI thì render markdown (đơn giản), User thì render text thường
    if (sender === 'ai') {
        contentDiv.innerHTML = content;
    } else {
        contentDiv.textContent = content;
    }
    
    msgDiv.appendChild(contentDiv);
    chatBox.appendChild(msgDiv);
    scrollToBottom();
    
    return contentDiv; // Trả về để có thể update (khi stream)
}

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;
    
    // Disable input while generating
    userInput.value = '';
    userInput.disabled = true;
    sendBtn.disabled = true;
    
    // Thêm tin nhắn user
    appendMessage(text, 'user');
    
    // Tạo sẵn bong bóng chat cho AI
    const aiContentDiv = appendMessage('<span style="color:#9ca3af">Đang suy nghĩ...</span>', 'ai');
    let fullResponse = "";
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: text
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Đọc stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        
        aiContentDiv.innerHTML = ""; // Xóa chữ Đang suy nghĩ
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            // value là Uint8Array, decode thành string
            const chunk = decoder.decode(value, { stream: true });
            
            // Format SSE từ server là: data: {text}\n\n
            const lines = chunk.split('\n');
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') continue; // Nếu server gửi [DONE]
                    
                    fullResponse += data;
                    // Tạm thời render thẳng, có thể replace \n thành <br>
                    aiContentDiv.innerHTML = parseMarkdown(fullResponse);
                    scrollToBottom();
                }
            }
        }
    } catch (error) {
        console.error('Error fetching stream:', error);
        aiContentDiv.innerHTML = '<span style="color:red">Xin lỗi, có lỗi xảy ra khi kết nối đến máy chủ.</span>';
    } finally {
        userInput.disabled = false;
        sendBtn.disabled = false;
        userInput.focus();
        scrollToBottom();
    }
}

// Events
sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
