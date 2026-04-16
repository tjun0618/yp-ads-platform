#!/usr/bin/env python3
"""
修复版网页端抓取脚本 - 正确保存 merchant_id
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

MERCHANTS_FILE = OUTPUT_DIR / "merchants_data.json"
MAP_FILE = OUTPUT_DIR / "asin_merchant_map.json"

def load_merchants():
    """Load merchants data"""
    if MERCHANTS_FILE.exists():
        with open(MERCHANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_asin_map():
    """Load existing ASIN map"""
    if MAP_FILE.exists():
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_asin_map(asin_map):
    """Save ASIN map"""
    with open(MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(asin_map, f, indent=2)

def scrape_merchant_products(mid, merchant_name=""):
    """Scrape products from merchant page"""
    url = f"https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id={SITE_ID}"
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if "/index/login/login" in resp.text:
            return None, "LOGIN_REQUIRED"
        
        # Extract tracking token
        track_match = re.search(r"track=([a-f0-9]{16})", resp.text)
        track = track_match.group(1) if track_match else None
        
        # Extract ASIN to PID mapping
        products = []
        
        # Pattern: asin=XXXXXXXXXX with pid
        detail_pattern = r'asin=([A-Z0-9]{10})[^>]*>.*?pid=(\d+)'
        detail_matches = re.findall(detail_pattern, resp.text, re.DOTALL)
        
        for asin, pid in detail_matches:
            tracking_url = None
            if track:
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
    print("网页端抓取商户商品 - 修复版")
    print("=" * 70)
    
    # Load data
    merchants = load_merchants()
    asin_map = load_asin_map()
    
    print(f"\n商户总数: {len(merchants)}")
    print(f"当前 ASIN 映射: {len(asin_map)} 个")
    
    # Get already scraped merchant IDs (handle None values)
    scraped_mids = set()
    for info in asin_map.values():
        mid = info.get("merchant_id")
        if mid is not None:
            scraped_mids.add(mid)
    
    print(f"已抓取商户: {len(scraped_mids)} 个")
    
    # Filter merchants to scrape
    to_scrape = []
    for m in merchants:
        mid = m.get("merchant_id")
        if mid and mid not in scraped_mids:
            to_scrape.append(m)
    
    print(f"待抓取商户: {len(to_scrape)} 个")
    
    if not to_scrape:
        print("\n所有商户已抓取完成!")
        return
    
    # Scrape merchants
    print("\n开始抓取...")
    print("-" * 70)
    
    total_new = 0
    processed = 0
    batch_size = 100  # Process 100 merchants per run
    
    for i, merchant in enumerate(to_scrape[:batch_size]):
        mid = merchant.get("merchant_id")
        name = merchant.get("merchant_name", "Unknown")
        name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
        
        products, error = scrape_merchant_products(mid, name)
        
        if error == "LOGIN_REQUIRED":
            print(f"\n[{i+1}] Cookie expired, stopping")
            break
        
        if products:
            new_count = 0
            for p in products:
                if p["asin"] and p["asin"] not in asin_map:
                    asin_map[p["asin"]] = {
                        "merchant_id": mid,
                        "merchant_name": name,
                        "pid": p["pid"],
                        "tracking_url": p["tracking_url"],
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    new_count += 1
            
            total_new += new_count
            print(f"[{i+1:3d}/{batch_size}] {name_safe[:30]:30s} - {len(products):3d} products, {new_count:3d} new (MID: {mid})")
        else:
            print(f"[{i+1:3d}/{batch_size}] {name_safe[:30]:30s} - 0 products (MID: {mid})")
        
        processed += 1
        time.sleep(0.3)  # Small delay between requests
        
        # Save progress every 20 merchants
        if processed % 20 == 0:
            save_asin_map(asin_map)
            print(f"\n  [进度保存] 已处理 {processed} 个商户, ASIN 映射: {len(asin_map)} 个\n")
    
    # Final save
    save_asin_map(asin_map)
    
    print("-" * 70)
    print("\n抓取完成!")
    print(f"本次处理: {processed} 个商户")
    print(f"新增 ASIN 映射: {total_new} 个")
    print(f"累计 ASIN 映射: {len(asin_map)} 个")
    print(f"\n数据已保存: {MAP_FILE}")

if __name__ == "__main__":
    main()
