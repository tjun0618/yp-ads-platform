# -*- coding: utf-8 -*-
"""
验证 getadvert API 返回的商户数据
"""
import requests
import json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
HEADERS = {'token': TOKEN}

BASE = 'https://www.yeahpromos.com'

print("=" * 80)
print("验证商户 API 数据")
print("=" * 80)

# 1. Get NORTIV 8 merchant details
print("\n[1] NORTIV 8 (MID: 362548) via getadvert API")
print("-" * 60)

url = f"{BASE}/index/getadvert/getadvert"
params = {'site_id': SITE_ID, 'advert_id': '362548'}
resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

if resp.status_code == 200:
    data = resp.json()
    if data.get('status') == 'SUCCESS':
        items = data['data'].get('Data', [])
        print(f"Returned {len(items)} items")
        
        if items:
            print("\nFirst 5 items:")
            for item in items[:5]:
                print(f"  MID: {item.get('mid', 'N/A')}")
                print(f"  Name: {item.get('name', 'N/A')}")
                print(f"  Commission: {item.get('commission', 'N/A')}")
                print(f"  ---")

# 2. Get NORTIV 8 products via getoffer with merchant filter
print("\n[2] NORTIV 8 products via getoffer (advert_id filter)")
print("-" * 60)

url = f"{BASE}/index/apioffer/getoffer"
params = {'site_id': SITE_ID, 'advert_id': '362548', 'page': 1, 'limit': 20}
resp = requests.get(url, headers=HEADERS, params=params, timeout=15)

if resp.status_code == 200:
    data = resp.json()
    if data.get('status') == 'SUCCESS':
        items = data['data'].get('data', [])
        print(f"Returned {len(items)} items")
        
        print("\nFirst 10 products:")
        for item in items[:10]:
            asin = item.get('asin', 'N/A')
            name = str(item.get('product_name', ''))[:50]
            price = item.get('price', 'N/A')
            merchant = item.get('merchant_name', 'N/A')
            print(f"  ASIN={asin} | Price={price} | Merchant={merchant}")
            print(f"    Name: {name}")

# 3. Compare with Excel data
print("\n[3] Compare with NORTIV 8 Excel data")
print("-" * 60)

try:
    import openpyxl
    wb = openpyxl.load_workbook(r'C:\Users\wuhj\Downloads\Offer_20260323232258_2131.xlsx', read_only=True)
    ws = wb.active
    
    excel_products = []
    for row in ws.iter_rows(min_row=2, max_row=21, values_only=True):  # First 20
        if row[0]:
            excel_products.append({
                'asin': str(row[0]),
                'name': str(row[1])[:50],
                'price': row[4],
                'commission': row[3]
            })
    wb.close()
    
    print(f"Excel has {len(excel_products)} products")
    print("\nFirst 10 from Excel:")
    for p in excel_products[:10]:
        print(f"  ASIN={p['asin']} | Price={p['price']} | Commission={p['commission']}")
        print(f"    Name: {p['name']}")
    
    # Check overlap
    api_asins = set()
    for item in items[:20]:
        api_asins.add(item.get('asin', ''))
    
    excel_asins = set(p['asin'] for p in excel_products)
    overlap = api_asins & excel_asins
    
    print(f"\nOverlap between API and Excel: {len(overlap)} ASINs")
    if overlap:
        print(f"  Common ASINs: {list(overlap)[:5]}")
    else:
        print("  NO OVERLAP - API returns completely different products!")
        
except Exception as e:
    print(f"Error reading Excel: {e}")

print("\n" + "=" * 80)
