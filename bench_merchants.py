"""测试 yp_merchants 查询优化方案"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
c = conn.cursor(dictionary=True)

def bench(label, sql):
    t0 = time.perf_counter()
    c.execute(sql)
    rows = c.fetchall()
    ms = (time.perf_counter()-t0)*1000
    print(f'[{ms:8.1f}ms] {label}  ({len(rows)} rows)')
    return ms

print('=== yp_merchants 查询优化测试 ===')

# 当前慢查询
bench('当前写法 (慢)', '''
SELECT m.merchant_id, m.merchant_name, m.avg_payout, m.cookie_days,
       COUNT(p.asin) product_count
FROM yp_merchants m
LEFT JOIN yp_us_products p ON p.yp_merchant_id = m.merchant_id
GROUP BY m.merchant_id ORDER BY m.avg_payout DESC LIMIT 20
''')

# 方案A: 预聚合子查询
bench('优化方案A (预聚合子查询)', '''
SELECT m.merchant_id, m.merchant_name, m.avg_payout, m.cookie_days,
       COALESCE(pc.product_count, 0) AS product_count
FROM yp_merchants m
LEFT JOIN (
    SELECT yp_merchant_id, COUNT(*) AS product_count
    FROM yp_us_products
    GROUP BY yp_merchant_id
) pc ON pc.yp_merchant_id = m.merchant_id
ORDER BY m.avg_payout DESC
LIMIT 20
''')

# 方案B: 完全不 JOIN，只返回商户信息
bench('优化方案B (不JOIN)', '''
SELECT merchant_id, merchant_name, avg_payout, cookie_days, country
FROM yp_merchants ORDER BY avg_payout DESC LIMIT 20
''')

# EXPLAIN 分析当前慢查询
print()
print('=== EXPLAIN 分析优化方案A ===')
c.execute('''EXPLAIN SELECT m.merchant_id, m.merchant_name, m.avg_payout, m.cookie_days,
       COALESCE(pc.product_count, 0) AS product_count
FROM yp_merchants m
LEFT JOIN (
    SELECT yp_merchant_id, COUNT(*) AS product_count
    FROM yp_us_products
    GROUP BY yp_merchant_id
) pc ON pc.yp_merchant_id = m.merchant_id
ORDER BY m.avg_payout DESC
LIMIT 20''')
for r in c.fetchall():
    print(r)

# 看看是否需要建索引
print()
c.execute("DESCRIBE yp_merchants")
cols = c.fetchall()
print('yp_merchants 列:')
for col in cols:
    print(f"  {col['Field']:30s} {col['Type']}")

conn.close()
print()
print('测试完成')
