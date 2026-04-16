"""深入分析 yp_products merchant_id 查询慢的原因"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
c = conn.cursor(dictionary=True)
mid = '363047'

print('=== EXPLAIN 分析 ===')
c.execute("""EXPLAIN SELECT COUNT(*) total,
       SUM(tracking_url IS NOT NULL AND tracking_url!='') as with_link
FROM yp_products WHERE merchant_id=%s""", (mid,))
for r in c.fetchall():
    print(r)

print()
print('=== yp_products 行数分布 ===')
c.execute('SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s', ('affiliate_marketing','yp_products'))
r = c.fetchone()
print(f'总行数估算: {list(r.values())[0]}')

c.execute('SELECT COUNT(*) cnt FROM yp_products WHERE merchant_id=%s', (mid,))
r = c.fetchone()
print(f'merchant_id={mid} 的行数: {r["cnt"]}')

print()
print('=== 索引详情 ===')
c.execute('SHOW INDEX FROM yp_products')
for r in c.fetchall():
    print(f'  {r["Key_name"]:30s} col={r["Column_name"]:20s} cardinality={r["Cardinality"]}')

print()
# 看看最大商户有多少商品
c.execute('SELECT merchant_id, COUNT(*) cnt FROM yp_products GROUP BY merchant_id ORDER BY cnt DESC LIMIT 5')
print('商品最多的5个商户:')
for r in c.fetchall():
    print(f'  merchant_id={r["merchant_id"]}  count={r["cnt"]}')

conn.close()
print('\n完成')
