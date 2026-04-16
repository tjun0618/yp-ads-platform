"""
从飞书下载所有10020个商户的MID列表
"""
import requests
import json
import time
from datetime import datetime

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
MERCHANTS_TABLE_ID = "tblR2JhVsdTugueo"
OUTPUT_FILE = "output/merchants_mid_list.json"


def get_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    return resp.json()["tenant_access_token"]


def download_all_merchants(token):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{MERCHANTS_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    merchants = []
    page_token = None
    page = 0
    
    while True:
        page += 1
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        result = resp.json()
        
        if result.get("code") != 0:
            print(f"Error: {result.get('msg')}")
            break
        
        data = result["data"]
        items = data.get("items", [])
        
        for item in items:
            fields = item.get("fields", {})
            mid = fields.get("Merchant ID", "")
            name = fields.get("Merchant Name", "")
            status = fields.get("Status", "")
            country = fields.get("Country", "")
            
            if mid:
                merchants.append({
                    "mid": str(mid),
                    "name": str(name),
                    "status": status,
                    "country": country
                })
        
        print(f"  Page {page}: {len(items)} records (total: {len(merchants)})")
        
        if not data.get("has_more"):
            break
        
        page_token = data.get("page_token")
        time.sleep(0.2)
    
    return merchants


def main():
    print(f"开始下载商户MID列表... {datetime.now().strftime('%H:%M:%S')}")
    
    token = get_token()
    merchants = download_all_merchants(token)
    
    print(f"\n总计: {len(merchants)} 个商户")
    
    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    
    print(f"已保存到: {OUTPUT_FILE}")
    
    # 统计
    mid_set = set(m["mid"] for m in merchants)
    print(f"唯一MID: {len(mid_set)}")
    
    if merchants:
        mids_int = [int(m["mid"]) for m in merchants if m["mid"].isdigit()]
        print(f"MID范围: {min(mids_int)} - {max(mids_int)}")
        print(f"Sample: {merchants[:3]}")
    
    return merchants


if __name__ == "__main__":
    main()
