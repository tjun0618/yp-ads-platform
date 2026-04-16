# -*- coding: utf-8 -*-
"""Test the report_performance and report_cpc API endpoints"""
import requests
import json

COOKIE = {
    'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc',
    'user_id': '2864',
    'user_name': 'Tong%20Jun',
}

BASE = 'https://yeahpromos.com'

# Test both endpoints with various parameters
ENDPOINTS = [
    '/index/offer/report_performance',
    '/index/offer/report_cpc',
]

PARAMS_VARIANTS = [
    # Variant 1: Full params
    {'start_date': '2026-03-01', 'end_date': '2026-03-23', 'site_id': '12002', 'dim': 'CampaignId'},
    # Variant 2: With page/limit
    {'start_date': '2026-03-01', 'end_date': '2026-03-23', 'site_id': '12002', 'dim': 'CampaignId', 'page': 1, 'limit': 10},
    # Variant 3: Different dim
    {'start_date': '2026-03-01', 'end_date': '2026-03-23', 'site_id': '12002', 'dim': 'Merchant'},
    # Variant 4: No dim
    {'start_date': '2026-03-01', 'end_date': '2026-03-23', 'site_id': '12002'},
]

for endpoint in ENDPOINTS:
    print(f"\n{'='*80}")
    print(f"Testing: {endpoint}")
    print('='*80)
    
    for i, params in enumerate(PARAMS_VARIANTS):
        url = f"{BASE}{endpoint}"
        print(f"\n[Variant {i+1}] params={params}")
        
        # Try GET
        try:
            resp = requests.get(url, cookies=COOKIE, params=params, timeout=15)
            print(f"  GET Status: {resp.status_code}")
            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', '')
                print(f"  Content-Type: {content_type}")
                
                # Try parse as JSON
                try:
                    data = resp.json()
                    print(f"  JSON Response keys: {list(data.keys())[:10]}")
                    
                    # Check for data structure
                    if 'data' in data:
                        d = data['data']
                        if isinstance(d, list):
                            print(f"  Data is list with {len(d)} items")
                            if d:
                                print(f"  First item keys: {list(d[0].keys()) if isinstance(d[0], dict) else 'not dict'}")
                        elif isinstance(d, dict):
                            print(f"  Data is dict with keys: {list(d.keys())[:10]}")
                    
                    # Save sample
                    sample_file = f"output/api_{endpoint.replace('/', '_')}_v{i+1}.json"
                    with open(sample_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"  Saved to {sample_file}")
                    
                except:
                    # Not JSON, might be HTML
                    if len(resp.text) < 1000:
                        print(f"  Text response: {resp.text[:200]}")
                    else:
                        print(f"  HTML response, length: {len(resp.text)}")
                        
        except Exception as e:
            print(f"  GET Error: {e}")
        
        # Try POST (some APIs use POST)
        try:
            resp = requests.post(url, cookies=COOKIE, data=params, timeout=15)
            print(f"  POST Status: {resp.status_code}")
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"  POST JSON keys: {list(data.keys())[:5]}")
                except:
                    pass
        except Exception as e:
            print(f"  POST Error: {e}")

print("\n" + "="*80)
print("Done")
