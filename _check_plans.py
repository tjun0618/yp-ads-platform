import mysql.connector, json

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)

# 查最近已完成的方案
cur.execute("SELECT asin, plan_status, campaign_count, ad_group_count, ad_count FROM ads_plans WHERE plan_status='completed' ORDER BY generated_at DESC LIMIT 5")
plans = cur.fetchall()
print('=== ads_plans (last 5 completed) ===')
for p in plans:
    print(p)

if not plans:
    # 看看是否有其他状态
    cur.execute("SELECT asin, plan_status FROM ads_plans ORDER BY generated_at DESC LIMIT 10")
    all_plans = cur.fetchall()
    print('All plans:', all_plans)
    conn.close()
    exit()

asin = plans[0]['asin']
print(f'\n=== Testing ASIN: {asin} ===')

# 查 ads_campaigns
cur.execute('SELECT id, campaign_name FROM ads_campaigns WHERE asin=%s', (asin,))
camps = cur.fetchall()
print(f'Campaigns count: {len(camps)}')
for c in camps:
    print(' ', c)
    cid = c['id']
    cur.execute('SELECT id, ad_group_name FROM ads_ad_groups WHERE campaign_id=%s', (cid,))
    groups = cur.fetchall()
    print(f'  Ad Groups: {len(groups)}')
    for g in groups:
        print('   ', g)
        cur.execute('SELECT id, variant, headlines FROM ads_ads WHERE ad_group_id=%s', (g['id'],))
        ads = cur.fetchall()
        print(f'    Ads: {len(ads)}')
        if ads:
            hl = json.loads(ads[0]['headlines'] or '[]')
            print(f'    first ad headlines count: {len(hl)}')

# 再测一下 HTTP 响应
import requests
r = requests.get(f'http://localhost:5055/plans/{asin}', timeout=15)
print(f'\n=== HTTP GET /plans/{asin} ===')
print(f'Status: {r.status_code}')
print(f'Content length: {len(r.text)}')
# 检查关键内容
print(f'Has "campaign_html": {"campaign_html" in r.text}')
print(f'Has "No campaigns": {"No campaigns" in r.text}')
print(f'Has "campaign-card": {"campaign-card" in r.text}')
print(f'Has "ad-group": {"ad-group" in r.text}')
# 打印 body 内容的前2000字符
print('\n--- HTML snippet (first 3000 chars) ---')
print(r.text[:3000])

conn.close()
