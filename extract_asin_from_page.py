#!/usr/bin/env python3
"""
Extract ASIN from merchant page HTML
"""
import requests
import re
import json

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def extract_products_with_asin(mid, name):
    """Extract products with both tracking link and ASIN"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": "12002"}
    
    resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
    html = resp.text
    
    products = []
    
    # Find all product rows with Copy button and extract nearby ASIN
    # Pattern to find each product section
    product_pattern = re.compile(
        r'<div[^>]*class=["\'][^"\']*product-line[^"\']*["\'][^>]*>(.*?)</div>\s*</div>\s*</div>\s*<div[^>]*class=["\'][^"\']*product-line["\'][^>]*>|</div>\s*</div>\s*</div>\s*$',
        re.DOTALL | re.IGNORECASE
    )
    
    # Simpler approach: find all ASINs and all tracking links, then match by position
    asin_pattern = re.compile(r'[A-Z0-9]{10}')
    tracking_pattern = re.compile(
        r'track=([a-f0-9]+)&amp;pid=(\d+)',
        re.IGNORECASE
    )
    
    # Find all ASINs with their positions
    asin_matches = list(asin_pattern.finditer(html))
    asins = [(m.group(), m.start()) for m in asin_matches if len(m.group()) == 10]
    
    # Find all tracking links with their positions
    tracking_matches = list(tracking_pattern.finditer(html))
    
    print(f"Found {len(asins)} ASINs and {len(tracking_matches)} tracking links")
    
    # Match by closest position
    for t_match in tracking_matches:
        track = t_match.group(1)
        pid = t_match.group(2)
        t_pos = t_match.start()
        
        # Find closest ASIN
        closest_asin = None
        min_dist = float('inf')
        for asin, a_pos in asins:
            dist = abs(a_pos - t_pos)
            if dist < min_dist and dist < 2000:  # Within 2000 chars
                min_dist = dist
                closest_asin = asin
        
        products.append({
            "pid": pid,
            "track": track,
            "asin": closest_asin,
            "tracking_url": f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
        })
    
    return products

# Test with TruSkin
print("=" * 60)
print("TruSkin (MID: 363372)")
print("=" * 60)
products = extract_products_with_asin("363372", "TruSkin")

for p in products[:10]:
    print(f"ASIN: {p['asin']}, PID: {p['pid']}, Track: {p['track'][:16]}...")

# Save results
with open('output/truskin_products.json', 'w') as f:
    json.dump(products, f, indent=2)
print(f"\nSaved {len(products)} products to output/truskin_products.json")

# Test with Physician's Choice
print("\n" + "=" * 60)
print("Physician's Choice (MID: 362247)")
print("=" * 60)
products2 = extract_products_with_asin("362247", "Physician's Choice")

for p in products2[:10]:
    print(f"ASIN: {p['asin']}, PID: {p['pid']}, Track: {p['track'][:16]}...")

with open('output/physicians_choice_products.json', 'w') as f:
    json.dump(products2, f, indent=2)
print(f"\nSaved {len(products2)} products to output/physicians_choice_products.json")
