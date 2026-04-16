#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP 全量商户采集脚本 - 增量式

功能:
  1. 从 YP API 分页采集全部商户数据
  2. 严格遵守速率限制: 1000条/10分钟
  3. 增量写入 MySQL (UPSERT), 支持断点续传
  4. 进度持久化, 重启后从断点继续
  5. 完成后输出统计摘要

API: https://www.yeahpromos.com/index/getadvert/getadvert
速率: 1000条/10分钟 -> 每页1000条, 间隔600秒
总量: ~206,640 条 -> 207 批 -> ~34.5 小时

用法:
  python yp_sync_merchants.py              # 运行(断点续传)
  python yp_sync_merchants.py --reset      # 从头开始
"""

import sys
import io
import os
import json
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import requests
import mysql.connector
from mysql.connector import errorcode

# ============================================================
# 配置
# ============================================================

SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"
API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"

PAGE_SIZE = 1000
BATCH_INTERVAL = 600      # 10分钟
REQUEST_TIMEOUT = 30
MAX_RETRIES = 5
RETRY_BACKOFF = 10

MYSQL_CONFIG = dict(
    host='localhost',
    port=3306,
    user='root',
    password='admin',
    database='affiliate_marketing',
    charset='utf8mb4',
    autocommit=False,
)

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "output" / "yp_sync_state.json"
LOG_FILE = BASE_DIR / "logs" / "yp_sync_merchants.log"

# ============================================================
# 日志 & 目录
# ============================================================

(BASE_DIR / "output").mkdir(exist_ok=True)
(BASE_DIR / "logs").mkdir(exist_ok=True)

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

logger = logging.getLogger("yp_sync")
logger.setLevel(logging.INFO)

fh = logging.FileHandler(str(LOG_FILE), encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(ch)


# ============================================================
# 进度状态
# ============================================================

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {"page": 0, "total": 0, "total_saved": 0, "started_at": None, "last_run_at": None}


def save_state(state):
    state["last_run_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


# ============================================================
# YP API
# ============================================================

def fetch_page(page, retry_count=0):
    params = {"site_id": SITE_ID, "page": page, "limit": PAGE_SIZE}
    headers = {"token": TOKEN}
    try:
        resp = requests.get(API_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != "100000" or data.get("status") != "SUCCESS":
            raise Exception(f"API error: code={data.get('code')}, msg={data.get('msg')}")
        inner = data.get("data", {})
        merchants = inner.get("Data", [])
        total = inner.get("Num", 0)
        page_total = inner.get("PageTotal", 0)
        if not isinstance(merchants, list):
            merchants = []
        return {"merchants": merchants, "total": total, "page_total": page_total}
    except requests.exceptions.RequestException as e:
        if retry_count < MAX_RETRIES:
            wait = RETRY_BACKOFF * (retry_count + 1)
            logger.warning(f"  请求失败 (第{retry_count+1}次): {e}, {wait}秒后重试...")
            time.sleep(wait)
            return fetch_page(page, retry_count + 1)
        raise


# ============================================================
# MySQL
# ============================================================

def get_connection():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    conn.time_zone = '+08:00'
    return conn


def ensure_table(conn):
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS yp_merchants (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id   VARCHAR(255) NOT NULL,
            merchant_name TEXT,
            avg_payout    DECIMAL(10,2) DEFAULT 0,
            payout_unit   VARCHAR(50) DEFAULT '%',
            cookie_days   INT DEFAULT 0,
            website       TEXT,
            country       VARCHAR(255),
            country_code  VARCHAR(10),
            transaction_type VARCHAR(50),
            tracking_url  TEXT,
            is_deeplink   VARCHAR(10),
            status        VARCHAR(50) DEFAULT 'UNAPPLIED',
            online_status VARCHAR(50),
            advert_status INT,
            logo          TEXT,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_merchant_id (merchant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def save_merchants(conn, merchants):
    if not merchants:
        return 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        INSERT INTO yp_merchants
            (merchant_id, merchant_name, avg_payout, payout_unit, cookie_days,
             website, country, country_code, transaction_type, tracking_url,
             is_deeplink, status, online_status, advert_status, logo, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            merchant_name=VALUES(merchant_name),
            avg_payout=VALUES(avg_payout),
            payout_unit=VALUES(payout_unit),
            cookie_days=VALUES(cookie_days),
            website=VALUES(website),
            country=VALUES(country),
            country_code=VALUES(country_code),
            transaction_type=VALUES(transaction_type),
            tracking_url=VALUES(tracking_url),
            is_deeplink=VALUES(is_deeplink),
            status=VALUES(status),
            online_status=VALUES(online_status),
            advert_status=VALUES(advert_status),
            logo=VALUES(logo),
            updated_at=VALUES(updated_at)
    """
    rows = []
    for m in merchants:
        country_raw = str(m.get("country", "") or "")
        parts = country_raw.split("/", 1)
        if len(parts) == 2:
            country = f"{parts[0].strip()} - {parts[1].strip()}"
            country_code = parts[0].strip()
        else:
            country, country_code = country_raw, None
        payout = float(m.get("avg_payout", 0) or 0)
        rows.append((
            str(m.get("mid", "")),
            str(m.get("merchant_name", "")),
            payout,
            str(m.get("payout_unit", "%")),
            int(m.get("rd", 0) or 0),
            str(m.get("site_url", "") or ""),
            country,
            country_code,
            str(m.get("transaction_type", "") or ""),
            str(m.get("tracking_url", "") or ""),
            str(m.get("is_deeplink", "0")),
            str(m.get("status", "UNAPPLIED")),
            str(m.get("merchant_status", "") or ""),
            int(m.get("advert_status", 0) or 0),
            str(m.get("logo", "") or ""),
            now,
        ))
    cursor = conn.cursor()
    cursor.executemany(sql, rows)
    conn.commit()
    return len(rows)


def get_db_count(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM yp_merchants")
    return cursor.fetchone()[0]


# ============================================================
# 主流程
# ============================================================

def run(reset=False):
    logger.info("=" * 60)
    logger.info("YP 全量商户同步开始")

    state = load_state()
    if reset:
        state = {"page": 0, "total": 0, "total_saved": 0, "started_at": None, "last_run_at": None}
        logger.info("已重置进度, 从头开始")

    start_page = state.get("page", 0) + 1
    if not state.get("started_at"):
        state["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    ensure_table(conn)
    current_db_count = get_db_count(conn)
    logger.info(f"当前数据库已有 {current_db_count} 条商户")

    if state.get("total", 0) == 0:
        logger.info("获取商户总数...")
        result = fetch_page(1)
        state["total"] = result["total"]
        logger.info(f"YP 平台商户总数: {state['total']:,}")

    total = state["total"]
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    estimated_hours = (total_pages - start_page + 1) * BATCH_INTERVAL / 3600

    logger.info(f"每页 {PAGE_SIZE} 条, 共 {total_pages} 页")
    logger.info(f"从第 {start_page} 页开始, 预计剩余 {estimated_hours:.1f} 小时")
    save_state(state)

    page = start_page
    while page <= total_pages:
        batch_start = time.time()
        try:
            result = fetch_page(page)
            merchants = result["merchants"]
            if not merchants:
                logger.info(f"第 {page} 页返回空数据, 停止")
                break

            saved = save_merchants(conn, merchants)
            state["page"] = page
            state["total_saved"] = (state.get("total_saved", 0) or 0) + saved

            progress = page / total_pages * 100
            elapsed_min = (time.time() - batch_start) / 60
            logger.info(
                f"第 {page}/{total_pages} 页 | "
                f"{len(merchants)} 条 | "
                f"DB写入 {saved} 条 | "
                f"累计 {state['total_saved']:,}/{total:,} ({progress:.1f}%) | "
                f"耗时 {elapsed_min:.1f}min"
            )
            save_state(state)

            elapsed = time.time() - batch_start
            wait = BATCH_INTERVAL - elapsed
            if wait > 0 and page < total_pages:
                logger.info(f"  等待 {wait:.0f} 秒 (速率限制: {BATCH_INTERVAL}s/批)...")
                time.sleep(wait)

        except KeyboardInterrupt:
            logger.info("用户中断, 进度已保存")
            save_state(state)
            conn.close()
            return
        except Exception as e:
            logger.error(f"第 {page} 页出错: {e}, 保存进度并退出")
            save_state(state)
            conn.close()
            raise
        page += 1

    final_count = get_db_count(conn)
    conn.close()

    logger.info("=" * 60)
    logger.info("全量同步完成!")
    logger.info(f"   数据库商户总数: {final_count:,}")
    logger.info(f"   本次写入: {state.get('total_saved', 0):,} 条")
    logger.info(f"   耗时: {state.get('started_at')} -> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 重置状态
    state = {"page": 0, "total": 0, "total_saved": 0, "started_at": None, "last_run_at": None}
    save_state(state)


def run_single_mids(mid_list):
    """按商户ID列表采集指定商户数据（通过 advert_id 参数直接查询）"""
    logger.info("=" * 60)
    logger.info(f"YP 按商户ID采集模式，共 {len(mid_list)} 个商户")

    conn = get_connection()
    ensure_table(conn)

    total_saved = 0
    for mid in mid_list:
        mid = str(mid).strip()
        if not mid:
            continue
        logger.info(f"采集商户 {mid} ...")
        try:
            params = {"site_id": SITE_ID, "advert_id": mid, "page": 1, "limit": 100}
            headers = {"token": TOKEN}
            resp = requests.get(API_URL, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != "100000" or data.get("status") != "SUCCESS":
                logger.error(f"  API 错误: code={data.get('code')}, msg={data.get('msg')}")
                continue
            merchants = data.get("data", {}).get("Data", [])
            if not merchants:
                logger.warning(f"  商户 {mid} 未找到数据")
                continue
            # API 可能返回重复数据，按 merchant_id 去重
            seen = set()
            unique_merchants = []
            for m in merchants:
                mid_val = str(m.get("mid", "") or m.get("merchant_id", "") or "")
                if mid_val and mid_val not in seen:
                    seen.add(mid_val)
                    unique_merchants.append(m)
            if len(unique_merchants) < len(merchants):
                logger.info(f"  商户 {mid}: API 返回 {len(merchants)} 条，去重后 {len(unique_merchants)} 条")
            saved = save_merchants(conn, unique_merchants)
            total_saved += saved
            names = [m.get("merchant_name", "?") for m in unique_merchants]
            logger.info(f"  商户 {mid} ({', '.join(names)}) — 写入 {saved} 条")
        except Exception as e:
            logger.error(f"  商户 {mid} 采集失败: {e}")

    conn.close()
    logger.info("=" * 60)
    logger.info(f"按商户ID采集完成，共写入 {total_saved} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YP 全量商户同步")
    parser.add_argument("--reset", action="store_true", help="从头开始")
    parser.add_argument("--mid", nargs="+", help="指定商户ID（空格分隔），只采集这些商户")
    args = parser.parse_args()
    if args.mid:
        run_single_mids(args.mid)
    else:
        run(reset=args.reset)
