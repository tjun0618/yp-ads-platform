import mysql.connector, json
conn = mysql.connector.connect(host='localhost',port=3306,user='root',password='admin',database='affiliate_marketing')
cur = conn.cursor()
cur.execute('DESCRIBE semrush_competitor_data')
print('SEMRUSH FIELDS:', [r[0] for r in cur.fetchall()])
cur.execute("SELECT asin, top_reviews FROM amazon_product_details WHERE top_reviews IS NOT NULL LIMIT 1")
row = cur.fetchone()
if row:
    try:
        reviews = json.loads(row[1])
        print('REVIEW SAMPLE:', json.dumps(reviews[0] if reviews else {}, ensure_ascii=False)[:500])
    except: print('review parse err')
cur.execute("SELECT merchant_id, merchant_name, keyword, keyword_source FROM ads_merchant_keywords LIMIT 5")
for r in cur.fetchall(): print('KW:', r)
cur.execute("SELECT merchant_name, domain, monthly_visits, organic_traffic, paid_traffic FROM semrush_competitor_data LIMIT 2")
for r in cur.fetchall(): print('SEMRUSH:', r)
conn.close()
