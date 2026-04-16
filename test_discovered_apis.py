# -*- coding: utf-8 -*-
"""
测试从页面发现的 API 端点
"""
import requests
import json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
HEADERS = {'token': TOKEN}
COOKIE = {'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc'}

BASE = 'https://yeahpromos.com'

# 从页面发现的端点
ENDPOINTS = [
    # Brands 页面相关
    {'path': '/index/offer/brands', 'params': {'is_delete': 0, 'page': 1}, 'name': 'Brands List'},
    
    # Advert 页面相关
    {'path': '/index/advert/index', 'params': {'is_delete': 0, 'page': 1}, 'name': 'Advert Index'},
    {'path': '/index/advert/advert_content', 'params': {'advert_id': '362548', 'site_id': SITE_ID}, 'name': 'Advert Content'},
    {'path': '/index/advert/export_top_merchants', 'params': {}, 'name': 'Export Top Merchants'},
    {'path': '/index/advert/injoin2', 'params': {}, 'name': 'Injoin2'},
    {'path': '/index/advert/bulk_application', 'params': {}, 'name': 'Bulk Application'},
    
    # Brand detail (页面，不是API)
    {'path': '/index/offer/brand_detail', 'params': {'advert_id': '362548', 'site_id': SITE_ID}, 'name': 'Brand Detail Page'},
]

print("=" * 80)
print("测试发现的端点")
print("=" * 80)

for ep in ENDPOINTS:
    url = f"{BASE}{ep['path']}"
    print(f"\n{'='*60}")
    print(f"Testing: {ep['name']}")
    print(f"Path: {ep['path']}")
    print(f"Params: {ep['params']}")
    print('='*60)
    
    # Try with token header
    try:
        resp = requests.get(url, headers=HEADERS, cookies=COOKIE, params=ep['params'], timeout=15)
        print(f"With Token - Status: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '')
            
            if 'json' in content_type.lower() or resp.text.strip().startswith('{'):
                try:
                    data = resp.json()
                    print(f"JSON Keys: {list(data.keys())[:10]}")
                    if 'data' in data:
                        d = data['data']
                        if isinstance(d, list):
                            print(f"Data: list[{len(d)}]")
                            if d and isinstance(d[0], dict):
                                print(f"First item keys: {list(d[0].keys())[:10]}")
                                print(f"First item sample: {json.dumps(d[0], ensure_ascii=False)[:200]}")
                        elif isinstance(d, dict):
                            print(f"Data keys: {list(d.keys())[:10]}")
                    
                    # Save
                    safe_name = ep['name'].replace(' ', '_').replace('/', '_')
                    with open(f'output/api_{safe_name}.json', 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"Saved to output/api_{safe_name}.json")
                except Exception as e:
                    print(f"JSON parse error: {e}")
            else:
                # HTML
                print(f"HTML response, length: {len(resp.text)}")
                
                # Save HTML for inspection
                safe_name = ep['name'].replace(' ', '_').replace('/', '_')
                with open(f'output/page_{safe_name}.html', 'w', encoding='utf-8') as f:
                    f.write(resp.text)
                print(f"Saved HTML to output/page_{safe_name}.html")
                
                # Look for data in HTML
                if 'brand_detail' in ep['path']:
                    # Look for product data
                    import re
                    products = re.findall(r'data-product-id=["\']([^"\']+)["\']', resp.text)
                    if products:
                        print(f"Found {len(products)} product references in HTML")
                    
                    # Look for table data
                    table_data = re.findall(r'<td[^>]*>([^<]+)</td>', resp.text)
                    if table_data:
                        print(f"Found {len(table_data)} table cells")
                        print(f"Sample: {table_data[:10]}")
    except Exception as e:
        print(f"Error: {e}")

print("\n" + "=" * 80)
