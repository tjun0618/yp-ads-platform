"""给 yp_products 表增加 amazon_url 字段"""
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', port=3306,
    user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

# 检查字段是否已存在
cur.execute("SHOW COLUMNS FROM yp_products LIKE 'amazon_url'")
if cur.fetchone():
    print("amazon_url 字段已存在，跳过")
else:
    cur.execute("ALTER TABLE yp_products ADD COLUMN amazon_url TEXT DEFAULT NULL COMMENT '亚马逊商品 URL' AFTER tracking_url")
    conn.commit()
    print("✅ amazon_url 字段已添加")

# 验证
cur.execute("DESCRIBE yp_products")
print("\n=== 当前表字段 ===")
for r in cur.fetchall():
    print(f"  {r[0]:20s} {r[1]}")

cur.close()
conn.close()
