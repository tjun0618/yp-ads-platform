#!/usr/bin/env python3
"""
Explore the relationship between merchants and offers in YP platform
"""
import requests
import json

TOKEN = "7951dc7484fa9f9d"
HEADERS = {"token": TOKEN}

def explore_offer_api():
    """Explore Offer API response structure"""
    print("=" * 60)
    print("Exploring Offer API")
    print("=" * 60)
    
    url = "https://www.yeahpromos.com/index/apioffer/getoffer"
    params = {"site_id": "12002", "page": 1, "limit": 5}
    
    resp = requests.get(url, headers=HEADERS, params=params)
    data = resp.json()
    
    if data.get("data", {}).get("data"):
        offer = data["data"]["data"][0]
        print("\nOffer fields:")
        for key in sorted(offer.keys()):
            value = offer[key]
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            print(f"  {key}: {value}")
        
        # Check for any merchant-related fields
        print("\nMerchant-related fields:")
        for key in offer.keys():
            if "merchant" in key.lower() or "advert" in key.lower() or "brand" in key.lower():
                print(f"  {key}: {offer[key]}")

def explore_merchant_api():
    """Explore Merchant API response structure"""
    print("\n" + "=" * 60)
    print("Exploring Merchant API")
    print("=" * 60)
    
    url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    params = {"site_id": "12002", "page": 1, "limit": 5}
    
    resp = requests.get(url, headers=HEADERS, params=params)
    data = resp.json()
    
    merchants = data.get("data", {}).get("Data") or data.get("data", {}).get("data", [])
    if merchants:
        merchant = merchants[0]
        print("\nMerchant fields:")
        for key in sorted(merchant.keys()):
            value = merchant[key]
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            print(f"  {key}: {value}")

def search_offer_by_asin(asin):
    """Search for an offer by ASIN"""
    print(f"\n" + "=" * 60)
    print(f"Searching for ASIN: {asin}")
    print("=" * 60)
    
    url = "https://www.yeahpromos.com/index/apioffer/getoffer"
    
    # Try searching through multiple pages
    for page in range(1, 20):
        params = {"site_id": "12002", "page": page, "limit": 100}
        resp = requests.get(url, headers=HEADERS, params=params)
        data = resp.json()
        
        offers = data.get("data", {}).get("data", [])
        for offer in offers:
            if asin in str(offer.get("product_name", "")) or \
               asin in str(offer.get("product_id", "")) or \
               asin in str(offer.get("amazon_link", "")):
                print(f"\nFound offer on page {page}:")
                print(f"  Product ID: {offer.get('product_id')}")
                print(f"  Product Name: {offer.get('product_name', '')[:60]}...")
                print(f"  Amazon Link: {offer.get('amazon_link', '')}")
                print(f"  All fields: {list(offer.keys())}")
                return offer
    
    print(f"  ASIN {asin} not found in first 2000 offers")
    return None

def check_offer_details(product_id):
    """Check if there's an API to get offer details"""
    print(f"\n" + "=" * 60)
    print(f"Checking offer details for product_id: {product_id}")
    print("=" * 60)
    
    # Try common API patterns
    endpoints = [
        f"https://www.yeahpromos.com/index/apioffer/getofferdetail",
        f"https://www.yeahpromos.com/index/apioffer/detail",
        f"https://www.yeahpromos.com/index/offer/detail",
    ]
    
    for endpoint in endpoints:
        try:
            resp = requests.get(endpoint, headers=HEADERS, params={"product_id": product_id, "site_id": "12002"}, timeout=5)
            if resp.status_code == 200:
                print(f"  Endpoint {endpoint} responded:")
                print(f"  {resp.text[:200]}")
        except Exception as e:
            pass

def main():
    # First, explore API structures
    explore_offer_api()
    explore_merchant_api()
    
    # Try to find a sample ASIN from Feishu in the API
    sample_asins = ["B0GDXPNRD4", "B0GL7QP2SF", "B08QSLJ8CC"]
    for asin in sample_asins:
        offer = search_offer_by_asin(asin)
        if offer:
            # Try to get more details
            check_offer_details(offer.get("product_id"))
            break

if __name__ == "__main__":
    main()
