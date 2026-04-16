"""检查 yp_products 并添加缺失索引"""
import mysql.connector, time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
c = conn.cursor(dictionary=True)

print('=== yp_products 现有索引 ===')
c.execute('SHOW INDEX FROM yp_products')
rows = c.fetchall()
existing_keys = set()
for r in rows:
    print(f'  {r["Key_name"]:30s} {r["Column_name"]}')
    existing_keys.add(r['Key_name'])

c.execute('SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s', ('affiliate_marketing','yp_products'))
r = c.fetchone()
print(f'\nyp_products 行数估算: {list(r.values())[0]}')

t0 = time.perf_counter()
c.execute('SELECT COUNT(*) cnt FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ""')
cnt = c.fetchone()['cnt']
ms = (time.perf_counter()-t0)*1000
print(f'[{ms:.0f}ms] yp_products valid tracking_url: {cnt}')

print()
# 添加 tracking_url 索引（前缀索引，因为是text/varchar大字段）
if 'idx_tracking_url_notnull' not in existing_keys:
    print('添加 tracking_url 前缀索引...')
    t0 = time.perf_counter()
    c.execute('ALTER TABLE yp_products ADD INDEX idx_tracking_notnull (tracking_url(10))')
    conn.commit()
    ms = (time.perf_counter()-t0)*1000
    print(f'[{ms:.0f}ms] 索引添加完成')
else:
    print('idx_tracking_url_notnull 已存在')

# 再次测速
t0 = time.perf_counter()
c.execute('SELECT COUNT(*) cnt FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ""')
cnt2 = c.fetchone()['cnt']
ms2 = (time.perf_counter()-t0)*1000
print(f'[{ms2:.0f}ms] 添加索引后 COUNT(*): {cnt2}')

# 同时确认 information_schema 估算
t0 = time.perf_counter()
c.execute('SELECT TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s', ('affiliate_marketing','yp_products'))
r = c.fetchone()
ms3 = (time.perf_counter()-t0)*1000
print(f'[{ms3:.0f}ms] information_schema TABLE_ROWS: {list(r.values())[0]}')

conn.close()
print('\n完成')
