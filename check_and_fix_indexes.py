"""
检查并添加缺失索引，修复慢查询
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

# ─── Step 1: 检查现有索引 ─────────────────────────────────────────────
def get_indexes(table):
    cur.execute(f'SHOW INDEX FROM {table}')
    return {r[2] for r in cur.fetchall()}

print('=' * 60)
print('Step 1: 现有索引检查')
print('=' * 60)
tables = ['yp_products', 'yp_us_products', 'amazon_product_details', 'ads_plans', 'ads_merchant_keywords', 'yp_merchants']
existing = {}
for t in tables:
    try:
        idx = get_indexes(t)
        existing[t] = idx
        print(f'{t}: {idx}')
    except Exception as e:
        print(f'{t}: ERROR - {e}')
        existing[t] = set()

# ─── Step 2: 检查各表行数 ─────────────────────────────────────────────
print('\n' + '=' * 60)
print('Step 2: 各表数据量')
print('=' * 60)
cur.execute("""
    SELECT table_name, table_rows, ROUND(data_length/1024/1024,2) data_mb 
    FROM information_schema.tables 
    WHERE table_schema='affiliate_marketing' 
    ORDER BY data_length DESC
""")
for r in cur.fetchall():
    print(f'  {r[0]}: ~{r[1]}行, {r[2]}MB')

# ─── Step 3: 添加缺失索引 ─────────────────────────────────────────────
print('\n' + '=' * 60)
print('Step 3: 添加缺失索引')
print('=' * 60)

indexes_to_add = [
    # table, index_name, columns, comment
    ('yp_products',           'idx_merchant_id',    'merchant_id',                       '商户商品列表最关键索引'),
    ('yp_products',           'idx_asin',           'asin',                              '按ASIN查商品'),
    ('yp_us_products',        'idx_asin',           'asin',                              '首页JOIN amazon_product_details'),
    ('yp_us_products',        'idx_yp_merchant_id', 'yp_merchant_id',                    'N+1子查询JOIN用'),
    ('yp_us_products',        'idx_product_id',     'product_id',                        'ORDER BY product_id DESC'),
    ('amazon_product_details','idx_asin',           'asin',                              'JOIN主键'),
    ('ads_plans',             'idx_asin',           'asin',                              '首页JOIN ads_plans'),
    ('ads_plans',             'idx_plan_status',    'plan_status',                       'plan_status过滤'),
    ('ads_merchant_keywords', 'idx_merchant_id',    'merchant_id',                       'N+1子查询用'),
]

added = 0
skipped = 0
for table, idx_name, columns, comment in indexes_to_add:
    if idx_name in existing.get(table, set()):
        print(f'  SKIP  {table}.{idx_name} (已存在)')
        skipped += 1
        continue
    try:
        t0 = time.time()
        cur.execute(f'ALTER TABLE {table} ADD INDEX {idx_name} ({columns})')
        conn.commit()
        elapsed = time.time() - t0
        print(f'  ADD   {table}.{idx_name} ({columns}) -- {comment} [{elapsed:.1f}s]')
        added += 1
    except Exception as e:
        print(f'  ERROR {table}.{idx_name}: {e}')

print(f'\n索引添加完成: 新增 {added} 个，跳过 {skipped} 个')

# ─── Step 4: 实际查询计时测试 ──────────────────────────────────────────
print('\n' + '=' * 60)
print('Step 4: 修复前后查询耗时对比（先加索引再测）')
print('=' * 60)

queries = [
    ('首页商品查询（无过滤）', """
        SELECT p.asin, p.product_name, a.rating, pl.plan_status
        FROM yp_us_products p
        LEFT JOIN amazon_product_details a ON p.asin = a.asin
        LEFT JOIN ads_plans pl ON p.asin = pl.asin
        ORDER BY p.product_id DESC LIMIT 30 OFFSET 0
    """, []),
    ('商户商品列表', """
        SELECT p.id, p.asin, p.product_name, d.rating
        FROM yp_products p 
        LEFT JOIN amazon_product_details d ON p.asin=d.asin
        WHERE p.merchant_id=%s 
        ORDER BY p.id DESC LIMIT 50 OFFSET 0
    """, ['DOVOH']),
    ('ads_merchant_keywords COUNT（旧N+1子查询）', """
        SELECT COUNT(*) FROM ads_merchant_keywords WHERE merchant_id=%s
    """, ['DOVOH']),
    ('JOIN方式替代N+1（批量统计）', """
        SELECT merchant_id, COUNT(*) as cnt 
        FROM ads_merchant_keywords 
        GROUP BY merchant_id
        LIMIT 1
    """, []),
]

for name, sql, params in queries:
    try:
        t0 = time.time()
        cur.execute(sql, params)
        cur.fetchall()
        elapsed = time.time() - t0
        print(f'  {name}: {elapsed*1000:.1f}ms')
    except Exception as e:
        print(f'  {name}: ERROR - {e}')

cur.close()
conn.close()
print('\n完成！')
