import mysql.connector
conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor(dictionary=True)

cur.execute("SELECT COUNT(*) cnt FROM yp_products WHERE category IS NOT NULL AND category != '' AND category != 'None'")
print('非空category条数:', cur.fetchone()['cnt'])

cur.execute("SELECT * FROM yp_categories LIMIT 10")
cats = cur.fetchall()
print()
print('=== yp_categories sample ===')
for c in cats:
    print(c)

cur.execute("SELECT COUNT(*) cnt FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")
print()
print('有 tracking_url 的商品数:', cur.fetchone()['cnt'])

cur.execute("SELECT COUNT(DISTINCT p.asin) cnt FROM yp_products p INNER JOIN amazon_product_details d ON p.asin=d.asin")
print('有Amazon详情的商品数:', cur.fetchone()['cnt'])

cur.execute("SELECT merchant_name, asin, product_name, category, price, commission, tracking_url FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != '' LIMIT 5")
print()
print('=== yp_products sample (has tracking_url) ===')
for r in cur.fetchall():
    print(' ', r['merchant_name'], '|', r['asin'], '|', r['category'], '|', r['price'], '|', r['commission'])

# 看下载了产品的商户，从download_state看，有tracking_url的不多，看看按merchant_id统计
cur.execute("SELECT merchant_id, merchant_name, COUNT(*) total, SUM(CASE WHEN tracking_url IS NOT NULL AND tracking_url!='' THEN 1 ELSE 0 END) has_track FROM yp_products GROUP BY merchant_id, merchant_name ORDER BY total DESC LIMIT 20")
print()
print('=== per merchant product counts ===')
for r in cur.fetchall():
    print(' ', r['merchant_id'], r['merchant_name'], 'total:', r['total'], 'has_track:', r['has_track'])

conn.close()
