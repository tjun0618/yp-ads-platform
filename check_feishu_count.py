import requests, json
from pathlib import Path

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'

# 获取 token
r = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    json={'app_id': APP_ID, 'app_secret': APP_SECRET})
token = r.json()['tenant_access_token']
headers = {'Authorization': f'Bearer {token}'}

# 读取 feishu_cache.json
cache_file = 'output/feishu_table_config.json'
with open(cache_file, encoding='utf-8') as f:
    cache = json.load(f)
app_token = cache.get('app_token')
table_id = cache.get('table_id')
print(f'app_token: {app_token}')
print(f'table_id: {table_id}')

# 查询记录总数
r2 = requests.get(
    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records',
    headers=headers,
    params={'page_size': 1}
)
d = r2.json()
print(f'API code: {d.get("code")}')
print(f'total records: {d.get("data", {}).get("total")}')
print(f'msg: {d.get("msg")}')
