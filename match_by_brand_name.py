#!/usr/bin/env python3
"""
通过 Product Name 中的品牌名匹配 Merchant Name
"""
import requests
import json
import re

# Feishu credentials
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

def get_feishu_token():
    """Get Feishu tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]

def get_feishu_records(token):
    """Get all records from Feishu table"""
    records = []
    page_token = None
    
    while True:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") == 0:
            batch = result["data"]["items"]
            records.extend(batch)
            
            if not result["data"].get("has_more"):
                break
            page_token = result["data"].get("page_token")
        else:
            print(f"Error: {result}")
            break
    
    return records

def extract_brand_from_product_name(product_name):
    """Extract brand name from product name"""
    if not product_name:
        return None
    
    # Common patterns for brand names at the start of product names
    # Pattern 1: "Brand Name Product Description"
    # Pattern 2: "BrandName Product Description"
    
    # Try to extract first 1-3 words as potential brand
    words = product_name.split()
    
    # Common brand indicators
    brand_indicators = [':', '-', '|', 'by', 'from']
    
    for i, word in enumerate(words[:5]):  # Check first 5 words
        # If we hit an indicator, return words before it
        if any(indicator in word for indicator in brand_indicators):
            return ' '.join(words[:i])
        
        # If word is all caps (likely a brand)
        if word.isupper() and len(word) >= 2:
            return word
    
    # Return first 1-2 words as potential brand
    if len(words) >= 2:
        # Check if first word looks like a brand (capitalized)
        if words[0][0].isupper():
            return words[0]
    
    return words[0] if words else None

def load_merchants():
    """Load merchants from local data"""
    try:
        with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def find_merchant_by_brand(brand_name, merchants):
    """Find merchant matching brand name"""
    if not brand_name:
        return None
    
    brand_lower = brand_name.lower()
    
    for merchant in merchants:
        merchant_name = merchant.get('merchant_name', '').lower()
        
        # Exact match
        if brand_lower == merchant_name:
            return merchant
        
        # Brand is in merchant name
        if brand_lower in merchant_name:
            return merchant
        
        # Merchant name is in brand
        if merchant_name in brand_lower:
            return merchant
    
    return None

def main():
    print("=" * 70)
    print("通过品牌名匹配商品和商户")
    print("=" * 70)
    
    # Load Feishu records
    print("\n[1] 获取飞书表格数据...")
    token = get_feishu_token()
    records = get_feishu_records(token)
    print(f"  获取 {len(records)} 条记录")
    
    # Load merchants
    print("\n[2] 加载商户数据...")
    merchants = load_merchants()
    print(f"  加载 {len(merchants)} 个商户")
    
    # Match by brand name
    print("\n[3] 匹配品牌名...")
    matches = []
    unmatched = []
    
    for record in records:
        fields = record.get('fields', {})
        asin = fields.get('ASIN', '')
        product_name = fields.get('Product Name', '')
        
        # Extract brand from product name
        brand = extract_brand_from_product_name(product_name)
        
        if brand:
            # Find matching merchant
            merchant = find_merchant_by_brand(brand, merchants)
            
            if merchant:
                mid = merchant.get('mid') or merchant.get('id') or merchant.get('advert_id')
                merchant_name = merchant.get('merchant_name', 'Unknown')
                
                matches.append({
                    'asin': asin,
                    'product_name': product_name[:50],
                    'extracted_brand': brand,
                    'merchant_name': merchant_name,
                    'mid': mid
                })
                brand_safe = brand.encode('ascii', 'ignore').decode('ascii')
                merchant_safe = merchant_name.encode('ascii', 'ignore').decode('ascii')
                print(f"  [匹配] {brand_safe} -> {merchant_safe} (ASIN: {asin})")
            else:
                unmatched.append({
                    'asin': asin,
                    'product_name': product_name[:50],
                    'extracted_brand': brand
                })
    
    # Summary
    print("\n" + "=" * 70)
    print("匹配结果")
    print("=" * 70)
    print(f"总记录: {len(records)}")
    print(f"成功匹配: {len(matches)}")
    print(f"未匹配: {len(unmatched)}")
    
    if matches:
        print("\n成功匹配的商品:")
        for m in matches[:10]:
            brand = m['extracted_brand'].encode('ascii', 'ignore').decode('ascii')
            name = m['product_name'][:40].encode('ascii', 'ignore').decode('ascii')
            merchant = m['merchant_name'].encode('ascii', 'ignore').decode('ascii')
            print(f"  - {brand}: {name}... -> {merchant}")
    
    if unmatched:
        print("\n未匹配的商品 (前10):")
        for u in unmatched[:10]:
            brand = u['extracted_brand'].encode('ascii', 'ignore').decode('ascii')
            name = u['product_name'][:40].encode('ascii', 'ignore').decode('ascii')
            print(f"  - {brand}: {name}...")
    
    # Save results
    with open('output/brand_matches.json', 'w', encoding='utf-8') as f:
        json.dump({'matched': matches, 'unmatched': unmatched}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: output/brand_matches.json")

if __name__ == "__main__":
    main()
