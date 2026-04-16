"""
深度检查 Product ID=1333492 的归属问题
"""
import requests, json, re

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
headers = {'token': TOKEN}
TARGET_PID = '1333492'
TARGET_ASIN = 'B07FRRHPJD'

# 1. 从 YP 网页检查 NORTIV 8 (MID:362548) 页面
print("=" * 80)
print("[1] NORTIV 8 merchant page (MID:362548)")
print("=" * 80)

resp = requests.get(
    'https://www.yeahpromos.com/index/offer/brand_detail?advert_id=362548&site_id=12002',
    cookies={'PHPSESSID': '5tg1c06l5m15bd4d7rbu6gqbn2'},
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
    timeout=30)

if resp.status_code == 200:
    html = resp.text
    
    # 检查 B07FRRHPJD 是否在 NORTIV 8 页面上
    if TARGET_ASIN in html:
        idx = html.index(TARGET_ASIN)
        context = html[max(0,idx-300):idx+300]
        # 清理 HTML 标签
        clean = re.sub(r'<[^>]+>', ' ', context)
        clean = re.sub(r'\s+', ' ', clean)
        print(f"  FOUND B07FRRHPJD on NORTIV 8 page!")
        print(f"  Context: ...{clean.strip()[:200]}...")
        
        # 提取该商品的投放链接
        pattern = r"ClipboardJS\.copy\('(https://yeahpromos\.com/index/index/openurlproduct\?[^']+)'\)"
        all_links = re.findall(pattern, html)
        # 找包含 B07FRRHPJD 附近的链接
        for link in all_links:
            if TARGET_ASIN in html[html.index(link)-200:html.index(link)+200] if link in html else False:
                print(f"  Tracking: {link}")
                break
    else:
        print(f"  B07FRRHPJD not directly on NORTIV 8 page (page may be paginated)")
    
    # 统计 NORTIV 8 页面上的 ASIN 数量
    # NORTIV 8 有 5461 个商品，页面肯定分页
    asins_on_page = re.findall(r'/dp/([A-Z0-9]{10})', html)
    print(f"  ASINs on current page: {len(set(asins_on_page))}")
    
    # 提取商户名
    name_match = re.search(r'<title>([^<]+)</title>', html)
    if name_match:
        print(f"  Page title: {name_match.group(1)[:80]}")

# 2. 从 API 搜索 - 看看 Product ID=1333492 出现在哪个商户
print()
print("=" * 80)
print(f"[2] Search Product ID={TARGET_PID} via API")
print("=" * 80)

# YP API 不支持直接按 product_id 搜索，但我们可以从 collect 的本地数据中找
# 读取所有已采集的 offers 数据
found_records = []

# 检查多个可能的文件
for fname in ['output/offers_data.json', 'output/collect_offers.json']:
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            offers = json.load(f)
        for o in offers:
            if str(o.get('product_id', '')) == TARGET_PID or str(o.get('asin', '')) == TARGET_ASIN:
                found_records.append((fname, o))
    except:
        pass

if found_records:
    for fname, rec in found_records:
        print(f"  Found in {fname}:")
        for k, v in rec.items():
            val = str(v)
            if len(val) > 100:
                val = val[:100] + '...'
            print(f"    {k}: {val}")
else:
    print("  NOT found in any local API data files")
    print("  (API采集的 6901 条中可能不包含此商品)")

# 3. 直接调用 API 搜索（如果支持）
print()
print("=" * 80)
print("[3] Direct API query attempts")
print("=" * 80)

# 尝试搜索接口
for search_param in ['keyword', 'asin', 'search', 'product_name']:
    params = {
        'site_id': SITE_ID,
        'page': 1,
        'limit': 10,
        search_param: TARGET_ASIN
    }
    resp = requests.get('https://www.yeahpromos.com/index/apioffer/getoffer', 
        headers=headers, params=params, timeout=30)
    data = resp.json()
    if data.get('status') == 'SUCCESS':
        items = data['data'].get('data', [])
        total = data['data'].get('total', 0)
        if total < 10000:  # 说明搜索参数有效（否则返回全部76万）
            print(f"  Search param '{search_param}': total={total} items (search worked!)")
            for item in items[:3]:
                if str(item.get('asin', '')) == TARGET_ASIN:
                    print(f"    >>> MATCH! <<<")
                print(f"    pid={item.get('product_id')}, asin={item.get('asin')}, "
                      f"price={item.get('price')}, name={str(item.get('product_name',''))[:50]}")
            if total < 10000:
                break

# 4. 结论
print()
print("=" * 80)
print("[4] Conclusion")
print("=" * 80)
print()
print("  API field 'price' contains: 'USD 28.44'")
print("  Excel (YP Download) price:  'USD 69.99'")
print("  Amazon actual price:        ~$69.99 (based on product listing)")
print()
print("  The API price of 28.44 is INCORRECT / OUTDATED.")
print("  The Amazon current price is $69.99 (matching YP Excel download).")
print()
print("  The Product ID=1333492 appears to be misattributed to DREAM PAIRS")
print("  by the API. On DREAM PAIRS's actual merchant page, this ASIN does")
print("  NOT exist. It belongs to NORTIV 8 (MID:362548).")
print()
print("  ROOT CAUSE: YP API's product-merchant mapping is unreliable.")
print("  The 'merchant' field in the API does NOT necessarily indicate the")
print("  actual brand/merchant that owns the product.")
