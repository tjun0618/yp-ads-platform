#!/usr/bin/env python3
"""
增量抓取商户商品信息，建立 ASIN -> Merchant 映射
与 yp_auto_collect.py 配合，在采集商户后运行
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
STATE_FILE = OUTPUT_DIR / "scrape_state.json"
MAP_FILE = OUTPUT_DIR / "asin_merchant_map.json"

def load_state():
    """Load scraping state"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "last_merchant_index": 0,
        "total_scraped": 0,
        "asin_count": 0
    }

def save_state(state):
    """Save scraping state"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_merchants():
    """Load merchants from local data"""
    try:
        with open(OUTPUT_DIR / "merchants_data.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
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
        json.dump(asin_map, f, ensure_ascii=False, indent=2)

def scrape_merchant_products(mid, name):
    """Scrape products from merchant page"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": SITE_ID}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        # Check login
        if "/index/login/login" in html:
            return None, "LOGIN_REQUIRED"
        
        # Extract ASINs and tracking links
        asins = re.findall(r'[A-Z0-9]{10}', html)
        
        # Extract tracking links with PID
        tracking_pattern = re.compile(r"track=([a-f0-9]+)&amp;pid=(\d+)")
        tracking_matches = tracking_pattern.findall(html)
        
        # Build product list
        products = []
        for i, (track, pid) in enumerate(tracking_matches):
            # Try to find ASIN for this product (approximate matching by position)
            asin = asins[i] if i < len(asins) else None
            
            products.append({
                "pid": pid,
                "track": track,
                "asin": asin,
                "tracking_url": f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
            })
        
        return {
            "mid": mid,
            "name": name,
            "products": products,
            "product_count": len(products)
        }, "OK"
        
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("增量抓取商户商品信息")
    print("=" * 70)
    
    # Load state and data
    state = load_state()
    merchants = load_merchants()
    asin_map = load_asin_map()
    
    print(f"\n已抓取商户: {state['total_scraped']}")
    print(f"已建立映射: {len(asin_map)} 个 ASIN")
    print(f"本地商户数据: {len(merchants)} 个")
    
    if not merchants:
        print("\n[错误] 没有找到商户数据，请先运行 yp_auto_collect.py 采集商户")
        return
    
    # Calculate how many to scrape this run
    start_index = state.get("last_merchant_index", 0)
    batch_size = 200  # Scrape 200 merchants per run
    end_index = min(start_index + batch_size, len(merchants))
    
    print(f"\n本次抓取: 第 {start_index+1} - {end_index} 个商户 (共 {len(merchants)})")
    print("=" * 70)
    
    new_asins = 0
    login_expired = False
    
    for i in range(start_index, end_index):
        merchant = merchants[i]
        mid = merchant.get("merchant_id") or merchant.get("mid") or merchant.get("id") or merchant.get("advert_id")
        name = merchant.get("merchant_name") or merchant.get("name", "Unknown")
        
        if not mid:
            continue
        
        name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
        print(f"\n[{i+1}/{len(merchants)}] {name_safe} (MID: {mid})")
        
        result, status = scrape_merchant_products(mid, name)
        
        if status == "LOGIN_REQUIRED":
            print("  [错误] Cookie已过期，请更新 PHPSESSID")
            login_expired = True
            break
        elif status == "OK" and result:
            print(f"  找到 {result['product_count']} 个产品")
            
            # Add to ASIN map
            for product in result["products"]:
                asin = product.get("asin")
                if asin and asin not in asin_map:
                    asin_map[asin] = {
                        "mid": mid,
                        "merchant_name": name,
                        "pid": product["pid"],
                        "track": product["track"],
                        "tracking_url": product["tracking_url"]
                    }
                    new_asins += 1
            
            state["total_scraped"] += 1
        else:
            print(f"  [失败] {status}")
        
        # Delay to avoid rate limiting
        time.sleep(0.5)
    
    # Update state
    state["last_merchant_index"] = end_index if not login_expired else start_index
    save_state(state)
    save_asin_map(asin_map)
    
    # Summary
    print("\n" + "=" * 70)
    print("抓取完成")
    print("=" * 70)
    print(f"本次处理: {end_index - start_index} 个商户")
    print(f"新增 ASIN 映射: {new_asins}")
    print(f"累计 ASIN 映射: {len(asin_map)}")
    print(f"下次从第 {state['last_merchant_index']+1} 个商户继续")
    
    if login_expired:
        print("\n[提示] Cookie已过期，请从浏览器获取新的 PHPSESSID 并更新脚本")
    else:
        print(f"\n映射数据已保存: {MAP_FILE}")

if __name__ == "__main__":
    main()
