import requests

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

# Get token
resp = requests.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", 
    json={"app_id": APP_ID, "app_secret": APP_SECRET})
token = resp.json()["tenant_access_token"]

# Get table fields
url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
resp = requests.get(url, headers={"Authorization": f"Bearer {token}"})
result = resp.json()

if result.get("code") == 0:
    print("=== Feishu Offers Table Fields ===\n")
    for field in result["data"]["items"]:
        field_type = field.get('field_type', field.get('type', 'unknown'))
        print(f"  {field['field_name']} ({field_type})")
    print(f"\nTotal fields: {len(result['data']['items'])}")
else:
    print(f"Error: {result}")

# Also get a sample record to see field values
print("\n=== Sample Record ===")
url2 = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
resp2 = requests.get(url2, headers={"Authorization": f"Bearer {token}"}, params={"page_size": 1})
result2 = resp2.json()

if result2.get("code") == 0 and result2["data"]["items"]:
    record = result2["data"]["items"][0]
    print(f"Record ID: {record['record_id']}")
    print("Fields:")
    for key, value in record["fields"].items():
        print(f"  {key}: {value}")
