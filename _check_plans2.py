import mysql.connector, json

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)
asin = 'B0FX34NS5K'

# 1. 看看 ads_plans 表里有没有 plan_id 或 raw_json 字段
cur.execute("DESCRIBE ads_plans")
cols = cur.fetchall()
print('=== ads_plans columns ===')
for c in cols:
    print(f"  {c['Field']} | {c['Type']} | {c.get('Key','')}")

# 2. 查 ads_plans 这行完整数据
cur.execute("SELECT * FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
plan = cur.fetchone()
print(f'\n=== ads_plans row for {asin} ===')
if plan:
    for k, v in plan.items():
        val = str(v)
        print(f'  {k}: {val[:200]}')

# 3. 看 ads_campaigns 表结构
cur.execute("DESCRIBE ads_campaigns")
cols = cur.fetchall()
print('\n=== ads_campaigns columns ===')
for c in cols:
    print(f"  {c['Field']} | {c['Type']} | {c.get('Key','')}")

# 4. ads_campaigns 总量 + 查有哪些 asin
cur.execute("SELECT COUNT(*) as cnt FROM ads_campaigns")
r = cur.fetchone()
print(f'\nads_campaigns total: {r["cnt"]}')

cur.execute("SELECT DISTINCT asin FROM ads_campaigns LIMIT 10")
rows = cur.fetchall()
print(f'Sample asin in ads_campaigns: {[r["asin"] for r in rows]}')

# 5. ads_ad_groups 表结构
cur.execute("DESCRIBE ads_ad_groups")
cols = cur.fetchall()
print('\n=== ads_ad_groups columns ===')
for c in cols:
    print(f"  {c['Field']} | {c['Type']} | {c.get('Key','')}")

# 6. ads_ads 表结构
cur.execute("DESCRIBE ads_ads")
cols = cur.fetchall()
print('\n=== ads_ads columns ===')
for c in cols:
    print(f"  {c['Field']} | {c['Type']} | {c.get('Key','')}")

conn.close()
