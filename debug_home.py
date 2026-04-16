"""
直接调用 Flask 路由函数，获取真实错误
"""
import sys
sys.path.insert(0, r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu')

import traceback
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

# 模拟首页 product_list 的逻辑
page = 1
per_page = 30
search = ''
has_amazon = ''
has_plan = ''
sort = 'newest'
category = ''
price_min = ''
price_max = ''

where_clauses = []
params = []

if search:
    where_clauses.append("(p.product_name LIKE %s OR p.asin LIKE %s OR p.merchant_name LIKE %s)")
    like = f'%{search}%'
    params += [like, like, like]

where_sql = ('WHERE ' + ' AND '.join(where_clauses)) if where_clauses else ''
order_sql = 'p.product_id DESC'

total = 0
if not where_clauses:
    try:
        cur.execute("""
            SELECT table_rows FROM information_schema.tables
            WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'
        """)
        r = cur.fetchone()
        total = int(r['table_rows']) if r and r['table_rows'] else 0
        print(f"information_schema 估算 total: {total}")
    except Exception as e:
        print(f"information_schema 错误: {e}")
        traceback.print_exc()

offset = (page - 1) * per_page

# 延迟关联查询
data_sql = f"""
    SELECT
        p.asin, p.product_name, p.price, p.commission, p.commission_num,
        p.tracking_url, p.merchant_name, p.yp_merchant_id AS merchant_id,
        a.asin         AS amz_asin,
        a.title        AS amz_title,
        a.rating, a.review_count, a.main_image_url AS img,
        pl.plan_status, pl.id AS plan_id,
        COALESCE(mk.kw_count, 0) AS kw_count
    FROM (
        SELECT asin, yp_merchant_id
        FROM yp_us_products
        {where_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
    ) sub
    JOIN yp_us_products p ON p.asin = sub.asin
    LEFT JOIN amazon_product_details a ON a.asin = sub.asin
    LEFT JOIN ads_plans pl ON pl.asin = sub.asin
    LEFT JOIN (
        SELECT merchant_id, COUNT(*) AS kw_count
        FROM ads_merchant_keywords
        GROUP BY merchant_id
    ) mk ON mk.merchant_id = sub.yp_merchant_id
"""

print(f"\nSQL:\n{data_sql[:500]}\n")
print(f"params: {params + [per_page, offset]}\n")

try:
    t0 = time.time()
    cur.execute(data_sql, params + [per_page, offset])
    rows = cur.fetchall()
    elapsed = time.time() - t0
    print(f"SUCCESS: {len(rows)} rows in {elapsed*1000:.1f}ms")
    if rows:
        print(f"First row keys: {list(rows[0].keys())}")
except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()

conn.close()
