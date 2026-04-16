import mysql.connector
conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',
                               database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()
cur.execute("""
SELECT TABLE_NAME, COLUMN_NAME, COLLATION_NAME, CHARACTER_SET_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA='affiliate_marketing'
  AND COLUMN_NAME IN ('asin','merchant_id')
  AND TABLE_NAME IN ('yp_products','yp_merchants','amazon_product_details',
                     'ads_plans','ads_campaigns','ads_ad_groups','ads_ads')
ORDER BY TABLE_NAME, COLUMN_NAME
""")
for r in cur.fetchall():
    print(r)
conn.close()
