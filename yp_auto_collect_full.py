#!/usr/bin/env python3
"""
YP平台全自动采集脚本 - 每15分钟运行一次
包含：Offers + Merchants + Categories + 商品映射抓取
"""
import requests
import json
import time
import re
from pathlib import Path
from datetime import datetime

# Configuration
SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"
BASE_URL = "https://www.yeahpromos.com"
API_URL = f"{BASE_URL}/index.php"

# Cookie for web scraping
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Collection settings
PAGE_SIZE = 100
BATCH_PAGES = 10  # 每轮采集10页 = 1000条
API_DELAY = 1.0   # API请求间隔
API_RETRY_DELAY = 5  # 限流后重试延迟
SCRAPE_DELAY = 0.5   # 网页抓取间隔
MERCHANTS_PER_SCRAPE = 50  # 每轮抓取50个商户的商品

# Paths
OUTPUT_DIR = Path("output")
STATE_FILE = OUTPUT_DIR / "full_collect_state.json"
MAP_FILE = OUTPUT_DIR / "asin_merchant_map.json"

# Feishu config
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"

# Table IDs
TABLE_OFFERS = "tblMCbaHhP88sgeS"
TABLE_MERCHANTS = "tblR2JhVsdTugueo"
TABLE_CATEGORIES = "tblgOVVvOccSVLgU"

# =============================================================================
# Feishu API Functions
# =============================================================================

def get_feishu_token():
    """Get Feishu tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json().get("tenant_access_token")

def get_existing_asins(token, table_id):
    """Get existing ASINs from Feishu table"""
    existing = set()
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    has_more = True
    page_token = None
    
    while has_more:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") == 0:
            items = result["data"]["items"]
            for item in items:
                asin = item.get("fields", {}).get("ASIN")
                if asin:
                    existing.add(asin)
            
            has_more = result["data"].get("has_more", False)
            page_token = result["data"].get("page_token")
        else:
            break
    
    return existing

def upload_to_feishu(token, table_id, records, existing_asins=None):
    """Upload records to Feishu, skip duplicates"""
    if not records:
        return 0
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{table_id}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    uploaded = 0
    skipped = 0
    
    for record in records:
        # Check for duplicates
        if existing_asins and table_id == TABLE_OFFERS:
            asin = record.get("fields", {}).get("ASIN")
            if asin and asin in existing_asins:
                skipped += 1
                continue
        
        resp = requests.post(url, headers=headers, json=record)
        result = resp.json()
        
        if result.get("code") == 0:
            uploaded += 1
            if existing_asins and table_id == TABLE_OFFERS:
                asin = record.get("fields", {}).get("ASIN")
                if asin:
                    existing_asins.add(asin)
        elif result.get("code") == 400:
            # Duplicate or validation error
            skipped += 1
        
        time.sleep(0.1)
    
    return uploaded

# =============================================================================
# API Collection Functions
# =============================================================================

def fetch_offers(page=1, limit=100):
    """Fetch offers from YP API"""
    url = f"{API_URL}/index/apioffer/getoffer"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "token": TOKEN,
        "siteid": SITE_ID
    }
    data = {"page": page, "limit": limit}
    
    resp = requests.post(url, headers=headers, data=data, timeout=30)
    result = resp.json()
    
    if result.get("code") == 200:
        data_list = result.get("data", {}).get("data", [])
        total = result.get("data", {}).get("total", 0)
        return data_list, total, len(data_list)
    return [], 0, 0

def fetch_merchants(page=1, limit=100):
    """Fetch merchants from YP API"""
    url = f"{API_URL}/index/getadvert/getadvert"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "token": TOKEN,
        "siteid": SITE_ID
    }
    data = {"page": page, "limit": limit}
    
    resp = requests.post(url, headers=headers, data=data, timeout=30)
    result = resp.json()
    
    if result.get("code") == 200:
        data_list = result.get("data", {}).get("Data", [])
        total = result.get("data", {}).get("total", 0)
        return data_list, total, len(data_list)
    return [], 0, 0

def fetch_categories():
    """Fetch categories from YP API"""
    url = f"{BASE_URL}/index/apioffer/getcategory"
    params = {"site_id": SITE_ID, "token": TOKEN}
    
    resp = requests.get(url, params=params, timeout=30)
    result = resp.json()
    
    if result.get("code") == 200:
        return result.get("data", [])
    return []

# =============================================================================
# Web Scraping Functions
# =============================================================================

def scrape_merchant_products(mid, merchant_name=""):
    """Scrape products from merchant page"""
    url = f"{BASE_URL}/index/offer/brand_detail?advert_id={mid}&site_id={SITE_ID}"
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if "/index/login/login" in resp.text:
            return None, "LOGIN_REQUIRED"
        
        # Extract tracking URL
        track_match = re.search(r"track=([a-f0-9]{16})", resp.text)
        track = track_match.group(1) if track_match else None
        
        # Extract products with ASIN and PID
        products = []
        
        # Pattern 1: ClipboardJS.copy with tracking URL
        pattern1 = r"data-clipboard-text=\"([^\"]+)\""
        matches1 = re.findall(pattern1, resp.text)
        
        for url_text in matches1:
            if "openurlproduct" in url_text:
                pid_match = re.search(r"pid=(\d+)", url_text)
                if pid_match:
                    pid = pid_match.group(1)
                    products.append({
                        "pid": pid,
                        "tracking_url": url_text,
                        "asin": None  # Will extract separately
                    })
        
        # Pattern 2: Extract ASINs from product links
        asin_pattern = r'asin=([A-Z0-9]{10})'
        asins = re.findall(asin_pattern, resp.text)
        
        # Pattern 3: Extract ASIN from product detail
        detail_pattern = r'asin=([A-Z0-9]{10})[^>]*>.*?pid=(\d+)'
        detail_matches = re.findall(detail_pattern, resp.text, re.DOTALL)
        
        asin_to_pid = {}
        for asin, pid in detail_matches:
            asin_to_pid[asin] = pid
        
        # Build final product list
        final_products = []
        for asin, pid in asin_to_pid.items():
            tracking_url = None
            if track:
                tracking_url = f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
            
            final_products.append({
                "asin": asin,
                "pid": pid,
                "tracking_url": tracking_url,
                "merchant_id": mid,
                "merchant_name": merchant_name
            })
        
        return final_products, None
        
    except Exception as e:
        return None, str(e)

# =============================================================================
# State Management
# =============================================================================

def load_state():
    """Load collection state"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "offers_page": 0,
        "merchants_page": 0,
        "last_merchant_scraped": 0,
        "total_offers": 0,
        "total_merchants": 0,
        "total_categories": 0,
        "total_asin_mapped": 0,
        "last_run": None
    }

def save_state(state):
    """Save collection state"""
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def load_asin_map():
    """Load ASIN to merchant mapping"""
    if MAP_FILE.exists():
        with open(MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_asin_map(asin_map):
    """Save ASIN to merchant mapping"""
    with open(MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(asin_map, f, indent=2)

# =============================================================================
# Main Collection Functions
# =============================================================================

def collect_offers_batch(token, existing_asins, start_page=1, max_pages=10):
    """Collect offers batch with retry"""
    uploaded = 0
    page = start_page
    
    while page < start_page + max_pages:
        retry_count = 0
        offers = None
        
        while retry_count < 3:
            try:
                offers, total, page_total = fetch_offers(page=page, limit=PAGE_SIZE)
                break
            except Exception as e:
                retry_count += 1
                if retry_count < 3:
                    time.sleep(API_RETRY_DELAY)
                else:
                    print(f"    [Offers] Page {page} failed after 3 retries")
        
        if offers is None:
            break
        
        if not offers:
            break
        
        # Format for Feishu
        records = []
        for offer in offers:
            record = {
                "fields": {
                    "ASIN": offer.get("asin", ""),
                    "Product Name": offer.get("product_name", "")[:200],
                    "Price": str(offer.get("price", "")),
                    "Category": offer.get("category_name", ""),
                    "Commission": str(offer.get("payout", "")),
                    "Product Status": offer.get("product_status", ""),
                    "Image URL": offer.get("image", ""),
                    "Amazon Link": f"https://www.amazon.com/dp/{offer.get('asin', '')}" if offer.get("asin") else "",
                    "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            records.append(record)
        
        uploaded += upload_to_feishu(token, TABLE_OFFERS, records, existing_asins)
        
        print(f"    [Offers] Page {page}: {len(records)} records, uploaded {uploaded}")
        
        page += 1
        time.sleep(API_DELAY)
    
    return uploaded, page - 1

def collect_merchants_batch(token, start_page=1, max_pages=10):
    """Collect merchants batch with retry"""
    uploaded = 0
    page = start_page
    merchants_data = []
    
    while page < start_page + max_pages:
        retry_count = 0
        merchants = None
        
        while retry_count < 3:
            try:
                merchants, total, page_total = fetch_merchants(page=page, limit=PAGE_SIZE)
                break
            except Exception as e:
                retry_count += 1
                if retry_count < 3:
                    time.sleep(API_RETRY_DELAY)
                else:
                    print(f"    [Merchants] Page {page} failed after 3 retries")
        
        if merchants is None:
            break
        
        if not merchants:
            break
        
        merchants_data.extend(merchants)
        
        # Format for Feishu
        records = []
        for m in merchants:
            record = {
                "fields": {
                    "Merchant ID": str(m.get("id", "")),
                    "Merchant Name": m.get("name", "")[:200],
                    "Commission Rate": str(m.get("commission_rate", "")),
                    "Cookie Days": str(m.get("cookie", "")),
                    "Website": m.get("website", ""),
                    "Country": m.get("country", ""),
                    "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            records.append(record)
        
        uploaded += upload_to_feishu(token, TABLE_MERCHANTS, records)
        
        print(f"    [Merchants] Page {page}: {len(records)} records")
        
        page += 1
        time.sleep(API_DELAY)
    
    # Save merchants to local file for scraping
    merchants_file = OUTPUT_DIR / "merchants_data.json"
    existing = []
    if merchants_file.exists():
        with open(merchants_file, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    
    # Merge and deduplicate
    all_merchants = {m.get("id"): m for m in existing}
    for m in merchants_data:
        all_merchants[m.get("id")] = m
    
    with open(merchants_file, 'w', encoding='utf-8') as f:
        json.dump(list(all_merchants.values()), f, indent=2)
    
    return uploaded, page - 1, list(all_merchants.values())

def collect_categories_batch(token):
    """Collect categories"""
    categories = fetch_categories()
    
    if not categories:
        return 0
    
    records = []
    for cat in categories:
        record = {
            "fields": {
                "Category ID": str(cat.get("category_id", "")),
                "Category Name": cat.get("category_name", ""),
                "采集时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        records.append(record)
    
    uploaded = upload_to_feishu(token, TABLE_CATEGORIES, records)
    print(f"    [Categories] {len(records)} records")
    
    return uploaded

def scrape_merchants_batch(merchants, asin_map, start_index=0, count=50):
    """Scrape products from merchants batch"""
    new_mappings = 0
    end_index = min(start_index + count, len(merchants))
    
    for i in range(start_index, end_index):
        merchant = merchants[i]
        mid = merchant.get("id") or merchant.get("merchant_id")
        name = merchant.get("name") or merchant.get("merchant_name", "Unknown")
        
        products, error = scrape_merchant_products(mid, name)
        
        if error == "LOGIN_REQUIRED":
            print(f"    [Scrape] Cookie expired, stopping")
            break
        
        if products:
            for p in products:
                if p["asin"] and p["asin"] not in asin_map:
                    asin_map[p["asin"]] = {
                        "merchant_id": mid,
                        "merchant_name": name,
                        "pid": p["pid"],
                        "tracking_url": p["tracking_url"],
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    new_mappings += 1
        
        time.sleep(SCRAPE_DELAY)
    
    return new_mappings, end_index

# =============================================================================
# Main Entry
# =============================================================================

def main():
    print("=" * 70)
    print("YP平台全自动采集 - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)
    
    # Load state
    state = load_state()
    asin_map = load_asin_map()
    
    print(f"\n当前状态:")
    print(f"  - Offers: 已采集到第 {state['offers_page']} 页")
    print(f"  - Merchants: 已采集到第 {state['merchants_page']} 页")
    print(f"  - ASIN映射: 已建立 {len(asin_map)} 个")
    
    # Get Feishu token
    token = get_feishu_token()
    if not token:
        print("[ERROR] Failed to get Feishu token")
        return
    
    # Get existing ASINs for deduplication
    print("\n[1/4] 获取飞书现有数据...")
    existing_asins = get_existing_asins(token, TABLE_OFFERS)
    print(f"  飞书已有 {len(existing_asins)} 个 ASIN")
    
    # Collect Offers
    print("\n[2/4] 采集 Offers (商品)...")
    offers_start = state.get("offers_page", 0) + 1
    offers_uploaded, offers_end = collect_offers_batch(
        token, existing_asins, 
        start_page=offers_start, max_pages=BATCH_PAGES
    )
    
    # Collect Merchants
    print("\n[3/4] 采集 Merchants (商户)...")
    merchants_start = state.get("merchants_page", 0) + 1
    merchants_uploaded, merchants_end, all_merchants = collect_merchants_batch(
        token,
        start_page=merchants_start, max_pages=BATCH_PAGES
    )
    
    # Collect Categories (only once, on first run)
    categories_uploaded = 0
    if state.get("total_categories", 0) == 0:
        print("\n[4/4] 采集 Categories (类别)...")
        categories_uploaded = collect_categories_batch(token)
    else:
        print("\n[4/4] Categories 已采集，跳过")
    
    # Scrape merchant products for ASIN mapping
    print("\n[5/4] 抓取商户商品映射...")
    scrape_start = state.get("last_merchant_scraped", 0)
    new_mappings, scrape_end = scrape_merchants_batch(
        all_merchants, asin_map,
        start_index=scrape_start, count=MERCHANTS_PER_SCRAPE
    )
    
    # Save ASIN map
    save_asin_map(asin_map)
    
    # Update state
    state["offers_page"] = offers_end
    state["merchants_page"] = merchants_end
    state["last_merchant_scraped"] = scrape_end
    state["total_offers"] = state.get("total_offers", 0) + offers_uploaded
    state["total_merchants"] = state.get("total_merchants", 0) + merchants_uploaded
    state["total_categories"] = state.get("total_categories", 0) + categories_uploaded
    state["total_asin_mapped"] = len(asin_map)
    save_state(state)
    
    # Summary
    print("\n" + "=" * 70)
    print("采集完成!")
    print("=" * 70)
    print(f"\n本次采集:")
    print(f"  - Offers: +{offers_uploaded} (累计: {state['total_offers']})")
    print(f"  - Merchants: +{merchants_uploaded} (累计: {state['total_merchants']})")
    print(f"  - Categories: +{categories_uploaded} (累计: {state['total_categories']})")
    print(f"  - ASIN映射: +{new_mappings} (累计: {len(asin_map)})")
    print(f"\n下次采集:")
    print(f"  - Offers: 从第 {offers_end + 1} 页开始")
    print(f"  - Merchants: 从第 {merchants_end + 1} 页开始")
    print(f"  - 商品映射: 从第 {scrape_end} 个商户继续")

if __name__ == "__main__":
    main()
