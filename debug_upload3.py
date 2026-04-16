import json, requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
BASE_URL = 'https://open.feishu.cn/open-apis'

r = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Use the latest bitable
app_token = 'CffObPI28aNhwFsBb5pcU050nfc'
merchants_table_id = 'tblC8RRyaSopZaip'

url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{merchants_table_id}/records/batch_create'

# Test with just text fields (no URL, no select)
record = {
    'fields': {
        'Merchant ID': 111334,
        'Merchant Name': 'Farfetch US',
        'Avg Payout (%)': 0,
        'Cookie Days': 30,
        'Country': 'AU - Australia',
        'Transaction Type': 'CPS',
    }
}
resp = requests.post(url, headers=headers, json={'records': [record]})
print(f"Test1 basic: code={resp.json().get('code')} msg={resp.json().get('msg')}")

# Test with select field
record2 = {
    'fields': {
        'Merchant ID': 111335,
        'Merchant Name': 'iHerb',
        'Avg Payout (%)': 0.75,
        'Cookie Days': 45,
        'Country': 'US - United States',
        'Transaction Type': 'CPS',
        'Status': 'UNAPPLIED',
        'Online Status': 'onLine',
        'Deep Link': 'Yes',
    }
}
resp2 = requests.post(url, headers=headers, json={'records': [record2]})
print(f"Test2 with select: code={resp2.json().get('code')} msg={resp2.json().get('msg')}")

# Test with URL as text (plain string)
record3 = {
    'fields': {
        'Merchant ID': 111336,
        'Merchant Name': 'Test URL',
        'Website': 'https://www.iherb.com',
    }
}
resp3 = requests.post(url, headers=headers, json={'records': [record3]})
print(f"Test3 with URL text: code={resp3.json().get('code')} msg={resp3.json().get('msg')}")
if resp3.json().get('code') != 0:
    print(f"  Full resp: {json.dumps(resp3.json())[:500]}")
