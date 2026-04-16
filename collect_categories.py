#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP Platform - Categories (类别) 数据独立采集脚本

功能:
  1. 通过 YP Category API 采集类别数据
  2. 一次性获取全部类别 (通常约 148 条)
  3. 数据保存为 JSON 格式
  4. 支持上传到飞书多维表格

API 端点: https://www.yeahpromos.com/index/apioffer/getcategory
认证方式: GET 参数 token=TOKEN
请求方式: GET
速率限制: 无明确限制

注意: Category API 的认证方式与其他 API 不同!
  - Merchant/Offer API: token 放在 HTTP Header 中
  - Category API: token 作为 GET 参数传递
"""

import requests
import json
import time
import sys
import io
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

CATEGORY_API_URL = "https://www.yeahpromos.com/index/apioffer/getcategory"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = "categories_data.json"


# ============================================================
# YP Category API
# ============================================================

def get_categories(site_id, token):
    """
    调用 YP Category API 获取全部类别列表

    Args:
        site_id: 网站/频道 ID
        token: API Token

    Returns:
        list: 类别列表，每个类别包含以下字段:
            - category_id: 类别 ID (整数)
            - category_name: 类别名称 (字符串)

    注意事项:
        - Category API 返回的是全部类别，无需分页
        - 通常返回约 148 个类别
        - 响应可能是 list 或 dict 格式

    Raises:
        Exception: API 请求失败时抛出异常
    """
    # 重要: Category API 的 token 作为 GET 参数，而非 Header!
    params = {
        "site_id": site_id,
        "token": token
    }

    response = requests.get(CATEGORY_API_URL, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    # Category API 有多种响应格式
    if isinstance(data, list):
        # 直接返回列表
        return data
    elif isinstance(data, dict):
        if data.get("code") == 100000 or data.get("status") == "SUCCESS":
            return data.get("data", [])
        else:
            raise Exception(f"API Error: {data}")
    else:
        raise Exception(f"Unexpected response type: {type(data).__name__}")


def clean_category_data(category):
    """
    清洗和标准化类别数据

    输入字段可能为:
        - category_id / id
        - category_name / name
    """
    return {
        "category_id": int(category.get("category_id") or category.get("id", 0)),
        "category_name": str(category.get("category_name") or category.get("name", "")),
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


def upload_to_feishu(categories, feishu_app_id, feishu_app_secret):
    """将类别数据上传到飞书多维表格"""
    print("\n[Feishu] 连接飞书...")
    client = FeishuBitableClient(feishu_app_id, feishu_app_secret)
    print("  [OK] 认证成功")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    bitable_name = f"YP Categories ({timestamp})"
    print(f"[Feishu] 创建多维表格: {bitable_name}")
    app_token = client.create_bitable(bitable_name)
    print(f"  [OK] App Token: {app_token}")

    tables = client.list_tables(app_token)
    table_id = tables[0]["table_id"] if tables else None

    print("[Feishu] 添加字段...")
    client.add_field(app_token, table_id, "Category ID", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "Category Name", 1)

    print("[Feishu] 上传数据...")
    records = []
    for c in categories:
        records.append({
            "fields": {
                "Category ID": c["category_id"],
                "Category Name": c["category_name"],
            }
        })

    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"[Feishu] 完成: {uploaded} 上传成功, {failed} 失败")
    print(f"[Feishu] URL: https://example.feishu.cn/base/{app_token}")

    return app_token, uploaded, failed


# ============================================================
# Statistics
# ============================================================

def print_statistics(categories):
    """打印类别数据统计信息"""
    if not categories:
        print("  无数据")
        return

    total = len(categories)
    names = [c["category_name"] for c in categories if c["category_name"]]

    print(f"\n{'=' * 50}")
    print(f"  数据统计")
    print(f"{'=' * 50}")
    print(f"  总类别数: {total}")
    print(f"  有效类别名: {len(names)}")
    print(f"  无名称类别: {total - len(names)}")

    # 按首字母分组
    groups = {}
    for name in names:
        first_char = name[0].upper() if name else "#"
        groups[first_char] = groups.get(first_char, 0) + 1

    print(f"\n  首字母分布 (共 {len(groups)} 个起始字母):")
    for char in sorted(groups.keys()):
        bar = "#" * min(groups[char], 20)
        print(f"    {char}: {bar} ({groups[char]})")

    # 前 10 个和后 10 个类别
    print(f"\n  前 10 个类别:")
    for c in categories[:10]:
        print(f"    {c['category_id']:>5}: {c['category_name']}")

    if len(categories) > 10:
        print(f"\n  后 10 个类别:")
        for c in categories[-10:]:
            print(f"    {c['category_id']:>5}: {c['category_name']}")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("  YP Categories (类别) 数据采集")
    print("=" * 60)
    print(f"  Site ID: {SITE_ID}")
    print(f"  Token: {TOKEN[:8]}...")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Step 1: 采集数据
    print("[Step 1] 采集类别数据...")
    print("  (类别数据通常约 148 条，一次性获取全部)")
    print()

    try:
        categories_raw = get_categories(SITE_ID, TOKEN)
    except Exception as e:
        print(f"  [ERROR] {e}")
        return

    print(f"  获取 {len(categories_raw)} 个类别")

    # Step 2: 清洗数据
    print(f"\n[Step 2] 清洗数据...")
    categories = [clean_category_data(c) for c in categories_raw]
    print(f"  清洗完成: {len(categories)} 条")

    # Step 3: 保存数据
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)
    print(f"\n[Step 3] 数据已保存: {output_path}")

    # Step 4: 统计
    print_statistics(categories)

    # Step 5: 上传到飞书 (可选)
    app_token = None
    if FEISHU_APP_ID and FEISHU_APP_SECRET and "--upload" in sys.argv:
        print(f"\n[Step 4] 上传到飞书...")
        try:
            app_token, uploaded, failed = upload_to_feishu(categories, FEISHU_APP_ID, FEISHU_APP_SECRET)
            result = {
                "app_token": app_token,
                "uploaded": uploaded,
                "failed": failed,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_records": len(categories)
            }
            result_path = OUTPUT_DIR / "categories_feishu_result.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  结果已保存: {result_path}")
        except Exception as e:
            print(f"  [ERROR] 上传失败: {e}")
    else:
        print(f"\n[Step 4] 跳过飞书上传")
        print(f"  提示: 添加 --upload 参数即可上传到飞书")

    # 全部类别列表
    print(f"\n{'=' * 60}")
    print(f"  全部类别列表")
    print(f"{'=' * 60}")
    print(f"  {'ID':>5} | {'Category Name'}")
    print(f"  {'-'*5}-+-{'-'*50}")
    for c in categories:
        print(f"  {c['category_id']:>5} | {c['category_name']}")

    print(f"\n{'=' * 60}")
    print("  采集完成!")
    print(f"{'=' * 60}")
    print(f"  输出文件: {output_path}")
    print(f"  总记录数: {len(categories)}")
    if app_token:
        print(f"  飞书表格: https://example.feishu.cn/base/{app_token}")


if __name__ == "__main__":
    main()
