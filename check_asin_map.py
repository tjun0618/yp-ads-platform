import json
from bs4 import BeautifulSoup

# 检查之前的抓取记录
with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
    asin_map = json.load(f)

print(f"ASIN 映射总记录数: {len(asin_map)}")

# 看几条记录的结构
first_keys = list(asin_map.keys())[:5]
print(f"\n前5条记录:")
for key in first_keys:
    data = asin_map[key]
    print(f"\nASIN: {key}")
    print(f"  商品名: {data.get('product_name', 'N/A')[:60]}...")
    print(f"  商户ID: {data.get('merchant_id', 'N/A')}")
    print(f"  商户名: {data.get('merchant_name', 'N/A')}")
    print(f"  Track: {data.get('track', 'N/A')}")
    print(f"  投放链接: {data.get('tracking_url', 'N/A')[:80] if data.get('tracking_url') else 'N/A'}...")

# 检查有多少记录有投放链接
has_tracking = sum(1 for v in asin_map.values() if v.get('tracking_url'))
print(f"\n有投放链接的记录: {has_tracking} / {len(asin_map)} ({has_tracking/len(asin_map)*100:.1f}%)")

# 看看之前抓取成功的 brand_detail HTML 是否还有保存
import os
html_files = [f for f in os.listdir('output') if 'brand_detail' in f.lower() and f.endswith('.html')]
print(f"\n保存的 brand_detail HTML 文件:")
for f in html_files:
    size = os.path.getsize(os.path.join('output', f))
    print(f"  {f} ({size:,} bytes)")
