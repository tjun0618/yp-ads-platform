#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建 Google Ads 关键词聚合表 (google_ads_keywords)
===================================================
将 google_suggest_keywords（已采集的品牌关键词）与
yp_products（商品表）按 merchant_id 关联，
生成一张专为 Google Ads 投放准备的宽表。

表结构（每行 = 一个商品对应一个品牌关键词）：
  - asin, product_name, category, price, commission
  - merchant_id, merchant_name, tracking_url, amazon_url
  - keyword（单个展开的关键词）
  - keyword_source（autocomplete / related）
  - title（亚马逊标题，若有）
  - rating, review_count（亚马逊评分，若有）
  - image_url（商品主图，若有）

用法:
    python -X utf8 build_ads_keywords_table.py
    python -X utf8 build_ads_keywords_table.py --rebuild   # 清空重建
"""

import argparse
import json
import mysql.connector

DB_CONFIG = {
    "host": "localhost", "port": 3306,
    "user": "root", "password": "admin",
    "database": "affiliate_marketing", "charset": "utf8mb4",
}

# ─── DDL ─────────────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS google_ads_keywords (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

    -- 商品信息（来自 yp_products）
    asin           VARCHAR(20)  NOT NULL,
    product_name   TEXT,
    category       VARCHAR(255),
    price          DECIMAL(10,2),
    commission     VARCHAR(50),
    tracking_url   TEXT,
    amazon_url     TEXT,

    -- 商户信息（来自 yp_merchants）
    merchant_id    VARCHAR(50)  NOT NULL,
    merchant_name  VARCHAR(255),

    -- 关键词（来自 google_suggest_keywords，每行一个词）
    keyword        VARCHAR(255) NOT NULL,
    keyword_source VARCHAR(20)  COMMENT 'autocomplete / related',

    -- 亚马逊详情（来自 amazon_product_details，若有）
    amazon_title   TEXT,
    rating         VARCHAR(20),
    review_count   VARCHAR(50),
    image_url      TEXT,

    -- 元数据
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- 索引：按 ASIN / 商户 / 关键词 查询
    INDEX idx_asin        (asin),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_keyword     (keyword),
    INDEX idx_category    (category),
    UNIQUE KEY uq_asin_kw (asin, keyword(200))   -- 同一商品同一词不重复
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Google Ads 投放关键词宽表';
"""

# ─── 核心逻辑 ─────────────────────────────────────────────────────────────────

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def build_table(conn, rebuild=False):
    cur = conn.cursor()

    if rebuild:
        cur.execute("DROP TABLE IF EXISTS google_ads_keywords")
        conn.commit()
        print("已清空旧表。")

    cur.execute(CREATE_TABLE_SQL)
    conn.commit()
    cur.close()
    print("表 google_ads_keywords 已就绪。")


def populate(conn):
    """
    从 google_suggest_keywords 取已采集的商户关键词，
    关联 yp_products（US商户商品），展开每个关键词为一行写入。
    """
    cur_read  = conn.cursor(dictionary=True)
    cur_write = conn.cursor()

    # 取所有已采集的美国商户关键词（只处理 US 商户的 google_suggest 记录）
    # CONVERT(...USING utf8mb4) 解决不同表排序规则冲突
    cur_read.execute("""
        SELECT
            g.merchant_id,
            g.merchant_name,
            g.autocomplete,
            g.related
        FROM google_suggest_keywords g
        JOIN yp_merchants m
          ON CONVERT(g.merchant_id USING utf8mb4) = CONVERT(m.merchant_id USING utf8mb4)
        WHERE m.country LIKE 'US%'
    """)
    merchants = cur_read.fetchall()
    print(f"有关键词的美国商户: {len(merchants)} 个")

    total_rows = 0
    total_skipped = 0

    for m in merchants:
        mid   = m["merchant_id"]
        mname = m["merchant_name"]

        # 解析关键词列表，带来源标记
        autocomplete = json.loads(m["autocomplete"]) if m["autocomplete"] else []
        related      = json.loads(m["related"])      if m["related"]      else []

        # 关键词 → (keyword, source) 列表，去重
        kw_list = [(k.strip().lower(), "autocomplete") for k in autocomplete if k.strip()]
        kw_list += [(k.strip().lower(), "related")     for k in related      if k.strip()]
        seen = set()
        kw_dedup = []
        for kw, src in kw_list:
            if kw not in seen:
                seen.add(kw)
                kw_dedup.append((kw, src))

        if not kw_dedup:
            continue

        # 取该商户下所有商品（包含亚马逊详情，若有）
        cur_read.execute("""
            SELECT
                p.asin,
                p.product_name,
                p.category,
                p.price,
                p.commission,
                p.tracking_url,
                p.amazon_url,
                a.title      AS amazon_title,
                a.rating,
                a.review_count,
                a.main_image_url
            FROM yp_products p
            LEFT JOIN amazon_product_details a
              ON p.asin COLLATE utf8mb4_general_ci = a.asin COLLATE utf8mb4_general_ci
            WHERE p.merchant_id COLLATE utf8mb4_general_ci = %s COLLATE utf8mb4_general_ci
        """, (str(mid),))
        products = cur_read.fetchall()

        if not products:
            # 商户无商品，跳过（关键词单独存在意义不大）
            continue

        # 写入：每个商品 × 每个关键词 = 一行
        rows_this_merchant = 0
        for prod in products:
            for kw, src in kw_dedup:
                try:
                    cur_write.execute("""
                        INSERT INTO google_ads_keywords
                            (asin, product_name, category, price, commission,
                             tracking_url, amazon_url,
                             merchant_id, merchant_name,
                             keyword, keyword_source,
                             amazon_title, rating, review_count, image_url)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON DUPLICATE KEY UPDATE
                            keyword_source = VALUES(keyword_source),
                            updated_at     = NOW()
                    """, (
                        prod["asin"],
                        prod["product_name"],
                        prod["category"],
                        prod["price"],
                        prod["commission"],
                        prod["tracking_url"],
                        prod["amazon_url"],
                        str(mid),
                        mname,
                        kw,
                        src,
                        prod["amazon_title"],
                        prod["rating"],
                        prod["review_count"],
                        prod["main_image_url"],
                    ))
                    rows_this_merchant += 1
                except Exception as e:
                    total_skipped += 1

        conn.commit()
        total_rows += rows_this_merchant
        print(f"  [{mid}] {mname}: {len(products)} 商品 × {len(kw_dedup)} 关键词 = {rows_this_merchant} 行")

    cur_read.close()
    cur_write.close()
    return total_rows, total_skipped


def print_summary(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM google_ads_keywords")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT merchant_id) FROM google_ads_keywords")
    merchants = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT asin) FROM google_ads_keywords")
    asins = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT keyword) FROM google_ads_keywords")
    keywords = cur.fetchone()[0]

    print(f"\n{'='*55}")
    print(f"google_ads_keywords 汇总:")
    print(f"  总行数    : {total:,}")
    print(f"  商户数    : {merchants}")
    print(f"  商品(ASIN): {asins:,}")
    print(f"  唯一关键词: {keywords:,}")

    # 样本
    cur.execute("""
        SELECT merchant_name, asin, product_name, keyword, keyword_source, commission
        FROM google_ads_keywords
        LIMIT 5
    """)
    print(f"\n--- 样本（前5行）---")
    for r in cur.fetchall():
        pname = (r[2] or "")[:40]
        print(f"  [{r[0]}] ASIN={r[1]} | {pname}... | kw='{r[3]}' ({r[4]}) | 佣金={r[5]}")

    cur.close()


# ─── 主程序 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="清空表后重建")
    args = parser.parse_args()

    conn = get_db()
    build_table(conn, rebuild=args.rebuild)
    total, skipped = populate(conn)
    print(f"\n写入完成: {total:,} 行，跳过(重复/异常) {skipped} 行")
    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
