"""
修复 ads_* 表的 collation，统一为 utf8mb4_unicode_ci
使其与 yp_products / amazon_product_details 一致，避免 JOIN 报 collation 冲突
"""
import mysql.connector

conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='admin',
                               database='affiliate_marketing', charset='utf8mb4')
cur = conn.cursor()

# SET sql_mode 先
cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'")

fixes = [
    # (table, column, type_def)
    ("ads_plans",       "asin",        "VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"),
    ("ads_plans",       "merchant_id", "VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL"),
    ("ads_campaigns",   "asin",        "VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"),
    ("ads_campaigns",   "merchant_id", "VARCHAR(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL"),
    ("ads_ad_groups",   "asin",        "VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"),
    ("ads_ads",         "asin",        "VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL"),
]

for table, col, typedef in fixes:
    try:
        sql = f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` {typedef}"
        cur.execute(sql)
        conn.commit()
        print(f"OK  {table}.{col} -> utf8mb4_unicode_ci")
    except Exception as e:
        print(f"ERR {table}.{col}: {e}")

# 验证
cur.execute("""
SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA='affiliate_marketing'
  AND COLUMN_NAME IN ('asin','merchant_id')
  AND TABLE_NAME IN ('yp_products','amazon_product_details',
                     'ads_plans','ads_campaigns','ads_ad_groups','ads_ads')
ORDER BY TABLE_NAME, COLUMN_NAME
""")
print("\n=== 验证排序规则 ===")
for r in cur.fetchall():
    print(f"  {r[0]}.{r[1]}: {r[2]}")

conn.close()
print("\n修复完成！")
