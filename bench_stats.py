"""测试商户作战室统计查询优化"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
c = conn.cursor(dictionary=True)
mid = '363047'

def t(label, sql, args=None):
    t0 = time.perf_counter()
    c.execute(sql, args or ())
    r = c.fetchall()
    ms = (time.perf_counter()-t0)*1000
    print(f'[{ms:7.1f}ms] {label}')
    return ms

print('=== merchant_room 统计查询优化 ===')

# 原始写法（来自 ads_manager.py 第2336行）
t('原始写法(SUM CASE + LEFT JOIN)', """
SELECT COUNT(*) as total,
       SUM(CASE WHEN tracking_url IS NOT NULL AND tracking_url!='' THEN 1 ELSE 0 END) as with_link,
       SUM(CASE WHEN d.asin IS NOT NULL THEN 1 ELSE 0 END) as with_amazon,
       MAX(p.price) as max_price,
       MIN(p.price) as min_price
FROM yp_products p
LEFT JOIN amazon_product_details d ON p.asin=d.asin
WHERE p.merchant_id=%s
""", (mid,))

# 方案A: 去掉外连接，用三次独立COUNT
t('方案A: 3 x COUNT(*)', """
SELECT 
    (SELECT COUNT(*) FROM yp_products WHERE merchant_id=%s) as total,
    (SELECT COUNT(*) FROM yp_products WHERE merchant_id=%s AND tracking_url IS NOT NULL AND tracking_url!='') as with_link,
    (SELECT COUNT(*) FROM yp_products p WHERE p.merchant_id=%s AND EXISTS (SELECT 1 FROM amazon_product_details d WHERE d.asin=p.asin)) as with_amazon
""", (mid, mid, mid))

# 方案B: 只保留 total 和 with_link，去掉外连接
t('方案B: 2 x COUNT 无JOIN', """
SELECT COUNT(*) total,
       SUM(tracking_url IS NOT NULL AND tracking_url!='') as with_link
FROM yp_products
WHERE merchant_id=%s
""", (mid,))

conn.close()
print('完成')
