#!/usr/bin/env python3
"""Check Feishu ASIN field"""
import requests
import json

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

# Get token
resp = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", 
    json={"app_id": APP_ID, "app_secret": APP_SECRET})
token = resp.json()["tenant_access_token"]

# Get first 5 records
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(url, headers=headers, params={"page_size": 5})
result = resp.json()

if result.get("code") == 0:
    print("Sample records:")
    for record in result["data"]["items"]:
        fields = record.get("fields", {})
        print(f"  Record ID: {record['record_id']}")
        print(f"  Fields: {list(fields.keys())}")
        print(f"  ASIN: {fields.get('ASIN', 'N/A')}")
        print()
else:
    print(f"Error: {result}")
