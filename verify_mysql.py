import mysql.connector
conn = mysql.connector.connect(
    host='localhost', port=3306,
    user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM yp_products')
total = cur.fetchone()[0]
print(f'[OK] Total records: {total}')

cur.execute('SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ""')
with_link = cur.fetchone()[0]
print(f'[OK] With tracking_url: {with_link} ({with_link*100//total}%)')

cur.execute('SELECT COUNT(DISTINCT merchant_id) FROM yp_products')
print(f'[OK] Distinct merchants: {cur.fetchone()[0]}')

cur.execute('SELECT COUNT(DISTINCT asin) FROM yp_products')
print(f'[OK] Distinct ASINs: {cur.fetchone()[0]}')

print('\n[Top 10 Categories]')
cur.execute('SELECT IFNULL(category,"(none)"), COUNT(*) cnt FROM yp_products GROUP BY category ORDER BY cnt DESC LIMIT 10')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print('\n[Sample Rows]')
cur.execute('SELECT merchant_name, asin, price, commission, LEFT(tracking_url,70) FROM yp_products WHERE tracking_url IS NOT NULL LIMIT 4')
for row in cur.fetchall():
    print(f'  {row[0]} | {row[1]} | ${row[2]} | {row[3]} | {row[4]}')

cur.execute('SELECT ROUND((data_length+index_length)/1024/1024,1) FROM information_schema.tables WHERE table_schema="affiliate_marketing" AND table_name="yp_products"')
print(f'\n[OK] Table size: {cur.fetchone()[0]} MB')

cur.close()
conn.close()
