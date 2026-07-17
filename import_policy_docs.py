import os
import re
from data_preprocessor import DataPreprocessor

def chunk_markdown(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Chia văn bản theo đoạn văn (paragraph) thay vì chia tùy tiện
    paragraphs = content.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Nối các đoạn văn lại với nhau cho đến khi đạt khoảng 800 ký tự (đủ ngữ cảnh)
        if len(current_chunk) + len(p) < 800:
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = p + "\n\n"
            
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def main():
    print("Khởi tạo DataPreprocessor...")
    preprocessor = DataPreprocessor('cleaned_data.json')
    if preprocessor.use_mock_db:
        print("Lỗi: Không kết nối được MongoDB. Vui lòng kiểm tra file .env")
        return
        
    db = preprocessor.db
    policy_col = db["policy_documents"]
    
    # Xóa dữ liệu cũ (nếu có) để import mới hoàn toàn
    policy_col.delete_many({}) 
    
    data_dir = 'data_new'
    md_files = [f for f in os.listdir(data_dir) if f.endswith('.md')]
    
    documents_to_insert = []
    
    print(f"Tìm thấy {len(md_files)} file Chính sách (Markdown).")
    for md_file in md_files:
        filepath = os.path.join(data_dir, md_file)
        chunks = chunk_markdown(filepath)
        
        print(f"-> File {md_file}: Băm thành {len(chunks)} chunks.")
        
        # Nhúng Vector cho từng chunk
        embeddings = preprocessor._call_embedding_api(chunks)
        
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            documents_to_insert.append({
                "source_file": md_file,
                "chunk_index": i,
                "content": chunk_text,
                "embedding": embedding
            })
            
    if documents_to_insert:
        policy_col.insert_many(documents_to_insert)
        print(f"\n[THÀNH CÔNG] Đã lưu {len(documents_to_insert)} chunks tài liệu + Vector vào bảng 'policy_documents' trên Atlas!")
    else:
        print("Không có dữ liệu để lưu.")

if __name__ == '__main__':
    main()
