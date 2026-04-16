#!/usr/bin/env python3
"""
探索 YP 平台所有可能的 API 端点，寻找商品-商户关联
"""
import requests
import json

TOKEN = "7951dc7484fa9f9d"
HEADERS = {"token": TOKEN}
SITE_ID = "12002"

def test_api(name, method, url, params=None, data=None):
    """Test an API endpoint"""
    try:
        if method == "GET":
            resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        else:
            resp = requests.post(url, headers=HEADERS, params=params, json=data, timeout=10)
        
        print(f"\n[{name}]")
        print(f"  URL: {url}")
        print(f"  Status: {resp.status_code}")
        
        if resp.status_code == 200:
            try:
                result = resp.json()
                print(f"  Response type: {type(result)}")
                
                if isinstance(result, dict):
                    print(f"  Keys: {list(result.keys())}")
                    
                    # Check for merchant-related data
                    if "data" in result and isinstance(result["data"], dict):
                        if "data" in result["data"] and isinstance(result["data"]["data"], list):
                            items = result["data"]["data"]
                            print(f"  Items count: {len(items)}")
                            if items:
                                print(f"  Item keys: {list(items[0].keys())}")
                                
                                # Check for merchant fields
                                merchant_fields = [k for k in items[0].keys() 
                                                   if any(x in k.lower() for x in ["merchant", "advert", "brand", "mid", "seller", "store"])]
                                if merchant_fields:
                                    print(f"  *** MERCHANT FIELDS FOUND: {merchant_fields} ***")
                                    for field in merchant_fields:
                                        print(f"      {field}: {items[0][field]}")
                
                return result
            except:
                print(f"  Response: {resp.text[:100]}")
    except Exception as e:
        print(f"\n[{name}] ERROR: {e}")
    return None

def main():
    print("=" * 70)
    print("探索 YP 平台所有 API 端点")
    print("=" * 70)
    
    # List of potential API endpoints to test
    endpoints = [
        # Offer related
        ("Offer API", "GET", "https://www.yeahpromos.com/index/apioffer/getoffer", {"site_id": SITE_ID, "page": 1, "limit": 5}),
        ("Offer Detail", "GET", "https://www.yeahpromos.com/index/apioffer/detail", {"site_id": SITE_ID, "product_id": "1350713"}),
        ("Offer by ID", "GET", "https://www.yeahpromos.com/index/apioffer/getofferbyid", {"site_id": SITE_ID, "id": "1350713"}),
        
        # Merchant related
        ("Merchant API", "GET", "https://www.yeahpromos.com/index/getadvert/getadvert", {"site_id": SITE_ID, "page": 1, "limit": 5}),
        ("Merchant Detail", "GET", "https://www.yeahpromos.com/index/getadvert/detail", {"site_id": SITE_ID, "advert_id": "363372"}),
        ("Merchant by ID", "GET", "https://www.yeahpromos.com/index/getadvert/getadvertbyid", {"site_id": SITE_ID, "id": "363372"}),
        
        # Potential relation APIs
        ("Merchant Offers", "GET", "https://www.yeahpromos.com/index/apioffer/getofferbyadvert", {"site_id": SITE_ID, "advert_id": "363372"}),
        ("Offer Merchant", "GET", "https://www.yeahpromos.com/index/apioffer/getadvertbyoffer", {"site_id": SITE_ID, "product_id": "1350713"}),
        
        # Category related
        ("Category API", "GET", "https://www.yeahpromos.com/index/apioffer/getcategory", {"site_id": SITE_ID}),
        ("Offers by Category", "GET", "https://www.yeahpromos.com/index/apioffer/getoffer", {"site_id": SITE_ID, "category_id": "1", "page": 1, "limit": 5}),
        
        # Other potential endpoints
        ("Brand API", "GET", "https://www.yeahpromos.com/index/apibrand/getbrand", {"site_id": SITE_ID}),
        ("Store API", "GET", "https://www.yeahpromos.com/index/apistore/getstore", {"site_id": SITE_ID}),
        ("Seller API", "GET", "https://www.yeahpromos.com/index/apiseller/getseller", {"site_id": SITE_ID}),
        
        # Search APIs
        ("Search Offers", "GET", "https://www.yeahpromos.com/index/apioffer/search", {"site_id": SITE_ID, "keyword": "YENSA"}),
        ("Search Merchants", "GET", "https://www.yeahpromos.com/index/getadvert/search", {"site_id": SITE_ID, "keyword": "TruSkin"}),
    ]
    
    found_relations = []
    
    for name, method, url, params in endpoints:
        result = test_api(name, method, url, params)
        
        # Check if this API returns merchant-related data
        if result and isinstance(result, dict):
            if "data" in result and isinstance(result["data"], dict):
                if "data" in result["data"] and isinstance(result["data"]["data"], list):
                    items = result["data"]["data"]
                    if items:
                        merchant_fields = [k for k in items[0].keys() 
                                           if any(x in k.lower() for x in ["merchant", "advert", "brand", "mid", "seller", "store"])]
                        if merchant_fields:
                            found_relations.append({
                                "api_name": name,
                                "url": url,
                                "merchant_fields": merchant_fields
                            })
    
    # Summary
    print("\n" + "=" * 70)
    print("探索完成 - 发现商品-商户关联的 API")
    print("=" * 70)
    
    if found_relations:
        print(f"\n发现 {len(found_relations)} 个 API 返回商户关联数据:")
        for fr in found_relations:
            print(f"\n  - {fr['api_name']}")
            print(f"    URL: {fr['url']}")
            print(f"    商户字段: {fr['merchant_fields']}")
    else:
        print("\n未发现返回商户关联数据的 API")
        print("\n可能的结论:")
        print("  1. YP 平台确实没有在 API 层暴露商品-商户关联")
        print("  2. 关联只能通过网页端获取")
        print("  3. 需要特殊权限或不同的认证方式才能访问关联 API")

if __name__ == "__main__":
    main()
