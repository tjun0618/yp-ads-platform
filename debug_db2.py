import sys
sys.path.insert(0, 'C:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu')
import mysql.connector

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor(dictionary=True)

# 测试 api_merchant_products 的数据源
# 找 /api/merchant_products 后端路由代码中使用哪个表
# 先直接测试几个有数据的商户
test_ids = [363047, 369117, 362400]
for mid in test_ids:
    cur.execute("SELECT COUNT(*) cnt FROM yp_us_products WHERE yp_merchant_id=%s", (mid,))
    cnt = cur.fetchone()['cnt']
    cur.execute("SELECT COUNT(*) cnt FROM yp_products WHERE merchant_id=%s", (str(mid),))
    cnt2 = cur.fetchone()['cnt'] if 'yp_products' else 0
    print(f"merchant_id {mid}: yp_us_products={cnt}, yp_products={cnt2}")

# 检查 approved_merchants.json 里的商户在 yp_us_products 中有没有数据
import json
from pathlib import Path
approved_file = Path('C:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu/output/approved_merchants.json')
if approved_file.exists():
    merchants = json.loads(approved_file.read_text(encoding='utf-8-sig'))
    print(f'\nTotal approved merchants in JSON: {len(merchants)}')
    # 取前10个检查
    print('First 5 merchant IDs:', [m['merchant_id'] for m in merchants[:5]])
    
    # 检查这些ID在 yp_us_products 里有多少
    ids = [m['merchant_id'] for m in merchants[:20]]
    placeholders = ','.join(['%s']*len(ids))
    cur.execute(f"SELECT yp_merchant_id, COUNT(*) cnt FROM yp_us_products WHERE yp_merchant_id IN ({placeholders}) GROUP BY yp_merchant_id", ids)
    in_db = {r['yp_merchant_id']: r['cnt'] for r in cur.fetchall()}
    print(f'Of first 20 JSON merchants, {len(in_db)} have data in yp_us_products:')
    for mid in ids[:20]:
        print(f'  {mid}: {in_db.get(mid, 0)} products')

conn.close()
