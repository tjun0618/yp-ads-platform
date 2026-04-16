"""
对比 Excel 下载的 YP 商品数据 vs 飞书 API 采集数据 vs 本地 asin_map
"""
import openpyxl, requests, json

EXCEL_FILE = r'C:\Users\wuhj\Downloads\Offer_20260323232258_2131.xlsx'
APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'
TARGET_ASIN = 'B07FRRHPJD'

# 1. 读取 Excel
print("Loading Excel...")
wb = openpyxl.load_workbook(EXCEL_FILE, read_only=True)
ws = wb.active

excel_data = {}
for row in ws.iter_rows(min_row=2, values_only=True):
    if row[0]:
        asin = str(row[0]).strip()
        excel_data[asin] = {
            'name': row[1] or '',
            'category': row[2] or '',
            'commission': str(row[3]) if row[3] else '',
            'price': str(row[4]) if row[4] else '',
            'tracking_link': row[5] or ''
        }

print(f"Excel: {len(excel_data)} products loaded")

# 2. 飞书认证
resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token}

# 3. 获取所有飞书 ASIN
print("Loading Feishu records...")
all_feishu_records = {}  # asin -> fields
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
    for item in items:
        fields = item.get('fields', {})
        asin_raw = fields.get('ASIN', '')
        if isinstance(asin_raw, list):
            asin = (asin_raw[0] if asin_raw else '') or ''
        else:
            asin = asin_raw or ''
        asin = asin.strip()
        if asin:
            all_feishu_records[asin] = fields
    page_token = data.get('data', {}).get('page_token')
    if not page_token or not items:
        break

print(f"Feishu: {len(all_feishu_records)} records loaded")

# 4. 加载 asin_map
print("Loading asin_map...")
with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
    asin_map = json.load(f)
print(f"asin_map: {len(asin_map)} entries loaded")

# ===== 对比 B07FRRHPJD =====
print()
print("=" * 80)
print(f"ASIN: {TARGET_ASIN}")
print("=" * 80)

print()
print("[1] Excel (YP Brand Page Download)")
if TARGET_ASIN in excel_data:
    e = excel_data[TARGET_ASIN]
    print(f"  Name:         {e['name'][:80]}")
    print(f"  Category:     {e['category']}")
    print(f"  Commission:   {e['commission']}")
    print(f"  Price:        {e['price']}")
    print(f"  Tracking Link:{e['tracking_link']}")
else:
    print("  NOT FOUND")

print()
print("[2] Feishu (API)")
if TARGET_ASIN in all_feishu_records:
    f_fields = all_feishu_records[TARGET_ASIN]
    for k, v in f_fields.items():
        if isinstance(v, list):
            v = v[0] if v else ''
        val_str = str(v) if v else '(empty)'
        if len(val_str) > 80:
            val_str = val_str[:80] + '...'
        print(f"  {k}: {val_str}")
else:
    print("  NOT FOUND in Feishu")

print()
print("[3] asin_map (Web Scrape)")
if TARGET_ASIN in asin_map:
    m = asin_map[TARGET_ASIN]
    for k, v in m.items():
        val_str = str(v) if v else '(empty)'
        if len(val_str) > 80:
            val_str = val_str[:80] + '...'
        print(f"  {k}: {val_str}")
else:
    print("  NOT FOUND in asin_map")

# ===== 总体统计 =====
print()
print("=" * 80)
print("Overall Coverage Statistics")
print("=" * 80)
print(f"Excel total products:       {len(excel_data)}")
print(f"Feishu total records:       {len(all_feishu_records)}")
print(f"asin_map total entries:     {len(asin_map)}")
print()

in_feishu = sum(1 for a in excel_data if a in all_feishu_records)
in_map = sum(1 for a in excel_data if a in asin_map)
in_both = sum(1 for a in excel_data if a in all_feishu_records and a in asin_map)
not_in_any = sum(1 for a in excel_data if a not in all_feishu_records and a not in asin_map)

# Excel 有 tracking link 的
excel_with_link = sum(1 for a, d in excel_data.items() if d['tracking_link'])
excel_no_link = len(excel_data) - excel_with_link

print(f"Excel in Feishu:            {in_feishu}/{len(excel_data)} ({in_feishu/len(excel_data)*100:.1f}%)")
print(f"Excel in asin_map:          {in_map}/{len(excel_data)} ({in_map/len(excel_data)*100:.1f}%)")
print(f"Excel in both:              {in_both}/{len(excel_data)} ({in_both/len(excel_data)*100:.1f}%)")
print(f"Excel not in any:           {not_in_any}/{len(excel_data)} ({not_in_any/len(excel_data)*100:.1f}%)")
print()
print(f"Excel with tracking link:   {excel_with_link}")
print(f"Excel without tracking link:{excel_no_link}")

# Excel 在飞书中但没 tracking URL 的
excel_in_feishu_no_url = 0
excel_in_feishu_has_url = 0
for asin in excel_data:
    if asin in all_feishu_records:
        url = all_feishu_records[asin].get('Tracking URL', '')
        if isinstance(url, list):
            url = url[0] if url else ''
        if url and url.strip():
            excel_in_feishu_has_url += 1
        else:
            excel_in_feishu_no_url += 1

print()
print(f"Excel->Feishu with URL:    {excel_in_feishu_has_url}")
print(f"Excel->Feishu without URL: {excel_in_feishu_no_url}")

# 对比差异示例
print()
print("=" * 80)
print("Sample Comparison (first 5 Excel products)")
print("=" * 80)

count = 0
for asin, e_data in list(excel_data.items())[:5]:
    in_f = "Y" if asin in all_feishu_records else "N"
    in_m = "Y" if asin in asin_map else "N"
    
    # 飞书中的佣金
    f_commission = "-"
    if asin in all_feishu_records:
        fc = all_feishu_records[asin].get('Payout (%)', '')
        if isinstance(fc, list):
            fc = fc[0] if fc else ''
        f_commission = str(fc) if fc else "-"
    
    # 飞书中的价格
    f_price = "-"
    if asin in all_feishu_records:
        fp = all_feishu_records[asin].get('Price (USD)', '')
        if isinstance(fp, list):
            fp = fp[0] if fp else ''
        f_price = str(fp) if fp else "-"
    
    # asin_map 中有 tracking url
    map_url = "-"
    if asin in asin_map and asin_map[asin]:
        mu = asin_map[asin].get('tracking_url', '')
        if mu:
            map_url = "Y"
        else:
            map_url = "N"
    
    name_short = e_data['name'][:50] if e_data['name'] else ''
    print(f"\n  ASIN: {asin}")
    print(f"    Name: {name_short}")
    print(f"    Excel: comm={e_data['commission']} price={e_data['price']} link={'Y' if e_data['tracking_link'] else 'N'}")
    print(f"    Feishu({in_f}): comm={f_commission} price={f_price}")
    print(f"    Map({in_m}): url={map_url}")
    count += 1

print()
print("=" * 80)
print("Key Findings:")
print("=" * 80)
print(f"1. NORTIV 8 (MID:362548) has {len(excel_data)} products on YP brand page")
print(f"2. Only {in_feishu} ({in_feishu/len(excel_data)*100:.1f}%) appear in Feishu Offers table")
print(f"3. Only {in_map} ({in_map/len(excel_data)*100:.1f}%) appear in local asin_map")
print(f"4. {not_in_any} ({not_in_any/len(excel_data)*100:.1f}%) are in neither source")
print(f"5. All {excel_with_link} Excel products have tracking links (brand is approved)")
