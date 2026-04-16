"""精细诊断4 - 正确表结构版本"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)

def t(label, sql, args=None):
    t0 = time.perf_counter()
    c = conn.cursor(dictionary=True)
    c.execute(sql, args or ())
    rows = c.fetchall()
    c.close()
    ms = (time.perf_counter()-t0)*1000
    print(f'[{ms:8.1f}ms] {label}  ({len(rows)} rows)')
    return rows, ms

print('=== SQL层逐步计时 ===')
total_sql = 0

rows, ms = t('TABLE_ROWS yp_us_products',
  'SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s',
  ('affiliate_marketing','yp_us_products'))
total_sql += ms
if rows: print(f'         -> TABLE_ROWS={list(rows[0].values())[0]}')

_, ms = t('TABLE_ROWS amazon_product_details',
  'SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s',
  ('affiliate_marketing','amazon_product_details'))
total_sql += ms

_, ms = t('TABLE_ROWS ads_plans',
  'SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s',
  ('affiliate_marketing','ads_plans'))
total_sql += ms

_, ms = t('GROUP BY ads_merchant_keywords',
  'SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id')
total_sql += ms

_, ms = t('yp_us_products ORDER BY product_id LIMIT30',
  'SELECT asin,yp_merchant_id FROM yp_us_products ORDER BY product_id DESC LIMIT 30')
total_sql += ms

_, ms = t('延迟关联 主查询', '''
SELECT p.asin, p.product_name, p.price, p.commission,
       p.yp_merchant_id, p.merchant_name,
       p.investment_score,
       a.rating, a.review_count, a.main_image_url, a.brand,
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
) mk ON mk.merchant_id = CAST(sub.yp_merchant_id AS CHAR)
''')
total_sql += ms

_, ms = t('yp_merchants GROUP BY product_count LIMIT20', '''
SELECT m.merchant_id, m.merchant_name, m.avg_payout, m.cookie_days,
       COUNT(p.asin) product_count
FROM yp_merchants m
LEFT JOIN yp_us_products p ON p.yp_merchant_id = m.merchant_id
GROUP BY m.merchant_id ORDER BY m.avg_payout DESC LIMIT 20
''')
total_sql += ms

_, ms = t('ads_plans 列表 LIMIT20', '''
SELECT id, asin, product_name, merchant_name, plan_status, avg_quality_score
FROM ads_plans ORDER BY id DESC LIMIT 20
''')
total_sql += ms

print(f'\n累计SQL耗时: {total_sql:.1f}ms')

conn.close()

print()
print('=== HTTP层 Flask全流程计时 ===')
import urllib.request

def http_get(url):
    req = urllib.request.urlopen(url, timeout=15)
    data = req.read()
    return len(data)

total_http = 0
for url, label in [
    ('http://localhost:5055/', '首页 /'),
    ('http://localhost:5055/api/products?page=1', '/api/products'),
    ('http://localhost:5055/api/merchants?page=1', '/api/merchants'),
    ('http://localhost:5055/qs_dashboard', '/qs_dashboard'),
    ('http://localhost:5055/competitor_ads', '/competitor_ads'),
]:
    t0 = time.perf_counter()
    try:
        size = http_get(url)
        ms = (time.perf_counter()-t0)*1000
        total_http += ms
        print(f'[{ms:8.1f}ms] {label}  ({size} bytes)')
    except Exception as e:
        ms = (time.perf_counter()-t0)*1000
        print(f'[{ms:8.1f}ms] {label}  ERROR: {e}')

print(f'\n累计HTTP耗时: {total_http:.1f}ms')
print()
print('诊断完成')
