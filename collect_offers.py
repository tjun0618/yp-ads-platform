#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP Platform - Offers (商品) 数据独立采集脚本

功能:
  1. 通过 YP Offer API 采集商品数据
  2. 支持分页采集，可获取全量数据
  3. 支持按类别筛选
  4. 数据保存为 JSON 格式
  5. 支持上传到飞书多维表格

API 端点: https://www.yeahpromos.com/index/apioffer/getoffer
认证方式: HTTP Header {"token": TOKEN}
请求方式: GET
速率限制: 每分钟 10 次
"""

import requests
import json
import time
import re
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# ============================================================
# Configuration - 在此配置你的凭证
# ============================================================

SITE_ID = "12002"           # 你的 Site ID (Channel ID)
TOKEN = "7951dc7484fa9f9d"  # 你的 Web Token

# 飞书配置 (可选，设为空字符串则不上传)
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"

# API 端点
OFFER_API_URL = "https://www.yeahpromos.com/index/apioffer/getoffer"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

# 输出配置
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = "offers_data.json"


# ============================================================
# YP Offer API
# ============================================================

def get_offers(site_id, token, page=1, limit=100, category_id=None):
    """
    调用 YP Offer API 获取商品列表

    Args:
        site_id: 网站/频道 ID
        token: API Token
        page: 页码 (从 1 开始)
        limit: 每页数量 (最大 100)
        category_id: 类别 ID (可选，用于筛选)

    Returns:
        list: 商品列表，每个商品包含以下字段:
            - product_id: 商品 ID
            - asin: 亚马逊 ASIN
            - product_name: 商品名称
            - price: 价格 (格式: "USD 164.99" 或 "0")
            - image: 商品图片 URL
            - category_id: 类别 ID
            - category_name: 类别名称
            - discount: 折扣信息
            - link_status: 链接状态
            - payout: 佣金率 (%)
            - tracking_url: 追踪链接
            - product_status: 商品状态 (Online/Offline)

    Raises:
        Exception: API 请求失败时抛出异常
    """
    headers = {"token": token}
    params = {
        "site_id": site_id,
        "page": page,
        "limit": limit
    }
    if category_id:
        params["category_id"] = category_id

    response = requests.get(OFFER_API_URL, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        # Offer API 的数据路径: data.data.data
        if "data" in data and isinstance(data["data"], dict):
            offers = data["data"].get("data", [])
            total = data["data"].get("total", 0)
            page_total = data["data"].get("PageTotal", 1)
            return offers, total, page_total
        elif "data" in data and isinstance(data["data"], list):
            return data["data"], len(data["data"]), 1
        elif "Data" in data and isinstance(data["Data"], list):
            return data["Data"], len(data["Data"]), 1
    else:
        raise Exception(f"API Error: {data}")


def get_all_offers(site_id, token, category_id=None, max_pages=None):
    """
    分页获取全部商品数据

    Args:
        site_id: 网站/频道 ID
        token: API Token
        category_id: 类别 ID (可选)
        max_pages: 最大页数 (可选，用于限制采集量)

    Returns:
        list: 所有商品数据
    """
    all_offers = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            print(f"  达到最大页数限制 ({max_pages}), 停止采集")
            break

        print(f"  采集第 {page} 页...", end=" ")
        try:
            offers, total, page_total = get_offers(site_id, token, page=page, limit=100, category_id=category_id)
        except Exception as e:
            print(f"失败: {e}")
            break

        if not offers:
            print("无数据，停止")
            break

        all_offers.extend(offers)
        print(f"获取 {len(offers)} 条 (累计 {len(all_offers)}/{total})")

        if page >= page_total or len(all_offers) >= total:
            print(f"  采集完成，共 {len(all_offers)} 条")
            break

        page += 1
        time.sleep(0.5)  # 速率控制

    return all_offers


def clean_offer_data(offer):
    """
    清洗和标准化商品数据

    将 API 返回的原始数据转换为标准格式:
    - price: "USD 164.99" -> 164.99 (float)
    - amazon_link: 根据 ASIN 构造亚马逊链接
    - payout: 确保为数字类型
    """
    price_raw = str(offer.get("price", "0"))
    price_match = re.search(r"([\d.]+)", price_raw)
    price_num = float(price_match.group(1)) if price_match else 0.0

    asin = str(offer.get("asin", "")).strip()
    amazon_link = f"https://www.amazon.com/dp/{asin}" if asin else ""

    return {
        "product_id": int(offer.get("product_id", 0)),
        "asin": asin,
        "product_name": str(offer.get("product_name", "")),
        "price": price_num,
        "price_raw": price_raw,
        "image": str(offer.get("image", "")),
        "category_id": int(offer.get("category_id", 0)),
        "category_name": str(offer.get("category_name", "")),
        "discount": str(offer.get("discount", "")),
        "payout": float(offer.get("payout", 0) or 0),
        "product_status": str(offer.get("product_status", "Online")),
        "amazon_link": amazon_link,
        "tracking_url": str(offer.get("tracking_url", "")),
    }


# ============================================================
# Feishu Upload
# ============================================================

class FeishuBitableClient:
    """飞书多维表格客户端"""

    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = None
        self._auth()

    def _auth(self):
        url = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"
        body = {"app_id": self.app_id, "app_secret": self.app_secret}
        resp = requests.post(url, json=body)
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            self.token = data["tenant_access_token"]
        else:
            raise Exception(f"Feishu auth failed: {data}")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def create_bitable(self, name):
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps"
        resp = requests.post(url, headers=self._headers(), json={"app": {"name": name}})
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["app"]["app_token"]
        raise Exception(f"Create bitable failed: {data}")

    def list_tables(self, app_token):
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables"
        resp = requests.get(url, headers=self._headers())
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["items"]
        return []

    def add_field(self, app_token, table_id, field_name, field_type, property=None):
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        body = {"field_name": field_name, "type": field_type}
        if property:
            body["property"] = property
        resp = requests.post(url, headers=self._headers(), json=body)
        data = resp.json()
        if str(data.get("code", -1)) == "0":
            return data["data"]["field"]["field_id"]
        return None

    def batch_create_records(self, app_token, table_id, records, batch_size=500):
        url = f"{FEISHU_BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
        uploaded = 0
        failed = 0
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            resp = requests.post(url, headers=self._headers(), json={"records": batch})
            data = resp.json()
            if str(data.get("code", -1)) == "0":
                uploaded += len(batch)
                print(f"    上传进度: {uploaded}/{len(records)}")
            else:
                failed += len(batch)
                print(f"    上传失败: {data.get('msg', '')}")
            if i + batch_size < len(records):
                time.sleep(0.5)
        return uploaded, failed


def upload_to_feishu(offers, feishu_app_id, feishu_app_secret):
    """
    将商品数据上传到飞书多维表格

    创建一个新的飞书多维表格，包含以下字段:
    - Product ID (Number): 商品 ID
    - ASIN (Text): 亚马逊 ASIN
    - Product Name (Text): 商品名称
    - Price (USD) (Number): 商品价格
    - Payout (%) (Number): 佣金率
    - Category Name (Text): 类别名称
    - Product Status (Select): 商品状态
    - Image (Text): 商品图片 URL
    - Amazon Link (Text): 亚马逊商品链接
    """
    print("\n[Feishu] 连接飞书...")
    client = FeishuBitableClient(feishu_app_id, feishu_app_secret)
    print("  [OK] 认证成功")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    bitable_name = f"YP Offers ({timestamp})"
    print(f"[Feishu] 创建多维表格: {bitable_name}")
    app_token = client.create_bitable(bitable_name)
    print(f"  [OK] App Token: {app_token}")

    tables = client.list_tables(app_token)
    table_id = tables[0]["table_id"] if tables else None

    print("[Feishu] 添加字段...")
    client.add_field(app_token, table_id, "Product ID", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "ASIN", 1)
    client.add_field(app_token, table_id, "Product Name", 1)
    client.add_field(app_token, table_id, "Price (USD)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Payout (%)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Category Name", 1)
    client.add_field(app_token, table_id, "Product Status", 3,
                     {"options": [{"name": "Online"}, {"name": "Offline"}]})
    client.add_field(app_token, table_id, "Image", 1)
    client.add_field(app_token, table_id, "Amazon Link", 1)

    print("[Feishu] 上传数据...")
    records = []
    for o in offers:
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
        records.append({"fields": fields})

    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"[Feishu] 完成: {uploaded} 上传成功, {failed} 失败")
    print(f"[Feishu] URL: https://example.feishu.cn/base/{app_token}")

    return app_token, uploaded, failed


# ============================================================
# Statistics
# ============================================================

def print_statistics(offers):
    """打印采集数据统计信息"""
    if not offers:
        print("  无数据")
        return

    total = len(offers)
    online = sum(1 for o in offers if o.get("product_status") == "Online")
    offline = total - online
    with_price = sum(1 for o in offers if o["price"] > 0)
    avg_price = sum(o["price"] for o in offers if o["price"] > 0) / max(with_price, 1)
    avg_payout = sum(o["payout"] for o in offers) / total
    categories = set(o["category_name"] for o in offers if o["category_name"])

    print(f"\n{'=' * 50}")
    print(f"  数据统计")
    print(f"{'=' * 50}")
    print(f"  总商品数: {total}")
    print(f"  在线商品: {online}")
    print(f"  离线商品: {offline}")
    print(f"  有价格商品: {with_price}")
    print(f"  无价格商品: {total - with_price}")
    print(f"  平均价格: ${avg_price:.2f}")
    print(f"  平均佣金率: {avg_payout:.2f}%")
    print(f"  涉及类别: {len(categories)}")

    # 佣金率分布
    high_payout = [o for o in offers if o["payout"] >= 10]
    mid_payout = [o for o in offers if 5 <= o["payout"] < 10]
    low_payout = [o for o in offers if 0 < o["payout"] < 5]
    print(f"\n  佣金率分布:")
    print(f"    >=10%: {len(high_payout)} 个商品")
    print(f"    5-10%: {len(mid_payout)} 个商品")
    print(f"    1-5%:  {len(low_payout)} 个商品")
    print(f"    0%:    {total - len(high_payout) - len(mid_payout) - len(low_payout)} 个商品")

    # 前 5 个类别
    cat_count = {}
    for o in offers:
        cn = o["category_name"] or "(无类别)"
        cat_count[cn] = cat_count.get(cn, 0) + 1
    top_cats = sorted(cat_count.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\n  前 5 个类别:")
    for cat_name, count in top_cats:
        print(f"    {cat_name}: {count}")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("  YP Offers (商品) 数据采集")
    print("=" * 60)
    print(f"  Site ID: {SITE_ID}")
    print(f"  Token: {TOKEN[:8]}...")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: 采集数据
    print("[Step 1] 采集商品数据...")
    print("  (提示: 默认采集第 1 页 100 条，加 --all 参数采集全部)")
    print()

    # 检查命令行参数
    fetch_all = "--all" in sys.argv
    category_filter = None
    for arg in sys.argv:
        if arg.startswith("--category="):
            category_filter = int(arg.split("=")[1])

    if fetch_all:
        print("  模式: 全量采集")
        offers_raw = get_all_offers(SITE_ID, TOKEN, category_id=category_filter)
    else:
        print("  模式: 单页采集 (100 条)")
        try:
            offers_raw, total, page_total = get_offers(SITE_ID, TOKEN, page=1, limit=100, category_id=category_filter)
            print(f"  获取 {len(offers_raw)} 条 (总 {total} 条, 共 {page_total} 页)")
        except Exception as e:
            print(f"  [ERROR] {e}")
            return

    # Step 2: 清洗数据
    print(f"\n[Step 2] 清洗数据...")
    offers = [clean_offer_data(o) for o in offers_raw]
    print(f"  清洗完成: {len(offers)} 条")

    # Step 3: 保存数据
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)
    print(f"\n[Step 3] 数据已保存: {output_path}")

    # Step 4: 统计
    print_statistics(offers)

    # Step 5: 上传到飞书 (可选)
    if FEISHU_APP_ID and FEISHU_APP_SECRET and "--upload" in sys.argv:
        print(f"\n[Step 5] 上传到飞书...")
        try:
            app_token, uploaded, failed = upload_to_feishu(offers, FEISHU_APP_ID, FEISHU_APP_SECRET)
            result = {
                "app_token": app_token,
                "uploaded": uploaded,
                "failed": failed,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_records": len(offers)
            }
            result_path = OUTPUT_DIR / "offers_feishu_result.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  结果已保存: {result_path}")
        except Exception as e:
            print(f"  [ERROR] 上传失败: {e}")
    elif not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print(f"\n[Step 5] 跳过飞书上传 (未配置 FEISHU_APP_ID/SECRET)")
        print(f"  提示: 添加 --upload 参数并配置飞书凭证即可上传")
    else:
        print(f"\n[Step 5] 跳过飞书上传")
        print(f"  提示: 添加 --upload 参数即可上传到飞书")

    # 显示样本
    print(f"\n{'=' * 60}")
    print(f"  商品样本 (前 3 条)")
    print(f"{'=' * 60}")
    for i, o in enumerate(offers[:3]):
        print(f"\n  [{i+1}] {o['product_name'][:60]}...")
        print(f"      ASIN: {o['asin']}")
        print(f"      价格: ${o['price']:.2f}")
        print(f"      佣金: {o['payout']}%")
        print(f"      类别: {o['category_name'] or '(无)'}")
        print(f"      链接: {o['amazon_link']}")

    print(f"\n{'=' * 60}")
    print("  采集完成!")
    print(f"{'=' * 60}")
    print(f"  输出文件: {output_path}")
    print(f"  总记录数: {len(offers)}")
    if FEISHU_APP_ID and FEISHU_APP_SECRET and "--upload" in sys.argv:
        print(f"  飞书表格: https://example.feishu.cn/base/{app_token}")


if __name__ == "__main__":
    main()
