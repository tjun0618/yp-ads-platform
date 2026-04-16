#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP Platform - Merchants (品牌) 数据独立采集脚本

功能:
  1. 通过 YP Merchant API 采集品牌数据
  2. 支持分页采集，可获取全量数据
  3. 支持按状态筛选 (elite/非elite)
  4. 数据保存为 JSON 格式
  5. 支持保存到 MySQL 数据库
  6. 支持上传到飞书多维表格

API 端点: https://www.yeahpromos.com/index/getadvert/getadvert
认证方式: HTTP Header {"token": TOKEN}
请求方式: GET
速率限制: 每分钟 10 次
"""

import requests
import json
import time
import sys
import io
import mysql.connector
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

# MySQL 数据库配置
MYSQL_CONFIG = dict(
    host='localhost',
    port=3306,
    user='root',
    password='admin',
    database='affiliate_marketing',
    charset='utf8mb4'
)

MERCHANT_API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"

OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_FILE = "merchants_data.json"




# ============================================================
# YP Merchant API
# ============================================================

def get_merchants(site_id, token, page=1, limit=20, elite=0):
    """
    调用 YP Merchant API 获取品牌列表

    Args:
        site_id: 网站/频道 ID
        token: API Token
        page: 页码 (从 1 开始)
        limit: 每页数量
        elite: 0=全部, 1=仅精英品牌

    Returns:
        tuple: (merchants_list, total_count, page_total)

    原始字段说明:
        - mid: 品牌 ID (整数)
        - merchant_name: 品牌名称
        - logo: 品牌 Logo URL
        - avg_payout: 平均佣金率 (数字)
        - payout_unit: 佣金单位 (通常为 "%")
        - rd: Cookie 持续天数 (整数)
        - site_url: 品牌网站 URL
        - country: 国家信息 (格式: "US/United States(US)")
        - transaction_type: 交易类型 (CPS/CPA 等)
        - tracking_url: 追踪链接
        - is_deeplink: 是否支持深度链接 ("1"/"0")
        - status: 申请状态 (UNAPPLIED/APPROVED/PENDING)
        - merchant_status: 在线状态 (onLine/offLine)
        - advert_status: 广告状态 (整数)
    """
    headers = {"token": token}
    params = {
        "site_id": site_id,
        "elite": elite,
        "page": page,
        "limit": limit
    }

    response = requests.get(MERCHANT_API_URL, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        # Merchant API 数据路径可能为:
        # 格式 A: data.data.Data (新格式，嵌套)
        # 格式 B: data.Data (旧格式，直接)
        inner = data.get("data", {})
        if isinstance(inner, dict) and "Data" in inner:
            merchants = inner["Data"]
            total = inner.get("Num", 0)
            page_total = inner.get("PageTotal", 1)
        elif isinstance(data, dict) and "Data" in data:
            merchants = data["Data"]
            total = data.get("Num", 0)
            page_total = data.get("PageTotal", 1)
        else:
            merchants = []
            total = 0
            page_total = 0

        if not isinstance(merchants, list):
            merchants = []

        return merchants, total, page_total
    else:
        raise Exception(f"API Error: {data}")


def get_all_merchants(site_id, token, elite=0, max_pages=None):
    """
    分页获取全部品牌数据

    Args:
        site_id: 网站/频道 ID
        token: API Token
        elite: 0=全部, 1=仅精英品牌
        max_pages: 最大页数 (可选)

    Returns:
        list: 所有品牌数据
    """
    all_merchants = []
    page = 1

    while True:
        if max_pages and page > max_pages:
            print(f"  达到最大页数限制 ({max_pages}), 停止采集")
            break

        print(f"  采集第 {page} 页...", end=" ")
        try:
            merchants, total, page_total = get_merchants(site_id, token, page=page, limit=100, elite=elite)
        except Exception as e:
            print(f"失败: {e}")
            break

        if not merchants:
            print("无数据，停止")
            break

        all_merchants.extend(merchants)
        print(f"获取 {len(merchants)} 条 (累计 {len(all_merchants)}/{total})")

        if page >= page_total or len(all_merchants) >= total:
            print(f"  采集完成，共 {len(all_merchants)} 条")
            break

        page += 1
        time.sleep(0.5)

    return all_merchants


def clean_merchant_data(merchant):
    """
    清洗和标准化品牌数据

    转换规则:
    - avg_payout: 确保为浮点数
    - country: "US/United States(US)" -> "US - United States(US)"
    - is_deeplink: "1"/"0" -> "Yes"/"No"
    - rd: 确保为整数
    """
    country_raw = str(merchant.get("country", ""))
    parts = country_raw.split("/", 1)
    country = f"{parts[0].strip()} - {parts[1].strip()}" if len(parts) == 2 else country_raw

    is_deeplink = str(merchant.get("is_deeplink", "0"))
    payout = float(merchant.get("avg_payout", 0) or 0)

    return {
        "merchant_id": int(merchant.get("mid", 0)),
        "merchant_name": str(merchant.get("merchant_name", "")),
        "logo": str(merchant.get("logo", "")),
        "avg_payout": payout,
        "payout_unit": str(merchant.get("payout_unit", "%")),
        "cookie_days": int(merchant.get("rd", 0) or 0),
        "website": str(merchant.get("site_url", "") or ""),
        "country_raw": country_raw,
        "country": country,
        "transaction_type": str(merchant.get("transaction_type", "")),
        "is_deeplink": "Yes" if is_deeplink == "1" else "No",
        "status": str(merchant.get("status", "UNAPPLIED")),
        "online_status": str(merchant.get("merchant_status", "")),
        "tracking_url": str(merchant.get("tracking_url", "") or ""),
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


def upload_to_feishu(merchants, feishu_app_id, feishu_app_secret):
    """将品牌数据上传到飞书多维表格"""
    print("\n[Feishu] 连接飞书...")
    client = FeishuBitableClient(feishu_app_id, feishu_app_secret)
    print("  [OK] 认证成功")

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    bitable_name = f"YP Merchants ({timestamp})"
    print(f"[Feishu] 创建多维表格: {bitable_name}")
    app_token = client.create_bitable(bitable_name)
    print(f"  [OK] App Token: {app_token}")

    tables = client.list_tables(app_token)
    table_id = tables[0]["table_id"] if tables else None

    print("[Feishu] 添加字段...")
    client.add_field(app_token, table_id, "Merchant ID", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "Merchant Name", 1)
    client.add_field(app_token, table_id, "Avg Payout (%)", 2, {"formatter": "0.00"})
    client.add_field(app_token, table_id, "Cookie Days", 2, {"formatter": "0"})
    client.add_field(app_token, table_id, "Website", 1)
    client.add_field(app_token, table_id, "Country", 1)
    client.add_field(app_token, table_id, "Transaction Type", 1)
    client.add_field(app_token, table_id, "Status", 3,
                     {"options": [{"name": "UNAPPLIED"}, {"name": "APPROVED"}, {"name": "PENDING"}]})
    client.add_field(app_token, table_id, "Online Status", 3,
                     {"options": [{"name": "onLine"}, {"name": "offLine"}]})
    client.add_field(app_token, table_id, "Deep Link", 3,
                     {"options": [{"name": "Yes"}, {"name": "No"}]})
    client.add_field(app_token, table_id, "Logo", 1)

    print("[Feishu] 上传数据...")
    records = []
    for m in merchants:
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
        records.append({"fields": fields})

    uploaded, failed = client.batch_create_records(app_token, table_id, records)
    print(f"[Feishu] 完成: {uploaded} 上传成功, {failed} 失败")
    print(f"[Feishu] URL: https://example.feishu.cn/base/{app_token}")

    return app_token, uploaded, failed


# ============================================================
# MySQL Save
# ============================================================

def save_to_mysql(merchants):
    """将商户数据保存到 MySQL 数据库"""
    print("\n[Step 5] 保存到 MySQL...")
    
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    
    # 删除旧表重新创建（保证结构最新）
    cursor.execute("DROP TABLE IF EXISTS yp_merchants")
    cursor.execute("""
        CREATE TABLE yp_merchants (
            merchant_id VARCHAR(255) PRIMARY KEY,
            merchant_name TEXT,
            avg_payout DECIMAL(10,2),
            payout_unit VARCHAR(50),
            cookie_days INT,
            website TEXT,
            country VARCHAR(255),
            country_code VARCHAR(10),
            transaction_type VARCHAR(50),
            tracking_url TEXT,
            is_deeplink VARCHAR(10),
            status VARCHAR(50),
            online_status VARCHAR(50),
            advert_status INT,
            logo TEXT,
            created_at DATETIME,
            updated_at DATETIME
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    
    # 插入数据
    inserted = 0
    for m in merchants:
        # 提取国家码 (从 "US - United States(US)" 提取 "US")
        country_code = m['country'].split('-')[0].strip() if '-' in m['country'] else m['country'][:2] if m['country'] else ''
        
        sql = """
            INSERT IGNORE INTO yp_merchants 
            (merchant_id, merchant_name, avg_payout, payout_unit, cookie_days, website, 
             country, country_code, transaction_type, tracking_url, is_deeplink, 
             status, online_status, advert_status, logo, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        values = (
            str(m['merchant_id']),
            m['merchant_name'],
            m['avg_payout'],
            m.get('payout_unit', '%'),
            m['cookie_days'],
            m.get('website', ''),
            m['country'],
            country_code,
            m.get('transaction_type', ''),
            m.get('tracking_url', ''),
            m['is_deeplink'],
            m['status'],
            m['online_status'],
            m.get('advert_status', 0),
            m.get('logo', '')
        )
        cursor.execute(sql, values)
        inserted += 1
        if inserted % 500 == 0:
            conn.commit()
            print(f"  已插入: {inserted}/{len(merchants)}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"  [OK] 完成: {inserted} 条记录已保存到 yp_merchants 表")
    return inserted


# ============================================================
# Statistics
# ============================================================

def print_statistics(merchants):
    """打印品牌数据统计信息"""
    if not merchants:
        print("  无数据")
        return

    total = len(merchants)
    online = sum(1 for m in merchants if m["online_status"] == "onLine")
    approved = sum(1 for m in merchants if m["status"] == "APPROVED")
    with_payout = [m for m in merchants if m["avg_payout"] > 0]
    avg_payout = sum(m["avg_payout"] for m in with_payout) / max(len(with_payout), 1)
    avg_cookie = sum(m["cookie_days"] for m in merchants) / total
    deeplink = sum(1 for m in merchants if m["is_deeplink"] == "Yes")

    # 国家分布
    countries = {}
    for m in merchants:
        code = m["country_raw"].split("/")[0].strip() if m["country_raw"] else "Unknown"
        countries[code] = countries.get(code, 0) + 1
    top_countries = sorted(countries.items(), key=lambda x: x[1], reverse=True)[:5]

    print(f"\n{'=' * 50}")
    print(f"  数据统计")
    print(f"{'=' * 50}")
    print(f"  总品牌数: {total}")
    print(f"  在线品牌: {online}")
    print(f"  离线品牌: {total - online}")
    print(f"  已申请: {approved}")
    print(f"  未申请: {total - approved}")
    print(f"  有佣金率: {len(with_payout)}")
    print(f"  平均佣金率: {avg_payout:.2f}%")
    print(f"  平均Cookie天数: {avg_cookie:.0f} 天")
    print(f"  支持深度链接: {deeplink}")

    print(f"\n  佣金率分布:")
    high = sum(1 for m in merchants if m["avg_payout"] >= 10)
    mid = sum(1 for m in merchants if 5 <= m["avg_payout"] < 10)
    low = sum(1 for m in merchants if 1 <= m["avg_payout"] < 5)
    print(f"    >=10%: {high} 个品牌")
    print(f"    5-10%: {mid} 个品牌")
    print(f"    1-5%:  {low} 个品牌")
    print(f"    0%:    {total - high - mid - low} 个品牌")

    print(f"\n  前 5 个国家:")
    for code, count in top_countries:
        print(f"    {code}: {count} 个品牌")

    # 高佣金品牌 Top 5
    top_payout = sorted(with_payout, key=lambda x: x["avg_payout"], reverse=True)[:5]
    if top_payout:
        print(f"\n  高佣金品牌 Top 5:")
        for m in top_payout:
            print(f"    {m['merchant_name']}: {m['avg_payout']}% (Cookie {m['cookie_days']}天)")


# ============================================================
# Main
# ============================================================

def main():
    print("=" * 60)
    print("  YP Merchants (品牌) 数据采集")
    print("=" * 60)
    print(f"  Site ID: {SITE_ID}")
    print(f"  Token: {TOKEN[:8]}...")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # 参数解析
    fetch_all = "--all" in sys.argv
    elite_only = "--elite" in sys.argv

    print("[Step 1] 采集品牌数据...")
    if fetch_all:
        print("  模式: 全量采集")
    else:
        print("  模式: 单页采集 (20 条)")
    if elite_only:
        print("  筛选: 仅精英品牌")
    print()

    if fetch_all:
        merchants_raw = get_all_merchants(SITE_ID, TOKEN, elite=1 if elite_only else 0)
    else:
        try:
            merchants_raw, total, page_total = get_merchants(
                SITE_ID, TOKEN, page=1, limit=20, elite=1 if elite_only else 0
            )
            print(f"  获取 {len(merchants_raw)} 条 (总 {total} 条, 共 {page_total} 页)")
        except Exception as e:
            print(f"  [ERROR] {e}")
            return

    # 清洗数据
    print(f"\n[Step 2] 清洗数据...")
    merchants = [clean_merchant_data(m) for m in merchants_raw]
    print(f"  清洗完成: {len(merchants)} 条")

    # 保存数据
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / OUTPUT_FILE
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    print(f"\n[Step 3] 数据已保存: {output_path}")

    # 统计
    print_statistics(merchants)

    # 保存到 MySQL (可选)
    if "--mysql" in sys.argv:
        try:
            mysql_inserted = save_to_mysql(merchants)
        except Exception as e:
            print(f"  [ERROR] MySQL 保存失败: {e}")
    else:
        print(f"\n[Step 5] 跳过 MySQL 保存")
        print(f"  提示: 添加 --mysql 参数即可保存到数据库")

    # 上传到飞书 (可选)
    app_token = None
    if FEISHU_APP_ID and FEISHU_APP_SECRET and "--upload" in sys.argv:
        print(f"\n[Step 6] 上传到飞书...")
        try:
            app_token, uploaded, failed = upload_to_feishu(merchants, FEISHU_APP_ID, FEISHU_APP_SECRET)
            result = {
                "app_token": app_token,
                "uploaded": uploaded,
                "failed": failed,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_records": len(merchants)
            }
            result_path = OUTPUT_DIR / "merchants_feishu_result.json"
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"  结果已保存: {result_path}")
        except Exception as e:
            print(f"  [ERROR] 上传失败: {e}")
    else:
        print(f"\n[Step 6] 跳过飞书上传")
        print(f"  提示: 添加 --upload 参数即可上传到飞书")

    # 样本
    print(f"\n{'=' * 60}")
    print(f"  品牌样本 (前 3 条)")
    print(f"{'=' * 60}")
    for i, m in enumerate(merchants[:3]):
        print(f"\n  [{i+1}] {m['merchant_name']}")
        print(f"      ID: {m['merchant_id']}")
        print(f"      佣金: {m['avg_payout']}% | Cookie: {m['cookie_days']}天")
        print(f"      国家: {m['country']}");
        print(f"      网站: {m['website']}");
        print(f"      状态: {m['status']} | 在线: {m['online_status']}");

    print(f"\n{'=' * 60}");
    print("  采集完成!");
    print(f"{'=' * 60}");
    print(f"  输出文件: {output_path}");
    print(f"  总记录数: {len(merchants)}");
    if "--mysql" in sys.argv:
        print(f"  MySQL: yp_merchants 表已更新");
    if app_token:
        print(f"  飞书表格: https://example.feishu.cn/base/{app_token}");


if __name__ == "__main__":
    main()
