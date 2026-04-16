#!/usr/bin/env python3
import requests, json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
headers = {'token': TOKEN}
params = {'site_id': SITE_ID, 'page': 1, 'limit': 5}

resp = requests.get('https://www.yeahpromos.com/index/apioffer/getoffer', headers=headers, params=params, timeout=30)
data = resp.json()

if isinstance(data, dict) and data.get('status') == 'SUCCESS':
    offers = data['data'].get('data', [])
    total = data['data'].get('total', 0)
    page_total = data['data'].get('PageTotal', 1)
    print(f"API OK: {len(offers)} offers, total={total}, pages={page_total}")
    for o in offers[:3]:
        asin = o.get("asin", "")
        name = o.get("product_name", "")[:50]
        payout = o.get("payout", "")
        print(f"  ASIN={asin} payout={payout} name={name}")
else:
    print(f"API Error: {data}")
