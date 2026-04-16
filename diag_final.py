"""
精细诊断：找出真正的2秒瓶颈
直接复现 Flask 路由里的每一步，精确计时
"""
import time, re
import mysql.connector

def get_conn():
    return mysql.connector.connect(
        host='localhost', port=3306,
        user='root', password='admin',
        database='affiliate_marketing',
        charset='utf8mb4'
    )

def timer(label, fn):
    t0 = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t0) * 1000
    print(f"  [{ms:7.1f}ms] {label}")
    return result

def run_sql(conn, sql, args=None):
    c = conn.cursor(dictionary=True)
    c.execute(sql, args or ())
    rows = c.fetchall()
    c.close()
    return rows

print("=" * 60)
print("精细诊断：逐步拆解首页/商品列表 2秒瓶颈")
print("=" * 60)

# 1. 新建连接耗时
conn = timer("新建 MySQL 连接", get_conn)

# 2. information_schema 行数估算
timer("COUNT via information_schema (yp_us_products)", 
      lambda: run_sql(conn, "SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA='affiliate_marketing' AND TABLE_NAME='yp_us_products'"))

timer("COUNT via information_schema (amazon_product_details)", 
      lambda: run_sql(conn, "SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA='affiliate_marketing' AND TABLE_NAME='amazon_product_details'"))

timer("COUNT via information_schema (ads_plans)", 
      lambda: run_sql(conn, "SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA='affiliate_marketing' AND TABLE_NAME='ads_plans'"))

# 3. 延迟关联主查询
timer("延迟关联 主查询 (LIMIT 30)", lambda: run_sql(conn, """
    SELECT p.asin, p.product_name, p.price, p.commission_rate,
           p.yp_merchant_id, p.merchant_name, p.category,
           p.investment_score,
           a.rating, a.review_count, a.image_url, a.brand,
           pl.plan_status,
           mk.kw_count
    FROM (
        SELECT p.asin, p.yp_merchant_id
        FROM yp_us_products p
        ORDER BY p.product_id DESC
        LIMIT 30 OFFSET 0
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
    LEFT JOIN (
        SELECT merchant_id, COUNT(*) AS kw_count
        FROM ads_merchant_keywords
        GROUP BY merchant_id
    ) mk ON mk.merchant_id = sub.yp_merchant_id
"""))

# 4. 单独测 GROUP BY 子查询
timer("ads_merchant_keywords GROUP BY 聚合", lambda: run_sql(conn, """
    SELECT merchant_id, COUNT(*) AS kw_count
    FROM ads_merchant_keywords
    GROUP BY merchant_id
"""))

# 5. 测一个空的 LIMIT
timer("yp_us_products ORDER BY product_id LIMIT 30", lambda: run_sql(conn, """
    SELECT asin, yp_merchant_id FROM yp_us_products ORDER BY product_id DESC LIMIT 30
"""))

# 6. 商户列表 API
timer("yp_merchants 列表 (LIMIT 20)", lambda: run_sql(conn, """
    SELECT m.merchant_id, m.merchant_name, m.avg_payout, m.cookie_days,
           m.website, m.country, m.category,
           COUNT(p.asin) as product_count
    FROM yp_merchants m
    LEFT JOIN yp_us_products p ON p.yp_merchant_id = m.merchant_id
    GROUP BY m.merchant_id
    ORDER BY m.avg_payout DESC
    LIMIT 20
"""))

# 7. QS dashboard
timer("QS dashboard 查询", lambda: run_sql(conn, """
    SELECT p.asin, p.product_name, p.merchant_name,
           q.overall_score, q.ctr_score, q.cvr_score,
           q.relevance_score, q.ad_strength_score, q.competition_score
    FROM ads_plans p
    LEFT JOIN ads_qs_scores q ON q.plan_id = p.plan_id
    WHERE p.plan_status = 'active'
    ORDER BY q.overall_score DESC
    LIMIT 20
"""))

# 8. HTTP 请求耗时（排除 MySQL）
print()
print("=" * 60)
print("HTTP层 额外开销测试")
print("=" * 60)
import urllib.request
def http_get(url):
    req = urllib.request.urlopen(url, timeout=10)
    return req.read()

# 直接 HTTP
timer("HTTP GET /  (Flask路由全流程)", lambda: http_get("http://localhost:5055/"))
timer("HTTP GET /api/products?page=1", lambda: http_get("http://localhost:5055/api/products?page=1"))
timer("HTTP GET /api/merchants?page=1", lambda: http_get("http://localhost:5055/api/merchants?page=1"))

conn.close()
print()
print("诊断完成")
