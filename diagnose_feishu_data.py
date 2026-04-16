"""
诊断飞书 Offers 表现有数据质量问题
"""
import requests, json

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

# 飞书认证
resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token}

# 获取全部记录
print("Loading all Feishu records...")
all_records = []
page_token = None

while True:
    params = {'page_size': 500}
    if page_token:
        params['page_token'] = page_token
    resp = requests.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
        headers=headers, params=params)
    data = resp.json()
    items = data.get('data', {}).get('items', [])
    all_records.extend(items)
    page_token = data.get('data', {}).get('page_token')
    if not page_token or not items:
        break

total = len(all_records)
print(f"Total: {total} records\n")

# 统计各维度
usd_count = 0
eur_count = 0
cad_count = 0
gbp_count = 0
other_currency = 0
no_price = 0

has_tracking_url = 0
no_tracking_url = 0
has_merchant = 0
no_merchant = 0

status_stats = {}
currency_details = {'USD': [], 'EUR': [], 'CAD': [], 'GBP': [], 'OTHER': []}

for rec in all_records:
    fields = rec.get('fields', {})
    
    # 推广状态
    status_raw = fields.get('推广状态')
    if isinstance(status_raw, list):
        status = (status_raw[0] if status_raw else '') or ''
    else:
        status = status_raw or ''
    status = str(status).strip() if status else '(empty)'
    status_stats[status] = status_stats.get(status, 0) + 1
    
    # 价格货币
    price_raw = fields.get('Price (USD)')
    if isinstance(price_raw, list):
        price = (price_raw[0] if price_raw else '') or ''
    else:
        price = price_raw or ''
    price = str(price).strip() if price else ''
    
    if not price:
        no_price += 1
    elif 'USD' in price.upper():
        usd_count += 1
        currency_details['USD'].append(price)
    elif 'EUR' in price.upper():
        eur_count += 1
        currency_details['EUR'].append(price)
    elif 'CAD' in price.upper():
        cad_count += 1
        currency_details['CAD'].append(price)
    elif 'GBP' in price.upper():
        gbp_count += 1
        currency_details['GBP'].append(price)
    else:
        other_currency += 1
        currency_details['OTHER'].append(price[:40])
    
    # Tracking URL
    url_raw = fields.get('Tracking URL')
    if isinstance(url_raw, list):
        url = (url_raw[0] if url_raw else '') or ''
    else:
        url = url_raw or ''
    url = str(url).strip() if url else ''
    
    if url:
        has_tracking_url += 1
    else:
        no_tracking_url += 1
    
    # Merchant
    mid_raw = fields.get('Merchant ID')
    if isinstance(mid_raw, list):
        mid = (mid_raw[0] if mid_raw else '') or ''
    else:
        mid = mid_raw or ''
    mid = str(mid).strip() if mid else ''
    
    if mid:
        has_merchant += 1
    else:
        no_merchant += 1

# ============ 输出 ============
print("=" * 70)
print("1. Currency Distribution")
print("=" * 70)
print(f"  USD:    {usd_count:>5} ({usd_count/total*100:.1f}%)")
print(f"  EUR:    {eur_count:>5} ({eur_count/total*100:.1f}%)")
print(f"  CAD:    {cad_count:>5} ({cad_count/total*100:.1f}%)")
print(f"  GBP:    {gbp_count:>5} ({gbp_count/total*100:.1f}%)")
print(f"  Other:  {other_currency:>5} ({other_currency/total*100:.1f}%)")
print(f"  No price: {no_price:>5} ({no_price/total*100:.1f}%)")

print()
print("=" * 70)
print("2. Tracking URL Status")
print("=" * 70)
print(f"  Has Tracking URL:     {has_tracking_url:>5} ({has_tracking_url/total*100:.1f}%)")
print(f"  No Tracking URL:      {no_tracking_url:>5} ({no_tracking_url/total*100:.1f}%)")

print()
print("=" * 70)
print("3. Merchant Mapping")
print("=" * 70)
print(f"  Has Merchant ID:      {has_merchant:>5} ({has_merchant/total*100:.1f}%)")
print(f"  No Merchant ID:       {no_merchant:>5} ({no_merchant/total*100:.1f}%)")

print()
print("=" * 70)
print("4. Promotion Status")
print("=" * 70)
for s, c in sorted(status_stats.items(), key=lambda x: -x[1]):
    print(f"  {s:<15} {c:>5} ({c/total*100:.1f}%)")

# ============ 核心问题分析 ============
print()
print("=" * 70)
print("5. KEY PROBLEMS")
print("=" * 70)

non_usd = total - usd_count
print(f"\n  Problem 1: Non-USD products (useless for US market)")
print(f"    EUR/CAD/GBP/Other: {non_usd} records ({non_usd/total*100:.1f}%)")
print(f"    These products are from EU/CA/UK Amazon stores")
print(f"    Their tracking links point to non-US Amazon pages")
print(f"    -> ACTION: Should be removed or filtered out")

print(f"\n  Problem 2: Tracking URL reliability")
print(f"    Has URL: {has_tracking_url}")
usd_with_url = 0
eur_with_url = 0
for rec in all_records:
    fields = rec.get('fields', {})
    url_raw = fields.get('Tracking URL')
    if isinstance(url_raw, list):
        url = (url_raw[0] if url_raw else '') or ''
    else:
        url = url_raw or ''
    url = str(url).strip() if url else ''
    
    price_raw = fields.get('Price (USD)')
    if isinstance(price_raw, list):
        price = (price_raw[0] if price_raw else '') or ''
    else:
        price = price_raw or ''
    price = str(price).strip() if price else ''
    
    if url:
        if 'USD' in price.upper():
            usd_with_url += 1
        elif 'EUR' in price.upper():
            eur_with_url += 1

print(f"    Of those with URL: USD={usd_with_url}, EUR={eur_with_url}")
print(f"    EUR URLs point to European Amazon -> useless for US Google Ads")
print(f"    -> ACTION: Need to verify URL destination is amazon.com not amazon.de/fr")

print(f"\n  Problem 3: Merchant attribution")
print(f"    API assigns products to merchants unreliably")
print(f"    Same ASIN under different merchants = different commissions")
print(f"    -> ACTION: Need to match against brand page data (Excel download)")

# 可用数据统计
print()
print("=" * 70)
print("6. USABLE DATA (for US market Google Ads)")
print("=" * 70)
print(f"  Total records:                      {total}")
print(f"  Minus non-USD:                     -{non_usd}")
print(f"  Minus no tracking URL:             -{no_tracking_url}")
print(f"  = Roughly usable:                   ~{usd_count - (usd_count - usd_with_url if usd_count else 0)}")
print(f"    (USD products with tracking URLs)")
print()
print(f"  But even these may have issues:")
print(f"  - Merchant attribution may be wrong")
print(f"  - Tracking URL may point to wrong merchant")
print(f"  - Commission rate may not match actual merchant")
print(f"  - Price may be outdated")

print()
print("=" * 70)
print("RECOMMENDATION")
print("=" * 70)
print()
print("The most reliable data source is: YP Brand Page Excel Download")
print("  - Contains ONLY the merchant's own products")
print("  - All have valid tracking links (already approved)")
print("  - Currency is consistent (merchant-specific)")
print("  - Commission is the correct rate for that merchant")
print()
print("Suggested workflow:")
print("  1. Filter Feishu: keep only USD records with tracking URLs")
print("  2. For approved brands: import their Excel downloads (most reliable)")
print("  3. Use API data only as backup/supplement for unapproved brands")
