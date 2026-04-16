import mysql.connector

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                               database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()

# yp_products 的字段
cur.execute("SHOW COLUMNS FROM yp_products")
print("yp_products 字段:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

print()

# yp_merchants 的字段
cur.execute("SHOW COLUMNS FROM yp_merchants")
print("yp_merchants 字段:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

print()

# 看 yp_products 里的 merchant_id 在 yp_merchants 里对应什么
cur.execute("SELECT DISTINCT merchant_id, merchant_name FROM yp_products LIMIT 5")
prods = cur.fetchall()
print("yp_products 样本 (merchant_id, merchant_name):")
for p in prods:
    print(f"  merchant_id={p[0]}, merchant_name={p[1]}")
    # 在 yp_merchants 里找
    cur.execute("SELECT merchant_id, merchant_name, country FROM yp_merchants WHERE merchant_name = %s LIMIT 1", (p[1],))
    m = cur.fetchone()
    if m:
        print(f"    -> yp_merchants: id={m[0]}, name={m[1]}, country={m[2]}")
    else:
        cur.execute("SELECT merchant_id, merchant_name, country FROM yp_merchants WHERE merchant_name LIKE %s LIMIT 1", (f"%{p[1][:10]}%",))
        m2 = cur.fetchone()
        print(f"    -> yp_merchants: {m2}")

conn.close()
