import mysql.connector, time

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                                database='affiliate_marketing',charset='utf8mb4')
cur2 = conn.cursor()
cur2.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")
cur2.close()

cur = conn.cursor(dictionary=True)

print("=== 修复后 SQL 诊断（COLLATE 修正版）===\n")

# 1. 类别查询（CAST + COLLATE utf8mb4_unicode_ci）
t0 = time.time()
cur.execute("""
    SELECT DISTINCT p.category FROM yp_products p
    JOIN yp_merchants m ON p.merchant_id = CAST(m.id AS CHAR) COLLATE utf8mb4_unicode_ci
    WHERE m.country LIKE 'US -%' AND p.category IS NOT NULL AND p.category != ''
    ORDER BY p.category LIMIT 100
""")
r = cur.fetchall()
print(f"1. 类别查询: {time.time()-t0:.2f}s  ({len(r)} 条)")
if r:
    print(f"   示例: {r[0]['category']}")

# 2. US 商品总数
t0 = time.time()
cur.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt FROM yp_products p
    JOIN yp_merchants m ON p.merchant_id = CAST(m.id AS CHAR) COLLATE utf8mb4_unicode_ci
    WHERE m.country LIKE 'US -%'
""")
r = cur.fetchone()
print(f"2. US商品总数: {time.time()-t0:.2f}s  ({r['cnt']} 条)")

# 3. 主列表 LIMIT 30
t0 = time.time()
cur.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.category,
           m.merchant_name, a.rating, pl.plan_status
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_id = CAST(m.id AS CHAR) COLLATE utf8mb4_unicode_ci
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    WHERE m.country LIKE 'US -%'
    GROUP BY p.asin
    ORDER BY CAST(p.commission AS DECIMAL(10,4)) DESC
    LIMIT 30 OFFSET 0
""")
rows = cur.fetchall()
print(f"3. 主列表LIMIT30: {time.time()-t0:.2f}s  ({len(rows)} 条)")
if rows:
    print(f"   第一条: {rows[0]['asin']} | 佣金:{rows[0]['commission']} | 商户:{rows[0]['merchant_name']}")

# 4. US merchants 数量
cur.execute("SELECT COUNT(*) as c FROM yp_merchants WHERE country LIKE 'US -%'")
r = cur.fetchone()
print(f"4. US merchants: {r['c']}")

conn.close()
print("\n所有查询完成！")
