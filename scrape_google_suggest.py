#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Autocomplete 关键词采集脚本
====================================
利用 Google Suggest API（免费，无限制）为每个商户采集相关搜索词，
用于 Google Ads 关键词规划。

数据来源: https://suggestqueries.google.com/complete/search
策略: 对每个商户名用多个查询模板（品牌词 + 意图词缀）获取全面的关键词

用法:
    python -X utf8 scrape_google_suggest.py              # 全量采集
    python -X utf8 scrape_google_suggest.py --limit 50   # 只采集前50个商户
    python -X utf8 scrape_google_suggest.py --merchant "REI"  # 指定商户
    python -X utf8 scrape_google_suggest.py --no-skip    # 强制重新采集

输出:
    - MySQL 表: google_suggest_keywords
    - 本地备份: output/google_suggest_YYYYMMDD.json
"""

import argparse
import json
import time
import re
import urllib.request
import urllib.parse
import os
import sys
from datetime import datetime
import mysql.connector

# ─── 配置 ────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4",
}

# Google Suggest API 端点
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

# 请求间隔（秒）— 避免触发速率限制
REQUEST_DELAY = 0.8

# 针对联盟营销的查询模板（品牌名会替换 {brand}）
# 每个模板对应不同的用户意图
QUERY_TEMPLATES = [
    "{brand}",                    # 品牌词本身
    "{brand} coupon",             # 优惠券
    "{brand} promo code",         # 促销码
    "{brand} discount",           # 折扣
    "{brand} sale",               # 促销
    "{brand} review",             # 评测
    "{brand} vs",                 # 对比
    "{brand} best",               # 最佳
    "{brand} deals",              # 优惠
    "{brand} free shipping",      # 免费配送
]

# 每次请求最大重试次数
MAX_RETRIES = 3

# ─── MySQL ───────────────────────────────────────────────────────────────────

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS google_suggest_keywords (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id   VARCHAR(50),
            merchant_name VARCHAR(255),
            brand_query   VARCHAR(255),
            keywords      JSON,
            keyword_count INT DEFAULT 0,
            status        VARCHAR(20) DEFAULT 'completed',
            scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_mid (merchant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    cur.close()


def get_target_merchants(conn, limit=None, merchant_name=None):
    """从 yp_merchants 获取有品牌名的商户列表"""
    cur = conn.cursor(dictionary=True)
    
    if merchant_name:
        cur.execute("""
            SELECT merchant_id, merchant_name, website
            FROM yp_merchants
            WHERE merchant_name LIKE %s
            ORDER BY merchant_id
        """, (f"%{merchant_name}%",))
    elif limit:
        cur.execute("""
            SELECT merchant_id, merchant_name, website
            FROM yp_merchants
            WHERE merchant_name IS NOT NULL AND merchant_name != ''
            ORDER BY merchant_id
            LIMIT %s
        """, (limit,))
    else:
        cur.execute("""
            SELECT merchant_id, merchant_name, website
            FROM yp_merchants
            WHERE merchant_name IS NOT NULL AND merchant_name != ''
            ORDER BY merchant_id
        """)
    
    merchants = cur.fetchall()
    cur.close()
    return merchants


def get_completed_ids(conn):
    """获取已完成的商户 ID 集合"""
    cur = conn.cursor()
    cur.execute("SELECT merchant_id FROM google_suggest_keywords WHERE status='completed'")
    ids = {row[0] for row in cur.fetchall()}
    cur.close()
    return ids


def save_to_mysql(conn, merchant_id, merchant_name, brand_query, all_keywords):
    """保存关键词到 MySQL"""
    cur = conn.cursor()
    deduped = sorted(set(all_keywords))
    cur.execute("""
        INSERT INTO google_suggest_keywords 
            (merchant_id, merchant_name, brand_query, keywords, keyword_count, status, scraped_at)
        VALUES (%s, %s, %s, %s, %s, 'completed', NOW())
        ON DUPLICATE KEY UPDATE
            brand_query   = VALUES(brand_query),
            keywords      = VALUES(keywords),
            keyword_count = VALUES(keyword_count),
            scraped_at    = NOW()
    """, (
        str(merchant_id),
        merchant_name,
        brand_query,
        json.dumps(deduped, ensure_ascii=False),
        len(deduped),
    ))
    conn.commit()
    cur.close()

# ─── Google Suggest API ───────────────────────────────────────────────────────

def fetch_suggest(query, retries=MAX_RETRIES):
    """调用 Google Suggest API，返回关键词列表"""
    params = urllib.parse.urlencode({
        "client": "firefox",
        "q": query,
        "hl": "en",
        "gl": "us",         # 地区：美国
        "ie": "utf-8",
    })
    url = f"{SUGGEST_URL}?{params}"
    
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/javascript, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # Google Suggest 返回格式: ["query", ["s1","s2",...], [], {}]
                if isinstance(data, list) and len(data) > 1:
                    suggestions = data[1]
                    if isinstance(suggestions, list):
                        return [s for s in suggestions if isinstance(s, str)]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"  [ERROR] fetch_suggest failed for '{query}': {e}")
    return []


def clean_brand_name(merchant_name):
    """从商户名提取干净的品牌查询词"""
    # 去掉常见后缀
    name = re.sub(r'\s+(US|UK|EU|AU|CA|PL|DE|FR|IT|ES|NL|COM|INC|LLC|LTD|CO\.|CORP\.?)$', 
                  '', merchant_name, flags=re.IGNORECASE).strip()
    # 去掉域名后缀
    name = re.sub(r'\.(com|net|org|io|co)$', '', name, flags=re.IGNORECASE).strip()
    # 去掉多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def scrape_merchant(merchant_name, verbose=True):
    """对单个商户采集所有模板的关键词"""
    brand = clean_brand_name(merchant_name)
    if verbose:
        print(f"  品牌词: '{brand}'")
    
    all_keywords = []
    
    for template in QUERY_TEMPLATES:
        query = template.format(brand=brand)
        suggestions = fetch_suggest(query)
        if verbose and suggestions:
            print(f"    [{template.replace('{brand}', brand)}] → {suggestions[:3]}{'...' if len(suggestions)>3 else ''}")
        all_keywords.extend(suggestions)
        time.sleep(REQUEST_DELAY)
    
    return brand, all_keywords


# ─── 主程序 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Google Suggest 关键词批量采集")
    parser.add_argument("--limit",    type=int, help="最多采集 N 个商户")
    parser.add_argument("--merchant", type=str, help="指定商户名（模糊匹配）")
    parser.add_argument("--no-skip",  action="store_true", help="强制重新采集已完成的商户")
    args = parser.parse_args()

    conn = get_db()
    ensure_table(conn)

    # 获取目标商户
    merchants = get_target_merchants(conn, limit=args.limit, merchant_name=args.merchant)
    print(f"目标商户数: {len(merchants)}")

    # 跳过已完成的
    if not args.no_skip:
        completed = get_completed_ids(conn)
        merchants = [m for m in merchants if str(m["merchant_id"]) not in completed]
        print(f"  已完成: {len(completed)}，待采集: {len(merchants)}")

    if not merchants:
        print("无需采集，退出。")
        return

    # 本地备份目录
    os.makedirs("output", exist_ok=True)
    backup_file = f"output/google_suggest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    success_count = 0
    error_count = 0
    
    for idx, m in enumerate(merchants, 1):
        mid = m["merchant_id"]
        mname = m["merchant_name"]
        print(f"\n[{idx}/{len(merchants)}] {mname} (ID:{mid})")
        
        try:
            brand_query, keywords = scrape_merchant(mname)
            deduped = sorted(set(keywords))
            
            # 存 MySQL
            save_to_mysql(conn, mid, mname, brand_query, deduped)
            
            # 本地备份
            with open(backup_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "merchant_id": str(mid),
                    "merchant_name": mname,
                    "brand_query": brand_query,
                    "keywords": deduped,
                    "keyword_count": len(deduped),
                    "scraped_at": datetime.now().isoformat(),
                }, ensure_ascii=False) + "\n")
            
            print(f"  ✓ 采集到 {len(deduped)} 个去重关键词")
            success_count += 1
            
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            error_count += 1
    
    # ─── 汇总 ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"采集完成！成功: {success_count}，失败: {error_count}")
    
    # 显示总数
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(keyword_count) FROM google_suggest_keywords WHERE status='completed'")
    row = cur.fetchone()
    print(f"数据库累计: {row[0]} 个商户，{row[1] or 0} 个关键词")
    cur.close()
    
    print(f"本地备份: {backup_file}")
    conn.close()


if __name__ == "__main__":
    main()
