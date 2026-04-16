import mysql.connector
conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4')
cur = conn.cursor()

print('=== yp_merchants ===')
cur.execute('SELECT COUNT(*) FROM yp_merchants')
print(f'总记录数: {cur.fetchone()[0]:,}')

cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE status='APPROVED'")
print(f'已批准商户: {cur.fetchone()[0]:,}')

cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE online_status='onLine'")
print(f'在线商户: {cur.fetchone()[0]:,}')

cur.execute('SELECT status, COUNT(*) cnt FROM yp_merchants GROUP BY status ORDER BY cnt DESC')
print('按状态分组:')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]:,}')

cur.execute("SELECT merchant_id, merchant_name, avg_payout, cookie_days, status, online_status FROM yp_merchants WHERE status='APPROVED' LIMIT 5")
print('APPROVED 商户样本:')
for r in cur.fetchall():
    print(f'  [{r[0]}] {r[1]}  payout={r[2]}  cookie={r[3]}d  {r[4]}/{r[5]}')

print()
print('=== yp_categories ===')
cur.execute('SELECT COUNT(*) FROM yp_categories')
print(f'总记录数: {cur.fetchone()[0]:,}')

cur.execute('SELECT category_id, category_name FROM yp_categories ORDER BY category_id LIMIT 10')
print('前10个类别:')
for r in cur.fetchall():
    print(f'  [{r[0]}] {r[1]}')

print()
print('=== 数据库全部表 ===')
cur.execute('SHOW TABLES')
for r in cur.fetchall():
    cur2 = conn.cursor()
    cur2.execute(f'SELECT COUNT(*) FROM {r[0]}')
    cnt = cur2.fetchone()[0]
    cur2.close()
    print(f'  {r[0]}  ({cnt:,} 条)')

cur.close()
conn.close()
