#!/usr/bin/env python3
"""
Batch find which merchants contain target ASINs
"""
import requests
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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

def check_merchant(merchant):
    """Check a single merchant page for target ASINs"""
    mid = merchant.get("mid") or merchant.get("id") or merchant.get("advert_id")
    name = merchant.get("merchant_name") or merchant.get("name", "Unknown")
    
    if not mid:
        return None
    
    url = "https://www.yeahpromos.com/index/offer/brand_detail"
    params = {"advert_id": mid, "site_id": "12002"}
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        html = resp.text
        
        # Check if redirected to login
        if "/index/login/login" in html:
            return {"error": "LOGIN_REQUIRED", "mid": mid, "name": name}
        
        # Find all ASINs on the page
        asins_on_page = set(re.findall(r'[A-Z0-9]{10}', html))
        
        # Check for matches
        matches = [asin for asin in TARGET_ASINS if asin in asins_on_page]
        
        if matches:
            return {
                "mid": mid,
                "name": name,
                "matches": matches,
                "all_asins": list(asins_on_page)[:10]  # First 10 ASINs for reference
            }
        
        return None
    except Exception as e:
        return {"error": str(e), "mid": mid, "name": name}

def main():
    print("=" * 60)
    print("Batch Finding Merchants for Target ASINs")
    print("=" * 60)
    print(f"\nTarget ASINs: {TARGET_ASINS}")
    
    # Load merchants
    try:
        with open('output/merchants_data.json', 'r') as f:
            merchants = json.load(f)
    except FileNotFoundError:
        print("Error: merchants_data.json not found")
        return
    
    print(f"Loaded {len(merchants)} merchants")
    
    # Check merchants in parallel
    found_merchants = []
    errors = []
    checked = 0
    
    print("\nChecking merchants...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(check_merchant, m): m for m in merchants}
        
        for future in as_completed(futures):
            result = future.result()
            checked += 1
            
            if result:
                if "error" in result:
                    if result["error"] == "LOGIN_REQUIRED":
                        print(f"\n[ERROR] Cookie expired at merchant {result['name']}")
                        errors.append(result)
                        break
                    else:
                        errors.append(result)
                else:
                    found_merchants.append(result)
                    print(f"\n[FOUND] {result['name']} (MID: {result['mid']})")
                    print(f"        Matches: {result['matches']}")
            
            if checked % 50 == 0:
                print(f"  Checked {checked}/{len(merchants)} merchants...")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Checked: {checked} merchants")
    print(f"Found: {len(found_merchants)} merchants with target ASINs")
    print(f"Errors: {len(errors)}")
    
    if found_merchants:
        print("\nMerchants containing target ASINs:")
        for fm in found_merchants:
            print(f"  - {fm['name']} (MID: {fm['mid']})")
            print(f"    ASINs: {fm['matches']}")
        
        # Save results
        with open('output/found_merchants.json', 'w') as f:
            json.dump(found_merchants, f, indent=2)
        print(f"\nSaved to output/found_merchants.json")
    else:
        print("\nNo merchants found containing target ASINs")
        print("\nThese ASINs may belong to:")
        print("  1. Merchants not yet collected (need to fetch more merchants)")
        print("  2. Merchants with different MID format")
        print("  3. Products not yet approved/available")

if __name__ == "__main__":
    main()
