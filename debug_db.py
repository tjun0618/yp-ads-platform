import mysql.connector
import sys

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor(dictionary=True)

# 1. 检查 yp_merchants 表结构和数据量
print('=== yp_merchants ===')
cur.execute("SELECT COUNT(*) cnt FROM yp_merchants")
print('Total:', cur.fetchone()['cnt'])

# 2. 检查商户 369117 是否在 yp_merchants
cur.execute("SELECT * FROM yp_merchants WHERE merchant_id='369117' OR merchant_id=369117 LIMIT 1")
row = cur.fetchone()
print('merchant_id 369117 in yp_merchants:', row)

# 3. 检查 yp_us_products 表
print('\n=== yp_us_products ===')
cur.execute("SELECT COUNT(*) cnt FROM yp_us_products")
print('Total:', cur.fetchone()['cnt'])

cur.execute("SELECT COUNT(*) cnt FROM yp_us_products WHERE yp_merchant_id=369117")
print('Products for merchant 369117:', cur.fetchone()['cnt'])

# 4. 看看 yp_merchants 里有没有任何数据
cur.execute("SELECT merchant_id, merchant_name FROM yp_merchants LIMIT 5")
rows = cur.fetchall()
print('\nSample yp_merchants:', rows)

# 5. 看 yp_us_products 里的商户 ID 分布（前5个）
cur.execute("SELECT yp_merchant_id, merchant_name, COUNT(*) cnt FROM yp_us_products GROUP BY yp_merchant_id, merchant_name ORDER BY cnt DESC LIMIT 5")
rows = cur.fetchall()
print('\nTop merchants in yp_us_products:', rows)

conn.close()
