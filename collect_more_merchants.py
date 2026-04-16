#!/usr/bin/env python3
"""
采集更多商户数据
"""
import requests
import json
import time

TOKEN = "7951dc7484fa9f9d"
HEADERS = {"token": TOKEN}
SITE_ID = "12002"

def get_merchants(page=1, limit=100):
    """Fetch merchants from API"""
    url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    params = {"site_id": SITE_ID, "page": page, "limit": limit}
    
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    data = resp.json()
    
    if data.get("status") == "SUCCESS":
        merchants = data.get("data", {}).get("Data") or data.get("data", {}).get("data", [])
        return merchants
    return []

def main():
    print("采集更多商户数据...")
    
    all_merchants = []
    
    # Collect first 100 pages (10000 merchants, but we'll stop at 2000)
    for page in range(1, 21):  # 20 pages = 2000 merchants
        print(f"  采集第 {page} 页...", end=" ")
        merchants = get_merchants(page, limit=100)
        
        if not merchants:
            print("无数据")
            break
        
        all_merchants.extend(merchants)
        print(f"获取 {len(merchants)} 个 (累计 {len(all_merchants)})")
        
        time.sleep(0.3)
    
    # Save
    with open('output/merchants_extended.json', 'w', encoding='utf-8') as f:
        json.dump(all_merchants, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！共采集 {len(all_merchants)} 个商户")
    print(f"保存到: output/merchants_extended.json")

if __name__ == "__main__":
    main()
