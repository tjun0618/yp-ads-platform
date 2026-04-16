#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP Platform Data - Feishu Bitable with 3 Tables

Creates a Feishu Bitable with:
1. Categories (148 categories)
2. Merchants (20 brands)
3. Offers (100 products)

Note: Relation fields need to be added manually in Feishu UI
(Feishu API v1 does not support creating relation fields programmatically)
"""

import json
import sys
import io
import time
import re
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

from pathlib import Path

# ============================================================
# Configuration
# ============================================================

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
BITABLE_NAME = "YP Platform Data (Merchants + Offers + Categories)"

BASE_URL = "https://open.feishu.cn/open-apis"

# ============================================================
# HTTP API helpers
# ============================================================

class FeishuClient:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = None
        self._authenticate()
    
    def _authenticate(self):
        url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
        body = {"app_id": self.app_id, "app_secret": self.app_secret}
        resp = requests.post(url, json=body)
        data = resp.json()
        if data.get("code") == 0:
            self.tenant_access_token = data["tenant_access_token"]
            print("  [OK] Authenticated")
        else:
            raise Exception(f"Auth failed: {data}")
    
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.tenant_access_token}",
            "Content-Type": "application/json"
        }
    
    def create_bitable(self, name):
        url = f"{BASE_URL}/bitable/v1/apps"
        body = {"app": {"name": name}}
        resp = requests.post(url, headers=self._headers(), json=body)
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            token = data["data"]["app"]["app_token"]
            print(f"  [OK] Created bitable: {token}")
            return token
        else:
            print(f"  [FAIL] Create bitable: code={data.get('code')}, msg={data.get('msg')}")
            return None
    
    def list_tables(self, app_token):
        url = f"{BASE_URL}/bitable/v1/apps/{app_token}/tables"
        resp = requests.get(url, headers=self._headers())
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["items"]
        return []
    
    def create_table(self, app_token, table_name):
        url = f"{BASE_URL}/bitable/v1/apps/{app_token}/tables"
        body = {"table": {"name": table_name}}
        resp = requests.post(url, headers=self._headers(), json=body)
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            d = data["data"]
            tid = d.get("table", {}).get("table_id") or d.get("table_id")
            print(f"  [OK] Created table: {table_name} (ID: {tid})")
            return tid
        else:
            print(f"  [FAIL] Create table '{table_name}': code={data.get('code')}, msg={data.get('msg')}")
            return None
    
    def add_field(self, app_token, table_id, field_name, field_type, property=None):
        url = f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        body = {"field_name": field_name, "type": field_type}
        if property:
            body["property"] = property
        
        resp = requests.post(url, headers=self._headers(), json=body)
        data = resp.json()
        code = data.get("code", -1)
        if str(code) == "0":
            try:
                field_id = data["data"]["field"]["field_id"]
                print(f"    [OK] {field_name} (type={field_type}, id={field_id})")
                return field_id
            except KeyError:
                print(f"    [FAIL] {field_name}: Unexpected response: {json.dumps(data)[:200]}")
                return None
        else:
            print(f"    [FAIL] {field_name}: code={code}, msg={data.get('msg')}")
            return None
    
    def batch_create_records(self, app_token, table_id, records):
        url = f"{BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        batch_size = 500
        total = len(records)
        uploaded = 0
        failed = 0
        
        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            body = {"records": batch}
            
            resp = requests.post(url, headers=self._headers(), json=body)
            data = resp.json()
            
            if str(data.get("code", -1)) == "0":
                uploaded += len(batch)
                print(f"  [Progress] {uploaded}/{total}")
            else:
                failed += len(batch)
                msg = data.get("msg", "")
                print(f"  [ERROR] Batch failed: {msg}")
            
            if i + batch_size < total:
                time.sleep(0.5)
        
        return uploaded, failed


# ============================================================
# Setup Functions
# ============================================================

def setup_categories(client, app_token, categories, table_id):
    print("\n[Step 1] Setup Categories table...")
    
    client.add_field(app_token, table_id, "Category ID", 2,
                     {"formatter": "0"})
    client.add_field(app_token, table_id, "Category Name", 1)
    
    print("  Uploading categories...")
    records = []
    for cat in categories:
        records.append({
            "fields": {
                "Category ID": int(cat.get("category_id", 0)),
                "Category Name": str(cat.get("category_name", "")),
            }
        })
    
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  Categories: {uploaded} uploaded, {failed} failed")
    return table_id


def setup_merchants(client, app_token, merchants):
    print("\n[Step 2] Creating Merchants table...")
    
    table_id = client.create_table(app_token, "Merchants")
    if not table_id:
        return None
    
    print("  Adding fields...")
    client.add_field(app_token, table_id, "Merchant ID", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "Merchant Name", 1)
    client.add_field(app_token, table_id, "Avg Payout (%)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Cookie Days", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "Website", 1)  # text (URL as text)
    client.add_field(app_token, table_id, "Country", 1)
    client.add_field(app_token, table_id, "Transaction Type", 1)
    client.add_field(app_token, table_id, "Status", 3,
                     {"options": [{"name": "UNAPPLIED"}, {"name": "APPROVED"}, {"name": "PENDING"}]})
    client.add_field(app_token, table_id, "Online Status", 3,
                     {"options": [{"name": "onLine"}, {"name": "offLine"}]})
    client.add_field(app_token, table_id, "Deep Link", 3,
                     {"options": [{"name": "Yes"}, {"name": "No"}]})
    client.add_field(app_token, table_id, "Logo", 1)  # text (URL as text)
    
    print("  Uploading merchants...")
    records = []
    for m in merchants:
        payout = float(m.get("avg_payout", 0) or 0)
        country_raw = str(m.get("country", ""))
        parts = country_raw.split("/", 1)
        country = f"{parts[0].strip()} - {parts[1].strip()}" if len(parts) == 2 else country_raw
        site_url = str(m.get("site_url", "") or "")
        logo_url = str(m.get("logo", "") or "")
        is_deeplink = str(m.get("is_deeplink", "0"))
        
        fields = {
            "Merchant ID": int(m.get("mid", 0)),
            "Merchant Name": str(m.get("merchant_name", "")),
            "Avg Payout (%)": payout,
            "Cookie Days": int(m.get("rd", 0) or 0),
            "Country": country,
            "Transaction Type": str(m.get("transaction_type", "")),
            "Status": str(m.get("status", "UNAPPLIED")),
            "Online Status": str(m.get("merchant_status", "")),
            "Deep Link": "Yes" if is_deeplink == "1" else "No",
        }
        if site_url:
            fields["Website"] = site_url
        if logo_url:
            fields["Logo"] = logo_url
        
        records.append({"fields": fields})
    
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  Merchants: {uploaded} uploaded, {failed} failed")
    return table_id


def setup_offers(client, app_token, offers):
    print("\n[Step 3] Creating Offers table...")
    
    table_id = client.create_table(app_token, "Offers")
    if not table_id:
        return None
    
    print("  Adding fields...")
    client.add_field(app_token, table_id, "Product ID", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "ASIN", 1)
    client.add_field(app_token, table_id, "Product Name", 1)
    client.add_field(app_token, table_id, "Price (USD)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Payout (%)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Category Name", 1)
    client.add_field(app_token, table_id, "Image", 1)  # text (URL as text)
    client.add_field(app_token, table_id, "Amazon Link", 1)  # text (URL as text)
    client.add_field(app_token, table_id, "Product Status", 3,
                     {"options": [{"name": "Online"}, {"name": "Offline"}]})
    
    print("  Uploading offers...")
    records = []
    for o in offers:
        price_raw = str(o.get("price", "0"))
        price_match = re.search(r"([\d.]+)", price_raw)
        price_num = float(price_match.group(1)) if price_match else 0.0
        
        asin = str(o.get("asin", ""))
        product_name = str(o.get("product_name", ""))
        category_name = str(o.get("category_name", ""))
        image_url = str(o.get("image", ""))
        payout = float(o.get("payout", 0) or 0)
        product_status = str(o.get("product_status", "Online"))
        amazon_link = f"https://www.amazon.com/dp/{asin}" if asin else ""
        
        fields = {
            "Product ID": int(o.get("product_id", 0)),
            "ASIN": asin,
            "Product Name": product_name,
            "Price (USD)": price_num,
            "Payout (%)": payout,
            "Category Name": category_name,
            "Product Status": product_status if product_status else "Online",
        }
        if image_url:
            fields["Image"] = image_url
        if amazon_link:
            fields["Amazon Link"] = amazon_link
        
        records.append({"fields": fields})
    
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  Offers: {uploaded} uploaded, {failed} failed")
    return table_id


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 70)
    print("  YP Platform Data -> Feishu Bitable (3 Tables)")
    print("=" * 70)
    
    project_dir = Path(__file__).parent
    
    print("\n[Step 0] Loading data files...")
    with open(project_dir / "categories_sample.json", "r", encoding="utf-8") as f:
        categories = json.load(f)
    print(f"  Categories: {len(categories)} records")
    
    with open(project_dir / "merchants_sample.json", "r", encoding="utf-8") as f:
        merchants = json.load(f)
    print(f"  Merchants: {len(merchants)} records")
    
    with open(project_dir / "offers_sample.json", "r", encoding="utf-8") as f:
        offers = json.load(f)
    print(f"  Offers: {len(offers)} records")
    
    print("\n[Step 0.5] Connecting to Feishu...")
    client = FeishuClient(APP_ID, APP_SECRET)
    
    print(f"\n[Step 0.6] Creating bitable: {BITABLE_NAME}")
    app_token = client.create_bitable(BITABLE_NAME)
    if not app_token:
        print("[FATAL] Failed to create bitable")
        return
    
    tables = client.list_tables(app_token)
    default_table_id = tables[0]["table_id"] if tables else None
    print(f"  [INFO] Default table: {default_table_id}")
    
    # Step 1: Categories
    categories_table_id = setup_categories(client, app_token, categories, default_table_id)
    if not categories_table_id:
        print("[FATAL] Failed to setup Categories")
        return
    
    time.sleep(1)
    
    # Step 2: Merchants
    merchants_table_id = setup_merchants(client, app_token, merchants)
    if not merchants_table_id:
        print("[FATAL] Failed to setup Merchants")
        return
    
    time.sleep(1)
    
    # Step 3: Offers
    offers_table_id = setup_offers(client, app_token, offers)
    if not offers_table_id:
        print("[FATAL] Failed to setup Offers")
        return
    
    # Summary
    print("\n" + "=" * 70)
    print("  SUCCESS! All 3 tables created with data!")
    print("=" * 70)
    print(f"\n  Bitable: {BITABLE_NAME}")
    print(f"  App Token: {app_token}")
    print(f"\n  Tables:")
    print(f"    1. Categories ({len(categories)} records)")
    print(f"       - Category ID (number)")
    print(f"       - Category Name (text)")
    print(f"    2. Merchants ({len(merchants)} records)")
    print(f"       - Merchant ID, Merchant Name, Avg Payout, Cookie Days")
    print(f"       - Website (URL), Country, Transaction Type")
    print(f"       - Status, Online Status, Deep Link (select)")
    print(f"       - Logo (URL)")
    print(f"    3. Offers ({len(offers)} records)")
    print(f"       - Product ID, ASIN, Product Name, Price (USD)")
    print(f"       - Payout (%), Category Name, Product Status (select)")
    print(f"       - Image (URL), Amazon Link (URL)")
    
    print(f"\n  [IMPORTANT] To add relation fields, open the Feishu Bitable and:")
    print(f"    1. In Offers table, add a 'Relation' field -> link to Categories")
    print(f"    2. In Offers table, add a 'Relation' field -> link to Merchants")
    print(f"    This takes about 30 seconds in the Feishu UI.")
    
    print(f"\n  URL: https://example.feishu.cn/base/{app_token}")
    
    # Save result
    result = {
        "app_token": app_token,
        "tables": {
            "Categories": {"table_id": categories_table_id, "records": len(categories)},
            "Merchants": {"table_id": merchants_table_id, "records": len(merchants)},
            "Offers": {"table_id": offers_table_id, "records": len(offers)},
        },
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "relation_instructions": {
            "Offers -> Categories": "Add relation field in Offers table pointing to Categories",
            "Offers -> Merchants": "Add relation field in Offers table pointing to Merchants",
        }
    }
    result_file = project_dir / "feishu_bitable_result.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  Result saved to: {result_file}")


if __name__ == "__main__":
    main()
