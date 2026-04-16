import json, requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
BASE_URL = 'https://open.feishu.cn/open-apis'

r = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Create a test relation field on the Merchants table
app_token = 'RpI6bMSqHaPBiSsLCaucn34bnE9'
table_id = 'tblej1bjERXgVHbO'  # Merchants table
foreign_table_id = 'tbla09upkskprDsg'  # Categories table

url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields'

# Try type as string "relation"
body1 = {
    "field_name": "Test Relation String",
    "type": "relation",
    "property": {"foreign_table_id": foreign_table_id}
}
resp1 = requests.post(url, headers=headers, json=body1)
print(f"Type 'relation': code={resp1.json().get('code')}, msg={resp1.json().get('msg')}")

# Try type as number 19
body2 = {
    "field_name": "Test Relation Num",
    "type": 19,
    "property": {"foreign_table_id": foreign_table_id}
}
resp2 = requests.post(url, headers=headers, json=body2)
print(f"Type 19: code={resp2.json().get('code')}, msg={resp2.json().get('msg')}")
