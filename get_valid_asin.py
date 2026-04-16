import mysql.connector

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor()
cur.execute("""
    SELECT asin, amazon_url, product_name 
    FROM yp_products 
    WHERE amazon_url IS NOT NULL AND amazon_url != '' 
    LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
