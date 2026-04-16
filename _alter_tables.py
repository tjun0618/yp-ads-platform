import mysql.connector

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

# 给 ads_ad_groups 补 asin 字段（润色功能需要）
try:
    cur.execute("ALTER TABLE ads_ad_groups ADD COLUMN asin VARCHAR(20) DEFAULT NULL AFTER campaign_id")
    conn.commit()
    print("Added asin to ads_ad_groups: OK")
except Exception as e:
    print(f"asin already exists or error: {e}")

# 给 ads_ad_groups 加索引
try:
    cur.execute("ALTER TABLE ads_ad_groups ADD INDEX idx_asin (asin)")
    conn.commit()
    print("Added index on asin: OK")
except Exception as e:
    print(f"Index already exists: {e}")

conn.close()
print("Done.")
