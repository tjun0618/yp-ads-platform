"""
检查 Product ID=1333492 / ASIN=B07FRRHPJD 的商品信息
从 API 直接查询，对比价格差异
"""
import requests, json

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
headers = {'token': TOKEN}
TARGET_ASIN = 'B07FRRHPJD'
TARGET_PID = '1333492'

# 1. 检查 API 返回的所有字段
print("=" * 80)
print("[1] API getoffer - 检查返回字段结构")
print("=" * 80)

params = {'site_id': SITE_ID, 'page': 1, 'limit': 2}
resp = requests.get('https://www.yeahpromos.com/index/apioffer/getoffer', headers=headers, params=params, timeout=30)
data = resp.json()
if data.get('status') == 'SUCCESS':
    items = data['data'].get('data', [])
    if items:
        print("API 返回的全部字段:")
        for k, v in items[0].items():
            val = str(v)
            if len(val) > 100:
                val = val[:100] + '...'
            print(f"  {k}: {val}")

# 2. 搜索该 ASIN 在 API 中的信息
print()
print("=" * 80)
print(f"[2] Search ASIN={TARGET_ASIN} in API")
print("=" * 80)

# 尝试多种搜索方式
found_by_search = None

# 方式A: 在 getoffer 中翻页搜索（从本地已采集数据中查找）
try:
    with open('output/offers_data.json', 'r', encoding='utf-8') as f:
        local_offers = json.load(f)
    
    for o in local_offers:
        if str(o.get('asin', '')) == TARGET_ASIN:
            found_by_search = o
            break
    
    if found_by_search:
        print("Found in local offers_data.json:")
        for k, v in found_by_search.items():
            val = str(v)
            if len(val) > 100:
                val = val[:100] + '...'
            print(f"  {k}: {val}")
    else:
        print("NOT found in local offers_data.json")
except Exception as e:
    print(f"Error reading local offers: {e}")

# 3. 直接访问亚马逊页面查看真实价格
print()
print("=" * 80)
print(f"[3] Amazon page check for ASIN={TARGET_ASIN}")
print("=" * 80)

import re
try:
    resp = requests.get(f'https://www.amazon.com/dp/{TARGET_ASIN}', 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                 'Accept-Language': 'en-US,en;q=0.9'},
        timeout=15)
    
    if resp.status_code == 200:
        html = resp.text
        
        # 提取标题
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
        title = title_match.group(1).strip() if title_match else 'N/A'
        print(f"  Title: {title[:100]}")
        
        # 提取价格
        price_patterns = [
            r'"priceAmount"\s*:\s*"?([\d.]+)"?',
            r'class="a-offscreen">\$([\d,.]+)',
            r'"lowPrice"\s*:\s*"?([\d.]+)"?',
            r'data-price="([\d.]+)"',
            r'current-price[^>]*>\s*\$?([\d,.]+)',
        ]
        
        prices = []
        for p in price_patterns:
            matches = re.findall(p, html)
            for m in matches:
                try:
                    price_val = float(m.replace(',', ''))
                    if 0 < price_val < 10000:
                        prices.append(price_val)
                except:
                    pass
        
        if prices:
            print(f"  Prices found: {set(prices)}")
        else:
            print("  Price: not extracted (page may require JS)")
        
        # 提取品牌
        brand_match = re.search(r'"brand"\s*:\s*"([^"]+)"', html)
        brand = brand_match.group(1) if brand_match else 'N/A'
        print(f"  Brand: {brand}")
        
    else:
        print(f"  HTTP {resp.status_code}")
except Exception as e:
    print(f"  Error: {e}")

# 4. 对比分析
print()
print("=" * 80)
print("[4] Price Discrepancy Analysis")
print("=" * 80)
print(f"  Excel (YP NORTIV 8):    USD 69.99")
print(f"  Feishu (API):           28.44")
print()
print(f"  Possible reasons:")
print(f"  1. API price is the product price, not the listed price")
print(f"  2. Different merchants show different prices for same ASIN")
print(f"  3. YP API price field may not be the Amazon selling price")
print(f"  4. Price discrepancy between DREAM PAIRS view vs NORTIV 8 view")
print()
print(f"  Key question: Is Product ID=1333492 really under DREAM PAIRS (MID:362851)?")
print(f"  Or is it misattributed by the API?")

# 5. 检查 DREAM PAIRS 网页上是否有这个商品
print()
print("=" * 80)
print("[5] Check DREAM PAIRS merchant page (MID:362851)")
print("=" * 80)

try:
    resp = requests.get('https://www.yeahpromos.com/index/offer/brand_detail?advert_id=362851&site_id=12002',
        cookies={'PHPSESSID': '5tg1c06l5m15bd4d7rbu6gqbn2'},
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        timeout=30)
    
    if resp.status_code == 200:
        html = resp.text
        # 搜索 B07FRRHPJD
        if TARGET_ASIN in html:
            # 找到上下文
            idx = html.index(TARGET_ASIN)
            context = html[max(0,idx-200):idx+200]
            print(f"  FOUND B07FRRHPJD on DREAM PAIRS page!")
            # 提取价格
            price_match = re.search(r'\$([\d,.]+)', context)
            if price_match:
                print(f"  Price on page: ${price_match.group(1)}")
        else:
            print(f"  NOT found on DREAM PAIRS page")
            
        # 统计该页面有多少产品
        all_asins = re.findall(r'/dp/([A-Z0-9]{10})', html)
        unique_asins = set(all_asins)
        print(f"  Total ASINs on DREAM PAIRS page: {len(unique_asins)}")
    else:
        print(f"  HTTP {resp.status_code}")
except Exception as e:
    print(f"  Error: {e}")
