"""精确找出各接口瓶颈"""
import mysql.connector, time, os

conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)

def t(label, sql, args=None):
    t0 = time.perf_counter()
    c = conn.cursor(dictionary=True)
    c.execute(sql, args or ())
    rows = c.fetchall()
    c.close()
    ms = (time.perf_counter()-t0)*1000
    print(f'[{ms:8.1f}ms] {label}  ({len(rows)} rows)')
    return rows, ms

print('=== 各路由具体慢查询定位 ===')

# 1. 首页路由的 COUNT 操作（每60s缓存一次）
_, ms1 = t('ads_plans COUNT WHERE completed', "SELECT COUNT(*) FROM ads_plans WHERE plan_status='completed'")

# 2. yp_products 旧表查询 + SQL_CALC_FOUND_ROWS
_, ms2 = t('/api/products 核心查询（旧yp_products表）', """
SELECT p.id, p.asin, p.merchant_name, p.merchant_id,
       p.product_name, p.price as yp_price, p.commission,
       d.rating, d.review_count, d.main_image_url, d.brand
FROM yp_products p 
LEFT JOIN amazon_product_details d ON p.asin=d.asin
WHERE p.tracking_url IS NOT NULL AND p.tracking_url != ''
ORDER BY p.id DESC LIMIT 50 OFFSET 0
""")

# 3. yp_products 的 COUNT
_, ms3 = t('yp_products COUNT(*)', "SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")

# 4. JSON 文件大小
from pathlib import Path
approved_file = Path(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\output\approved_merchants.json')
if approved_file.exists():
    size_mb = approved_file.stat().st_size / 1024 / 1024
    t0 = time.perf_counter()
    import json
    data = json.loads(approved_file.read_text(encoding='utf-8-sig'))
    parse_ms = (time.perf_counter()-t0)*1000
    print(f'[{parse_ms:8.1f}ms] approved_merchants.json 解析  (size={size_mb:.2f}MB, {len(data)} records)')
else:
    print('  approved_merchants.json 不存在')

# 5. QS dashboard 路由实际做了什么
# 需要查 ads_manager.py 确认
print()
print('=== qs_dashboard 和 competitor_ads 路由诊断 ===')
# 先测每个路由2秒内做的查询
_, ms5 = t('ads_plans JOIN ads_campaigns GROUP BY', """
SELECT p.asin, p.merchant_name, p.product_name, p.plan_status,
       p.avg_quality_score,
       COUNT(c.id) as campaign_count,
       COUNT(ag.id) as ad_group_count
FROM ads_plans p
LEFT JOIN ads_campaigns c ON c.asin = p.asin
LEFT JOIN ads_ad_groups ag ON ag.asin = p.asin
GROUP BY p.id
ORDER BY p.id DESC LIMIT 20
""")

_, ms6 = t('semrush_competitor_data 查询', """
SELECT merchant_id, merchant_name, domain, 
       traffic, organic_keywords, paid_keywords,
       scraped_at
FROM semrush_competitor_data
ORDER BY scraped_at DESC LIMIT 20
""")

conn.close()

print()
print(f'=== 汇总 ===')
print(f'ads_plans COUNT(*): {ms1:.0f}ms  {"← 慢!" if ms1>200 else "OK"}')
print(f'yp_products 分页查询: {ms2:.0f}ms  {"← 慢!" if ms2>200 else "OK"}')
print(f'yp_products COUNT(*): {ms3:.0f}ms  {"← 慢!" if ms3>200 else "OK"}')
