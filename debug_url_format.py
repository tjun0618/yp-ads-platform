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
url = f'{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create'

# Test 1: URL as list of link objects
record = {'fields': {'Merchant ID': 111340, 'Merchant Name': 'URL Test', 'Website': [{'link': 'https://www.iherb.com'}]}}
resp = requests.post(url, headers=headers, json={'records': [record]})
code = resp.json().get('code')
msg = resp.json().get('msg')
print(f'URL list format: code={code} msg={msg}')

# Test 2: URL as list with text and link
record2 = {'fields': {'Merchant ID': 111341, 'Merchant Name': 'URL Test2', 'Website': [{'link': 'https://www.test.com', 'text': 'Test Site'}]}}
resp2 = requests.post(url, headers=headers, json={'records': [record2]})
code2 = resp2.json().get('code')
msg2 = resp2.json().get('msg')
print(f'URL list+text format: code={code2} msg={msg2}')

# Test 3: Logo as list
record3 = {'fields': {'Merchant ID': 111342, 'Merchant Name': 'Logo Test', 'Logo': [{'link': 'https://www.test.com/logo.jpg'}]}}
resp3 = requests.post(url, headers=headers, json={'records': [record3]})
code3 = resp3.json().get('code')
msg3 = resp3.json().get('msg')
print(f'Logo list format: code={code3} msg={msg3}')
