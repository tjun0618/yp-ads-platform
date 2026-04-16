"""
诊断首页真正的耗时瓶颈：逐步计时
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

def tq(label, sql, params=()):
    t0 = time.time()
    cur.execute(sql, params)
    r = cur.fetchall()
    ms = (time.time()-t0)*1000
    flag = "✅" if ms < 100 else ("⚠️" if ms < 500 else "❌")
    print(f"  {flag} [{ms:>8.1f}ms] {label}  ({len(r)} rows)")
    return r

print("=" * 65)
print("首页各步骤单独计时")
print("=" * 65)

tq("1. COUNT yp_us_products", "SELECT COUNT(*) as cnt FROM yp_us_products")
tq("2. COUNT amazon_product_details", "SELECT COUNT(*) as c FROM amazon_product_details")
tq("3. COUNT ads_plans completed", "SELECT COUNT(*) as c FROM ads_plans WHERE plan_status='completed'")
tq("4. TABLE_ROWS estimation", "SELECT TABLE_ROWS FROM information_schema.tables WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'")
tq("5. categories query", "SELECT category_id, category_name FROM yp_categories ORDER BY category_name")

print("\n  --- 延迟关联主查询 ---")
tq("6. 延迟关联主查询", """
    SELECT p.asin, p.product_name, p.price, p.commission, p.commission_num,
           p.tracking_url, p.merchant_name, p.yp_merchant_id,
           a.asin AS amz_asin, a.title, a.rating, a.review_count, a.main_image_url,
           pl.plan_status, pl.id AS plan_id,
           COALESCE(mk.kw_count, 0) AS kw_count
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
        SELECT merchant_id, COUNT(*) AS kw_count FROM ads_merchant_keywords GROUP BY merchant_id
    ) mk ON mk.merchant_id = sub.yp_merchant_id
""")

# 模拟 Python 渲染耗时
print("\n  --- Python 渲染模拟 ---")
cur.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.commission_num,
           p.tracking_url, p.merchant_name, p.yp_merchant_id,
           a.asin AS amz_asin, a.title, a.rating, a.review_count, a.main_image_url,
           pl.plan_status, pl.id AS plan_id,
           COALESCE(mk.kw_count, 0) AS kw_count
    FROM (
        SELECT p.asin, p.yp_merchant_id FROM yp_us_products p ORDER BY p.product_id DESC LIMIT 30 OFFSET 0
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
    LEFT JOIN (SELECT merchant_id, COUNT(*) AS kw_count FROM ads_merchant_keywords GROUP BY merchant_id) mk ON mk.merchant_id = sub.yp_merchant_id
""")
products = cur.fetchall()

t0 = time.time()
rows_html = ''
for p in products:
    price_raw = str(p['price'] or '')
    price_str = price_raw if price_raw.startswith('$') else (f"${price_raw}" if price_raw else '--')
    rows_html += f'<tr><td>{p["asin"]}</td><td>{p["product_name"][:50]}</td><td>{price_str}</td></tr>'
ms = (time.time()-t0)*1000
print(f"  ✅ [{ms:>8.1f}ms] Python 渲染 {len(products)} 行 HTML  ({len(rows_html)} chars)")

# 测下数据库连接本身的耗时
print("\n  --- 连接池 vs 每次新建连接 ---")
t0 = time.time()
for i in range(5):
    c = mysql.connector.connect(host='localhost', port=3306, user='root', password='admin', database='affiliate_marketing', charset='utf8mb4')
    c.close()
ms = (time.time()-t0)*1000
print(f"  新建连接5次: {ms:.0f}ms avg={ms/5:.0f}ms each")

conn.close()
print("\n完成！")
