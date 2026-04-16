# -*- coding: utf-8 -*-
"""
测试已知的 YP API，尝试用不同参数获取商户商品
"""
import requests
import json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
HEADERS = {'token': TOKEN}

BASE = 'https://www.yeahpromos.com'

print("=" * 80)
print("测试已知 API 的不同参数组合")
print("=" * 80)

# 1. Test getoffer with merchant filter
print("\n[1] /index/apioffer/getoffer with merchant filter")
print("-" * 60)

merchant_filters = [
    {'advert_id': '362548'},  # NORTIV 8
    {'merchant_id': '362548'},
    {'mid': '362548'},
    {'merchant': '362548'},
]

for filt in merchant_filters:
    params = {'site_id': SITE_ID, 'page': 1, 'limit': 10}
    params.update(filt)
    
    url = f"{BASE}/index/apioffer/getoffer"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    
    print(f"\n  Params: {filt}")
    print(f"  Status: {resp.status_code}")
    
    if resp.status_code == 200:
        try:
            data = resp.json()
            if data.get('status') == 'SUCCESS':
                items = data['data'].get('data', [])
                print(f"  Items returned: {len(items)}")
                if items:
                    print(f"  First item ASIN: {items[0].get('asin', 'N/A')}")
                    print(f"  First item name: {str(items[0].get('product_name', ''))[:50]}")
            else:
                print(f"  API status: {data.get('status')}")
                print(f"  Message: {data.get('msg', 'N/A')}")
        except Exception as e:
            print(f"  Error parsing: {e}")

# 2. Test getadvert with different params
print("\n[2] /index/getadvert/getadvert with different params")
print("-" * 60)

advert_params = [
    {'site_id': SITE_ID, 'page': 1, 'limit': 5},
    {'site_id': SITE_ID, 'advert_id': '362548'},
    {'site_id': SITE_ID, 'merchant_id': '362548'},
]

for params in advert_params:
    url = f"{BASE}/index/getadvert/getadvert"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    
    print(f"\n  Params: {params}")
    print(f"  Status: {resp.status_code}")
    
    if resp.status_code == 200:
        try:
            data = resp.json()
            status = data.get('status', data.get('Status', 'unknown'))
            print(f"  API status: {status}")
            
            if status == 'SUCCESS' or 'Data' in data.get('data', {}):
                d = data.get('data', {}).get('Data', [])
                print(f"  Items: {len(d) if isinstance(d, list) else 'N/A'}")
        except Exception as e:
            print(f"  Error: {e}")

# 3. Try to find product by ASIN
print("\n[3] Search for specific ASIN (B07FRRHPJD)")
print("-" * 60)

search_params = [
    {'site_id': SITE_ID, 'keyword': 'B07FRRHPJD'},
    {'site_id': SITE_ID, 'search': 'B07FRRHPJD'},
    {'site_id': SITE_ID, 'asin': 'B07FRRHPJD'},
    {'site_id': SITE_ID, 'product_id': '543934'},  # NORTIV 8 version
]

for params in search_params:
    url = f"{BASE}/index/apioffer/getoffer"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
    
    print(f"\n  Params: {params}")
    if resp.status_code == 200:
        try:
            data = resp.json()
            if data.get('status') == 'SUCCESS':
                items = data['data'].get('data', [])
                print(f"  Found {len(items)} items")
                for item in items[:3]:
                    print(f"    PID={item.get('product_id')} ASIN={item.get('asin')} Price={item.get('price')} Merchant={item.get('merchant_name', 'N/A')}")
        except:
            pass

# 4. Check if there's a merchant products endpoint
print("\n[4] Test merchant-specific endpoints")
print("-" * 60)

merchant_endpoints = [
    '/index/offer/getproducts',
    '/index/offer/getmerchantproducts',
    '/index/apioffer/getmerchantproducts',
    '/index/getadvert/getproducts',
]

for endpoint in merchant_endpoints:
    url = f"{BASE}{endpoint}"
    params = {'site_id': SITE_ID, 'advert_id': '362548', 'page': 1, 'limit': 5}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        print(f"\n  {endpoint}")
        print(f"    Status: {resp.status_code}")
        if resp.status_code == 200:
            try:
                data = resp.json()
                print(f"    Response: {json.dumps(data, ensure_ascii=False)[:200]}")
            except:
                print(f"    Not JSON: {resp.text[:100]}")
    except Exception as e:
        print(f"\n  {endpoint}: Error - {e}")

print("\n" + "=" * 80)
print("Done")
