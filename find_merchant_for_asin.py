#!/usr/bin/env python3
"""
Find which merchant an ASIN belongs to by checking merchant pages
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

# Target ASINs from Feishu
TARGET_ASINS = ["B0GDXPNRD4", "B0GL7QP2SF", "B0C545BTQN", "B0FNWMSTR8", "B0BR6DL25V"]

def get_all_merchants():
    """Get list of all merchants from local data"""
    try:
        with open('output/merchants_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def check_merchant_page(mid, name, target_asins):
    """Check if merchant page contains any of the target ASINs"""
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": "12002"}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        # Check if redirected to login
        if "/index/login/login" in html:
            return None, "LOGIN_REQUIRED"
        
        # Find all ASINs on the page
        asins_on_page = re.findall(r'[A-Z0-9]{10}', html)
        
        # Check for matches
        matches = []
        for asin in target_asins:
            if asin in asins_on_page:
                matches.append(asin)
        
        return matches, "OK"
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 60)
    print("Finding Merchants for Target ASINs")
    print("=" * 60)
    print(f"\nTarget ASINs: {TARGET_ASINS}")
    
    # Load merchants
    merchants = get_all_merchants()
    print(f"\nLoaded {len(merchants)} merchants from local data")
    
    # Check first 20 merchants
    found_merchants = []
    
    for i, merchant in enumerate(merchants[:50]):
        mid = merchant.get("mid") or merchant.get("id") or merchant.get("advert_id")
        name = merchant.get("merchant_name") or merchant.get("name", "Unknown")
        
        if not mid:
            continue
        
        print(f"\n[{i+1}] Checking {name} (MID: {mid})...", end=" ")
        
        matches, status = check_merchant_page(mid, name, TARGET_ASINS)
        
        if status == "LOGIN_REQUIRED":
            print("COOKIE EXPIRED!")
            break
        elif matches:
            print(f"FOUND: {matches}")
            found_merchants.append({
                "mid": mid,
                "name": name,
                "matches": matches
            })
        else:
            print("No match")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if found_merchants:
        for fm in found_merchants:
            print(f"  {fm['name']} (MID: {fm['mid']}): {fm['matches']}")
    else:
        print("  No merchants found containing target ASINs")
        print("\n  Possible reasons:")
        print("  1. Cookie expired - need fresh PHPSESSID")
        print("  2. These ASINs belong to merchants not yet in local data")
        print("  3. Need to check more merchants")

if __name__ == "__main__":
    main()
