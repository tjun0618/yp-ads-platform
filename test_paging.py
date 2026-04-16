#!/usr/bin/env python3
"""测试 API 分页逻辑"""
import requests, json, time

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
headers = {'token': TOKEN}

for page in [1, 2, 3]:
    params = {'site_id': SITE_ID, 'page': page, 'limit': 100}
    resp = requests.get('https://www.yeahpromos.com/index/apioffer/getoffer', headers=headers, params=params, timeout=30)
    data = resp.json()
    
    if isinstance(data, dict) and data.get('status') == 'SUCCESS':
        offers = data['data'].get('data', [])
        total = data['data'].get('total', 0)
        page_total = data['data'].get('PageTotal', 1)
        first_asin = offers[0].get('asin', '') if offers else 'N/A'
        print(f"Page {page}: {len(offers)} offers, total={total}, page_total={page_total}, first_asin={first_asin}")
    else:
        print(f"Page {page}: Error - {data}")
    
    time.sleep(1)
