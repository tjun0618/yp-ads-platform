"""
优化查询性能：
1. 给 yp_merchants 加 country 索引（如果没有）
2. 给 amazon_product_details 加 asin 索引（如果没有）
3. 验证查询速度
"""
import mysql.connector, time

conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                               database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

print("=== 添加优化索引 ===")

# 1. yp_merchants 的 country 索引
try:
    cur.execute("ALTER TABLE yp_merchants ADD INDEX idx_country (country)")
    conn.commit()
    print("OK: yp_merchants.country 索引")
except Exception as e:
    print(f"已存在或跳过: {e}")

# 2. amazon_product_details 的 asin 索引
try:
    cur.execute("SHOW INDEX FROM amazon_product_details")
    existing = [r[2] for r in cur.fetchall()]
    if 'idx_asin' not in existing and 'PRIMARY' not in existing:
        cur.execute("ALTER TABLE amazon_product_details ADD INDEX idx_asin (asin)")
        conn.commit()
        print("OK: amazon_product_details.asin 索引")
    else:
        print(f"amazon_product_details 已有索引: {existing}")
except Exception as e:
    print(f"amazon_product_details 索引: {e}")

print("\n=== 测试优化后的查询速度 ===\n")

# 使用子查询方式（先获取 US merchant_id 列表）
t0 = time.time()
cur.execute("""
    SELECT DISTINCT p.category FROM yp_products p
    WHERE p.merchant_id IN (SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%')
      AND p.category IS NOT NULL AND p.category != ''
    ORDER BY p.category LIMIT 100
""")
r = cur.fetchall()
print(f"类别查询(子查询): {time.time()-t0:.2f}s  ({len(r)} 条)")
if r:
    print(f"  示例: {r[:3]}")

t0 = time.time()
cur.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt FROM yp_products p
    WHERE p.merchant_id IN (SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%')
""")
r = cur.fetchone()
print(f"US商品总数(子查询): {time.time()-t0:.2f}s  ({r[0]} 条)")

t0 = time.time()
cur.execute("""
    SELECT COUNT(DISTINCT p.asin) as cnt
    FROM yp_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    WHERE p.merchant_id IN (SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%')
""")
r = cur.fetchone()
print(f"主列表COUNT(子查询): {time.time()-t0:.2f}s  ({r[0]} 条)")

t0 = time.time()
cur.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.category,
           p.merchant_id, p.merchant_name,
           a.title AS amz_title, a.rating, a.review_count, a.main_image_url,
           pl.plan_status, pl.id AS plan_id
    FROM yp_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    WHERE p.merchant_id IN (SELECT merchant_id FROM yp_merchants WHERE country LIKE 'US%')
    GROUP BY p.asin
    ORDER BY p.commission DESC
    LIMIT 30 OFFSET 0
""")
rows = cur.fetchall()
print(f"主列表LIMIT30(子查询): {time.time()-t0:.2f}s  ({len(rows)} 条)")
if rows:
    print(f"  第一条: {rows[0][0]} | {str(rows[0][1])[:40]}")

conn.close()
print("\n优化完成！")
