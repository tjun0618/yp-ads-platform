"""
查看飞书多维表格中所有表及其字段结构
"""
import requests, json

APP_ID     = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN  = 'VgOiblBCKac38ZsNx9acHpCGnQb'

r = requests.post(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET}
)
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}'}

# 列出所有表
resp = requests.get(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables',
    headers=headers
)
data = resp.json()
tables = data.get('data', {}).get('items', [])
print(f'=== 飞书多维表格 [{APP_TOKEN}] ===')
print(f'共 {len(tables)} 张表\n')

for t in tables:
    tid  = t['table_id']
    name = t['name']
    print(f'[{tid}] {name}')

    # 查字段
    rf = requests.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{tid}/fields',
        headers=headers
    )
    fields = rf.json().get('data', {}).get('items', [])
    for f in fields:
        print(f'    字段: {f["field_name"]}  (type={f["type"]})')

    # 查记录数（只取1条）
    rr = requests.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{tid}/records',
        headers=headers, params={'page_size': 1}
    )
    rdata = rr.json().get('data', {})
    total = rdata.get('total', '?')
    items = rdata.get('items', [])
    print(f'    记录数: {total}')
    if items:
        print(f'    样本字段: {list(items[0].get("fields", {}).keys())}')
    print()
