import mysql.connector, time

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

# 方案A: 先查 US merchant_name 列表 (子查询 IN)
t0 = time.time()
cur2 = conn.cursor(dictionary=True)
cur2.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.merchant_name
    FROM yp_products p
    WHERE p.merchant_name IN (
        SELECT merchant_name FROM yp_merchants WHERE country LIKE 'US -%'
    )
    GROUP BY p.asin
    ORDER BY p.id DESC
    LIMIT 30 OFFSET 0
""")
rows = cur2.fetchall()
print(f"方案A (IN子查询, ORDER BY id DESC): {len(rows)} 条 ({time.time()-t0:.2f}s)")

# 方案B: 先获取 US merchant_name list, Python 侧过滤
t0 = time.time()
cur2.execute("SELECT merchant_name FROM yp_merchants WHERE country LIKE 'US -%'")
us_names = set(r['merchant_name'] for r in cur2.fetchall())
print(f"方案B: US merchant 数量: {len(us_names)}")

cur2.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.merchant_name
    FROM yp_products p
    WHERE p.merchant_name IN ({})
    GROUP BY p.asin
    ORDER BY CAST(p.commission AS DECIMAL(10,4)) DESC
    LIMIT 30 OFFSET 0
""".format(','.join(['%s']*min(len(us_names),1000))), list(us_names)[:1000])
rows = cur2.fetchall()
print(f"方案B (先捞名单): {len(rows)} 条 ({time.time()-t0:.2f}s)")

# 方案C: 加物化视图（建一张 US products 视图）- 看是否可行
t0 = time.time()
try:
    cur.execute("DROP TABLE IF EXISTS _us_products_cache")
    cur.execute("""
        CREATE TABLE _us_products_cache AS
        SELECT p.* FROM yp_products p
        JOIN yp_merchants m ON p.merchant_name = m.merchant_name
        WHERE m.country LIKE 'US -%'
    """)
    conn.commit()
    cur2.execute("SELECT COUNT(*) as c FROM _us_products_cache")
    r = cur2.fetchone()
    print(f"方案C: 建缓存表 {r['c']} 条 ({time.time()-t0:.2f}s)")
    
    # 用缓存表测速
    t0 = time.time()
    cur2.execute("SELECT asin, product_name, price, commission FROM _us_products_cache ORDER BY CAST(commission AS DECIMAL(10,4)) DESC LIMIT 30")
    rows = cur2.fetchall()
    print(f"  缓存表查询: {len(rows)} 条 ({time.time()-t0:.2f}s)")
    if rows:
        print(f"  第一条: {rows[0]}")
except Exception as e:
    print(f"方案C 失败: {e}")

conn.close()
