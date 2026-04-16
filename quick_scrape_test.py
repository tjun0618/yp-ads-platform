#!/usr/bin/env python3
"""Quick test scraping first 5 merchants"""
import requests
import json
import re
import time

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Load merchants
with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
    merchants = json.load(f)

print(f"Total merchants: {len(merchants)}")

asin_map = {}

# Scrape first 5 merchants
for i, merchant in enumerate(merchants[:5]):
    mid = merchant.get("merchant_id")
    name = merchant.get("merchant_name", "Unknown")
    name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
    
    print(f"\n[{i+1}] {name_safe} (MID: {mid})")
    
    if not mid:
        print("  Skip: No MID")
        continue
    
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": "12002"}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        
        if "/index/login/login" in resp.text:
            print("  Skip: Login required")
            continue
        
        # Extract ASINs and tracking
        asins = re.findall(r'[A-Z0-9]{10}', resp.text)
        tracking_pattern = re.compile(r"track=([a-f0-9]+)&amp;pid=(\d+)")
        tracking_matches = tracking_pattern.findall(resp.text)
        
        print(f"  Found {len(tracking_matches)} products, {len(asins)} ASINs")
        
        # Add to map
        for j, (track, pid) in enumerate(tracking_matches):
            asin = asins[j] if j < len(asins) else None
            if asin:
                asin_map[asin] = {
                    "mid": mid,
                    "merchant_name": name,
                    "pid": pid,
                    "track": track
                }
        
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(0.5)

print(f"\n\nTotal ASINs mapped: {len(asin_map)}")
print("\nSample mappings:")
for asin, info in list(asin_map.items())[:5]:
    merchant_safe = info['merchant_name'].encode('ascii', 'ignore').decode('ascii')
    print(f"  {asin} -> {merchant_safe} (MID: {info['mid']})")

# Save
with open('output/quick_asin_map.json', 'w', encoding='utf-8') as f:
    json.dump(asin_map, f, ensure_ascii=False, indent=2)
print(f"\nSaved to output/quick_asin_map.json")
