#!/usr/bin/env python3
"""
Update Feishu table with tracking links based on ASIN matching
"""
import requests
import json
import time

# Feishu credentials
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"

def get_feishu_token():
    """Get Feishu tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]

def load_products_with_tracking():
    """Load products with ASIN and tracking links from JSON files"""
    all_products = []
    
    for filename in ["truskin_products.json", "physicians_choice_products.json"]:
        try:
            with open(f"output/{filename}", "r") as f:
                products = json.load(f)
                all_products.extend(products)
                print(f"  Loaded {len(products)} products from {filename}")
        except FileNotFoundError:
            print(f"  File not found: {filename}")
    
    # Create ASIN to tracking info mapping
    asin_map = {}
    for p in all_products:
        if p.get("asin"):
            asin_map[p["asin"]] = {
                "tracking_url": p["tracking_url"],
                "track_token": p["track"],
                "pid": p["pid"]
            }
    
    return asin_map

def get_feishu_records(token):
    """Get all records from Feishu table"""
    records = []
    page_token = None
    
    while True:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") == 0:
            batch = result["data"]["items"]
            records.extend(batch)
            
            if not result["data"].get("has_more"):
                break
            page_token = result["data"].get("page_token")
        else:
            print(f"Error fetching records: {result}")
            break
    
    return records

def update_record(token, record_id, fields):
    """Update a single record"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    resp = requests.put(url, headers=headers, json={"fields": fields})
    return resp.json()

def main():
    print("=" * 60)
    print("Update Feishu with Tracking Links")
    print("=" * 60)
    
    # Load tracking data
    print("\n[1] Loading tracking data...")
    asin_map = load_products_with_tracking()
    print(f"  Total ASIN mappings: {len(asin_map)}")
    
    # Get Feishu token
    print("\n[2] Getting Feishu token...")
    token = get_feishu_token()
    print("  Token obtained")
    
    # Get Feishu records
    print("\n[3] Fetching Feishu records...")
    records = get_feishu_records(token)
    print(f"  Total records: {len(records)}")
    
    # Match and update
    print("\n[4] Matching and updating records...")
    updated = 0
    matched = 0
    
    for record in records:
        record_id = record["record_id"]
        fields = record.get("fields", {})
        asin = fields.get("ASIN", "")
        
        if not asin:
            continue
        
        # Check if we have tracking data for this ASIN
        if asin in asin_map:
            matched += 1
            tracking_info = asin_map[asin]
            
            # Check if already has tracking URL
            if fields.get("Tracking URL"):
                print(f"  [SKIP] ASIN {asin} already has tracking URL")
                continue
            
            # Update fields
            update_fields = {
                "Tracking URL": tracking_info["tracking_url"],
                "Track Token": tracking_info["track_token"],
                "PID": tracking_info["pid"]
            }
            
            result = update_record(token, record_id, update_fields)
            if result.get("code") == 0:
                updated += 1
                print(f"  [OK] Updated ASIN {asin} with tracking URL")
            else:
                print(f"  [FAIL] Failed to update ASIN {asin}: {result.get('msg')}")
            
            time.sleep(0.1)  # Rate limiting
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Total records: {len(records)}")
    print(f"  Matched ASINs: {matched}")
    print(f"  Updated: {updated}")
    print("=" * 60)

if __name__ == "__main__":
    main()
