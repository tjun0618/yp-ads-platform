"""快速查看飞书价格字段的实际值"""
import requests, json

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token}

resp = requests.get(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
    headers=headers, params={'page_size': 20})
items = resp.json().get('data', {}).get('items', [])

print(f"Sample records (first 20):\n")
for i, item in enumerate(items):
    fields = item.get('fields', {})
    
    def get_val(key):
        v = fields.get(key)
        if isinstance(v, list):
            return (v[0] if v else '') or ''
        return v or ''
    
    asin = get_val('ASIN')
    price = get_val('Price (USD)')
    name = str(get_val('Product Name'))[:40]
    payout = get_val('Payout (%)')
    url = get_val('Tracking URL')
    merchant = get_val('Merchant Name')
    status = get_val('推广状态')
    
    price_display = price if price else '-'
    url_short = 'Y' if url and str(url).strip() else 'N'
    
    name_safe = name.encode('ascii', 'replace').decode('ascii')
    print(f"  {i+1:>2}. ASIN={asin:<12} price={price_display:<12} comm={payout:<5} "
          f"merchant={str(merchant)[:15]:<15} url={url_short} status={status}")
    print(f"      name={name_safe}")
