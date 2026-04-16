#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
sync_merchants.py — YP 商户信息每日轮询同步脚本

功能：
  1. 调用 YP API 拉取最新全量商户列表
  2. 与 MySQL yp_merchants 对比，检测新增 / 删除 / 变动
  3. 将变动记录写入 merchant_change_log 表
  4. UPSERT 更新 yp_merchants 表
  5. 打印变动摘要，可配合 Windows 计划任务每日执行

用法：
  python -X utf8 sync_merchants.py              # 正常同步
  python -X utf8 sync_merchants.py --dry-run    # 仅对比，不写库
"""

import sys
import time
import json
import requests
import mysql.connector
from datetime import datetime
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────────────────────────────
SITE_ID  = "12002"
TOKEN    = "7951dc7484fa9f9d"
API_URL  = "https://www.yeahpromos.com/index/getadvert/getadvert"

DB_CONFIG = dict(
    host='localhost', port=3306,
    user='root', password='admin',
    database='affiliate_marketing',
    charset='utf8mb4',
    autocommit=False,
)

# 监控哪些字段的变动（字段名必须与 API 返回的 key 一致）
WATCH_FIELDS = [
    ('merchant_name', 'name'),
    ('avg_payout',    'avg_payout'),
    ('cookie_days',   'cookie_days'),
    ('website',       'website'),
    ('country',       'country'),
    ('online_status', 'merchant_status'),  # API key → DB column
    ('status',        'status'),           # APPROVED / PENDING / UNAPPLIED
]

DRY_RUN = '--dry-run' in sys.argv

LOG_FILE = Path(__file__).parent / 'output' / 'sync_merchants.log'
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# ─── 日志 ──────────────────────────────────────────────────────────────────
def log(tag, msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}][{tag}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except Exception:
        pass

# ─── 建表（如果不存在）────────────────────────────────────────────────────
CREATE_CHANGE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS merchant_change_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id  VARCHAR(32) NOT NULL,
    merchant_name VARCHAR(200),
    change_type  ENUM('added', 'removed', 'changed') NOT NULL,
    field_name   VARCHAR(64),
    old_value    TEXT,
    new_value    TEXT,
    checked_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mid (merchant_id),
    INDEX idx_checked (checked_at),
    INDEX idx_type (change_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户信息每日变动日志';
"""

# ─── 从 YP API 拉取全量商户 ────────────────────────────────────────────────
def fetch_all_merchants():
    log("API", "开始拉取全量商户...")
    all_merchants = []
    page = 1
    while True:
        try:
            resp = requests.get(
                API_URL,
                headers={"token": TOKEN},
                params={"site_id": SITE_ID, "page": page, "limit": 100, "elite": 0},
                timeout=30
            )
            data = resp.json()
            if data.get('code') != 0 and str(data.get('code')) != '0':
                log("API", f"API 返回错误: {data}")
                break
            items = (data.get('data') or {}).get('list') or []
            if not items:
                break
            all_merchants.extend(items)
            total = int((data.get('data') or {}).get('total', 0))
            log("API", f"  第 {page} 页，本页 {len(items)} 条，累计 {len(all_merchants)} / {total}")
            if len(all_merchants) >= total:
                break
            page += 1
            time.sleep(0.5)  # 避免触发速率限制
        except Exception as e:
            log("API", f"第 {page} 页请求失败: {e}")
            break
    log("API", f"拉取完成，共 {len(all_merchants)} 个商户")
    return all_merchants

# ─── 从 API 数据构建规范化字典 ─────────────────────────────────────────────
def normalize_merchant(m: dict) -> dict:
    """把 API 返回的字段映射到统一格式"""
    return {
        'merchant_id':   str(m.get('id') or m.get('advert_id') or ''),
        'merchant_name': (m.get('name') or '').strip(),
        'avg_payout':    str(m.get('avg_payout') or '0'),
        'cookie_days':   str(m.get('cookie_days') or '0'),
        'website':       (m.get('website') or '').strip(),
        'country':       (m.get('country') or '').strip().upper(),
        'online_status': 'ONLINE' if str(m.get('merchant_status', '')).lower() in ('online', '1') else 'OFFLINE',
        'status':        (m.get('status') or 'UNAPPLIED').upper(),
        'is_deeplink':   str(m.get('is_deeplink') or '0'),
        'logo':          (m.get('logo') or '').strip(),
        'transaction_type': (m.get('transaction_type') or '').strip(),
    }

# ─── 读取 DB 中现有商户快照 ───────────────────────────────────────────────
def load_db_merchants(conn) -> dict:
    """返回 {merchant_id: row_dict}"""
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT merchant_id, merchant_name, avg_payout, cookie_days,
               website, country, online_status, status
        FROM yp_merchants
    """)
    rows = cur.fetchall()
    cur.close()
    return {str(r['merchant_id']): r for r in rows}

# ─── UPSERT 商户到 yp_merchants ───────────────────────────────────────────
UPSERT_MERCHANT_SQL = """
INSERT INTO yp_merchants
    (merchant_id, merchant_name, avg_payout, cookie_days, website,
     country, online_status, status, deep_link, logo, transaction_type, collected_at)
VALUES
    (%(merchant_id)s, %(merchant_name)s, %(avg_payout)s, %(cookie_days)s, %(website)s,
     %(country)s, %(online_status)s, %(status)s, %(is_deeplink)s, %(logo)s,
     %(transaction_type)s, %(collected_at)s)
ON DUPLICATE KEY UPDATE
    merchant_name    = VALUES(merchant_name),
    avg_payout       = VALUES(avg_payout),
    cookie_days      = VALUES(cookie_days),
    website          = VALUES(website),
    country          = VALUES(country),
    online_status    = VALUES(online_status),
    status           = VALUES(status),
    deep_link        = VALUES(deep_link),
    logo             = VALUES(logo),
    transaction_type = VALUES(transaction_type),
    collected_at     = VALUES(collected_at)
"""

# ─── 主逻辑 ────────────────────────────────────────────────────────────────
def main():
    log("SYNC", "=" * 60)
    log("SYNC", f"YP 商户每日轮询同步{'（DRY-RUN 模式）' if DRY_RUN else ''}")
    log("SYNC", "=" * 60)

    # 1. 拉取最新商户
    api_merchants_raw = fetch_all_merchants()
    if not api_merchants_raw:
        log("SYNC", "未拉到任何商户，退出")
        return

    api_merchants = {m['merchant_id']: m for m in [normalize_merchant(r) for r in api_merchants_raw]}

    # 2. 连接 DB
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        log("DB", "MySQL 连接成功")
    except Exception as e:
        log("DB", f"连接失败: {e}")
        return

    # 3. 建表（如不存在）
    if not DRY_RUN:
        cur = conn.cursor()
        cur.execute(CREATE_CHANGE_LOG_TABLE)
        conn.commit()
        cur.close()

    # 4. 读现有快照
    db_merchants = load_db_merchants(conn)
    log("DB", f"DB 中现有商户: {len(db_merchants)} 个")

    checked_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 5. 对比
    api_ids = set(api_merchants.keys())
    db_ids  = set(db_merchants.keys())

    added_ids   = api_ids - db_ids
    removed_ids = db_ids  - api_ids
    common_ids  = api_ids & db_ids

    change_logs = []  # 待写入 merchant_change_log 的记录

    # 5a. 新增商户
    for mid in added_ids:
        m = api_merchants[mid]
        change_logs.append({
            'merchant_id':   mid,
            'merchant_name': m['merchant_name'],
            'change_type':   'added',
            'field_name':    None,
            'old_value':     None,
            'new_value':     json.dumps(m, ensure_ascii=False),
            'checked_at':    checked_at,
        })

    # 5b. 删除商户（平台下线或不再可见）
    for mid in removed_ids:
        db_row = db_merchants[mid]
        change_logs.append({
            'merchant_id':   mid,
            'merchant_name': db_row.get('merchant_name', ''),
            'change_type':   'removed',
            'field_name':    None,
            'old_value':     json.dumps({k: str(v) for k, v in db_row.items()}, ensure_ascii=False),
            'new_value':     None,
            'checked_at':    checked_at,
        })

    # 5c. 变动字段
    for mid in common_ids:
        new = api_merchants[mid]
        old = db_merchants[mid]
        for db_col, api_key in WATCH_FIELDS:
            old_val = str(old.get(db_col) or '')
            new_val = str(new.get(db_col) or '')
            if old_val.strip() != new_val.strip():
                change_logs.append({
                    'merchant_id':   mid,
                    'merchant_name': new['merchant_name'],
                    'change_type':   'changed',
                    'field_name':    db_col,
                    'old_value':     old_val,
                    'new_value':     new_val,
                    'checked_at':    checked_at,
                })

    # 6. 打印摘要
    added_names   = [api_merchants[i]['merchant_name'] for i in list(added_ids)[:5]]
    removed_names = [db_merchants[i].get('merchant_name','?') for i in list(removed_ids)[:5]]
    changed_mids  = list({cl['merchant_id'] for cl in change_logs if cl['change_type'] == 'changed'})[:5]

    log("DIFF", f"新增商户: {len(added_ids)} 个 → {added_names}{'...' if len(added_ids)>5 else ''}")
    log("DIFF", f"删除商户: {len(removed_ids)} 个 → {removed_names}{'...' if len(removed_ids)>5 else ''}")
    log("DIFF", f"字段变动: {len([c for c in change_logs if c['change_type']=='changed'])} 条（涉及 {len(changed_mids)} 个商户）")

    if DRY_RUN:
        log("SYNC", "DRY-RUN 模式，不写入数据库，退出")
        conn.close()
        return

    # 7. 写入变动日志
    if change_logs:
        cur = conn.cursor()
        cur.executemany("""
            INSERT INTO merchant_change_log
                (merchant_id, merchant_name, change_type, field_name, old_value, new_value, checked_at)
            VALUES
                (%(merchant_id)s, %(merchant_name)s, %(change_type)s, %(field_name)s,
                 %(old_value)s, %(new_value)s, %(checked_at)s)
        """, change_logs)
        conn.commit()
        cur.close()
        log("DB", f"变动日志写入 {len(change_logs)} 条")

    # 8. UPSERT 全量商户到 yp_merchants
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    upsert_rows = []
    for m in api_merchants.values():
        row = dict(m)
        row['collected_at'] = now_str
        upsert_rows.append(row)

    cur = conn.cursor()
    batch_size = 500
    upserted = 0
    for i in range(0, len(upsert_rows), batch_size):
        batch = upsert_rows[i:i+batch_size]
        cur.executemany(UPSERT_MERCHANT_SQL, batch)
        conn.commit()
        upserted += len(batch)
    cur.close()
    log("DB", f"yp_merchants UPSERT 完成，共 {upserted} 条")

    conn.close()
    log("SYNC", "=" * 60)
    log("SYNC", f"同步完成 ✅  新增 {len(added_ids)} | 删除 {len(removed_ids)} | 变动字段 {len([c for c in change_logs if c['change_type']=='changed'])}")
    log("SYNC", "=" * 60)


if __name__ == '__main__':
    main()
