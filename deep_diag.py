"""
深度诊断：找出真正的慢查询根源
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

print("=" * 70)
print("深度诊断：逐步拆解慢查询")
print("=" * 70)

def tq(label, sql, params=()):
    t0 = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    ms = (time.time() - t0) * 1000
    print(f"  [{ms:>8.1f}ms] {label}  ({len(rows)} rows)")
    return rows, ms

# ── 1. 单表性能 ──────────────────────────────────────────────────────
print("\n[A] 单表基础查询")
tq("yp_us_products COUNT", "SELECT COUNT(*) FROM yp_us_products")
tq("yp_products COUNT", "SELECT COUNT(*) FROM yp_products")
tq("amazon_product_details COUNT", "SELECT COUNT(*) FROM amazon_product_details")

print("\n[B] 首页 - 逐步拆解 (yp_us_products 只有32万行)")
tq("yp_us_products 全表扫描30条", "SELECT asin FROM yp_us_products ORDER BY product_id DESC LIMIT 30")
tq("yp_us_products JOIN amz (30条)", """
    SELECT p.asin, a.title
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    ORDER BY p.product_id DESC LIMIT 30
""")
tq("yp_us_products JOIN amz+plans (30条)", """
    SELECT p.asin, a.title, pl.plan_status
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    ORDER BY p.product_id DESC LIMIT 30
""")
tq("yp_us_products JOIN amz+plans+kw_sub (30条) [N+1旧法]", """
    SELECT p.asin, a.title, pl.plan_status,
        (SELECT COUNT(*) FROM ads_merchant_keywords mk WHERE mk.merchant_id = p.yp_merchant_id) kw_cnt
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    ORDER BY p.product_id DESC LIMIT 30
""")
tq("yp_us_products JOIN amz+plans+kw_join (30条) [JOIN新法]", """
    SELECT p.asin, a.title, pl.plan_status, COALESCE(mk.kw_count,0) kw_cnt
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    LEFT JOIN (SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id) mk
        ON mk.merchant_id = p.yp_merchant_id
    ORDER BY p.product_id DESC LIMIT 30
""")

# ── 2. 商品管理 API - 逐步拆解 ───────────────────────────────────────
print("\n[C] 商品管理 API - 逐步拆解")
tq("yp_products 只查自身30条 (tracking_url过滤)", """
    SELECT id, asin, merchant_name FROM yp_products 
    WHERE tracking_url IS NOT NULL AND tracking_url != ''
    ORDER BY id DESC LIMIT 50
""")
tq("yp_products JOIN amazon_product_details 50条", """
    SELECT p.id, p.asin, d.title
    FROM yp_products p
    LEFT JOIN amazon_product_details d ON p.asin=d.asin
    WHERE p.tracking_url IS NOT NULL AND p.tracking_url != ''
    ORDER BY p.id DESC LIMIT 50
""")
tq("yp_products COUNT(有tracking_url的)", """
    SELECT COUNT(*) FROM yp_products 
    WHERE tracking_url IS NOT NULL AND tracking_url != ''
""")

# ── 3. _us_products_cache 表 ──────────────────────────────────────────
print("\n[D] _us_products_cache vs yp_us_products 对比")
tq("_us_products_cache COUNT", "SELECT COUNT(*) FROM _us_products_cache")
try:
    tq("_us_products_cache SHOW INDEXES",
       "SELECT INDEX_NAME FROM information_schema.statistics WHERE TABLE_NAME='_us_products_cache' AND TABLE_SCHEMA='affiliate_marketing'")
except Exception as e:
    print(f"  _us_products_cache 索引查询: {e}")

# ── 4. EXPLAIN 首页核心查询 ───────────────────────────────────────────
print("\n[E] EXPLAIN 首页核心查询")
cur.execute("""
    EXPLAIN 
    SELECT p.asin, a.title, pl.plan_status, COALESCE(mk.kw_count,0) kw_cnt
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    LEFT JOIN (SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id) mk
        ON mk.merchant_id = p.yp_merchant_id
    ORDER BY p.product_id DESC LIMIT 30
""")
rows = cur.fetchall()
print(f"  {'table':<30} {'type':<12} {'key':<25} {'rows':<10} Extra")
print("  " + "-" * 90)
for r in rows:
    print(f"  {str(r[2]):<30} {str(r[4]):<12} {str(r[6]):<25} {str(r[9]):<10} {str(r[11])}")

# ── 5. tracking_url 索引检查 ─────────────────────────────────────────
print("\n[F] tracking_url 索引类型检查（TEXT字段有限制）")
cur.execute("""
    SELECT INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, SUB_PART, INDEX_TYPE
    FROM information_schema.statistics 
    WHERE TABLE_NAME='yp_products' AND TABLE_SCHEMA='affiliate_marketing'
    ORDER BY INDEX_NAME, SEQ_IN_INDEX
""")
for r in cur.fetchall():
    print(f"  {r[0]}: col={r[2]}, sub_part={r[3]}, type={r[4]}")

conn.close()
print("\n诊断完成！")
