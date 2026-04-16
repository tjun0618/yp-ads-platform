#!/usr/bin/env python3
"""快速测试：采集前3页商品，匹配 ASIN 映射"""
import requests, json, time, sys, io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
API_URL = 'https://www.yeahpromos.com/index/apioffer/getoffer'

# 加载 asin_map
print("加载 ASIN 映射...")
with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
    asin_map = json.load(f)
print(f"  ASIN 映射: {len(asin_map):,} 个")

total_offers = 0
total_matched = 0
total_with_url = 0

for page in range(1, 4):
    print(f"\n--- 第 {page} 页 ---")
    resp = requests.get(API_URL, headers={'token': TOKEN}, params={'site_id': SITE_ID, 'page': page, 'limit': 100}, timeout=30)
    data = resp.json()
    offers = data.get('data', {}).get('data', [])
    total = data.get('data', {}).get('total', 0)
    
    print(f"  获取 {len(offers)} 条 (总数 {total:,})")
    total_offers += len(offers)
    
    page_matched = 0
    for o in offers:
        asin = str(o.get('asin', '')).strip()
        if asin in asin_map:
            map_data = asin_map[asin]
            page_matched += 1
            total_matched += 1
            if map_data.get('tracking_url'):
                total_with_url += 1
            if page_matched <= 3:
                name = o.get('product_name', '')[:50].encode('ascii', 'ignore').decode('ascii')
                merchant = map_data.get('merchant_name', '')[:20].encode('ascii', 'ignore').decode('ascii')
                has_url = "URL" if map_data.get('tracking_url') else "NO-URL"
                print(f"  [匹配] {asin} {name}... -> {merchant} [{has_url}]")
    
    print(f"  本页匹配: {page_matched} 条")
    time.sleep(6)

print(f"\n{'='*60}")
print(f"  3页汇总: 采集 {total_offers} 条, 匹配 {total_matched} 条 ({total_matched/max(total_offers,1)*100:.1f}%), 有链接 {total_with_url} 条")
print(f"  预估全量匹配率: {total_matched/max(total_offers,1)*100:.1f}%")
print(f"  预估全量有链接: {total_with_url} ({total_with_url/max(total_offers,1)*100:.1f}%)")
print(f"{'='*60}")
