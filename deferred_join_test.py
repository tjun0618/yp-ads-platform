"""
终极方案：延迟关联（Deferred Join）+ 计数缓存
让 ORDER BY + LIMIT 只扫描索引，不走全表
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

print("=" * 70)
print("延迟关联测试：先用子查询拿 asin 列表，再 JOIN 详情")
print("=" * 70)

def tq(label, sql, params=()):
    t0 = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    ms = (time.time() - t0) * 1000
    flag = "✅" if ms < 300 else ("⚠️" if ms < 1000 else "❌")
    print(f"  {flag} [{ms:>8.1f}ms] {label}  ({len(rows)} rows)")
    return rows, ms

# ── 旧方法（全表扫描）
tq("旧法：直接三表JOIN + ORDER BY LIMIT", """
    SELECT p.asin, a.title, pl.plan_status
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    ORDER BY p.product_id DESC LIMIT 30
""")

# ── 延迟关联 V1：子查询先拿 asin，再 JOIN
tq("延迟关联V1：子查询拿asin，再JOIN详情", """
    SELECT p.asin, a.title, pl.plan_status
    FROM (
        SELECT asin, yp_merchant_id 
        FROM yp_us_products 
        ORDER BY product_id DESC LIMIT 30
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
""")

# ── 延迟关联 V2：完整版（含 kw_count）
tq("延迟关联V2：完整版含kw_count", """
    SELECT p.asin, p.product_name, p.price, p.commission_num, p.tracking_url,
           p.merchant_name, p.yp_merchant_id,
           a.asin AS amz_asin, a.title, a.rating, a.review_count, a.main_image_url,
           pl.plan_status, pl.id AS plan_id,
           COALESCE(mk.kw_count, 0) AS kw_count
    FROM (
        SELECT asin, yp_merchant_id
        FROM yp_us_products
        ORDER BY product_id DESC LIMIT 30 OFFSET 0
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
    LEFT JOIN (
        SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id
    ) mk ON mk.merchant_id = sub.yp_merchant_id
""")

# EXPLAIN 延迟关联
print("\n  EXPLAIN 延迟关联V2：")
cur.execute("""
    EXPLAIN 
    SELECT p.asin, a.title, pl.plan_status
    FROM (
        SELECT asin, yp_merchant_id
        FROM yp_us_products
        ORDER BY product_id DESC LIMIT 30
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
""")
rows = cur.fetchall()
print(f"  {'table':<30} {'type':<12} {'key':<25} {'rows':<10} Extra")
print("  " + "-" * 90)
for r in rows:
    print(f"  {str(r[2]):<30} {str(r[4]):<12} {str(r[6]):<25} {str(r[9]):<10} {str(r[11])}")

# 也测下 yp_products COUNT 的解法
print("\n  yp_products COUNT 优化方案：")
tq("COUNT(*) 用函数索引 (已建)", """
    SELECT COUNT(*) FROM yp_products 
    WHERE tracking_url IS NOT NULL AND tracking_url != ''
""")
# 尝试近似估算（INFORMATION_SCHEMA 秒级返回）
tq("估算行数（information_schema，秒级）", """
    SELECT table_rows FROM information_schema.tables 
    WHERE table_schema='affiliate_marketing' AND table_name='yp_products'
""")

conn.close()
print("\n测试完成！")
