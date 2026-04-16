#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP Platform - 定时自动采集脚本

功能:
  1. 每 15 分钟自动从 YP 平台采集商品、品牌、类别数据
  2. 增量追加到固定飞书多维表格（历史数据保留）
  3. 自动处理去重（基于 product_id / merchant_id / category_id）
  4. 添加采集时间戳，方便追踪数据更新

API 限制:
  - 每次最多 1000 条（每页 100 条 x 10 页）
  - 速率限制: 每分钟 10 次请求
  - 分批采集: 使用 --start-page 和 --max-pages 控制批次

使用方式:
  python yp_auto_collect.py                   # 默认: 单页采集 (快速测试)
  python yp_auto_collect.py --batch           # 批量模式: 每轮 1000 条 (10页)
  python yp_auto_collect.py --all             # 全量采集 (耗时较长)
  python yp_auto_collect.py --start-page=11 --max-pages=10  # 从第11页开始采10页
"""

import requests
import json
import time
import re
import sys
import io
import os
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# ============================================================
# Configuration
# ============================================================

SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"

FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"

# 飞书表格 App Token (固定写入的目标表格)
# 首次运行时如果为空，会自动创建并保存
FEISHU_APP_TOKEN = os.environ.get("YP_FEISHU_APP_TOKEN", "")

# API 端点
OFFER_API_URL = "https://www.yeahpromos.com/index/apioffer/getoffer"
MERCHANT_API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"
CATEGORY_API_URL = "https://www.yeahpromos.com/index/apioffer/getcategory"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# 输出配置
OUTPUT_DIR = Path(__file__).parent / "output"
STATE_FILE = OUTPUT_DIR / "collect_state.json"

# 采集配置
PAGE_SIZE = 100        # 每页 100 条 (API 最大值)
BATCH_PAGES = 10       # 批量模式: 每轮 10 页 = 1000 条 (API 限制)
API_DELAY = 1.0        # API 请求间隔 (秒) - 增加延迟避免限流
API_RETRY_DELAY = 5    # API 限流后重试延迟 (秒)


# ============================================================
# YP API Functions
# ============================================================

def fetch_offers(page=1, limit=100, category_id=None):
    """采集一页商品数据"""
    headers = {"token": TOKEN}
    params = {"site_id": SITE_ID, "page": page, "limit": limit}
    if category_id:
        params["category_id"] = category_id

    resp = requests.get(OFFER_API_URL, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        if "data" in data and isinstance(data["data"], dict):
            offers = data["data"].get("data", [])
            total = data["data"].get("total", 0)
            page_total = data["data"].get("PageTotal", 1)
            return offers, total, page_total
        elif "data" in data and isinstance(data["data"], list):
            return data["data"], len(data["data"]), 1
    raise Exception(f"Offers API Error: {data}")


def fetch_merchants(page=1, limit=20, elite=0):
    """采集一页品牌数据"""
    headers = {"token": TOKEN}
    params = {"site_id": SITE_ID, "elite": elite, "page": page, "limit": limit}

    resp = requests.get(MERCHANT_API_URL, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        inner = data.get("data", {})
        if isinstance(inner, dict) and "Data" in inner:
            return inner["Data"], inner.get("Num", 0), inner.get("PageTotal", 1)
        elif isinstance(data, dict) and "Data" in data:
            return data["Data"], data.get("Num", 0), data.get("PageTotal", 1)
        return [], 0, 0
    raise Exception(f"Merchants API Error: {data}")


def fetch_categories():
    """采集全部类别数据 (一次性)"""
    params = {"site_id": SITE_ID, "token": TOKEN}

    resp = requests.get(CATEGORY_API_URL, params=params, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        if data.get("code") == 100000 or data.get("status") == "SUCCESS":
            return data.get("data", [])
    raise Exception(f"Categories API Error: {data}")


# ============================================================
# Data Cleaning
# ============================================================

def clean_offer(offer):
    """清洗单条商品数据"""
    price_raw = str(offer.get("price", "0"))
    price_match = re.search(r"([\d.]+)", price_raw)
    price_num = float(price_match.group(1)) if price_match else 0.0

    asin = str(offer.get("asin", "")).strip()
    return {
        "product_id": int(offer.get("product_id", 0)),
        "asin": asin,
        "product_name": str(offer.get("product_name", "")),
        "price": price_num,
        "image": str(offer.get("image", "")),
        "category_id": int(offer.get("category_id", 0)),
        "category_name": str(offer.get("category_name", "")),
        "payout": float(offer.get("payout", 0) or 0),
        "product_status": str(offer.get("product_status", "Online")),
        "amazon_link": f"https://www.amazon.com/dp/{asin}" if asin else "",
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def clean_merchant(merchant):
    """清洗单条品牌数据"""
    country_raw = str(merchant.get("country", ""))
    parts = country_raw.split("/", 1)
    country = f"{parts[0].strip()} - {parts[1].strip()}" if len(parts) == 2 else country_raw

    return {
        "merchant_id": int(merchant.get("mid", 0)),
        "merchant_name": str(merchant.get("merchant_name", "")),
        "avg_payout": float(merchant.get("avg_payout", 0) or 0),
        "cookie_days": int(merchant.get("rd", 0) or 0),
        "website": str(merchant.get("site_url", "") or ""),
        "country": country,
        "transaction_type": str(merchant.get("transaction_type", "")),
        "status": str(merchant.get("status", "UNAPPLIED")),
        "online_status": str(merchant.get("merchant_status", "")),
        "is_deeplink": "Yes" if str(merchant.get("is_deeplink", "0")) == "1" else "No",
        "logo": str(merchant.get("logo", "")),
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def clean_category(category):
    """清洗单条类别数据"""
    return {
        "category_id": int(category.get("category_id") or category.get("id", 0)),
        "category_name": str(category.get("category_name") or category.get("name", "")),
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# Feishu Client (增量追加模式)
# ============================================================

class FeishuClient:
    """飞书多维表格客户端 - 支持增量追加"""

    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self._auth()

    def _auth(self):
        url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = requests.post(url, json={"app_id": self.app_id, "app_secret": self.app_secret})
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            self.token = data["tenant_access_token"]
        else:
            raise Exception(f"Feishu auth failed: {data}")

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def create_bitable(self, name):
        """创建新的多维表格"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps"
        resp = requests.post(url, headers=self._headers(), json={"app": {"name": name}})
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["app"]["app_token"]
        raise Exception(f"Create bitable failed: {data}")

    def list_tables(self, app_token):
        """列出表格"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables"
        resp = requests.get(url, headers=self._headers())
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["items"]
        return []

    def create_table(self, app_token, table_name):
        """创建新数据表"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables"
        resp = requests.post(url, headers=self._headers(), json={"table": {"name": table_name}})
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            d = data["data"]
            return d.get("table", {}).get("table_id") or d.get("table_id")
        raise Exception(f"Create table failed: {data}")

    def add_field(self, app_token, table_id, field_name, field_type, property=None):
        """添加字段"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        body = {"field_name": field_name, "type": field_type}
        if property:
            body["property"] = property
        resp = requests.post(url, headers=self._headers(), json=body)
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["field"]["field_id"]
        # 字段可能已存在，忽略
        return None

    def list_records(self, app_token, table_id, page_size=500):
        """获取已有记录 (用于去重)"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        all_records = []
        page_token = None

        while True:
            params = {"page_size": page_size}
            if page_token:
                params["page_token"] = page_token

            resp = requests.get(url, headers=self._headers(), params=params)
            data = resp.json()
            if str(data.get("code", -1)) != "0":
                break

            items = data["data"].get("items", [])
            all_records.extend(items)

            if not data["data"].get("has_more", False):
                break
            page_token = data["data"].get("page_token")

        return all_records

    def batch_create_records(self, app_token, table_id, records, batch_size=500):
        """批量追加记录"""
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        uploaded = 0
        failed = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            resp = requests.post(url, headers=self._headers(), json={"records": batch})
            data = resp.json()
            if str(data.get("code", -1)) == "0":
                uploaded += len(batch)
            else:
                failed += len(batch)
                print(f"    [WARN] 上传失败: {data.get('msg', '')}")
            if i + batch_size < len(records):
                time.sleep(0.3)
        return uploaded, failed


# ============================================================
# State Management
# ============================================================

def load_state():
    """加载采集状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "feishu_app_token": "",
        "offers_page": 0,
        "offers_total": 0,
        "merchants_page": 0,
        "merchants_total": 0,
        "last_run": None,
        "total_offers_collected": 0,
        "total_merchants_collected": 0,
        "total_categories_collected": 0,
    }


def save_state(state):
    """保存采集状态"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============================================================
# Table Setup
# ============================================================

OFFER_FIELDS = [
    ("Product ID", 2, {"formatter": "0"}),
    ("ASIN", 1, None),
    ("Product Name", 1, None),
    ("Price (USD)", 2, {"formatter": "0.00"}),
    ("Payout (%)", 2, {"formatter": "0.00"}),
    ("Category Name", 1, None),
    ("Product Status", 3, {"options": [{"name": "Online"}, {"name": "Offline"}]}),
    ("Image", 1, None),
    ("Amazon Link", 1, None),
    ("Collected At", 5, {"date_formatter": "yyyy/MM/dd HH:mm"}),
]

MERCHANT_FIELDS = [
    ("Merchant ID", 2, {"formatter": "0"}),
    ("Merchant Name", 1, None),
    ("Avg Payout (%)", 2, {"formatter": "0.00"}),
    ("Cookie Days", 2, {"formatter": "0"}),
    ("Website", 1, None),
    ("Country", 1, None),
    ("Transaction Type", 1, None),
    ("Status", 3, {"options": [{"name": "UNAPPLIED"}, {"name": "APPROVED"}, {"name": "PENDING"}]}),
    ("Online Status", 3, {"options": [{"name": "onLine"}, {"name": "offLine"}]}),
    ("Deep Link", 3, {"options": [{"name": "Yes"}, {"name": "No"}]}),
    ("Logo", 1, None),
    ("Collected At", 5, {"date_formatter": "yyyy/MM/dd HH:mm"}),
]

CATEGORY_FIELDS = [
    ("Category ID", 2, {"formatter": "0"}),
    ("Category Name", 1, None),
    ("Collected At", 5, {"date_formatter": "yyyy/MM/dd HH:mm"}),
]


def setup_feishu_tables(app_token, state):
    """初始化飞书表格结构（仅首次需要）"""
    print("[Feishu] 连接飞书...")
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    print("  [OK] 认证成功")

    tables = client.list_tables(app_token)
    table_map = {t["name"]: t["table_id"] for t in tables}

    # 确保 3 个数据表存在
    needed = {
        "Offers": OFFER_FIELDS,
        "Merchants": MERCHANT_FIELDS,
        "Categories": CATEGORY_FIELDS,
    }

    for table_name, fields in needed.items():
        if table_name in table_map:
            print(f"  [OK] {table_name} 表已存在 ({table_map[table_name]})")
            state[f"{table_name.lower()}_table_id"] = table_map[table_name]
        else:
            print(f"  创建 {table_name} 表...")
            tid = client.create_table(app_token, table_name)
            print(f"  [OK] {table_name} 表创建成功 ({tid})")
            state[f"{table_name.lower()}_table_id"] = tid

            # 添加字段
            for field_name, field_type, property in fields:
                client.add_field(app_token, tid, field_name, field_type, property)
            print(f"  [OK] {table_name} 字段添加完成")

    return client, state


def init_bitable(state):
    """初始化飞书多维表格"""
    # 优先使用环境变量中的 App Token
    app_token = os.environ.get("YP_FEISHU_APP_TOKEN", "") or state.get("feishu_app_token", "")

    if app_token:
        print(f"[Feishu] 使用现有表格: {app_token}")
        return app_token

    # 首次运行，创建新表格
    print("[Feishu] 首次运行，创建多维表格...")
    client = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
    name = "YP Platform Data (Auto Collect)"
    app_token = client.create_bitable(name)
    print(f"[Feishu] [OK] 创建成功: {app_token}")
    print(f"[Feishu] URL: https://example.feishu.cn/base/{app_token}")
    return app_token


# ============================================================
# Data Collection & Upload
# ============================================================

def dedup_offers(new_offers, existing_records):
    """商品去重 (基于 product_id)"""
    existing_ids = set()
    for r in existing_records:
        pid = r.get("fields", {}).get("Product ID")
        if pid is not None:
            existing_ids.add(int(pid))

    unique = [o for o in new_offers if o["product_id"] not in existing_ids]
    duplicates = len(new_offers) - len(unique)
    if duplicates > 0:
        print(f"  去重: {duplicates} 条已存在，{len(unique)} 条为新数据")
    return unique


def dedup_merchants(new_merchants, existing_records):
    """品牌去重 (基于 merchant_id)"""
    existing_ids = set()
    for r in existing_records:
        mid = r.get("fields", {}).get("Merchant ID")
        if mid is not None:
            existing_ids.add(int(mid))

    unique = [m for m in new_merchants if m["merchant_id"] not in existing_ids]
    duplicates = len(new_merchants) - len(unique)
    if duplicates > 0:
        print(f"  去重: {duplicates} 条已存在，{len(unique)} 条为新数据")
    return unique


def dedup_categories(new_categories, existing_records):
    """类别去重 (基于 category_id)"""
    existing_ids = set()
    for r in existing_records:
        cid = r.get("fields", {}).get("Category ID")
        if cid is not None:
            existing_ids.add(int(cid))

    unique = [c for c in new_categories if c["category_id"] not in existing_ids]
    duplicates = len(new_categories) - len(unique)
    if duplicates > 0:
        print(f"  去重: {duplicates} 条已存在，{len(unique)} 条为新数据")
    return unique


def make_offer_record(o):
    """构造飞书记录 (Offers)"""
    fields = {
        "Product ID": o["product_id"],
        "ASIN": o["asin"],
        "Product Name": o["product_name"],
        "Price (USD)": o["price"],
        "Payout (%)": o["payout"],
        "Category Name": o["category_name"],
        "Product Status": o["product_status"] if o["product_status"] else "Online",
    }
    if o.get("image"):
        fields["Image"] = o["image"]
    if o.get("amazon_link"):
        fields["Amazon Link"] = o["amazon_link"]
    if o.get("collected_at"):
        fields["Collected At"] = int(time.time()) * 1000
    return {"fields": fields}


def make_merchant_record(m):
    """构造飞书记录 (Merchants)"""
    fields = {
        "Merchant ID": m["merchant_id"],
        "Merchant Name": m["merchant_name"],
        "Avg Payout (%)": m["avg_payout"],
        "Cookie Days": m["cookie_days"],
        "Country": m["country"],
        "Transaction Type": m["transaction_type"],
        "Status": m["status"],
        "Online Status": m["online_status"],
        "Deep Link": m["is_deeplink"],
    }
    if m.get("website"):
        fields["Website"] = m["website"]
    if m.get("logo"):
        fields["Logo"] = m["logo"]
    if m.get("collected_at"):
        fields["Collected At"] = int(time.time()) * 1000
    return {"fields": fields}


def make_category_record(c):
    """构造飞书记录 (Categories)"""
    fields = {
        "Category ID": c["category_id"],
        "Category Name": c["category_name"],
    }
    if c.get("collected_at"):
        fields["Collected At"] = int(time.time()) * 1000
    return {"fields": fields}


# ============================================================
# Main Collect Logic
# ============================================================

def collect_offers_batch(client, app_token, table_id, start_page=1, max_pages=10):
    """批量采集商品并追加到飞书"""
    print(f"\n{'='*60}")
    print(f"  [Offers] 采集商品数据 (第 {start_page} 页起, 最多 {max_pages} 页)")
    print(f"{'='*60}")

    all_offers_raw = []
    page = start_page
    total = 0
    page_total = 1

    while page < start_page + max_pages:
        retry_count = 0
        max_retries = 3
        offers = None
        
        while retry_count < max_retries:
            try:
                print(f"  采集第 {page} 页...", end=" ", flush=True)
                offers, total, page_total = fetch_offers(page=page, limit=PAGE_SIZE)
                break  # Success, exit retry loop
            except Exception as e:
                retry_count += 1
                print(f"失败({retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    print(f"    等待 {API_RETRY_DELAY} 秒后重试...")
                    time.sleep(API_RETRY_DELAY)
                else:
                    print(f"    达到最大重试次数，跳过此页")
        
        if offers is None:
            break

        if not offers:
            print("无数据")
            break

        all_offers_raw.extend(offers)
        print(f"{len(offers)} 条 (累计 {len(all_offers_raw)}/{total})")

        if page >= page_total or len(all_offers_raw) >= total:
            break

        page += 1
        time.sleep(API_DELAY)

    if not all_offers_raw:
        print("  [Offers] 无数据采集")
        return 0

    # 清洗
    offers = [clean_offer(o) for o in all_offers_raw]
    print(f"  清洗完成: {len(offers)} 条")

    # 去重
    print("  检查已有数据...")
    existing = client.list_records(app_token, table_id)
    unique = dedup_offers(offers, existing)

    if not unique:
        print("  [Offers] 全部已存在，无需追加")
        return 0

    # 追加到飞书
    print(f"  追加 {len(unique)} 条到飞书...")
    records = [make_offer_record(o) for o in unique]
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  [Offers] 完成: {uploaded} 追加成功, {failed} 失败")

    # 保存本地
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / "offers_data.json"
    with open(local_path, 'w', encoding='utf-8') as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

    return uploaded


def collect_merchants_batch(client, app_token, table_id, start_page=1, max_pages=10):
    """批量采集品牌并追加到飞书"""
    print(f"\n{'='*60}")
    print(f"  [Merchants] 采集品牌数据 (第 {start_page} 页起, 最多 {max_pages} 页)")
    print(f"{'='*60}")

    all_merchants_raw = []
    page = start_page
    total = 0
    page_total = 1

    while page < start_page + max_pages:
        retry_count = 0
        max_retries = 3
        merchants = None
        
        while retry_count < max_retries:
            try:
                print(f"  采集第 {page} 页...", end=" ", flush=True)
                merchants, total, page_total = fetch_merchants(page=page, limit=PAGE_SIZE)
                break  # Success, exit retry loop
            except Exception as e:
                retry_count += 1
                print(f"失败({retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    print(f"    等待 {API_RETRY_DELAY} 秒后重试...")
                    time.sleep(API_RETRY_DELAY)
                else:
                    print(f"    达到最大重试次数，跳过此页")
        
        if merchants is None:
            break
        
        if not merchants:
            print("无数据")
            break

        all_merchants_raw.extend(merchants)
        print(f"{len(merchants)} 条 (累计 {len(all_merchants_raw)}/{total})")

        if page >= page_total or len(all_merchants_raw) >= total:
            break

        page += 1
        time.sleep(API_DELAY)

    if not all_merchants_raw:
        print("  [Merchants] 无数据采集")
        return 0

    # 清洗
    merchants = [clean_merchant(m) for m in all_merchants_raw]
    print(f"  清洗完成: {len(merchants)} 条")

    # 去重
    print("  检查已有数据...")
    existing = client.list_records(app_token, table_id)
    unique = dedup_merchants(merchants, existing)

    if not unique:
        print("  [Merchants] 全部已存在，无需追加")
        return 0

    # 追加到飞书
    print(f"  追加 {len(unique)} 条到飞书...")
    records = [make_merchant_record(m) for m in unique]
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  [Merchants] 完成: {uploaded} 追加成功, {failed} 失败")

    # 保存本地
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / "merchants_data.json"
    with open(local_path, 'w', encoding='utf-8') as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)

    return uploaded


def collect_categories_batch(client, app_token, table_id):
    """采集类别并追加到飞书"""
    print(f"\n{'='*60}")
    print(f"  [Categories] 采集类别数据")
    print(f"{'='*60}")

    try:
        categories_raw = fetch_categories()
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 0

    print(f"  获取 {len(categories_raw)} 个类别")

    # 清洗
    categories = [clean_category(c) for c in categories_raw]

    # 去重
    print("  检查已有数据...")
    existing = client.list_records(app_token, table_id)
    unique = dedup_categories(categories, existing)

    if not unique:
        print("  [Categories] 全部已存在，无需追加")
        return 0

    # 追加到飞书
    print(f"  追加 {len(unique)} 条到飞书...")
    records = [make_category_record(c) for c in unique]
    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"  [Categories] 完成: {uploaded} 追加成功, {failed} 失败")

    # 保存本地
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    local_path = OUTPUT_DIR / "categories_data.json"
    with open(local_path, 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    return uploaded


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("  YP Platform - 定时自动采集")
    print("=" * 60)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  模式: ", end="")
    if "--all" in sys.argv:
        print("全量采集")
    elif "--batch" in sys.argv:
        print("批量采集 (1000条/轮)")
    else:
        print("单页采集 (快速测试)")
    print()

    # 加载状态
    state = load_state()

    # 解析参数
    is_all = "--all" in sys.argv
    is_batch = "--batch" in sys.argv
    start_page = 1
    max_pages = 1

    for arg in sys.argv:
        if arg.startswith("--start-page="):
            start_page = int(arg.split("=")[1])
        if arg.startswith("--max-pages="):
            max_pages = int(arg.split("=")[1])

    if is_all:
        max_pages = 999999  # 全量
    elif is_batch:
        start_page = state.get("offers_page", 0) + 1
        if start_page <= 1:
            start_page = 1
        max_pages = BATCH_PAGES

    # 初始化飞书表格
    try:
        app_token = init_bitable(state)
        state["feishu_app_token"] = app_token
    except Exception as e:
        print(f"  [FATAL] 飞书初始化失败: {e}")
        return

    # 初始化表结构
    try:
        client, state = setup_feishu_tables(app_token, state)
    except Exception as e:
        print(f"  [FATAL] 表结构初始化失败: {e}")
        return

    offers_tid = state.get("offers_table_id", "")
    merchants_tid = state.get("merchants_table_id", "")
    categories_tid = state.get("categories_table_id", "")

    # 采集 Categories
    cat_uploaded = 0
    if categories_tid:
        try:
            cat_uploaded = collect_categories_batch(client, app_token, categories_tid)
        except Exception as e:
            print(f"  [ERROR] Categories 采集失败: {e}")

    # 采集 Merchants
    mer_uploaded = 0
    if merchants_tid:
        try:
            mer_start_page = state.get("merchants_page", 0) + 1
            if mer_start_page <= 1:
                mer_start_page = 1
            mer_uploaded = collect_merchants_batch(client, app_token, merchants_tid,
                                                   start_page=mer_start_page, max_pages=max_pages)
        except Exception as e:
            print(f"  [ERROR] Merchants 采集失败: {e}")

    # 采集 Offers
    off_uploaded = 0
    if offers_tid:
        try:
            off_uploaded = collect_offers_batch(client, app_token, offers_tid,
                                                start_page=start_page, max_pages=max_pages)
        except Exception as e:
            print(f"  [ERROR] Offers 采集失败: {e}")

    # 更新状态
    state["total_offers_collected"] = state.get("total_offers_collected", 0) + off_uploaded
    state["total_merchants_collected"] = state.get("total_merchants_collected", 0) + mer_uploaded
    state["total_categories_collected"] = state.get("total_categories_collected", 0) + cat_uploaded
    # 更新页码状态（用于下次从正确的位置继续）
    if is_batch or is_all:
        state["offers_page"] = start_page + max_pages - 1
        state["merchants_page"] = mer_start_page + max_pages - 1
    save_state(state)

    # 汇总
    print(f"\n{'='*60}")
    print(f"  采集汇总")
    print(f"{'='*60}")
    print(f"  Offers:     {off_uploaded} 条新增")
    print(f"  Merchants:  {mer_uploaded} 条新增")
    print(f"  Categories: {cat_uploaded} 条新增")
    print(f"  ---")
    print(f"  飞书表格: https://example.feishu.cn/base/{app_token}")
    print(f"  下次采集: 从第 {start_page + max_pages} 页开始")
    print(f"{'='*60}")

    # 输出环境变量提示
    if not os.environ.get("YP_FEISHU_APP_TOKEN"):
        print(f"\n  [提示] 已创建飞书表格，App Token: {app_token}")
        print(f"  [提示] 请设置环境变量 YP_FEISHU_APP_TOKEN={app_token}")
        print(f"  [提示] 或下次运行会自动使用保存的 token")


if __name__ == "__main__":
    main()
