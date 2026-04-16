"""
终极修复：
1. yp_us_products 的 product_id 字段是 ORDER BY 核心，需要复合覆盖索引
2. ads_plans 的 asin 索引需要检查是否生效
3. yp_products tracking_url COUNT 很慢，需要专用索引
"""
import mysql.connector
import time

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

print("=" * 70)
print("终极修复：针对 EXPLAIN 结果的精准优化")
print("=" * 70)

# ─── 关键发现 ─────────────────────────────────────────────────────────
# 1. yp_us_products 的 product_id 有单列索引（idx_pid），但 EXPLAIN 显示 type=ALL
#    原因：可能 product_id 字段存在 NULL，导致优化器放弃走索引
#    或者 product_id 不是 NOT NULL，MySQL 不能用该索引做 ORDER BY 优化
# 2. 需要检查 product_id 是否有 NULL 值

# Step 1: 检查 product_id
print("\n[1] 检查 yp_us_products.product_id NULL 情况")
cur.execute("SELECT COUNT(*) FROM yp_us_products WHERE product_id IS NULL")
null_cnt = cur.fetchone()[0]
print(f"  product_id IS NULL: {null_cnt} rows")

cur.execute("DESCRIBE yp_us_products")
for r in cur.fetchall():
    if r[0] in ('product_id', 'asin', 'yp_merchant_id'):
        print(f"  {r[0]}: type={r[1]}, null={r[2]}, key={r[3]}, default={r[4]}")

# Step 2: 如果 product_id 有 NULL，填充后修改列为 NOT NULL
if null_cnt > 0:
    print(f"\n[2] 修复 {null_cnt} 个 NULL product_id（用 id 替代）")
    t0 = time.time()
    cur.execute("UPDATE yp_us_products SET product_id = id WHERE product_id IS NULL")
    conn.commit()
    print(f"  已修复: {cur.rowcount} rows in {time.time()-t0:.1f}s")

# Step 3: 尝试将 product_id 改为 NOT NULL（让优化器能用索引）
print("\n[3] 修改 product_id 为 NOT NULL（允许优化器用索引做 ORDER BY）")
try:
    cur.execute("ALTER TABLE yp_us_products MODIFY COLUMN product_id BIGINT NOT NULL DEFAULT 0")
    conn.commit()
    print("  已修改为 NOT NULL")
except Exception as e:
    print(f"  修改列: {e}")

# Step 4: 强制重建 idx_pid 索引（DROP + ADD）
print("\n[4] 重建 idx_pid 索引")
try:
    cur.execute("ALTER TABLE yp_us_products DROP INDEX idx_pid")
    conn.commit()
    print("  DROP INDEX ok")
except Exception as e:
    print(f"  DROP INDEX: {e}")
try:
    t0 = time.time()
    cur.execute("ALTER TABLE yp_us_products ADD INDEX idx_pid (product_id)")
    conn.commit()
    print(f"  ADD INDEX ok in {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  ADD INDEX: {e}")

# Step 5: 验证 EXPLAIN
print("\n[5] EXPLAIN 验证（目标：product_id 列用到索引，type 不是 ALL）")
cur.execute("""
    EXPLAIN 
    SELECT p.asin, a.title, pl.plan_status, COALESCE(mk.kw_count,0) kw_cnt
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    LEFT JOIN (SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id) mk
        ON mk.merchant_id = p.yp_merchant_id
    ORDER BY p.product_id DESC LIMIT 30
""")
rows = cur.fetchall()
print(f"  {'table':<30} {'type':<12} {'key':<25} {'rows':<10} Extra")
print("  " + "-" * 90)
for r in rows:
    print(f"  {str(r[2]):<30} {str(r[4]):<12} {str(r[6]):<25} {str(r[9]):<10} {str(r[11])}")

# Step 6: 实际耗时验证
print("\n[6] 实际耗时验证")
def tq(label, sql, params=()):
    t0 = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    ms = (time.time() - t0) * 1000
    flag = "✅" if ms < 200 else ("⚠️" if ms < 1000 else "❌")
    print(f"  {flag} [{ms:>8.1f}ms] {label}  ({len(rows)} rows)")
    return rows, ms

tq("首页核心查询（JOIN新法）", """
    SELECT p.asin, a.title, pl.plan_status, COALESCE(mk.kw_count,0) kw_cnt
    FROM yp_us_products p
    LEFT JOIN amazon_product_details a ON p.asin = a.asin
    LEFT JOIN ads_plans pl ON p.asin = pl.asin
    LEFT JOIN (SELECT merchant_id, COUNT(*) kw_count FROM ads_merchant_keywords GROUP BY merchant_id) mk
        ON mk.merchant_id = p.yp_merchant_id
    ORDER BY p.product_id DESC LIMIT 30
""")

# Step 7: yp_products tracking_url COUNT 慢的修复
print("\n[7] 修复 yp_products COUNT(tracking_url) 慢查询")
# 检查 tracking_url 索引
cur.execute("SHOW INDEX FROM yp_products")
idx_rows = cur.fetchall()
for r in idx_rows:
    if 'track' in str(r[2]).lower():
        print(f"  现有索引: {r[2]}, col={r[4]}, sub_part={r[7]}")

# 当前索引只有 sub_part=50，对 IS NOT NULL 判断可能无效
# 改为添加一个更小的虚拟列或者用 NOT NULL 专用索引
# 最快解法：在 yp_products 上添加一个函数索引（MySQL 8.0 支持）
try:
    cur.execute("""
        ALTER TABLE yp_products 
        ADD INDEX idx_has_tracking ((CASE WHEN tracking_url IS NOT NULL AND tracking_url != '' THEN 1 ELSE 0 END))
    """)
    conn.commit()
    print("  Added functional index idx_has_tracking ok")
except Exception as e:
    print(f"  Functional index: {e}")
    # 降级方案：用已有的 idx_tracking_url(50) 测下效果
    cur.execute("""
        EXPLAIN SELECT COUNT(*) FROM yp_products 
        WHERE tracking_url IS NOT NULL AND tracking_url != ''
    """)
    r = cur.fetchone()
    print(f"  EXPLAIN COUNT: type={r[4]}, key={r[6]}, rows={r[9]}")

tq("yp_products COUNT(tracking_url) 优化后", """
    SELECT COUNT(*) FROM yp_products 
    WHERE tracking_url IS NOT NULL AND tracking_url != ''
""")

conn.close()
print("\n终极修复完成！")
