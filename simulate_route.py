"""
直接在本地运行，模拟 Flask 路由内的行为，精确计时每一步
不走 HTTP，直接调用 ads_manager 的逻辑
"""
import sys, time
sys.path.insert(0, r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu')

print('开始...')
t0 = time.perf_counter()

# 模拟连接池取连接
import mysql.connector.pooling as _pool
DB = dict(host='localhost', port=3306, user='root', password='admin',
          database='affiliate_marketing', charset='utf8mb4', autocommit=True)

_db_pool = _pool.MySQLConnectionPool(pool_name='test_pool', pool_size=5, **DB)
print(f'[{(time.perf_counter()-t0)*1000:.0f}ms] 连接池初始化完成')

# 模拟首页路由全流程
import time as _time

t1 = time.perf_counter()
conn = _db_pool.get_connection()
print(f'[{(time.perf_counter()-t1)*1000:.0f}ms] 连接池 get_connection()')

cur = conn.cursor(dictionary=True)

# 类别
t1 = time.perf_counter()
cur.execute("SELECT category_id, category_name FROM yp_categories ORDER BY category_name")
cats = cur.fetchall()
print(f'[{(time.perf_counter()-t1)*1000:.0f}ms] 类别查询 ({len(cats)} rows)')

# information_schema 估算
t1 = time.perf_counter()
cur.execute("SELECT TABLE_ROWS FROM information_schema.tables WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'")
r = cur.fetchone()
est = list(r.values())[0]
print(f'[{(time.perf_counter()-t1)*1000:.0f}ms] information_schema TABLE_ROWS={est}')

# ads_plans COUNT
t1 = time.perf_counter()
cur.execute("SELECT COUNT(*) FROM ads_plans WHERE plan_status='completed'")
r = cur.fetchone()
print(f'[{(time.perf_counter()-t1)*1000:.0f}ms] ads_plans COUNT={list(r.values())[0]}')

# 延迟关联主查询
t1 = time.perf_counter()
cur.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.commission_num,
           p.tracking_url, p.merchant_name, p.yp_merchant_id AS merchant_id,
           a.asin AS amz_asin, a.rating, a.review_count, a.main_image_url AS img,
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
        SELECT merchant_id, COUNT(*) AS kw_count
        FROM ads_merchant_keywords
        GROUP BY merchant_id
    ) mk ON mk.merchant_id = sub.yp_merchant_id
""")
products = cur.fetchall()
print(f'[{(time.perf_counter()-t1)*1000:.0f}ms] 延迟关联主查询 ({len(products)} rows)')

cur.close()
conn.close()

total = (time.perf_counter()-t0)*1000
print(f'\n总计: {total:.0f}ms')
print()
print('注：Flask HTTP 响应约 2000ms 但本地直接调用只需上述时间')
print('差值 = 连接开销 + HTTP协议 + Flask路由分发 + HTML渲染')
