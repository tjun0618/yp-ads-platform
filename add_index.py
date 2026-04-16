import mysql.connector

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor()

print("开始建索引...")

# 给 tracking_url 加索引（前缀索引，取前 50 字符）
try:
    cur.execute("CREATE INDEX idx_tracking_url ON yp_products (tracking_url(50))")
    print("idx_tracking_url: OK")
except Exception as e:
    print(f"idx_tracking_url: {e}")

conn.commit()

# 验证
cur.execute("SHOW INDEX FROM yp_products")
print("\n现有索引:")
for r in cur.fetchall():
    print(f"  {r[2]:30s} {r[4]:30s} {r[10]}")

conn.close()
print("完成")
