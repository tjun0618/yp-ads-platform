"""快速测试：取 10 条 tracking_url，验证解析逻辑"""
import mysql.connector
import requests
import re

DB_CONFIG = dict(host='localhost', port=3306, user='root', password='admin',
                 database='affiliate_marketing', charset='utf8mb4')

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})

conn = mysql.connector.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("""
    SELECT id, asin, product_name, tracking_url
    FROM yp_products
    WHERE tracking_url IS NOT NULL AND tracking_url != ''
    LIMIT 10
""")
rows = cur.fetchall()
cur.close()
conn.close()

success = 0
fail = 0

for row_id, asin, name, tracking_url in rows:
    try:
        resp = SESSION.get(tracking_url, allow_redirects=False, timeout=12)
        refresh = resp.headers.get("refresh", "")
        m = re.search(r'url=(.+)', refresh, re.IGNORECASE)
        amazon_url = m.group(1).strip() if m else None

        if amazon_url and "amazon.com" in amazon_url:
            success += 1
            print(f"✅ ASIN={asin}")
            print(f"   tracking: {tracking_url}")
            print(f"   amazon  : {amazon_url[:120]}")
        else:
            fail += 1
            print(f"❌ ASIN={asin} | refresh={repr(refresh[:100])}")
    except Exception as e:
        fail += 1
        print(f"❌ ASIN={asin} | 错误: {e}")
    print()

print(f"=== 结果: 成功 {success}/10，失败 {fail}/10 ===")
