"""深入分析 yp_products merchant_id 查询慢的原因 v2"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
c = conn.cursor(dictionary=True)
mid = '363047'

print('=== EXPLAIN 分析 ===')
c.execute("""EXPLAIN SELECT COUNT(*) total,
       SUM(tracking_url IS NOT NULL) as with_link
FROM yp_products WHERE merchant_id=%s""", (mid,))
for r in c.fetchall():
    print(r)

print()
print('=== 索引详情 ===')
c.execute('SHOW INDEX FROM yp_products')
for r in c.fetchall():
    col = r.get("Column_name") or "(none)"
    print(f'  {r["Key_name"]:30s} col={col:20s} cardinality={r["Cardinality"]}')

print()
c.execute('SELECT COUNT(*) cnt FROM yp_products WHERE merchant_id=%s', (mid,))
r = c.fetchone()
print(f'merchant_id={mid} 的行数: {r["cnt"]}')

# 最大商户
c.execute('SELECT merchant_id, COUNT(*) cnt FROM yp_products GROUP BY merchant_id ORDER BY cnt DESC LIMIT 5')
print('商品最多的5个商户:')
for r in c.fetchall():
    print(f'  merchant_id={r["merchant_id"]}  count={r["cnt"]}')

# 测试 tracking_url 字段类型
c.execute("SHOW COLUMNS FROM yp_products LIKE 'tracking_url'")
r = c.fetchone()
print(f'\ntracking_url 字段: {r}')

# 测试 merchant_id 字段类型
c.execute("SHOW COLUMNS FROM yp_products LIKE 'merchant_id'")
r = c.fetchone()
print(f'merchant_id 字段: {r}')

conn.close()
print('\n完成')
