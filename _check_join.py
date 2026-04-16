"""
诊断 merchant_id JOIN 问题 + 加速索引
"""
import mysql.connector

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                               database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

# 1. 检查 yp_merchants.merchant_id 的数据类型
cur.execute("SHOW COLUMNS FROM yp_merchants WHERE Field='merchant_id' OR Field='country'")
for r in cur.fetchall():
    print("yp_merchants:", r)

# 2. 检查 yp_products.merchant_id 的数据类型
cur.execute("SHOW COLUMNS FROM yp_products WHERE Field='merchant_id'")
for r in cur.fetchall():
    print("yp_products:", r)

# 3. 先看有多少 US 商户
cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE country LIKE 'US%'")
print("\nUS merchants:", cur.fetchone()[0])

# 4. 测试直接 JOIN
cur.execute("""
    SELECT COUNT(*)
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_id = m.merchant_id
    WHERE m.country LIKE 'US%'
    LIMIT 1
""")
print("Direct JOIN count:", cur.fetchone()[0])

# 5. 检查现有索引
cur.execute("SHOW INDEX FROM yp_products")
idxs = cur.fetchall()
print("\nyp_products indexes:")
for r in idxs:
    print(f"  {r[2]} on {r[4]}")

cur.execute("SHOW INDEX FROM yp_merchants")
idxs = cur.fetchall()
print("\nyp_merchants indexes:")
for r in idxs:
    print(f"  {r[2]} on {r[4]}")

conn.close()
