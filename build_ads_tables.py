#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Ads 关键词表构建脚本
============================
只做一件事：把 google_suggest_keywords 里已采集的品牌词
整理写入 ads_merchant_keywords（商户 × 关键词）。

商品数据不在这里处理，按需制作广告时实时 JOIN yp_products 即可。

用法:
    python -X utf8 build_ads_tables.py            # 增量同步
    python -X utf8 build_ads_tables.py --rebuild  # 清空重建
"""

import argparse
import json
import mysql.connector

DB_CONFIG = {
    "host": "localhost", "port": 3306,
    "user": "root", "password": "admin",
    "database": "affiliate_marketing", "charset": "utf8mb4",
}

DDL = """
CREATE TABLE IF NOT EXISTS ads_merchant_keywords (
    id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- 商户信息
    merchant_id    VARCHAR(50)  NOT NULL,
    merchant_name  VARCHAR(255),
    website        TEXT,
    avg_payout     DECIMAL(12,2) COMMENT '商户平均佣金金额($)',
    cookie_days    SMALLINT      COMMENT 'Cookie有效天数',

    -- 关键词（每行一个词）
    keyword        VARCHAR(255) NOT NULL,
    keyword_source VARCHAR(20)  COMMENT 'autocomplete / related',

    synced_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_merchant_id (merchant_id),
    INDEX idx_keyword     (keyword),
    UNIQUE KEY uq_mid_kw  (merchant_id, keyword(200))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
  COMMENT='Google Ads 投放：品牌关键词表（US商户，来自 Google Suggest）';
"""


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def setup_table(conn, rebuild=False):
    cur = conn.cursor()
    if rebuild:
        for t in ("ads_merchant_keywords", "ads_products", "google_ads_keywords"):
            cur.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
        print("旧表已清理。")
    cur.execute(DDL)
    conn.commit()
    cur.close()
    print("表 ads_merchant_keywords 已就绪。")


def sync_keywords(conn):
    """把 google_suggest_keywords（US商户）展开写入 ads_merchant_keywords"""
    cur_r = conn.cursor(dictionary=True)
    cur_w = conn.cursor()

    cur_r.execute("""
        SELECT
            g.merchant_id,
            g.merchant_name,
            g.autocomplete,
            g.related,
            m.website,
            m.avg_payout,
            m.cookie_days
        FROM google_suggest_keywords g
        JOIN yp_merchants m
          ON CONVERT(g.merchant_id USING utf8mb4) = CONVERT(m.merchant_id USING utf8mb4)
        WHERE m.country LIKE 'US%'
    """)
    merchants = cur_r.fetchall()
    print(f"有关键词的 US 商户：{len(merchants)} 个")

    inserted = updated = 0
    for r in merchants:
        autocomplete = json.loads(r["autocomplete"]) if r["autocomplete"] else []
        related      = json.loads(r["related"])      if r["related"]      else []

        # 合并去重，保留来源
        seen = {}
        for kw in autocomplete:
            k = kw.strip()
            if k and k.lower() not in seen:
                seen[k.lower()] = (k, "autocomplete")
        for kw in related:
            k = kw.strip()
            if k and k.lower() not in seen:
                seen[k.lower()] = (k, "related")

        for _, (kw_orig, src) in seen.items():
            cur_w.execute("""
                INSERT INTO ads_merchant_keywords
                    (merchant_id, merchant_name, website, avg_payout, cookie_days,
                     keyword, keyword_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    merchant_name  = VALUES(merchant_name),
                    website        = VALUES(website),
                    avg_payout     = VALUES(avg_payout),
                    cookie_days    = VALUES(cookie_days),
                    keyword_source = VALUES(keyword_source),
                    synced_at      = NOW()
            """, (
                str(r["merchant_id"]),
                r["merchant_name"],
                r["website"],
                r["avg_payout"],
                r["cookie_days"],
                kw_orig,
                src,
            ))
            if cur_w.rowcount == 1:
                inserted += 1
            else:
                updated += 1

    conn.commit()
    cur_r.close()
    cur_w.close()
    return inserted, updated


def print_summary(conn):
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM ads_merchant_keywords")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT merchant_id) FROM ads_merchant_keywords")
    merchants = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT keyword) FROM ads_merchant_keywords")
    unique_kw = cur.fetchone()[0]

    print(f"\n{'='*55}")
    print(f"ads_merchant_keywords 汇总：")
    print(f"  商户数    : {merchants:,}")
    print(f"  总行数    : {total:,}")
    print(f"  唯一关键词: {unique_kw:,}")

    # 样本
    cur.execute("""
        SELECT merchant_name, website, avg_payout, cookie_days,
               keyword, keyword_source
        FROM ads_merchant_keywords
        ORDER BY merchant_id, keyword_source
        LIMIT 10
    """)
    rows = cur.fetchall()
    print(f"\n--- 样本（前10行）---")
    print(f"  {'商户':<25} {'关键词':<35} {'来源':<14} {'佣金$':>7} {'Cookie':>7}")
    print(f"  {'-'*93}")
    for r in rows:
        print(f"  {str(r[0]):<25} {str(r[4]):<35} {str(r[5]):<14} "
              f"{str(r[2] or ''):>7} {str(r[3] or ''):>7}")
    cur.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    conn = get_db()
    setup_table(conn, rebuild=args.rebuild)
    ins, upd = sync_keywords(conn)
    print(f"同步完成：新增 {ins} 行，更新 {upd} 行")
    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
