import mysql.connector, json
conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing',charset='utf8mb4')
cur = conn.cursor()

# 1. ads_merchant_keywords 现状
cur.execute('SELECT COUNT(DISTINCT merchant_id), COUNT(*) FROM ads_merchant_keywords')
r = cur.fetchone()
print(f'ads_merchant_keywords: {r[0]} 商户 / {r[1]} 条关键词')

# 2. 有亚马逊详情的US商品样本
cur.execute("""
    SELECT p.asin, p.product_name, p.price, p.commission, p.merchant_id, m.merchant_name,
           a.title, a.rating, a.review_count, a.brand
    FROM yp_products p
    JOIN yp_merchants m ON p.merchant_id = m.merchant_id
    JOIN amazon_product_details a ON p.asin = a.asin
    WHERE m.country LIKE 'US%'
    LIMIT 5
""")
rows = cur.fetchall()
print()
print(f'=== 有亚马逊详情的US商品样本({len(rows)}条)===')
for r in rows:
    print(f'  ASIN:{r[0]} | {str(r[6])[:40]} | ${r[2]} | 佣金:{r[3]}% | {r[8]}条评价 | merchant:{r[5]}')

# 3. 有关键词的商户
cur.execute('SELECT merchant_id, merchant_name, COUNT(*) as kw_cnt FROM ads_merchant_keywords GROUP BY merchant_id, merchant_name')
rows2 = cur.fetchall()
print()
print(f'=== 有关键词的商户({len(rows2)}个) ===')
for r in rows2:
    print(f'  [{r[0]}] {r[1]} ({r[2]}个关键词)')

# 4. 现有广告相关表
cur.execute('SHOW TABLES')
all_tables = [r[0] for r in cur.fetchall()]
ads_tables = [t for t in all_tables if 'ads' in t.lower() or 'campaign' in t.lower() or 'google' in t.lower()]
print()
print(f'=== 广告相关表 ===')
for t in ads_tables:
    print(f'  {t}')

conn.close()
