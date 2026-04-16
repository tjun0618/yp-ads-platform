"""诊断飞书单选字段更新格式"""
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

# 测试不同的字段值格式
formats = [
    ("格式1: 字符串", "可推广"),
    ("格式2: 数组", ["可推广"]),
    ("格式3: 字符串带空格", "可推广 "),
]

for label, value in formats:
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

    if code == 0:
        print(f"  成功! 使用 {label}")
        # 验证
        resp2 = requests.get(
            f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}',
            headers=headers)
        fields = resp2.json().get('data', {}).get('record', {}).get('fields', {})
        status = fields.get('推广状态', '')
        print(f"  验证值: {status}")
        break
