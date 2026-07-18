import sys
import time
import asyncio
from query_tools import AsyncQueryEngine

log_file = open("tool_execution.log", "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_file.write(msg + "\n")

def print_result(title, result, duration):
    log(f"\n{'='*50}\n[TEST] {title} (Time: {duration:.4f}s)")
    if not result:
        log("-> Trống (Không tìm thấy kết quả)")
    elif isinstance(result, list):
        log(f"-> Số lượng kết quả: {len(result)}")
        for i, r in enumerate(result[:3]): # In tối đa 3 kết quả đầu
            if isinstance(r, tuple):
                item, score = r
                name = item.get('name') or item.get('question') or 'Unknown'
                log(f"  {i+1}. Tên/Câu hỏi: {name} | Score: {score:.4f}")
            else:
                name = r.get('name', 'Unknown')
                price = r.get('sale_price', 'N/A')
                log(f"  {i+1}. Tên: {name} | Giá: {price}")
    elif isinstance(result, dict):
        if "new_stock" in result:
            log(f"-> Cập nhật kho: {result}")
        else:
            name = result.get('name', 'Unknown')
            price = result.get('sale_price', 'N/A')
            log(f"-> Tên: {name} | Giá: {price}")
    else:
        log(f"-> {result}")

async def run_test(title, func, *args, **kwargs):
    t0 = time.time()
    res = await func(*args, **kwargs)
    t1 = time.time()
    print_result(title, res, t1 - t0)

async def main():
    log("Khởi tạo AsyncQueryEngine (Chế độ MongoDB Async)...")
    t_start = time.time()
    engine = AsyncQueryEngine('cleaned_data.json')
    log(f"Khởi tạo xong trong {time.time() - t_start:.4f}s")
    
    sample_product = engine.products[0] if engine.products else {}
    sample_sku = sample_product.get("sku", str(sample_product.get("_id", "123")))
    sample_category = sample_product.get("category", "Điện thoại")
    sample_brand = sample_product.get("brand", "Samsung")

    log(f"Sử dụng sản phẩm mẫu: {sample_product.get('name')} (SKU: {sample_sku}) | Nhóm: {sample_category}")

    total_t0 = time.time()
    
    await run_test("1. tool_query_products (Hybrid Search)", engine.tool_query_products, category=sample_category, budget=20000000, raw_query="chạy êm tiết kiệm điện")
    await run_test("2. tool_query_similar_products (Vector Similar)", engine.tool_query_similar_products, product_id=sample_sku, top_k=2)
    await run_test("3. tool_query_faq (Chính sách/Bảo hành)", engine.tool_query_faq, raw_query="Chính sách bảo hành như thế nào")
    await run_test("4. tool_get_product_details (Tìm theo ID)", engine.tool_get_product_details, product_id=sample_sku)
    await run_test("5. tool_search_product_by_name (Tìm bằng tên gốc)", engine.tool_search_product_by_name, query_name=sample_product.get("name", "Test").split()[0])
    await run_test("6. tool_query_products_by_brand (Tìm bằng tên Hãng)", engine.tool_query_products_by_brand, category=sample_category, brand=sample_brand)
    await run_test("7. tool_query_products_by_spec_range (Diện tích phòng 15-20)", engine.tool_query_products_by_spec_range, category="Máy lạnh", spec_name="room_area", min_val=15, max_val=20)
    await run_test("8. tool_query_by_features (Tính năng: Inverter)", engine.tool_query_by_features, category="Máy lạnh", features=["Inverter"])
    await run_test("9. tool_sort_products_by_price (Rẻ nhất ASC)", engine.tool_sort_products_by_price, category=sample_category, sort_order="asc", limit=3)
    await run_test("10. tool_query_discount_products (Giảm giá sâu nhất)", engine.tool_query_discount_products, category=sample_category, limit=3)
    await run_test("11. tool_query_best_promotions (Khuyến mãi khủng)", engine.tool_query_best_promotions, category=sample_category)
    await run_test("12. tool_query_out_of_stock (Tìm hàng hết kho)", engine.tool_query_out_of_stock)
    await run_test("13. tool_search_policy_documents (Chính sách văn bản dài)", engine.tool_search_policy_documents, query="bảo hành iPhone khui hộp thế nào")
    
    total_t1 = time.time()
    log(f"\n--- HOÀN TẤT BỘ TEST TỔNG THỜI GIAN: {total_t1 - total_t0:.4f}s ---")
    log_file.close()

if __name__ == '__main__':
    asyncio.run(main())
