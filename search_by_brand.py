#!/usr/bin/env python3
"""
Search YP merchants by brand name extracted from product names
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

# Products from Feishu with their brand names (extracted from product names)
PRODUCTS = [
    {"asin": "B0GDXPNRD4", "name": "Magnetic Wireless Charger", "brand": "Unknown"},
    {"asin": "B0GL7QP2SF", "name": "Magnetic Wireless Charger", "brand": "Unknown"},
    {"asin": "B0C545BTQN", "name": "YENSA Vibrant Silk Lipstick", "brand": "YENSA"},
    {"asin": "B0FNWMSTR8", "name": "Cyperus Rotundus Oil", "brand": "Unknown"},
    {"asin": "B0BR6DL25V", "name": "Xymogen Red Yeast Rice", "brand": "Xymogen"},
    {"asin": "B0FF4PXHRN", "name": "LILIE&WHITE Cherry Keychain", "brand": "LILIE&WHITE"},
    {"asin": "B0GHSXZ9Q2", "name": "LS Rash", "brand": "LS"},
    {"asin": "B0GHSW4VWY", "name": "Hurley Cropped LS Rash", "brand": "Hurley"},
    {"asin": "B0BH9GBCFB", "name": "Maude Soak", "brand": "Maude"},
    {"asin": "B0CQZ2HQBN", "name": "MAUDE Soothe + Shine", "brand": "MAUDE"},
]

def search_merchant_by_name(brand_name):
    """Search for merchant by brand name in YP"""
    # Try to find in local merchants first
    try:
        with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
            merchants = json.load(f)
    except FileNotFoundError:
        merchants = []
    
    matches = []
    for m in merchants:
        name = m.get('merchant_name', '').lower()
        if brand_name.lower() in name:
            matches.append(m)
    
    return matches

def check_product_on_merchant_page(mid, asin):
    """Check if a specific ASIN exists on merchant page"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": "12002"}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        if "/index/login/login" in html:
            return "LOGIN_REQUIRED"
        
        return asin in html
    except Exception as e:
        return str(e)

def main():
    print("=" * 60)
    print("Searching Merchants by Brand Name")
    print("=" * 60)
    
    for product in PRODUCTS:
        brand = product['brand']
        asin = product['asin']
        
        print(f"\n[{asin}] {product['name'][:40]}...")
        print(f"  Brand: {brand}")
        
        # Search by brand name
        matches = search_merchant_by_name(brand)
        
        if matches:
            print(f"  Found {len(matches)} potential merchant(s):")
            for m in matches:
                mid = m.get('mid') or m.get('id') or m.get('merchant_id')
                name = m.get('merchant_name', 'Unknown')
                print(f"    - {name} (MID: {mid})")
                
                # Verify by checking if ASIN is on the page
                result = check_product_on_merchant_page(mid, asin)
                if result == True:
                    print(f"      [OK] CONFIRMED: ASIN found on merchant page!")
                elif result == "LOGIN_REQUIRED":
                    print(f"      [FAIL] Cookie expired")
                    return
                else:
                    print(f"      [FAIL] ASIN not found on this merchant page")
        else:
            print(f"  No merchants found matching brand '{brand}'")

if __name__ == "__main__":
    main()
