import json, requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
BASE_URL = 'https://open.feishu.cn/open-apis'

r = requests.post(f'{BASE_URL}/auth/v3/tenant_access_token/internal', json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

app_token = 'RpI6bMSqHaPBiSsLCaucn34bnE9'
table_id = 'tblIvAUADjh6NGeh'  # Offers table
foreign_table_id = 'tbla09upkskprDsg'  # Categories table

url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields'

# Try different property formats
tests = [
    {"name": "Test1 basic", "type": 19, "property": {"foreign_table_id": foreign_table_id}},
    {"name": "Test2 as string", "type": "19", "property": {"foreign_table_id": foreign_table_id}},
    {"name": "Test3 with version", "type": 19, "property": {"foreign_table_id": foreign_table_id, "version": 1}},
    {"name": "Test4 with table_id key", "type": 19, "property": {"table_id": foreign_table_id}},
    {"name": "Test5 relation type", "type": "relation", "property": {"foreign_table_id": foreign_table_id}},
    {"name": "Test6 no property", "type": 19},
]

for t in tests:
    body = {"field_name": t["name"], "type": t["type"]}
    if "property" in t:
        body["property"] = t["property"]
    resp = requests.post(url, headers=headers, json=body)
    code = resp.json().get('code')
    msg = resp.json().get('msg', '')[:60]
    print(f"  {t['name']}: type={t['type']}, code={code}, msg={msg}")
    if code == 0:
        # Clean up - delete the field
        fid = resp.json()['data']['field']['field_id']
        del_url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields/{fid}'
        requests.delete(del_url, headers=headers)
