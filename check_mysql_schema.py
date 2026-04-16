# -*- coding: utf-8 -*-
import mysql.connector

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin', database='affiliate_marketing'
)
cur = conn.cursor()

# 查看所有表
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
print("=== 数据库表 ===")
for t in tables:
    print(f"  {t}")
print()

# 查看 yp_products 表结构
cur.execute("DESCRIBE yp_products")
print("=== yp_products 字段 ===")
for row in cur.fetchall():
    print(f"  {row[0]:<25} {row[1]:<20} {row[2]}")
print()

# 查看记录数和 amazon_url 样本
cur.execute("SELECT COUNT(*) FROM yp_products")
print(f"yp_products 总记录: {cur.fetchone()[0]:,}")

cur.execute("SELECT asin, amazon_url FROM yp_products WHERE amazon_url IS NOT NULL AND amazon_url != '' LIMIT 5")
print("\namazon_url 样本:")
for r in cur.fetchall():
    print(f"  ASIN={r[0]}  URL={r[1][:80]}")

conn.close()
