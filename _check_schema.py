import mysql.connector

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

# 检查 ads_ad_groups 是否有 asin, campaign_name, headline, description 字段
cur.execute("DESCRIBE ads_ad_groups")
cols = cur.fetchall()
print('ads_ad_groups columns:')
for c in cols:
    print(f"  {c['Field']}")

# 检查 ads_campaigns 是否有缺失字段
cur.execute("DESCRIBE ads_campaigns")
cols = cur.fetchall()
print('\nads_campaigns columns:')
for c in cols:
    print(f"  {c['Field']}")

conn.close()
