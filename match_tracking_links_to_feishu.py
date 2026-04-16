"""
YP Platform - Match Tracking Links to Feishu Products
1. Scrape merchant pages to get ASIN -> PID mapping
2. Read Feishu products
3. Match by ASIN and update Tracking URL
"""
import requests
import json
import re
import os

BASE_URL = "https://www.yeahpromos.com"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

YP_COOKIES = {
    "PHPSESSID": "10a93bfea903b9dffe23744392eef7aa",
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

FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
OFFERS_TABLE_ID = "tblMCbaHhP88sgeS"

# Regex patterns
ASIN_PATTERN = re.compile(r'asin=([A-Z0-9]{10})')
PID_PATTERN = re.compile(r'[?&]pid=(\d+)')
TRACK_PATTERN = re.compile(r'[?&]track=([a-f0-9]+)')
TRACKING_LINK_PATTERN = re.compile(r"ClipboardJS\.copy\('([^']+)'\)", re.IGNORECASE)


def get_feishu_token():
    """Get Feishu tenant access token."""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json()["tenant_access_token"]


def get_feishu_products(token):
    """Get all products from Feishu Offers table."""
    records = []
    has_more = True
    page_token = None
    
    while has_more:
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{OFFERS_TABLE_ID}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") != 0:
            print(f"Error: {result}")
            break
        
        data = result.get("data", {})
        records.extend(data.get("items", []))
        has_more = data.get("has_more", False)
        page_token = data.get("page_token")
    
    # Create ASIN -> record mapping
    products_by_asin = {}
    for record in records:
        asin = record.get("fields", {}).get("ASIN")
        if asin:
            products_by_asin[asin] = record
    
    return products_by_asin


def scrape_merchant_with_asins(merchant_id, merchant_name=""):
    """
    Scrape merchant page and extract ASIN -> tracking link mapping.
    Returns dict: {asin: {tracking_url, track, pid}}
    """
    url = f"{BASE_URL}/index/offer/brand_detail"
    params = {"advert_id": merchant_id, "site_id": "12002"}
    
    print(f"Scraping {merchant_name} (MID: {merchant_id})...")
    
    try:
        resp = requests.get(url, params=params, headers=YP_HEADERS, cookies=YP_COOKIES, timeout=30)
        
        if "/login" in resp.url:
            print(f"  ERROR: Cookie expired")
            return {}
        
        results = {}
        
        # Find all product rows with Copy buttons
        # Look for patterns like: asin=XXXX in the HTML near tracking links
        html = resp.text
        
        # Extract all tracking links
        matches = TRACKING_LINK_PATTERN.findall(html)
        
        for match in matches:
            tracking_url = match.replace("&amp;", "&")
            
            # Extract track and pid
            track_match = TRACK_PATTERN.search(tracking_url)
            pid_match = PID_PATTERN.search(tracking_url)
            
            track = track_match.group(1) if track_match else None
            pid = pid_match.group(1) if pid_match else None
            
            # Find ASIN near this link in HTML
            # Look for amazon link or asin pattern before the link
            pos = html.find(match)
            if pos > 0:
                context = html[max(0, pos-1000):pos]
                
                # Try to find ASIN in amazon link
                amazon_match = re.search(r'amazon\.com/dp/([A-Z0-9]{10})', context)
                if amazon_match:
                    asin = amazon_match.group(1)
                    results[asin] = {
                        "tracking_url": tracking_url,
                        "track": track,
                        "pid": pid,
                        "merchant_id": merchant_id,
                        "merchant_name": merchant_name
                    }
        
        print(f"  Found {len(results)} products with ASIN mapping")
        return results
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return {}


def update_feishu_record(token, record_id, fields):
    """Update a Feishu record."""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{OFFERS_TABLE_ID}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"fields": fields}
    
    resp = requests.put(url, headers=headers, json=data)
    return resp.json()


def add_fields_to_feishu(token):
    """Add Tracking URL, Track Token, PID fields to Feishu table if not exist."""
    # Note: This requires table admin permission
    # For now, we'll just print a reminder
    print("\nNote: Please ensure your Feishu table has these fields:")
    print("  - Tracking URL (文本)")
    print("  - Track Token (文本)")
    print("  - PID (文本)")
    print("  - Merchant ID (文本) - optional")
    print()


def main():
    print("=" * 70)
    print("Match Tracking Links to Feishu Products")
    print("=" * 70)
    print()
    
    # 1. Get Feishu token
    print("1. Getting Feishu token...")
    token = get_feishu_token()
    print("   OK")
    
    # 2. Check/add fields
    add_fields_to_feishu(token)
    
    # 3. Get Feishu products
    print("2. Reading Feishu products...")
    products = get_feishu_products(token)
    print(f"   Found {len(products)} products")
    
    # 4. Scrape target merchants
    target_merchants = [
        {"mid": "363372", "name": "TruSkin"},
        {"mid": "362247", "name": "Physician's Choice"},
    ]
    
    print("\n3. Scraping merchant pages...")
    all_links = {}
    for merchant in target_merchants:
        links = scrape_merchant_with_asins(merchant["mid"], merchant["name"])
        all_links.update(links)
    
    print(f"\n   Total ASIN mappings: {len(all_links)}")
    
    # 5. Match and update
    print("\n4. Matching and updating Feishu records...")
    matched = 0
    updated = 0
    
    for asin, link_data in all_links.items():
        if asin in products:
            matched += 1
            record = products[asin]
            record_id = record["record_id"]
            
            # Prepare update fields
            update_fields = {
                "Tracking URL": link_data["tracking_url"],
                "Track Token": link_data["track"],
                "PID": link_data["pid"],
                "Merchant ID": link_data["merchant_id"]
            }
            
            # Update record
            result = update_feishu_record(token, record_id, update_fields)
            if result.get("code") == 0:
                updated += 1
                print(f"   ✓ Updated {asin} -> PID {link_data['pid']}")
            else:
                print(f"   ✗ Failed {asin}: {result.get('msg', 'Unknown')}")
    
    # 6. Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Feishu products: {len(products)}")
    print(f"Merchant products: {len(all_links)}")
    print(f"Matched by ASIN: {matched}")
    print(f"Updated in Feishu: {updated}")
    
    # Save unmatched
    unmatched = set(all_links.keys()) - set(products.keys())
    if unmatched:
        print(f"\nUnmatched merchant products ({len(unmatched)}):")
        for asin in list(unmatched)[:10]:
            print(f"  - {asin}")
    
    # Save results
    results_file = os.path.join(OUTPUT_DIR, "feishu_match_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_products": len(products),
            "total_merchant_products": len(all_links),
            "matched": matched,
            "updated": updated,
            "mappings": all_links
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()
