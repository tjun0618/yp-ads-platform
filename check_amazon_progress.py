import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM yp_products WHERE amazon_url IS NOT NULL AND amazon_url != '' AND amazon_url != 'FAILED'")
print(f"成功获取 amazon_url: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM yp_products WHERE amazon_url = 'FAILED'")
print(f"FAILED 记录数: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM yp_products WHERE amazon_url IS NULL OR amazon_url = ''")
print(f"尚未处理: {cur.fetchone()[0]:,}")

cur.execute("SELECT id, asin, amazon_url FROM yp_products WHERE amazon_url IS NOT NULL AND amazon_url != '' AND amazon_url != 'FAILED' LIMIT 3")
print("\n样本:")
for r in cur.fetchall():
    print(f"  id={r[0]} ASIN={r[1]}")
    print(f"  {r[2][:100]}")

cur.close()
conn.close()
