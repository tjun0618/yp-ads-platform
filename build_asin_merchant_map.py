#!/usr/bin/env python3
"""
建立 ASIN -> Merchant ID 映射数据库
通过批量抓取商户页面获取商品信息
"""
import requests
import json
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Target ASINs from Feishu
TARGET_ASINS = set(["B0GDXPNRD4", "B0GL7QP2SF", "B0C545BTQN", "B0FNWMSTR8", "B0BR6DL25V", 
                "B0FF4PXHRN", "B0GHSXZ9Q2", "B0GHSW4VWY", "B0BH9GBCFB", "B0CQZ2HQBN"])

def get_merchants_batch(page, limit=100):
    """Fetch merchants from API"""
    url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    headers = {"token": TOKEN}
    params = {"site_id": SITE_ID, "page": page, "limit": limit}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()
        
        if data.get("status") == "SUCCESS":
            merchants = data.get("data", {}).get("Data") or data.get("data", {}).get("data", [])
            return merchants
    except Exception as e:
        print(f"  Error fetching page {page}: {e}")
    
    return []

def scrape_merchant_page(mid, name):
    """Scrape a merchant page for ASINs and tracking links"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": SITE_ID}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        # Check login
        if "/index/login/login" in html:
            return None, "LOGIN_REQUIRED"
        
        # Extract all ASINs
        asins = set(re.findall(r'[A-Z0-9]{10}', html))
        
        # Extract tracking links with their PIDs
        tracking_pattern = re.compile(r"track=([a-f0-9]+)&amp;pid=(\d+)")
        tracking_matches = tracking_pattern.findall(html)
        
        # Build tracking links
        tracking_links = {}
        for track, pid in tracking_matches:
            tracking_links[pid] = f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
        
        # Check for target ASINs
        found_asins = asins.intersection(TARGET_ASINS)
        
        return {
            "mid": mid,
            "name": name,
            "asins": list(asins),
            "tracking_links": tracking_links,
            "found_targets": list(found_asins)
        }, "OK"
        
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("建立 ASIN -> Merchant ID 映射数据库")
    print("=" * 70)
    print(f"\n目标ASIN: {TARGET_ASINS}")
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Phase 1: Collect merchants
    print("\n[阶段1] 采集商户列表...")
    all_merchants = []
    
    for page in range(1, 51):  # First 50 pages = 5000 merchants
        merchants = get_merchants_batch(page, limit=100)
        if not merchants:
            break
        all_merchants.extend(merchants)
        print(f"  第{page}页: {len(merchants)}个商户 (累计{len(all_merchants)})")
        time.sleep(0.3)
    
    print(f"\n共采集 {len(all_merchants)} 个商户")
    
    # Save merchants list
    with open(output_dir / "all_merchants_5000.json", "w", encoding="utf-8") as f:
        json.dump(all_merchants, f, ensure_ascii=False, indent=2)
    
    # Phase 2: Scrape merchant pages
    print("\n[阶段2] 抓取商户页面获取商品信息...")
    
    asin_to_merchant = {}  # ASIN -> {mid, name, tracking_url}
    found_targets = {}  # Target ASIN -> merchant info
    login_expired = False
    
    # Process in batches
    batch_size = 50
    total = len(all_merchants)
    
    for i in range(0, total, batch_size):
        batch = all_merchants[i:i+batch_size]
        
        print(f"\n  处理第 {i+1}-{min(i+batch_size, total)}/{total} 个商户...")
        
        for merchant in batch:
            mid = merchant.get("mid") or merchant.get("id") or merchant.get("advert_id")
            name = merchant.get("merchant_name") or merchant.get("name", "Unknown")
            
            if not mid:
                continue
            
            result, status = scrape_merchant_page(mid, name)
            
            if status == "LOGIN_REQUIRED":
                print(f"    [错误] Cookie已过期!")
                login_expired = True
                break
            elif status == "OK" and result:
                # Add all ASINs to mapping
                for asin in result["asins"]:
                    if asin not in asin_to_merchant:
                        asin_to_merchant[asin] = []
                    asin_to_merchant[asin].append({
                        "mid": mid,
                        "name": name,
                        "tracking_links": result["tracking_links"]
                    })
                
                # Check for target ASINs
                if result["found_targets"]:
                    for asin in result["found_targets"]:
                        found_targets[asin] = {
                            "mid": mid,
                            "name": name,
                            "tracking_links": result["tracking_links"]
                        }
                    print(f"    [发现] {name}: {result['found_targets']}")
            
            time.sleep(0.1)
        
        if login_expired:
            break
        
        # Progress update
        if (i // batch_size) % 5 == 0:
            print(f"    进度: 已处理 {min(i+batch_size, total)}/{total}, 找到 {len(found_targets)}/{len(TARGET_ASINS)} 个目标ASIN")
    
    # Phase 3: Save results
    print("\n[阶段3] 保存结果...")
    
    # Save full mapping
    with open(output_dir / "asin_merchant_map.json", "w", encoding="utf-8") as f:
        json.dump(asin_to_merchant, f, ensure_ascii=False, indent=2)
    
    # Save target findings
    with open(output_dir / "target_asin_found.json", "w", encoding="utf-8") as f:
        json.dump(found_targets, f, ensure_ascii=False, indent=2)
    
    # Summary
    print("\n" + "=" * 70)
    print("完成!")
    print("=" * 70)
    print(f"已处理商户: {len(all_merchants)}")
    print(f"ASIN映射总数: {len(asin_to_merchant)}")
    print(f"找到目标ASIN: {len(found_targets)}/{len(TARGET_ASINS)}")
    
    if found_targets:
        print("\n找到的目标ASIN:")
        for asin, info in found_targets.items():
            print(f"  {asin} -> {info['name']} (MID: {info['mid']})")
    else:
        print("\n未找到目标ASIN，可能原因:")
        print("  1. 目标ASIN属于未处理的商户")
        print("  2. Cookie已过期")
        print("  3. 这些商品不在YP平台")
    
    print(f"\n输出文件:")
    print(f"  - output/asin_merchant_map.json (完整映射)")
    print(f"  - output/target_asin_found.json (目标ASIN结果)")

if __name__ == "__main__":
    main()
