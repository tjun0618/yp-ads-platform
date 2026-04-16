"""
Add required fields to Feishu Offers table
"""
import requests

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

# Fields to add
FIELDS_TO_ADD = [
    {"name": "Tracking URL", "type": 1},  # Text
    {"name": "Track Token", "type": 1},   # Text
    {"name": "PID", "type": 1},           # Text
    {"name": "Merchant ID", "type": 1},   # Text
]


def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]


def add_field(token, field_name, field_type):
    """Add a field to Feishu table."""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "field_name": field_name,
        "type": field_type
    }
    
    resp = requests.post(url, headers=headers, json=data)
    result = resp.json()
    
    if result.get("code") == 0:
        print(f"  [OK] Created field: {field_name}")
        return True
    elif "field_name has exist" in result.get("msg", "") or "already exists" in result.get("msg", ""):
        print(f"  [EXIST] Field already exists: {field_name}")
        return True
    else:
        print(f"  [FAIL] Failed to create {field_name}: {result.get('msg', result)}")
        return False


def main():
    print("=" * 60)
    print("Adding fields to Feishu Offers table")
    print("=" * 60)
    print()
    
    # Get token
    print("1. Getting Feishu token...")
    token = get_feishu_token()
    print("   OK")
    
    # Add fields
    print("\n2. Adding fields...")
    success_count = 0
    for field in FIELDS_TO_ADD:
        if add_field(token, field["name"], field["type"]):
            success_count += 1
    
    print(f"\n3. Summary: {success_count}/{len(FIELDS_TO_ADD)} fields ready")
    
    if success_count == len(FIELDS_TO_ADD):
        print("\n[OK] All fields are ready! You can now run the match script.")
    else:
        print("\n[WARN] Some fields could not be created. Please check permissions.")


if __name__ == "__main__":
    main()
