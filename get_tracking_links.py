#!/usr/bin/env python3
"""
直接获取飞书表格中商品的投放链接
"""
import requests
import json
import re
import time
from pathlib import Path
from datetime import datetime

# Configuration
SITE_ID = "12002"
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Feishu config
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_OFFERS = "tblMCbaHhP88sgeS"

def get_feishu_token():
    """Get Feishu tenant access token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json().get("tenant_access_token")

def get_feishu_offers(token):
    """Get all offers from Feishu table"""
    offers = []
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OFFERS}/records"
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
                fields = item.get("fields", {})
                offers.append({
                    "record_id": item.get("record_id"),
                    "asin": fields.get("ASIN"),
                    "product_name": fields.get("Product Name", ""),
                    "amazon_link": fields.get("Amazon Link", "")
                })
            
            has_more = result["data"].get("has_more", False)
            page_token = result["data"].get("page_token")
        else:
            break
    
    return offers

def update_feishu_record(token, record_id, tracking_url):
    """Update a Feishu record with tracking URL"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OFFERS}/records/{record_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "fields": {
            "Tracking URL": tracking_url
        }
    }
    
    resp = requests.put(url, headers=headers, json=data)
    result = resp.json()
    
    return result.get("code") == 0

def search_product_on_yp(asin):
    """Search for product on YP platform"""
    # Try to find product by searching merchant pages
    # This is a simplified version - in practice, we'd need to check multiple merchants
    
    url = f"https://www.yeahpromos.com/index/offer/index?site_id={SITE_ID}"
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if "/index/login/login" in resp.text:
            return None, "LOGIN_REQUIRED"
        
        # Look for ASIN in the page
        if asin in resp.text:
            # Extract tracking URL if found
            # Pattern: data-clipboard-text="..."
            pattern = r'data-clipboard-text="([^"]+)"'
            matches = re.findall(pattern, resp.text)
            
            for url_text in matches:
                if asin in url_text or "openurlproduct" in url_text:
                    return url_text, None
        
        return None, "NOT_FOUND"
        
    except Exception as e:
        return None, str(e)

def scrape_tracking_link_from_merchant(mid, asin):
    """Scrape tracking link for specific ASIN from merchant page"""
    url = f"https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id={SITE_ID}"
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if "/index/login/login" in resp.text:
            return None, "LOGIN_REQUIRED"
        
        # Extract tracking token
        track_match = re.search(r"track=([a-f0-9]{16})", resp.text)
        track = track_match.group(1) if track_match else None
        
        # Look for ASIN and extract PID
        pattern = rf'asin={asin}[^>]*>.*?pid=(\d+)'
        match = re.search(pattern, resp.text, re.DOTALL)
        
        if match and track:
            pid = match.group(1)
            tracking_url = f"https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}"
            return tracking_url, None
        
        return None, "NOT_FOUND"
        
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("获取飞书商品投放链接")
    print("=" * 70)
    
    # Get Feishu token
    token = get_feishu_token()
    if not token:
        print("[ERROR] Failed to get Feishu token")
        return
    
    # Get offers from Feishu
    print("\n[1/3] 获取飞书商品数据...")
    offers = get_feishu_offers(token)
    print(f"  飞书表格共有 {len(offers)} 个商品")
    
    # Filter offers without tracking URL
    offers_to_update = [o for o in offers if o.get("asin")]
    print(f"  需要获取投放链接: {len(offers_to_update)} 个")
    
    if not offers_to_update:
        print("\n所有商品已有投放链接!")
        return
    
    # Load merchants
    print("\n[2/3] 加载商户数据...")
    merchants_file = Path("output/merchants_data.json")
    if merchants_file.exists():
        with open(merchants_file, 'r', encoding='utf-8') as f:
            merchants = json.load(f)
    else:
        merchants = []
    
    print(f"  本地商户数据: {len(merchants)} 个")
    
    # Try to get tracking links
    print("\n[3/3] 抓取投放链接...")
    print("-" * 70)
    
    updated = 0
    not_found = 0
    
    # For each offer, try to find tracking link
    for i, offer in enumerate(offers_to_update[:20]):  # Process first 20 for testing
        asin = offer.get("asin")
        name = offer.get("product_name", "")[:30]
        record_id = offer.get("record_id")
        
        print(f"\n[{i+1}] {name}...")
        print(f"    ASIN: {asin}")
        
        # Try to find in merchants
        found = False
        for merchant in merchants[:100]:  # Check first 100 merchants
            mid = merchant.get("merchant_id")
            if not mid:
                continue
            
            tracking_url, error = scrape_tracking_link_from_merchant(mid, asin)
            
            if error == "LOGIN_REQUIRED":
                print("    Cookie expired!")
                return
            
            if tracking_url:
                print(f"    Found! {tracking_url[:60]}...")
                
                # Update Feishu
                if update_feishu_record(token, record_id, tracking_url):
                    print("    Updated in Feishu!")
                    updated += 1
                else:
                    print("    Failed to update Feishu")
                
                found = True
                break
            
            time.sleep(0.2)
        
        if not found:
            print("    Not found in first 100 merchants")
            not_found += 1
        
        time.sleep(0.5)
    
    print("-" * 70)
    print("\n完成!")
    print(f"已更新: {updated} 个商品")
    print(f"未找到: {not_found} 个商品")

if __name__ == "__main__":
    main()
