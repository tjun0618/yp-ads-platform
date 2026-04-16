import mysql.connector
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor(dictionary=True)
cur.execute("SELECT * FROM amazon_product_details WHERE asin='B09G1Z83GM'")
row = cur.fetchone()
if row:
    for k, v in row.items():
        if v is None:
            print(f"  {k}: NULL")
        elif k in ('bullet_points', 'product_details', 'keywords', 'top_reviews'):
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    print(f"  {k}: [{len(parsed)} items]")
                    for i, item in enumerate(parsed[:2]):
                        print(f"    [{i}]: {str(item)[:80]}")
                elif isinstance(parsed, dict):
                    print(f"  {k}: {{{len(parsed)} fields}}")
                    for i, (dk, dv) in enumerate(list(parsed.items())[:3]):
                        print(f"    {dk}: {str(dv)[:60]}")
            except:
                print(f"  {k}: {str(v)[:100]}")
        elif k == 'description':
            print(f"  {k}: {str(v)[:150]}...")
        else:
            print(f"  {k}: {str(v)[:120]}")
else:
    print("No record found")
conn.close()
