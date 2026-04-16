#!/usr/bin/env python3
"""
使用扩展的商户数据进行品牌匹配
"""
import requests
import json
import re
from pathlib import Path

# Feishu credentials
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]

def get_feishu_records(token):
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
            break
    
    return records

def load_all_merchants():
    """Load merchants from all available sources"""
    merchants = []
    
    # Try multiple files
    files = [
        'output/merchants_extended.json',
        'output/merchants_data.json',
        'output/all_merchants_5000.json'
    ]
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)
                merchants.extend(data)
                print(f"  从 {f} 加载 {len(data)} 个商户")
        except:
            pass
    
    # Remove duplicates by mid
    seen = set()
    unique = []
    for m in merchants:
        mid = m.get('mid') or m.get('id') or m.get('advert_id')
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)
    
    return unique

def extract_brand_candidates(product_name):
    """Extract multiple brand candidates from product name"""
    if not product_name:
        return []
    
    candidates = []
    words = product_name.split()
    
    # Candidate 1: First word (if capitalized)
    if words and words[0][0].isupper():
        candidates.append(words[0])
    
    # Candidate 2: First 2 words
    if len(words) >= 2:
        candidates.append(f"{words[0]} {words[1]}")
    
    # Candidate 3: All caps words (likely brands)
    for word in words[:5]:
        clean = re.sub(r'[^\w]', '', word)
        if clean.isupper() and len(clean) >= 2:
            candidates.append(clean)
    
    # Candidate 4: Words before common separators
    for i, word in enumerate(words[:5]):
        if any(sep in word for sep in [':', '-', '|', 'by']):
            candidates.append(' '.join(words[:i]))
            break
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in candidates:
        c_clean = c.strip()
        if c_clean and c_clean.lower() not in seen:
            seen.add(c_clean.lower())
            unique.append(c_clean)
    
    return unique

def find_best_merchant_match(candidates, merchants):
    """Find best matching merchant from candidates"""
    for candidate in candidates:
        candidate_lower = candidate.lower()
        
        for merchant in merchants:
            merchant_name = merchant.get('merchant_name', '').lower()
            
            # Exact match
            if candidate_lower == merchant_name:
                return merchant, candidate, "exact"
            
            # Candidate in merchant name
            if candidate_lower in merchant_name:
                return merchant, candidate, "contains"
            
            # Merchant name in candidate
            if merchant_name in candidate_lower:
                return merchant, candidate, "reverse"
    
    return None, None, None

def main():
    print("=" * 70)
    print("使用扩展商户数据进行品牌匹配")
    print("=" * 70)
    
    # Load Feishu records
    print("\n[1] 获取飞书表格数据...")
    token = get_feishu_token()
    records = get_feishu_records(token)
    print(f"  获取 {len(records)} 条记录")
    
    # Load merchants
    print("\n[2] 加载商户数据...")
    merchants = load_all_merchants()
    print(f"  共加载 {len(merchants)} 个唯一商户")
    
    # Match
    print("\n[3] 匹配品牌名...")
    matches = []
    unmatched = []
    
    for record in records:
        fields = record.get('fields', {})
        asin = fields.get('ASIN', '')
        product_name = fields.get('Product Name', '')
        
        # Extract brand candidates
        candidates = extract_brand_candidates(product_name)
        
        if candidates:
            merchant, matched_brand, match_type = find_best_merchant_match(candidates, merchants)
            
            if merchant:
                mid = merchant.get('mid') or merchant.get('id') or merchant.get('advert_id')
                merchant_name = merchant.get('merchant_name', 'Unknown')
                
                matches.append({
                    'asin': asin,
                    'product_name': product_name,
                    'matched_brand': matched_brand,
                    'match_type': match_type,
                    'merchant_name': merchant_name,
                    'mid': mid
                })
            else:
                unmatched.append({
                    'asin': asin,
                    'product_name': product_name,
                    'candidates': candidates
                })
        else:
            unmatched.append({
                'asin': asin,
                'product_name': product_name,
                'candidates': []
            })
    
    # Summary
    print("\n" + "=" * 70)
    print("匹配结果")
    print("=" * 70)
    print(f"总记录: {len(records)}")
    print(f"成功匹配: {len(matches)}")
    print(f"未匹配: {len(unmatched)}")
    
    if matches:
        print("\n成功匹配的商品 (前20):")
        for m in matches[:20]:
            brand = m['matched_brand'][:20].encode('ascii', 'ignore').decode('ascii')
            name = m['product_name'][:35].encode('ascii', 'ignore').decode('ascii')
            merchant = m['merchant_name'][:25].encode('ascii', 'ignore').decode('ascii')
            print(f"  [{m['match_type'][:3]}] {brand} -> {merchant}")
            print(f"       {name}...")
    
    if unmatched:
        print("\n未匹配的商品 (前10):")
        for u in unmatched[:10]:
            name = u['product_name'][:50].encode('ascii', 'ignore').decode('ascii')
            cands = ', '.join(u['candidates'][:3]).encode('ascii', 'ignore').decode('ascii')
            print(f"  - {name}...")
            print(f"    候选: {cands}")
    
    # Save
    with open('output/brand_match_results.json', 'w', encoding='utf-8') as f:
        json.dump({'matched': matches, 'unmatched': unmatched}, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: output/brand_match_results.json")

if __name__ == "__main__":
    main()
