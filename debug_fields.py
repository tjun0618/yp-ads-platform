import json, requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
BASE_URL = 'https://open.feishu.cn/open-apis'

r = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

app_token = 'RpI6bMSqHaPBiSsLCaucn34bnE9'
table_id = 'tblej1bjERXgVHbO'

# List fields
url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields'
resp = requests.get(url, headers=headers)
data = resp.json()
if data.get('code') == 0:
    for f in data['data']['items']:
        prop = f.get('property', '')
        print(f"  {f['field_name']}: type={f['type']} property={prop}")
else:
    print('Error:', data)
