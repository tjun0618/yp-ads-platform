"""
检查 yp_products.amazon_url 字段存的是什么 URL
"""
import mysql.connector

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor(dictionary=True)

# 取一些样本，看 URL 格式
cur.execute("""
    SELECT asin, amazon_url, tracking_url
    FROM yp_products
    WHERE amazon_url IS NOT NULL AND amazon_url != ''
    LIMIT 10
""")
rows = cur.fetchall()

print("===== yp_products 中的 amazon_url 样本 =====\n")
for r in rows:
    print(f"ASIN         : {r['asin']}")
    print(f"amazon_url   : {(r['amazon_url'] or '')[:200]}")
    print(f"tracking_url : {(r['tracking_url'] or '')[:150]}")
    print()

# 统计 URL 类型
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN amazon_url LIKE 'https://www.amazon.com/dp/%' THEN 1 ELSE 0 END) as direct_dp,
        SUM(CASE WHEN amazon_url LIKE '%yeahpromos%' THEN 1 ELSE 0 END) as yp_link,
        SUM(CASE WHEN amazon_url LIKE '%tag=%' THEN 1 ELSE 0 END) as has_tag,
        SUM(CASE WHEN amazon_url LIKE '%maas_banner%' THEN 1 ELSE 0 END) as has_maas
    FROM yp_products
    WHERE amazon_url IS NOT NULL AND amazon_url != ''
""")
stats = cur.fetchone()
print("===== URL 类型统计 =====")
print(f"总数          : {stats['total']:,}")
print(f"直接 /dp/ URL : {stats['direct_dp']:,}")
print(f"含 yeahpromos : {stats['yp_link']:,}")
print(f"含 tag=       : {stats['has_tag']:,}")
print(f"含 maas_banner: {stats['has_maas']:,}")

db.close()
