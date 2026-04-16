"""
YP Platform - Update Feishu with Tracking Links
1. Read products from Feishu table
2. Scrape tracking links for each merchant
3. Update Feishu records with tracking links
"""
import requests
import json
import re
import time
import os

# Configuration
BASE_URL = "https://www.yeahpromos.com"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# YP Cookie (update if expired)
YP_COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

YP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.yeahpromos.com/"
}

# Feishu Configuration
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"

# Regex patterns
TRACKING_LINK_PATTERN = re.compile(r"ClipboardJS\.copy\('([^']+)'\)", re.IGNORECASE)
PID_PATTERN = re.compile(r'[?&]pid=(\d+)')


def get_feishu_token():
    """Get Feishu tenant access token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    
    resp = requests.post(url, headers=headers, json=data)
    result = resp.json()
    
    if result.get("code") == 0:
        return result["tenant_access_token"]
    else:
        raise Exception(f"Failed to get token: {result}")


def get_table_records(token, table_id, view_id=None, page_size=500):
    """Get all records from a Feishu table."""
    records = []
    has_more = True
    page_token = None
    
    while has_more:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": min(page_size, 500)}
        if page_token:
            params["page_token"] = page_token
        if view_id:
            params["view_id"] = view_id
        
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") != 0:
            print(f"Error getting records: {result}")
            break
        
        data = result.get("data", {})
        items = data.get("items", [])
        records.extend(items)
        
        has_more = data.get("has_more", False)
        page_token = data.get("page_token")
        
        if not has_more:
            break
    
    return records


def update_record(token, table_id, record_id, fields):
    """Update a Feishu table record."""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"fields": fields}
    
    resp = requests.put(url, headers=headers, json=data)
    return resp.json()


def scrape_merchant_tracking_links(merchant_id):
    """Scrape all tracking links for a merchant."""
    url = f"{BASE_URL}/index/offer/brand_detail"
    params = {"advert_id": merchant_id, "site_id": "12002"}
    
    try:
        resp = requests.get(url, params=params, headers=YP_HEADERS, cookies=YP_COOKIES, timeout=30)
        
        if "/login" in resp.url:
            print(f"    ERROR: Cookie expired for merchant {merchant_id}")
            return {}
        
        # Extract all tracking links with their pids
        matches = TRACKING_LINK_PATTERN.findall(resp.text)
        
        links_by_pid = {}
        for match in matches:
            tracking_url = match.replace("&amp;", "&")
            pid_match = PID_PATTERN.search(tracking_url)
            if pid_match:
                pid = pid_match.group(1)
                links_by_pid[pid] = tracking_url
        
        return links_by_pid
        
    except Exception as e:
        print(f"    ERROR scraping merchant {merchant_id}: {e}")
        return {}


def main():
    print("=" * 70)
    print("YP Platform - Update Feishu with Tracking Links")
    print("=" * 70)
    print()
    
    # 1. Get Feishu token
    print("1. Getting Feishu access token...")
    try:
        token = get_feishu_token()
        print("   Success!")
    except Exception as e:
        print(f"   Failed: {e}")
        return
    
    # 2. Get Offers table records
    print("\n2. Reading Offers table from Feishu...")
    offers_table_id = "tblMCbaHhP88sgeS"  # From collect_state.json
    
    try:
        records = get_table_records(token, offers_table_id)
        print(f"   Found {len(records)} records")
    except Exception as e:
        print(f"   Error: {e}")
        return
    
    # 3. Group records by merchant
    print("\n3. Grouping records by merchant...")
    merchants_to_scrape = {}
    
    for record in records:
        fields = record.get("fields", {})
        merchant_name = fields.get("Merchant Name", "")
        merchant_id = fields.get("Merchant ID", "")
        
        # Try to extract MID from merchant_id field or merchant_name
        mid = None
        if merchant_id and str(merchant_id).isdigit():
            mid = str(merchant_id)
        
        if mid and mid not in merchants_to_scrape:
            merchants_to_scrape[mid] = {
                "name": merchant_name,
                "records": []
            }
        
        if mid:
            merchants_to_scrape[mid]["records"].append(record)
    
    print(f"   Found {len(merchants_to_scrape)} unique merchants")
    
    # 4. Scrape tracking links for each merchant
    print("\n4. Scraping tracking links from YP platform...")
    all_tracking_links = {}
    
    for i, (mid, info) in enumerate(merchants_to_scrape.items()):
        print(f"   [{i+1}/{len(merchants_to_scrape)}] {info['name']} (MID: {mid})...")
        links = scrape_merchant_tracking_links(mid)
        all_tracking_links[mid] = links
        print(f"       Found {len(links)} tracking links")
        time.sleep(1)  # Be nice to the server
    
    # 5. Update Feishu records
    print("\n5. Updating Feishu records with tracking links...")
    updated_count = 0
    
    for mid, info in merchants_to_scrape.items():
        links = all_tracking_links.get(mid, {})
        
        for record in info["records"]:
            record_id = record["record_id"]
            fields = record.get("fields", {})
            
            # Try to find matching tracking link
            # We need to map product to pid - this is tricky without product_id to pid mapping
            # For now, we'll store all merchant links in a field
            
            if links:
                # Get the first link as example (you may need to adjust logic)
                first_pid = list(links.keys())[0]
                first_link = links[first_pid]
                
                # Update record with tracking link
                update_fields = {
                    "Tracking URL": first_link,
                    "Track Token": re.search(r'track=([a-f0-9]+)', first_link).group(1) if re.search(r'track=([a-f0-9]+)', first_link) else "",
                    "PID": first_pid
                }
                
                try:
                    result = update_record(token, offers_table_id, record_id, update_fields)
                    if result.get("code") == 0:
                        updated_count += 1
                        print(f"   Updated record {record_id[:8]}...")
                    else:
                        print(f"   Failed to update {record_id[:8]}: {result.get('msg', 'Unknown error')}")
                except Exception as e:
                    print(f"   Error updating {record_id[:8]}: {e}")
    
    print(f"\n   Updated {updated_count} records")
    
    # 6. Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total records in Feishu: {len(records)}")
    print(f"Unique merchants: {len(merchants_to_scrape)}")
    print(f"Total tracking links scraped: {sum(len(links) for links in all_tracking_links.values())}")
    print(f"Records updated: {updated_count}")
    
    # Save detailed results
    results_file = os.path.join(OUTPUT_DIR, "feishu_tracking_update.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({
            "merchants": {mid: {"name": info["name"], "links": all_tracking_links.get(mid, {})} 
                         for mid, info in merchants_to_scrape.items()},
            "updated_count": updated_count
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
