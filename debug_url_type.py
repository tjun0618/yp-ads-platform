import json, requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
BASE_URL = 'https://open.feishu.cn/open-apis'

r = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
app_token = 'CffObPI28aNhwFsBb5pcU050nfc'
table_id = 'tblC8RRyaSopZaip'

# List all fields with full details
url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields'
resp = requests.get(url, headers=headers)
data = resp.json()
if data.get('code') == 0:
    for f in data['data']['items']:
        name = f['field_name']
        ftype = f['type']
        prop = json.dumps(f.get('property', {}), ensure_ascii=False)
        print(f"  {name}: type={ftype}, property={prop}")
else:
    print('Error:', data)

# Try to create a URL field with a different approach
print("\n--- Creating a new URL field with type=17 (url type) ---")
# Actually, the correct type for URL might be different
# Let me check by trying to use type=11 with no property
