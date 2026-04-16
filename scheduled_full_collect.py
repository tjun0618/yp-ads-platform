#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时全自动全量采集 YP 商户数据
----------------------------------------
功能:
  - 定时自动分批采集，每批 1000 条，采集完暂停 10 分钟
  - 遇到 API 限流自动重试，暂停后继续
  - 采集完成自动退出
  - 支持断点续采，停止后下次启动自动继续
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
OUTPUT_DIR = Path(__file__).parent / "output"
STATE_FILE = OUTPUT_DIR / "full_collect_state.json"

PAGE_SIZE = 100          # 每页条数
BATCH_SIZE = 10 * PAGE_SIZE  # 每批条数 = 1000
PAUSE_MINUTES = 10       # 每批后暂停分钟
RETRY_WAIT_MINUTES = 15   # API失败后等待分钟
MAX_RETRIES = 3          # 单页最大重试次数

# ============================================================
# YP Merchant API
# ============================================================

def get_merchants_page(page=1, limit=100, elite=0):
    """获取单页商户数据"""
    headers = {"token": TOKEN}
    params = {
        "site_id": SITE_ID,
        "elite": elite,
        "page": page,
        "limit": limit
    }

    response = requests.get(MERCHANT_API_URL, headers=headers, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")

    data = response.json()

    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        inner = data.get("data", {})
        if isinstance(inner, dict) and "Data" in inner:
            merchants = inner.get("Data", [])
            total = inner.get("total", 0)
            return merchants, total
        else:
            merchants = data.get("Data", [])
            total = data.get("total", 0)
            return merchants, total
    else:
        raise Exception(f"API 返回错误 status: {data.get('status')}, msg: {data.get('msg', '')}")


def clean_merchant_data(m):
    """清洗原始商户数据为标准格式"""
    country_raw = m.get('country', '')
    if country_raw and '/' in country_raw:
        country = country_raw.replace('/', ' - ')
    else:
        country = country_raw

    if not country:
        country_code = ''
    elif '-' in country:
        country_code = country.split('-')[0].strip()
    else:
        country_code = country[:2] if country else ''

    try:
        avg_payout = float(m.get('avg_payout', 0))
    except:
        avg_payout = 0.0

    try:
        cookie_days = int(m.get('rd', 0))
    except:
        cookie_days = 0

    is_deeplink = "Yes" if str(m.get('is_deeplink', '0')) == "1" else "No"

    return {
        "merchant_id": str(m.get('mid', '')),
        "merchant_name": m.get('merchant_name', ''),
        "avg_payout": avg_payout,
        "payout_unit": m.get('payout_unit', '%'),
        "cookie_days": cookie_days,
        "website": m.get('site_url', ''),
        "country": country,
        "country_code": country_code,
        "transaction_type": m.get('transaction_type', ''),
        "tracking_url": m.get('tracking_url', ''),
        "is_deeplink": is_deeplink,
        "status": m.get('status', 'UNAPPLIED'),
        "online_status": m.get('merchant_status', 'onLine'),
        "advert_status": m.get('advert_status', 0),
        "logo": m.get('logo', '')
    }


def save_state(current_page, total_count, collected_count):
    """保存采集状态用于断点续采"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "current_page": current_page,
        "total_count": total_count,
        "collected_count": collected_count,
        "last_update": datetime.now().isoformat()
    }
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_state():
    """加载采集状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def init_mysql():
    """初始化 MySQL 表"""
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS yp_merchants_full")
    cursor.execute("""
        CREATE TABLE yp_merchants_full (
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
    cursor.close()
    conn.close()
    print("[MySQL] 表 yp_merchants_full 已初始化")


def batch_save_to_mysql(merchants):
    """批量保存商户数据到 MySQL"""
    if not merchants:
        return 0

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    inserted = 0
    for m in merchants:
        sql = """
            INSERT IGNORE INTO yp_merchants_full
            (merchant_id, merchant_name, avg_payout, payout_unit, cookie_days, website,
             country, country_code, transaction_type, tracking_url, is_deeplink,
             status, online_status, advert_status, logo, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """
        values = (
            m['merchant_id'],
            m['merchant_name'],
            m['avg_payout'],
            m['payout_unit'],
            m['cookie_days'],
            m['website'],
            m['country'],
            m['country_code'],
            m['transaction_type'],
            m['tracking_url'],
            m['is_deeplink'],
            m['status'],
            m['online_status'],
            m['advert_status'],
            m['logo']
        )
        try:
            cursor.execute(sql, values)
            inserted += 1
        except Exception as e:
            print(f"  [WARN] 插入失败 {m['merchant_id']}: {e}")
            continue

    conn.commit()
    cursor.close()
    conn.close()
    return inserted


def scheduled_full_collect():
    """定时全自动全量采集，支持断点续采"""
    print("=" * 60)
    print("YP Merchants - 定时全自动全量采集")
    print("=" * 60)
    print(f"  Site ID: {SITE_ID}")
    print(f"  Token: {TOKEN[:8]}...")
    print(f"  每页: {PAGE_SIZE} 条")
    print(f"  每批: {BATCH_SIZE} 条 = {BATCH_SIZE//PAGE_SIZE} 页")
    print(f"  批间隔: {PAUSE_MINUTES} 分钟")
    print()

    # 初始化 MySQL 表 - 只在第一次启动时创建，断点重启不覆盖已采集数据
    state = load_state()
    if state is None:
        print("[MySQL] 初始化表...")
        init_mysql()
    else:
        print(f"[断点] 从断点继续，已经采集 {state.get('collected_count', 0):,} 条")

    start_page = 1
    collected = 0
    total_api = 0

    if state:
        start_page = state.get("current_page", 1)
        collected = state.get("collected_count", 0)
        total_api = state.get("total_count", 0)
        print(f"[断点] 从第 {start_page} 页继续，已采集 {collected} 条")
    else:
        print("[新采集] 从第 1 页开始...")
        # 获取第一页得到总数
        try:
            print("\n[开始] 获取第 1 页获取总数...")
            _, total = get_merchants_page(1, PAGE_SIZE)
            total_api = total
            print(f"  [OK] API 报告总商户数: {total:,}")
        except Exception as e:
            print(f"  [ERROR] 获取第一页失败: {e}")
            return

    page = start_page
    batch_merchants = []
    batch_count = 0
    retries = 0

    try:
        while True:
            if collected >= total_api:
                print(f"\n[完成] 已采集 {collected}/{total_api} 条，完成!")
                if batch_merchants:
                    print(f"[保存] 最后一批 {len(batch_merchants)} 条...")
                    inserted = batch_save_to_mysql(batch_merchants)
                    collected += inserted
                    save_state(page, total_api, collected)
                break

            print(f"\n[采集] 第 {page} 页... ", end='', flush=True)

            success = False
            merchants_page = None
            for retry in range(MAX_RETRIES):
                try:
                    merchants_page, _ = get_merchants_page(page, PAGE_SIZE)
                    print(f"获取 {len(merchant_page)} 条", flush=True)
                    success = True
                    break
                except Exception as e:
                    print(f"\n  [ERROR] 尝试 {retry+1}/{MAX_RETRIES} 失败: {e}")
                    if retry < MAX_RETRIES - 1:
                        wait_seconds = RETRY_WAIT_MINUTES * 60
                        print(f"  [WAIT] 等待 {RETRY_WAIT_MINUTES} 分钟后重试...")
                        for i in range(wait_seconds):
                            time.sleep(1)
                            if i % 60 == 0:
                                print(f"    {wait_seconds - i} 秒剩余", flush=True)

            if not success:
                print(f"\n  [FAIL] 连续 {MAX_RETRIES} 次失败，停止采集")
                print("         下次启动会自动从当前页继续")
                if batch_merchants:
                    print(f"  [保存] 当前批 {len(batch_merchants)} 条...")
                    inserted = batch_save_to_mysql(batch_merchants)
                    collected += inserted
                save_state(page, total_api, collected)
                return

            # 清洗添加到批
            for m in merchants_page:
                cleaned = clean_merchant_data(m)
                batch_merchants.append(cleaned)
                collected += 1
                batch_count += 1

            page += 1

            # 达到批大小，保存并暂停
            if batch_count >= BATCH_SIZE:
                print(f"\n[批次完成] 已收集 {len(batch_merchants)} 条，保存到 MySQL...")
                inserted = batch_save_to_mysql(batch_merchants)
                collected += inserted
                batch_merchants = []
                batch_count = 0
                collected_total = collected
                if total_api > 0:
                    pct = (collected_total / total_api * 100)
                    print(f"  [进度] {collected_total}/{total_api:,} ({pct:.1f}%)")
                else:
                    print(f"  [进度] {collected_total}/?  (total unknown from API)")
                save_state(page, total_api, collected_total)
                pause_seconds = PAUSE_MINUTES * 60
                print(f"  [暂停] {PAUSE_MINUTES} 分钟 ({pause_seconds} 秒) 避免 API 限流...")
                for i in range(pause_seconds):
                    time.sleep(1)
                    if i % 60 == 0:
                        remaining = pause_seconds - i
                        print(f"    {remaining} 秒剩余", flush=True)
                print(f"  [继续] 开始下一批...", flush=True)

    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断采集，已保存当前进度，可以随时继续")
        if batch_merchants:
            print(f"[保存] 当前未完成批 {len(batch_merchants)} 条...")
            inserted = batch_save_to_mysql(batch_merchants)
            collected += inserted
        save_state(page, total_api, collected)
        print("退出")
        return

    # 完成
    print("\n" + "=" * 60)
    print("  ✅ 全量采集完成!")
    print(f"  总采集: {collected:,} 条")
    print(f"  MySQL: affiliate_marketing.yp_merchants_full")
    print(f"  状态文件: {STATE_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    scheduled_full_collect()
