import mysql.connector, time

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

# 加 country 索引
try:
    cur.execute("CREATE INDEX idx_merchants_country ON yp_merchants(country(50))")
    print("idx_merchants_country 创建成功")
except Exception as e:
    print(f"已存在: {e}")

conn.commit()

# 测试直接 JOIN 速度
cur2 = conn.cursor(dictionary=True)

t0 = time.time()
cur2.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    WHERE m.country LIKE 'US -%'
""")
r = cur2.fetchone()
print(f"JOIN COUNT: {r['cnt']} ({time.time()-t0:.2f}s)")

t0 = time.time()
cur2.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.merchant_name,
           a.title AS amz_title, a.rating, pl.plan_status
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    WHERE m.country LIKE 'US -%'
    GROUP BY p.asin
    ORDER BY CAST(REPLACE(p.commission,'%','') AS DECIMAL(10,4)) DESC
    LIMIT 30 OFFSET 0
""")
rows = cur2.fetchall()
print(f"JOIN LIMIT30: {len(rows)} ({time.time()-t0:.2f}s)")
if rows:
    print(f"第一条: {rows[0]['asin']} | {rows[0]['commission']} | {rows[0]['merchant_name']}")

conn.close()
