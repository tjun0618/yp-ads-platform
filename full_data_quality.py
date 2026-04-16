"""完整数据质量诊断"""
import requests, json

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token}

def get_val(fields, key):
    v = fields.get(key)
    if isinstance(v, list):
        return (v[0] if v else '') or ''
    return v or ''

# 获取全部记录
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

# 统计
price_zero = 0
price_valid = 0
price_missing = 0
has_url = 0
has_url_usable = 0
has_merchant = 0
status_empty = 0

for rec in all_records:
    fields = rec.get('fields', {})
    
    price = get_val(fields, 'Price (USD)')
    try:
        pval = float(price)
        if pval == 0:
            price_zero += 1
        else:
            price_valid += 1
    except:
        price_missing += 1
    
    url = get_val(fields, 'Tracking URL')
    if url and url.strip():
        has_url += 1
    
    mid = get_val(fields, 'Merchant ID')
    if mid and mid.strip():
        has_merchant += 1
    
    status = get_val(fields, 'promotion_status' if 'promotion_status' in fields else '推广状态')
    if not status or not status.strip():
        status_empty += 1

print(f"Total records: {total}")
print()
print("DATA QUALITY SUMMARY")
print("=" * 60)
print()
print(f"  Price > 0:       {price_valid:>5} ({price_valid/total*100:.1f}%)  <- Potentially usable")
print(f"  Price = 0:       {price_zero:>5} ({price_zero/total*100:.1f}%)  <- No price data")
print(f"  Price invalid:   {price_missing:>5} ({price_missing/total*100:.1f}%)")
print()
print(f"  Has Tracking URL:{has_url:>5} ({has_url/total*100:.1f}%)")
print(f"  Has Merchant ID: {has_merchant:>5} ({has_merchant/total*100:.1f}%)")
print(f"  Status empty:    {status_empty:>5} ({status_empty/total*100:.1f}%)")

# 交叉分析：有URL + 价格 > 0
url_and_price = 0
for rec in all_records:
    fields = rec.get('fields', {})
    url = get_val(fields, 'Tracking URL')
    price = get_val(fields, 'Price (USD)')
    if url and url.strip():
        try:
            if float(price) > 0:
                url_and_price += 1
        except:
            pass

print()
print("CROSS ANALYSIS")
print("=" * 60)
print(f"  Has URL AND price > 0:  {url_and_price}  <- BEST candidates for ads")
print(f"  Has URL BUT price = 0:  {has_url - url_and_price}")
print()

# 价格分布
prices = []
for rec in all_records:
    fields = rec.get('fields', {})
    price = get_val(fields, 'Price (USD)')
    try:
        pval = float(price)
        if pval > 0:
            prices.append(pval)
    except:
        pass

if prices:
    prices.sort()
    print("PRICE DISTRIBUTION (price > 0)")
    print("=" * 60)
    print(f"  Min:    ${min(prices):.2f}")
    print(f"  Median: ${prices[len(prices)//2]:.2f}")
    print(f"  Max:    ${max(prices):.2f}")
    
    buckets = [0, 10, 20, 30, 50, 100, 200, 500, 1000, 99999]
    labels = ['0-10', '10-20', '20-30', '30-50', '50-100', '100-200', '200-500', '500-1000', '1000+']
    for i in range(len(labels)):
        lo, hi = buckets[i], buckets[i+1]
        cnt = sum(1 for p in prices if lo <= p < hi)
        bar = '#' * (cnt // 5)
        print(f"  ${labels[i]:>8}  {cnt:>5}  {bar}")

print()
print("=" * 60)
print("BOTTOM LINE")
print("=" * 60)
print()
print(f"  Feishu table has {total} records from API collection")
print(f"  BUT:")
print(f"    - Price field lost currency prefix (USD/EUR/CAD mixed)")
print(f"      Cannot distinguish US vs EU products by price alone")
print(f"    - {price_zero} records have price=0 (no pricing data)")
print(f"    - Only {has_url} records have tracking URLs ({has_url/total*100:.1f}%)")
print(f"    - {has_merchant} records have merchant mapping ({has_merchant/total*100:.1f}%)")
print(f"    - {status_empty} records still missing status ({status_empty/total*100:.1f}%)")
print()
print(f"  MOST RELIABLE APPROACH:")
print(f"    1. Import Excel downloads from approved brand pages")
print(f"    2. These have: correct price, correct commission, valid tracking URL")
print(f"    3. Use API data only for discovery, not for actual ad deployment")
