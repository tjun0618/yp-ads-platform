#!/usr/bin/env python3
"""Check if Feishu ASINs are in the scraped map"""
import json
import requests

# Load ASIN map
with open('output/quick_asin_map.json', 'r', encoding='utf-8') as f:
    asin_map = json.load(f)

print(f"Total ASINs in map: {len(asin_map)}")

# Feishu ASINs
TARGET_ASINS = ["B0GDXPNRD4", "B0GL7QP2SF", "B0C545BTQN", "B0FNWMSTR8", "B0BR6DL25V", 
                "B0FF4PXHRN", "B0GHSXZ9Q2", "B0GHSW4VWY", "B0BH9GBCFB", "B0CQZ2HQBN"]

print(f"\nChecking {len(TARGET_ASINS)} target ASINs:")
found = 0
for asin in TARGET_ASINS:
    if asin in asin_map:
        info = asin_map[asin]
        merchant_safe = info['merchant_name'].encode('ascii', 'ignore').decode('ascii')
        print(f"  [FOUND] {asin} -> {merchant_safe} (MID: {info['mid']})")
        found += 1
    else:
        print(f"  [NOT FOUND] {asin}")

print(f"\nResult: {found}/{len(TARGET_ASINS)} ASINs found in map")

# Get Feishu records to check all ASINs
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

resp = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", 
    json={"app_id": APP_ID, "app_secret": APP_SECRET})
token = resp.json()["tenant_access_token"]

url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get(url, headers=headers, params={"page_size": 500})
result = resp.json()

if result.get("code") == 0:
    records = result["data"]["items"]
    print(f"\nFeishu records: {len(records)}")
    
    matched = 0
    for record in records:
        asin = record.get("fields", {}).get("ASIN", "")
        if asin in asin_map:
            matched += 1
    
    print(f"Matched with map: {matched}/{len(records)}")
