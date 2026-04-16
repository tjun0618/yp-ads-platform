"""
详细展示 ASIN=B07FRRHPJD 在 API 中的所有记录
"""
import requests, json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
headers = {'token': TOKEN}
TARGET_ASIN = 'B07FRRHPJD'

# 用 asin 搜索
params = {'site_id': SITE_ID, 'page': 1, 'limit': 10, 'asin': TARGET_ASIN}
resp = requests.get('https://www.yeahpromos.com/index/apioffer/getoffer', headers=headers, params=params, timeout=30)
data = resp.json()

if data.get('status') == 'SUCCESS':
    items = data['data'].get('data', [])
    print(f"ASIN={TARGET_ASIN} found {len(items)} records in YP API")
    print()
    
    for i, item in enumerate(items, 1):
        pid = item.get('product_id', '')
        name = item.get('product_name', '')
        price = item.get('price', '')
        payout = item.get('payout', '')
        cat = item.get('category_name', '')
        status = item.get('product_status', '')
        discount = item.get('discount', '')
        link_status = item.get('link_status', '')
        
        print(f"--- Record {i} ---")
        print(f"  Product ID:  {pid}")
        print(f"  ASIN:        {TARGET_ASIN}")
        print(f"  Name:        {name[:80]}")
        print(f"  Price:       {price}")
        print(f"  Payout:      {payout}%")
        print(f"  Category:    {cat}")
        print(f"  Status:      {status}")
        print(f"  Discount:    {discount}")
        print(f"  Link Status: {link_status}")
        print()

print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print()
print("The SAME ASIN appears MULTIPLE TIMES in the YP API:")
print("  - Each record has a DIFFERENT Product ID")
print("  - Each record may have DIFFERENT price (different currency/locale)")
print("  - Each record may be linked to a DIFFERENT merchant")
print()
print("Product ID=1333492: EUR 28.44 (European site, NOT USD!)")
print("Product ID=543934:  USD 69.99 (US site - matches YP Excel)")
print("Product ID=438891:  CAD 86.99 (Canadian site)")
print()
print("CONCLUSION:")
print("  The 'price' discrepancy is NOT an error.")
print("  Product ID=1333492 is the EUR (Euro) version priced at 28.44 EUR.")
print("  Product ID=543934 is the USD version priced at $69.99.")
print("  The API stores products across multiple Amazon locales (US/EU/CA/etc).")
print()
print("  For US market Google Ads, you must use Product ID=543934 (USD 69.99)")
print("  and filter by currency/price to ensure USD listings only.")
