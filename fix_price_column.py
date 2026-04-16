"""
为 yp_us_products 添加 price_num 数值列，支持价格范围过滤走索引
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

# 1. 添加 price_num 列
try:
    cur.execute('ALTER TABLE yp_us_products ADD COLUMN price_num DECIMAL(10,2) DEFAULT NULL')
    conn.commit()
    print('Added price_num column')
except Exception as e:
    if 'Duplicate column' in str(e):
        print('price_num column already exists, skip')
    else:
        print(f'Add column error: {e}')

# 2. 填充 price_num（从 varchar price 提取数字）
try:
    t0 = time.time()
    sql = r"""
        UPDATE yp_us_products 
        SET price_num = CASE 
            WHEN price REGEXP '^[0-9$]' 
            THEN CAST(REGEXP_REPLACE(price, '[^0-9.]', '') AS DECIMAL(10,2)) 
            ELSE NULL 
        END
    """
    cur.execute(sql)
    conn.commit()
    print(f'Updated price_num: {cur.rowcount} rows in {time.time()-t0:.1f}s')
except Exception as e:
    print(f'Update price_num error: {e}')

# 3. 添加索引
try:
    cur.execute('ALTER TABLE yp_us_products ADD INDEX idx_price_num (price_num)')
    conn.commit()
    print('Added idx_price_num index')
except Exception as e:
    if 'Duplicate key name' in str(e):
        print('idx_price_num index already exists, skip')
    else:
        print(f'Add index error: {e}')

# 4. 验证
cur.execute('SELECT COUNT(*) FROM yp_us_products WHERE price_num IS NOT NULL')
cnt = cur.fetchone()[0]
print(f'price_num filled: {cnt} rows')

cur.execute('SELECT MIN(price_num), MAX(price_num) FROM yp_us_products WHERE price_num IS NOT NULL')
r = cur.fetchone()
print(f'price range: ${r[0]} - ${r[1]}')

conn.close()
print('Done!')
