# -*- coding: utf-8 -*-
import pymysql, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = pymysql.connect(host='localhost', port=3306, user='root', password='admin',
                       database='affiliate_marketing', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT id, merchant_id, merchant_name, avg_payout, payout_unit, cookie_days, website, country, country_code, status, online_status FROM yp_merchants ORDER BY id LIMIT 20")
rows = cur.fetchall()

print(f"{'#':<4} {'merchant_id':<12} {'merchant_name':<30} {'payout':<10} {'cookie':<8} {'country':<12} {'status':<12} {'online':<10} {'website'}")
print("-" * 140)
for i, r in enumerate(rows):
    name = (r['merchant_name'] or '')[:28]
    web = (r['website'] or '')[:40]
    print(f"{i+1:<4} {r['merchant_id']:<12} {name:<30} {r['avg_payout']}{r['payout_unit']:<7} {r['cookie_days']}d      {r['country'] or '':<12} {r['status'] or '':<12} {r['online_status'] or '':<10} {web}")

cur.close()
conn.close()
