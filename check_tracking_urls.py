import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306,
    user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")
print(f"有 tracking_url 的记录数: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NULL OR tracking_url = ''")
print(f"无 tracking_url 的记录数: {cur.fetchone()[0]:,}")

cur.execute("SELECT merchant_name, asin, tracking_url FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != '' LIMIT 5")
print()
print("=== Tracking URL 样本 ===")
for r in cur.fetchall():
    print(f"  [{r[0]}] ASIN={r[1]}")
    print(f"    URL: {r[2]}")

cur.execute("DESCRIBE yp_products")
print()
print("=== 当前表字段 ===")
for r in cur.fetchall():
    print(f"  {r[0]:20s} {r[1]}")

cur.close()
conn.close()
