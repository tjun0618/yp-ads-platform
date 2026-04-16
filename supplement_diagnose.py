# -*- coding: utf-8 -*-
"""
飞书数据补充检查：价格分析 + 商品名匹配
"""
import requests, json, time
import requests.adapters
from collections import Counter

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

session = requests.Session()
retry = requests.adapters.Retry(total=3, backoff_factor=1)
session.mount("https://", requests.adapters.HTTPAdapter(max_retries=retry))

def get_token():
    resp = session.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
                         json={'app_id': APP_ID, 'app_secret': APP_SECRET}, timeout=30)
    return resp.json()['tenant_access_token']

token = get_token()
headers = {'Authorization': 'Bearer ' + token}

# 读取所有记录
all_records = []
page_token = None
while True:
    params = {'page_size': 500}
    if page_token:
        params['page_token'] = page_token
    resp = session.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
        headers=headers, params=params, timeout=60)
    data = resp.json()
    items = data.get('data', {}).get('items', [])
    all_records.extend(items)
    page_token = data.get('data', {}).get('page_token')
    if not page_token or not items:
        break
    if len(all_records) % 3000 == 0:
        token = get_token()
        headers = {'Authorization': 'Bearer ' + token}

print(f"Total records: {len(all_records)}")

# ---- Price Analysis ----
print("\n=== PRICE ANALYSIS ===")
prices = []
price_zero = 0
price_samples = []

for rec in all_records:
    fields = rec.get('fields', {})
    price_raw = fields.get('Price (USD)')
    if price_raw is None:
        continue
    
    # price could be various types
    price_str = str(price_raw) if not isinstance(price_raw, str) else price_raw
    
    # Check if price has currency prefix
    has_usd_prefix = 'USD' in price_str.upper()
    has_eur_prefix = 'EUR' in price_str.upper()
    has_cad_prefix = 'CAD' in price_str.upper()
    
    try:
        # Extract number
        num_str = price_str.replace('USD', '').replace('EUR', '').replace('CAD', '').replace('$', '').replace(',', '').strip()
        price = float(num_str)
        
        if price == 0:
            price_zero += 1
        else:
            prices.append({
                'value': price,
                'original': price_str,
                'is_usd': has_usd_prefix or not (has_eur_prefix or has_cad_prefix),
                'asin': str(fields.get('ASIN', '')),
                'product_id': str(fields.get('Product ID', '')),
            })
    except (ValueError, TypeError):
        pass

print(f"Price=0: {price_zero}")
print(f"Valid prices: {len(prices)}")

# 价格分布
if prices:
    sorted_prices = sorted(prices, key=lambda x: x['value'])
    print(f"Min: {sorted_prices[0]['value']:.2f}")
    print(f"Max: {sorted_prices[-1]['value']:.2f}")
    median = sorted_prices[len(sorted_prices)//2]['value']
    print(f"Median: {median:.2f}")
    avg = sum(p['value'] for p in prices) / len(prices)
    print(f"Avg: {avg:.2f}")
    
    # 区间
    bins = [(0, 1), (1, 5), (5, 10), (10, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, float('inf'))]
    for lo, hi in bins:
        count = sum(1 for p in prices if lo <= p['value'] < hi)
        pct = count / len(prices) * 100
        bar = '#' * int(pct / 2)
        label = f"${lo}-${hi}" if hi != float('inf') else f"${lo}+"
        print(f"  {label:>12}: {count:>5} ({pct:5.1f}%) {bar}")
    
    # 抽样低价和高价
    print("\n  Lowest 10 prices:")
    for p in sorted_prices[:10]:
        print(f"    ASIN={p['asin']} PID={p['product_id']} price={p['original']}")
    
    print("\n  Highest 10 prices:")
    for p in sorted_prices[-10:]:
        print(f"    ASIN={p['asin']} PID={p['product_id']} price={p['original']}")

# ---- Product Name vs Merchant Name ----
print("\n=== PRODUCT NAME vs MERCHANT NAME ===")
match_count = 0
mismatch_count = 0
checked = 0
mismatches = []

for rec in all_records:
    fields = rec.get('fields', {})
    
    # 检查有链接的
    url = fields.get('Tracking URL')
    if isinstance(url, list):
        url = url[0] if url else ''
    if not url or not str(url).strip():
        continue
    
    merchant = fields.get('Merchant Name')
    if isinstance(merchant, list):
        merchant = merchant[0] if merchant else ''
    
    name = fields.get('Product Name')
    if isinstance(name, list):
        name = name[0] if name else ''
    
    if not merchant or not name:
        continue
    
    merchant = str(merchant).strip().upper()
    name_upper = str(name).strip().upper()
    
    checked += 1
    
    # 商户名关键部分
    merchant_clean = merchant.replace('US', '').replace('INC', '').replace('LLC', '').replace('LTD', '').replace(',', '').strip()
    parts = [w for w in merchant_clean.split() if len(w) > 2]
    
    found = any(p in name_upper for p in parts)
    
    if found:
        match_count += 1
    else:
        mismatch_count += 1
        asin = str(fields.get('ASIN', ''))
        if len(mismatches) < 10:
            mismatches.append(f"ASIN={asin} | merchant={merchant} | name={str(name)[:60]}")

print(f"Checked: {checked}")
print(f"Match: {match_count} ({match_count/checked*100:.1f}%)" if checked else "N/A")
print(f"Mismatch: {mismatch_count} ({mismatch_count/checked*100:.1f}%)" if checked else "N/A")
print("\nMismatch samples:")
for m in mismatches:
    safe = m.encode('ascii', 'replace').decode('ascii')
    print(f"  {safe}")

# ---- Collected At ----
print("\n=== COLLECTED AT ===")
dates = Counter()
for rec in all_records:
    ct = rec.get('fields', {}).get('Collected At')
    if isinstance(ct, list):
        ct = ct[0] if ct else ''
    ct = str(ct).strip()[:10]
    if ct:
        dates[ct] += 1

for d, c in sorted(dates.items()):
    print(f"  {d}: {c}")

# ---- Product Status ----
print("\n=== PRODUCT STATUS ===")
statuses = Counter()
for rec in all_records:
    ps = rec.get('fields', {}).get('Product Status')
    if isinstance(ps, list):
        ps = ps[0] if ps else ''
    statuses[str(ps)] += 1

for s, c in statuses.most_common():
    print(f"  {s}: {c}")

print("\nDone.")
