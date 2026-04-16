#!/usr/bin/env python3
"""Test scraping first merchant"""
import requests
import re

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Test first merchant
mid = "362564"
url = "https://www.yeahpromos.com/index/offer/brand_detail"
params = {"advert_id": mid, "site_id": "12002"}

print(f"Testing merchant {mid}...")
resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)

print(f"Status: {resp.status_code}")
print(f"Contains login: {'/index/login/login' in resp.text}")
print(f"Contains Copy: {'ClipboardJS.copy' in resp.text}")

# Extract tracking links
tracking_pattern = re.compile(r"track=([a-f0-9]+)&amp;pid=(\d+)")
matches = tracking_pattern.findall(resp.text)
print(f"\nTracking links found: {len(matches)}")

# Extract ASINs
asins = re.findall(r'[A-Z0-9]{10}', resp.text)
print(f"ASINs found: {len(asins)}")

if matches and asins:
    print("\nSample products:")
    for i, (track, pid) in enumerate(matches[:3]):
        asin = asins[i] if i < len(asins) else 'N/A'
        print(f"  PID={pid}, ASIN={asin}, Track={track[:16]}...")
