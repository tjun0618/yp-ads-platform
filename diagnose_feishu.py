#!/usr/bin/env python3
"""诊断飞书字段问题并逐条更新"""
import requests, json, time, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"
FEISHU_BASE = "https://open.feishu.cn/open-apis"

def get_token():
    resp = requests.post(f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]

token = get_token()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 1. 查看所有字段及类型
print("=== 飞书字段信息 ===")
resp = requests.get(f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields", headers=headers)
fields_data = resp.json()
for f in fields_data.get("data", {}).get("items", []):
    fname = f["field_name"]
    ftype = f["type"]
    ftype_name = {1: "Text", 2: "Number", 3: "Select", 4: "Date",
                  5: "Checkbox", 7: "Phone", 11: "Url", 13: "Attachment",
                  15: "Member", 17: "Relation", 18: "Formula", 1001: "CreatedTime",
                  1002: "LastModifiedTime", 1003: "CreatedBy", 1004: "LastModifiedBy",
                  1005: "AutoNumber"}.get(ftype, f"Unknown({ftype})")
    print(f"  {fname}: type={ftype_name}")

# 2. 获取一条记录测试
print("\n=== 测试记录 ===")
resp2 = requests.get(
    f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records",
    headers=headers, params={"page_size": 1}
)
data2 = resp2.json()
if data2.get("code") == 0 and data2["data"]["items"]:
    item = data2["data"]["items"][0]
    rid = item["record_id"]
    fields = item["fields"]
    print(f"  record_id: {rid}")
    print(f"  fields: {json.dumps(fields, ensure_ascii=False)[:300]}")

    # 3. 尝试更新一条记录
    print("\n=== 测试更新 ===")
    test_fields = {"Merchant Name": "TEST_MERCHANT", "Merchant ID": "TEST_123"}
    resp3 = requests.put(
        f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}",
        headers=headers, json={"fields": test_fields}
    )
    print(f"  更新结果: {json.dumps(resp3.json(), ensure_ascii=False)[:500]}")
