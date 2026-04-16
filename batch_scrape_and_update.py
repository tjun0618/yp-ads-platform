#!/usr/bin/env python3
"""
批量抓取商户商品并更新飞书表格
高效方案：先批量抓取，再批量更新
"""
import requests
import json
import time
import re
from pathlib import Path
from datetime import datetime

# Configuration
SITE_ID = "12002"
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
OUTPUT_DIR = Path("output")

# Feishu config
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_OFFERS = "tblMCbaHhP88sgeS"

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json().get("tenant_access_token")

def get_feishu_asins(token):
    """Get all ASINs from Feishu"""
    asins = {}
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OFFERS}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    has_more = True
    page_token = None
    
    while has_more:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") == 0:
            items = result["data"]["items"]
            for item in items:
                fields = item.get("fields", {})
                asin = fields.get("ASIN")
                if asin:
                    asins[asin] = item.get("record_id")
            
            has_more = result["data"].get("has_more", False)
            page_token = result["data"].get("page_token")
        else:
            break
    
    return asins

def update_feishu_batch(token, updates):
    """Batch update Feishu records"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OFFERS}/records/batch_update"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Feishu batch update limit is 500 records per request
    batch_size = 500
    updated = 0
    
    for i in range(0, len(updates), batch_size):
        batch = updates[i:i+batch_size]
        
        records = []
        for record_id, tracking_url in batch:
            records.append({
                "record_id": record_id,
                "fields": {
                    "Tracking URL": tracking_url
                }
            })
        
        data = {"records": records}
        resp = requests.post(url, headers=headers, json=data)
        result = resp.json()
        
        if result.get("code") == 0:
            updated += len(batch)
        else:
            print(f"  Batch update failed: {result.get('msg')}")
        
        time.sleep(0.5)
    
    return updated

def scrape_merchant_products(mid, merchant_name=""):
    """Scrape all products from merchant page"""
    url = f"https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id={SITE_ID}"
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if "/index/login/login" in resp.text:
            return None, "LOGIN_REQUIRED"
        
        # Extract tracking token
        track_match = re.search(r"track=([a-f0-9]{16})", resp.text)
        track = track_match.group(1) if track_match else None
        
        if not track:
            return [], None  # No tracking token means no products or not approved
        
        # Extract ASIN to PID mapping
        products = []
        
        # Pattern: asin=XXXXXXXXXX with pid
        detail_pattern = r'asin=([A-Z0-9]{10})[^>]*>.*?pid=(\d+)'
        detail_matches = re.findall(detail_pattern, resp.text, re.DOTALL)
        
        for asin, pid in detail_matches:
            tracking_url = f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
            
            products.append({
                "asin": asin,
                "pid": pid,
                "tracking_url": tracking_url,
                "merchant_id": mid,
                "merchant_name": merchant_name
            })
        
        return products, None
        
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("批量抓取投放链接并更新飞书")
    print("=" * 70)
    
    # Get Feishu token
    token = get_feishu_token()
    if not token:
        print("[ERROR] Failed to get Feishu token")
        return
    
    # Get target ASINs from Feishu
    print("\n[1/4] 获取飞书商品 ASIN...")
    target_asins = get_feishu_asins(token)
    print(f"  飞书表格共有 {len(target_asins)} 个商品")
    
    if not target_asins:
        print("  没有需要处理的商品")
        return
    
    # Load merchants
    print("\n[2/4] 加载商户数据...")
    merchants_file = OUTPUT_DIR / "merchants_data.json"
    if merchants_file.exists():
        with open(merchants_file, 'r', encoding='utf-8') as f:
            merchants = json.load(f)
    else:
        print("  [ERROR] 没有找到商户数据文件")
        return
    
    print(f"  本地商户数据: {len(merchants)} 个")
    
    # Scrape products from merchants
    print("\n[3/4] 批量抓取商户商品...")
    print("-" * 70)
    
    asin_to_tracking = {}  # ASIN -> Tracking URL
    found_asins = set()
    processed = 0
    
    # Process merchants until we find all target ASINs or exhaust merchants
    for i, merchant in enumerate(merchants):
        mid = merchant.get("merchant_id")
        name = merchant.get("merchant_name", "Unknown")
        name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
        
        if not mid:
            continue
        
        products, error = scrape_merchant_products(mid, name)
        
        if error == "LOGIN_REQUIRED":
            print(f"\n  Cookie expired! Stopping.")
            break
        
        if products:
            new_found = 0
            for p in products:
                asin = p["asin"]
                if asin in target_asins and asin not in found_asins:
                    asin_to_tracking[asin] = p["tracking_url"]
                    found_asins.add(asin)
                    new_found += 1
            
            if new_found > 0:
                print(f"[{i+1:4d}] {name_safe[:25]:25s} - Found {new_found} target ASINs ({len(found_asins)}/{len(target_asins)})")
        
        processed += 1
        
        # Progress update every 50 merchants
        if processed % 50 == 0:
            print(f"  ... processed {processed} merchants, found {len(found_asins)}/{len(target_asins)} ASINs")
        
        # Stop if we found all ASINs
        if len(found_asins) >= len(target_asins):
            print(f"\n  All {len(target_asins)} ASINs found!")
            break
        
        time.sleep(0.2)
    
    print("-" * 70)
    print(f"\n  抓取完成: 处理了 {processed} 个商户")
    print(f"  找到目标 ASIN: {len(found_asins)}/{len(target_asins)}")
    
    if not asin_to_tracking:
        print("\n  没有找到任何投放链接")
        return
    
    # Update Feishu
    print("\n[4/4] 更新飞书表格...")
    
    updates = []
    for asin, tracking_url in asin_to_tracking.items():
        record_id = target_asins.get(asin)
        if record_id and tracking_url:
            updates.append((record_id, tracking_url))
    
    print(f"  需要更新: {len(updates)} 条记录")
    
    if updates:
        updated = update_feishu_batch(token, updates)
        print(f"  成功更新: {updated} 条记录")
    
    # Summary
    print("\n" + "=" * 70)
    print("完成!")
    print("=" * 70)
    print(f"\n统计:")
    print(f"  飞书商品总数: {len(target_asins)}")
    print(f"  找到投放链接: {len(asin_to_tracking)}")
    print(f"  成功更新: {len(updates)}")
    print(f"  未找到: {len(target_asins) - len(asin_to_tracking)}")

if __name__ == "__main__":
    main()
