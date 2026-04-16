#!/usr/bin/env python3
"""Check raw API response for merchant-related fields"""
import requests
import json

TOKEN = "7951dc7484fa9f9d"
HEADERS = {"token": TOKEN}

def check_raw_response():
    """Get raw API response and check all fields"""
    url = "https://www.yeahpromos.com/index/apioffer/getoffer"
    params = {"site_id": "12002", "page": 1, "limit": 3}
    
    resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
    data = resp.json()
    
    if data.get("status") == "SUCCESS" and data.get("data", {}).get("data"):
        offer = data["data"]["data"][0]
        
        print("=" * 60)
        print("Raw Offer API Response - All Fields")
        print("=" * 60)
        
        for key in sorted(offer.keys()):
            value = offer[key]
            if isinstance(value, str) and len(value) > 80:
                value = value[:80] + "..."
            print(f"  {key}: {value}")
        
        # Check for any merchant-related fields
        print("\n" + "=" * 60)
        print("Searching for merchant-related fields")
        print("=" * 60)
        
        merchant_keywords = ['merchant', 'advert', 'brand', 'seller', 'store', 'vendor', 'shop', 'mid']
        found = False
        for key in offer.keys():
            if any(kw in key.lower() for kw in merchant_keywords):
                print(f"  FOUND: {key} = {offer[key]}")
                found = True
        
        if not found:
            print("  No merchant-related fields found in Offer API")
        
        # Save full response for inspection
        with open('output/raw_offer_response.json', 'w') as f:
            json.dump(data["data"]["data"][:3], f, indent=2)
        print("\nSaved raw response to output/raw_offer_response.json")

if __name__ == "__main__":
    check_raw_response()
