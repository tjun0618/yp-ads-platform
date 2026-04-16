import mysql.connector, time
conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor()

# 检测有效商品数（有 tracking_url 的）
t0 = time.time()
cur.execute("SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")
cnt = cur.fetchone()[0]
print(f'有 tracking_url 的商品: {cnt} (耗时 {(time.time()-t0)*1000:.0f}ms)')

# 查 EXPLAIN
cur.execute("EXPLAIN SELECT SQL_CALC_FOUND_ROWS p.id FROM yp_products p WHERE p.tracking_url IS NOT NULL AND p.tracking_url != '' ORDER BY p.id DESC LIMIT 50")
print('\nEXPLAIN for filtered query:')
for r in cur.fetchall(): print(r)

# 现有索引
cur.execute('SHOW INDEX FROM yp_products')
print('\n现有索引:')
for r in cur.fetchall(): print(r[2], r[4], r[10])

conn.close()
