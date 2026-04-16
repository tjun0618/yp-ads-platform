#!/usr/bin/env python3
"""
批量采集商户并查找飞书表格中ASIN对应的商户
"""
import requests
import json
import time
import re
from pathlib import Path

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
TARGET_ASINS = ["B0GDXPNRD4", "B0GL7QP2SF", "B0C545BTQN", "B0FNWMSTR8", "B0BR6DL25V", 
                "B0FF4PXHRN", "B0GHSXZ9Q2", "B0GHSW4VWY", "B0BH9GBCFB", "B0CQZ2HQBN"]

def get_merchants_from_api(page=1, limit=100):
    """Fetch merchants from YP API"""
    url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    headers = {"token": TOKEN}
    params = {"site_id": SITE_ID, "page": page, "limit": limit}
    
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    data = resp.json()
    
    if data.get("status") == "SUCCESS":
        merchants = data.get("data", {}).get("Data") or data.get("data", {}).get("data", [])
        total = data.get("data", {}).get("total", 0)
        last_page = data.get("data", {}).get("last_page", 1)
        return merchants, total, last_page
    return [], 0, 1

def check_merchant_page(mid, name):
    """Check if merchant page contains any target ASINs"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": SITE_ID}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        if "/index/login/login" in html:
            return None, "LOGIN_REQUIRED"
        
        # Find all ASINs on the page
        asins_on_page = set(re.findall(r'[A-Z0-9]{10}', html))
        
        # Check for matches
        matches = [asin for asin in TARGET_ASINS if asin in asins_on_page]
        
        if matches:
            # Also extract tracking links for matched ASINs
            tracking_links = []
            pattern = re.compile(r"ClipboardJS\.copy\('([^']+track=[a-f0-9]+&amp;pid=\d+)[^']*'\)")
            for match in pattern.findall(html):
                url_decoded = match.replace('&amp;', '&')
                # Extract ASIN from nearby HTML
                # This is a simplified approach - we'd need to parse more carefully
                tracking_links.append(url_decoded)
            
            return {
                "mid": mid,
                "name": name,
                "matches": matches,
                "tracking_links": tracking_links[:len(matches)]  # Approximate matching
            }, "FOUND"
        
        return None, "NO_MATCH"
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("批量采集商户并查找目标ASIN")
    print("=" * 70)
    print(f"\n目标ASIN: {TARGET_ASINS}")
    
    # Get total merchants info
    _, total, last_page = get_merchants_from_api(page=1, limit=1)
    print(f"\nYP平台总商户数: {total}, 总页数: {last_page}")
    
    # We'll check first 2000 merchants (20 pages)
    MAX_PAGES = 100
    found_merchants = []
    checked_count = 0
    
    print(f"\n计划检查: 前 {MAX_PAGES * 20} 个商户")
    print("=" * 70)
    
    for page in range(1, MAX_PAGES + 1):
        print(f"\n[第 {page}/{MAX_PAGES} 页] 采集商户列表...")
        merchants, _, _ = get_merchants_from_api(page=page, limit=20)
        
        if not merchants:
            print("  无数据，跳过")
            continue
        
        print(f"  获取 {len(merchants)} 个商户，开始检查...")
        
        for merchant in merchants:
            mid = merchant.get("mid") or merchant.get("id") or merchant.get("advert_id")
            name = merchant.get("merchant_name") or merchant.get("name", "Unknown")
            
            if not mid:
                continue
            
            result, status = check_merchant_page(mid, name)
            checked_count += 1
            
            if status == "LOGIN_REQUIRED":
                print(f"\n  [错误] Cookie已过期，请提供新的PHPSESSID")
                break
            elif status == "FOUND":
                found_merchants.append(result)
                print(f"\n  [发现] {name} (MID: {mid})")
                print(f"         匹配ASIN: {result['matches']}")
            
            # Small delay to avoid rate limiting
            time.sleep(0.2)
        
        # Progress update
        if page % 10 == 0:
            print(f"\n  进度: 已检查 {checked_count} 个商户，发现 {len(found_merchants)} 个匹配")
        
        # Rate limiting between pages
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("查找完成")
    print("=" * 70)
    print(f"已检查商户: {checked_count}")
    print(f"发现匹配: {len(found_merchants)}")
    
    if found_merchants:
        print("\n匹配的商户:")
        for fm in found_merchants:
            print(f"  - {fm['name']} (MID: {fm['mid']})")
            print(f"    ASINs: {fm['matches']}")
        
        # Save results
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        with open(output_dir / "matched_merchants.json", "w", encoding="utf-8") as f:
            json.dump(found_merchants, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存: output/matched_merchants.json")
    else:
        print("\n未找到包含目标ASIN的商户")
        print("\n可能原因:")
        print("  1. 目标ASIN属于未检查的商户（需要检查更多页）")
        print("  2. 这些商品可能不在YP平台的任何商户中")
        print("  3. Cookie可能已过期")

if __name__ == "__main__":
    main()
