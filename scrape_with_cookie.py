"""
YP Platform - Scrape Tracking Links using Cookie
Uses PHPSESSID cookie to access authenticated pages.
"""
import requests
import re
import json
import csv
import os

BASE_URL = "https://www.yeahpromos.com"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# Cookie from user's browser
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://www.yeahpromos.com/"
}

# Regex patterns
TRACKING_LINK_PATTERN = re.compile(r"ClipboardJS\.copy\('([^']+)'\)", re.IGNORECASE)
PID_PATTERN = re.compile(r'[?&]pid=(\d+)')
TRACK_PATTERN = re.compile(r'[?&]track=([a-f0-9]+)')


def scrape_merchant(merchant_id, merchant_name=""):
    """Scrape tracking links from a merchant page."""
    url = f"{BASE_URL}/index/offer/brand_detail"
    params = {"advert_id": merchant_id, "site_id": "12002"}
    
    print(f"Scraping merchant {merchant_id} ({merchant_name})...")
    
    try:
        resp = requests.get(url, params=params, headers=HEADERS, cookies=COOKIES, timeout=30)
        resp.raise_for_status()
        
        # Check if redirected to login
        if "/login" in resp.url or "/signin" in resp.url:
            print(f"  ERROR: Cookie expired or invalid. Redirected to login.")
            return []
        
        # Extract tracking links
        matches = TRACKING_LINK_PATTERN.findall(resp.text)
        
        links = []
        for match in matches:
            tracking_url = match.replace("&amp;", "&")
            
            track_match = TRACK_PATTERN.search(tracking_url)
            pid_match = PID_PATTERN.search(tracking_url)
            
            links.append({
                "tracking_url": tracking_url,
                "track": track_match.group(1) if track_match else None,
                "pid": pid_match.group(1) if pid_match else None,
                "merchant_name": merchant_name,
                "merchant_id": merchant_id
            })
        
        print(f"  Found {len(links)} tracking links")
        return links
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return []


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    print("=" * 60)
    print("YP Platform Cookie-based Scraper")
    print("=" * 60)
    print()
    
    # Test with TruSkin
    target_merchants = [
        {"mid": "363372", "name": "TruSkin"},
        {"mid": "362247", "name": "Physician's Choice"},
    ]
    
    all_links = []
    for merchant in target_merchants:
        links = scrape_merchant(merchant["mid"], merchant["name"])
        all_links.extend(links)
    
    # Save results
    print("\n" + "=" * 60)
    print("Saving results...")
    print("=" * 60)
    
    # JSON
    json_path = os.path.join(OUTPUT_DIR, "cookie_tracking_links.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_links, f, indent=2, ensure_ascii=False)
    
    # CSV
    csv_path = os.path.join(OUTPUT_DIR, "cookie_tracking_links.csv")
    if all_links:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_links[0].keys())
            writer.writeheader()
            writer.writerows(all_links)
    
    print(f"\nTotal links: {len(all_links)}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    
    # Print sample
    if all_links:
        print("\n" + "=" * 60)
        print("Sample links:")
        print("=" * 60)
        for link in all_links[:5]:
            print(f"\n{link['merchant_name']} - PID {link['pid']}:")
            print(f"  {link['tracking_url']}")


if __name__ == "__main__":
    main()
