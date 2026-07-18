import os
import sys

# Thêm đường dẫn để có thể import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_preprocessor import DataPreprocessor

def main():
    print("Khởi tạo DataPreprocessor nhưng bỏ qua bước tạo Embedding...")
    
    # Kế thừa và override phương thức build_vector_indices để nó không làm gì cả
    class SafeDataPreprocessor(DataPreprocessor):
        def build_vector_indices(self):
            print("[Push Data] Đã bỏ qua bước build_vector_indices. Dữ liệu đã được đẩy lên MongoDB.")
            pass

    # Chạy khởi tạo với mock_db.json / cleaned_data.json
    dp = SafeDataPreprocessor('.')
    
    print("Hoàn tất đẩy dữ liệu cơ bản lên MongoDB!")

if __name__ == '__main__':
    main()
