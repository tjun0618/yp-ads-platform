import mysql.connector, time

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

# 1. 检查 category 字段数据
cur.execute("SELECT COUNT(*) FROM yp_products WHERE category IS NOT NULL AND category != ''")
r = cur.fetchone()
print(f"有 category 的商品: {r[0]}")

cur.execute("SELECT category, COUNT(*) as c FROM yp_products WHERE category IS NOT NULL AND category != '' GROUP BY category ORDER BY c DESC LIMIT 10")
print("Top 10 类别:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

# 2. 查这些有 category 的商品能不能通过 merchant_name JOIN 到 US merchants
cur.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt FROM yp_products p
    JOIN yp_merchants m ON p.merchant_name = m.merchant_name
    WHERE m.country LIKE 'US -%' AND p.category IS NOT NULL AND p.category != ''
""")
r = cur.fetchone()
print(f"\n有 category 的 US 商品: {r[0]}")

# 3. 加索引，提升速度
print("\n正在添加索引...")
try:
    cur.execute("CREATE INDEX idx_products_merchant_name ON yp_products(merchant_name(100))")
    print("  idx_products_merchant_name 创建成功")
except Exception as e:
    print(f"  已存在或错误: {e}")

try:
    cur.execute("CREATE INDEX idx_merchants_name_country ON yp_merchants(merchant_name(100), country(50))")
    print("  idx_merchants_name_country 创建成功")
except Exception as e:
    print(f"  已存在或错误: {e}")

try:
    cur.execute("CREATE INDEX idx_products_asin ON yp_products(asin)")
    print("  idx_products_asin 创建成功")
except Exception as e:
    print(f"  已存在或错误: {e}")

conn.commit()

# 4. 重新测速
cur2 = conn.cursor(dictionary=True)
t0 = time.time()
cur2.execute("""
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
rows = cur2.fetchall()
print(f"\n加索引后主列表LIMIT30: {len(rows)} 条 ({time.time()-t0:.2f}s)")

conn.close()
