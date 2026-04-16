import mysql.connector

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                               database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()

# 先看看 yp_products.merchant_id 样本
cur.execute("SELECT DISTINCT merchant_id FROM yp_products LIMIT 5")
print("yp_products.merchant_id 样本:", [r[0] for r in cur.fetchall()])

# yp_merchants.merchant_id 样本
cur.execute("SELECT merchant_id, country FROM yp_merchants LIMIT 5")
print("yp_merchants (merchant_id, country) 样本:", cur.fetchall())

# 用 CAST 强制转为 CHAR 来 JOIN
cur.execute("""
    SELECT COUNT(*) FROM yp_products p
    JOIN yp_merchants m ON CAST(p.merchant_id AS UNSIGNED) = m.merchant_id
    WHERE m.country LIKE 'US%'
""")
print("CAST JOIN 数量:", cur.fetchone()[0])

# US merchant_id 子查询（CAST 方式）
cur.execute("""
    SELECT COUNT(*) FROM yp_products p
    WHERE CAST(p.merchant_id AS UNSIGNED) IN (
        SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%'
    )
""")
print("子查询 CAST 数量:", cur.fetchone()[0])

# 单纯比较
cur.execute("SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%' LIMIT 3")
us_ids = [str(r[0]) for r in cur.fetchall()]
print("US merchant_id 示例:", us_ids)
cur.execute("SELECT merchant_id FROM yp_products WHERE merchant_id IN (%s,%s,%s) LIMIT 3" % tuple(['%s']*3), us_ids)
print("匹配到的 yp_products:", cur.fetchall())

conn.close()
