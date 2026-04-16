"""测试用 option id 更新单选字段"""
import requests, json

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = resp.json()['tenant_access_token']
headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

# 获取一条记录
resp = requests.get(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
    headers=headers, params={'page_size': 1})
items = resp.json().get('data', {}).get('items', [])
rid = items[0]['record_id']

# 测试不同格式
tests = [
    ("option id 字符串", "optFXPI1Ku"),
    ("option id 数组", ["optFXPI1Ku"]),
    ("单条 update API 字符串", None),  # 用单条API
]

for label, value in tests[:2]:
    body = {
        "records": [{
            "record_id": rid,
            "fields": {
                "推广状态": value
            }
        }]
    }
    resp = requests.put(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/batch_update',
        headers=headers, json=body)
    result = resp.json()
    code = result.get('code', -1)
    msg = result.get('msg', '')
    print(f"{label}: code={code}, msg={msg}")

# 测试用单条 update API
body = {
    "fields": {
        "推广状态": "可推广"
    }
}
resp = requests.put(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}',
    headers=headers, json=body)
result = resp.json()
code = result.get('code', -1)
msg = result.get('msg', '')
print(f"单条update API (字符串): code={code}, msg={msg}")

if code == 0:
    resp2 = requests.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}',
        headers=headers)
    fields = resp2.json().get('data', {}).get('record', {}).get('fields', {})
    print(f"  验证值: {fields.get('推广状态')}")
else:
    # 试 option id
    body = {
        "fields": {
            "推广状态": "optFXPI1Ku"
        }
    }
    resp = requests.put(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}',
        headers=headers, json=body)
    result = resp.json()
    print(f"单条update API (opt id): code={result.get('code')}, msg={result.get('msg')}")
    
    if result.get('code') == 0:
        resp2 = requests.get(
            f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}',
            headers=headers)
        fields = resp2.json().get('data', {}).get('record', {}).get('fields', {})
        print(f"  验证值: {fields.get('推广状态')}")
