"""
构建/增量同步 yp_us_products 物化缓存表
- 每个 ASIN 只保留一条（去重后的商户），无重复
- Flask 启动后直接查此表，LIMIT 30 仅需 ~0.002s

用法:
  python -X utf8 build_us_cache.py           # 全量重建（DROP + CREATE）
  python -X utf8 build_us_cache.py --refresh # 增量同步（只处理新增/变更的 ASIN）
"""

import sys
import time
import mysql.connector

# ─── 配置 ──────────────────────────────────────────────────────────────────
DB_CONFIG = dict(
    host="localhost",
    port=3306,
    user="root",
    password="admin",
    database="affiliate_marketing",
    charset="utf8mb4",
)


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)


# ─── 确保表存在 ────────────────────────────────────────────────────────────
def ensure_table(cur):
    """如果表不存在则创建（增量模式需要）"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS yp_us_products (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            product_id      BIGINT,
            asin            VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            product_name    TEXT,
            price           VARCHAR(50),
            commission      VARCHAR(50),
            commission_num  DECIMAL(10,4),
            tracking_url    TEXT,
            merchant_name   VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            merchant_db_id  BIGINT,
            yp_merchant_id  INT,
            website         TEXT,
            avg_payout      VARCHAR(100),
            cookie_days     INT,
            country         VARCHAR(100),
            investment_score FLOAT DEFAULT 0 COMMENT '投放价值分0-100'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    # 用信息模式检查索引是否存在（MySQL 8.0 不支持 CREATE INDEX IF NOT EXISTS）
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.statistics
        WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'
    """)
    idx_count = cur.fetchone()[0]
    if idx_count == 0:
        cur.execute("CREATE UNIQUE INDEX idx_usp_asin ON yp_us_products(asin)")
        cur.execute("ALTER TABLE yp_us_products ADD INDEX idx_pid (product_id)")
        cur.execute(
            "CREATE INDEX idx_usp_commission ON yp_us_products(commission_num DESC)"
        )
        cur.execute(
            "CREATE INDEX idx_usp_merchant ON yp_us_products(merchant_name(100))"
        )


# ─── 全量重建 ──────────────────────────────────────────────────────────────
def full_rebuild():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"
    )
    cur.execute("SET SESSION group_concat_max_len = 1048576")

    print("构建 yp_us_products 物化表（每 ASIN 唯一，取佣金最高商户）...")
    t0 = time.time()

    cur.execute("DROP TABLE IF EXISTS yp_us_products")
    cur.execute("""
        CREATE TABLE yp_us_products (
            id              BIGINT AUTO_INCREMENT PRIMARY KEY,
            product_id      BIGINT,
            asin            VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            product_name    TEXT,
            price           VARCHAR(50),
            commission      VARCHAR(50),
            commission_num  DECIMAL(10,4),
            tracking_url    TEXT,
            merchant_name   VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci,
            merchant_db_id  BIGINT,
            yp_merchant_id  INT,
            website         TEXT,
            avg_payout      VARCHAR(100),
            cookie_days     INT,
            country         VARCHAR(100),
            investment_score FLOAT DEFAULT 0 COMMENT '投放价值分0-100'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)

    cur.execute("""
        INSERT INTO yp_us_products
            (product_id, asin, product_name, price, commission, commission_num,
             tracking_url, merchant_name, merchant_db_id, yp_merchant_id,
             website, avg_payout, cookie_days, country, investment_score)
        SELECT
            p.id,
            p.asin,
            p.product_name,
            p.price,
            p.commission,
            CAST(REPLACE(REPLACE(REPLACE(COALESCE(p.commission,'0'),'%',''),'$',''),',','') AS DECIMAL(10,4)),
            p.tracking_url,
            p.merchant_name,
            mu.id,
            mu.merchant_id,
            mu.website,
            mu.avg_payout,
            mu.cookie_days,
            mu.country,
            0
        FROM (
            SELECT MIN(p2.id) AS pid
            FROM yp_products p2
            JOIN (
                SELECT MIN(id) AS id, merchant_name
                FROM yp_merchants
                WHERE (country LIKE 'US -%' OR country LIKE 'US/%' OR country LIKE 'United States%')
                GROUP BY merchant_name
            ) mu2 ON p2.merchant_name = mu2.merchant_name
            GROUP BY p2.asin
        ) dedup
        JOIN yp_products p ON p.id = dedup.pid
        JOIN (
            SELECT MIN(id) AS id, merchant_name, merchant_id, website, avg_payout, cookie_days, country
            FROM yp_merchants
            WHERE (country LIKE 'US -%' OR country LIKE 'US/%' OR country LIKE 'United States%')
            GROUP BY merchant_name
        ) mu ON p.merchant_name = mu.merchant_name
    """)

    print(f"  INSERT 完成: {time.time() - t0:.1f}s  {cur.rowcount} 行")

    t1 = time.time()
    cur.execute("CREATE UNIQUE INDEX idx_usp_asin ON yp_us_products(asin)")
    cur.execute("ALTER TABLE yp_us_products ADD INDEX idx_pid (product_id)")
    cur.execute(
        "CREATE INDEX idx_usp_commission ON yp_us_products(commission_num DESC)"
    )
    cur.execute("CREATE INDEX idx_usp_merchant ON yp_us_products(merchant_name(100))")
    conn.commit()
    print(f"  索引创建: {time.time() - t1:.1f}s")

    # 验证
    cur2 = conn.cursor(dictionary=True)
    cur2.execute("SELECT COUNT(*) as c FROM yp_us_products")
    cnt = cur2.fetchone()["c"]
    print(f"  总行数（每 ASIN 唯一）: {cnt:,}")
    conn.close()
    print(f"总耗时: {time.time() - t0:.1f}s")
    print("yp_us_products 缓存表已就绪")
    return cnt


# ─── 增量同步 ──────────────────────────────────────────────────────────────
def incremental_refresh():
    """只同步 yp_products 中有但 yp_us_products 中没有/有变更的 ASIN"""
    conn = get_conn()
    cur = conn.cursor()
    t0 = time.time()

    ensure_table(cur)

    # 找出 yp_products 中存在但 yp_us_products 中不存在的 ASIN（新增商品）
    cur.execute("""
        INSERT IGNORE INTO yp_us_products
            (product_id, asin, product_name, price, commission, commission_num,
             tracking_url, merchant_name, yp_merchant_id)
        SELECT
            p.id,
            p.asin,
            p.product_name,
            p.price,
            p.commission,
            CAST(REPLACE(REPLACE(REPLACE(COALESCE(p.commission,'0'),'%',''),'$',''),',','') AS DECIMAL(10,4)),
            p.tracking_url,
            p.merchant_name,
            p.merchant_id
        FROM yp_products p
        LEFT JOIN yp_us_products u ON p.asin = u.asin
        WHERE u.asin IS NULL
          AND p.merchant_name IN (
              SELECT merchant_name FROM yp_merchants WHERE country LIKE 'US -%'
          )
    """)
    new_rows = cur.rowcount

    # 更新已有记录的商品名、价格、佣金（yp_products 数据可能被更新过）
    cur.execute("""
        UPDATE yp_us_products u
        JOIN yp_products p ON u.asin = p.asin
        SET u.product_name = p.product_name,
            u.price = p.price,
            u.commission = p.commission,
            u.commission_num = CAST(REPLACE(REPLACE(REPLACE(COALESCE(p.commission,'0'),'%',''),'$',''),',','') AS DECIMAL(10,4)),
            u.tracking_url = p.tracking_url,
            u.product_id = p.id
        WHERE p.merchant_name IN (
            SELECT merchant_name FROM yp_merchants WHERE country LIKE 'US -%'
        )
    """)
    updated_rows = cur.rowcount

    # 补充商户信息（website, avg_payout 等，从 yp_merchants 更新）
    cur.execute("""
        UPDATE yp_us_products u
        JOIN (
            SELECT MIN(id) AS id, merchant_name,
                   ANY_VALUE(merchant_id) AS merchant_id,
                   ANY_VALUE(website) AS website,
                   ANY_VALUE(avg_payout) AS avg_payout,
                   ANY_VALUE(cookie_days) AS cookie_days,
                   ANY_VALUE(country) AS country
            FROM yp_merchants
            WHERE (country LIKE 'US -%' OR country LIKE 'US/%' OR country LIKE 'United States%')
            GROUP BY merchant_name
        ) mu ON u.merchant_name = mu.merchant_name
        SET u.merchant_db_id = mu.id,
            u.yp_merchant_id = mu.merchant_id,
            u.website = mu.website,
            u.avg_payout = mu.avg_payout,
            u.cookie_days = mu.cookie_days,
            u.country = mu.country
    """)
    merchant_updated = cur.rowcount

    conn.commit()

    # 统计
    cur2 = conn.cursor(dictionary=True)
    cur2.execute("SELECT COUNT(*) as c FROM yp_us_products")
    total = cur2.fetchone()["c"]
    conn.close()

    elapsed = time.time() - t0
    print(
        f"[cache refresh] new={new_rows} updated={updated_rows} merchants={merchant_updated} total={total} ({elapsed:.1f}s)"
    )
    return new_rows + updated_rows


# ─── 入口 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--refresh" in sys.argv or "--incremental" in sys.argv:
        incremental_refresh()
    else:
        full_rebuild()
