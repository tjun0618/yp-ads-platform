import mysql.connector
conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("""
    SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA='affiliate_marketing'
    AND COLUMN_NAME='merchant_name'
    AND TABLE_NAME IN ('yp_products','yp_merchants')
""")
for r in cur.fetchall():
    print(r)

# 也验证下 JOIN 速度
import time
cur2 = conn.cursor()
cur2.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")
cur2.close()

cur3 = conn.cursor(dictionary=True)
t0 = time.time()
cur3.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    WHERE m.country LIKE 'US -%'
""")
r = cur3.fetchone()
print(f"\nJOIN by merchant_name US COUNT: {r['cnt']} ({time.time()-t0:.2f}s)")

t0 = time.time()
cur3.execute("""
    SELECT DISTINCT p.category FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    WHERE m.country LIKE 'US -%' AND p.category IS NOT NULL AND p.category != ''
    ORDER BY p.category LIMIT 100
""")
cats = cur3.fetchall()
print(f"类别查询: {len(cats)} 条 ({time.time()-t0:.2f}s)")
if cats:
    print(f"示例: {cats[0]}")

t0 = time.time()
cur3.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, m.merchant_name
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    WHERE m.country LIKE 'US -%'
    GROUP BY p.asin
    ORDER BY CAST(p.commission AS DECIMAL(10,4)) DESC
    LIMIT 30 OFFSET 0
""")
rows = cur3.fetchall()
print(f"主列表LIMIT30: {len(rows)} 条 ({time.time()-t0:.2f}s)")
if rows:
    print(f"第一条: {rows[0]}")

conn.close()
