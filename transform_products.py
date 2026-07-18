import json
import os

def main():
    input_file = "products_detail.json"
    output_file = "cleaned_data.json"
    
    print(f"Reading from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total input items: {len(data)}")
    
    # Check if cleaned_data.json exists to preserve its structure if it's a dict
    cleaned_wrapper = {"products": [], "faq": [], "scenarios": []}
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            try:
                old_data = json.load(f)
                if isinstance(old_data, dict):
                    cleaned_wrapper = old_data
            except Exception as e:
                print(f"Warning: could not read old {output_file}: {e}")

    new_products = []
    
    for item in data:
        original_price = item.get("Giá gốc")
        if original_price in (None, ""):
            original_price = 0
            
        sale_price = item.get("Giá khuyến mãi")
        if sale_price in (None, ""):
            sale_price = original_price

        try:
            original_price = float(original_price)
        except ValueError:
            original_price = 0.0

        try:
            sale_price = float(sale_price)
        except ValueError:
            sale_price = original_price
            
        new_prod = {
            "category": item.get("category_name", ""),
            "brand": item.get("brand", ""),
            "name": item.get("tên sản phẩm", ""),
            "original_price": original_price,
            "sale_price": sale_price,
            "promotion": item.get("promotion", ""),
            "specs": item.get("spec_product", {})
        }
        # Copy productid if needed, data_preprocessor doesn't strictly need it but good to have
        if "product_id" in item:
            new_prod["productidweb"] = item["product_id"]
        elif "productcode" in item:
            new_prod["sku"] = item["productcode"]

        new_products.append(new_prod)
        
    if isinstance(cleaned_wrapper, dict) and "products" in cleaned_wrapper:
        cleaned_wrapper["products"] = new_products
        output_data = cleaned_wrapper
    else:
        output_data = {"products": new_products}
        
    print(f"Writing {len(new_products)} products to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print("Done!")

if __name__ == "__main__":
    main()
