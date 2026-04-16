"""测试商户作战室路由的各个查询耗时"""
import mysql.connector, time

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

# 取一个有数据的商户 ID
rows, _ = t('随机取一个有商品的商户', 'SELECT merchant_id, COUNT(*) cnt FROM yp_products GROUP BY merchant_id ORDER BY cnt DESC LIMIT 1')
mid = rows[0]['merchant_id'] if rows else '1'
print(f'测试商户 ID: {mid}')
print()

t('商户基本信息', 'SELECT merchant_id, merchant_name, avg_payout FROM yp_merchants WHERE merchant_id=%s LIMIT 1', (mid,))
t('商品统计 MAX/MIN/COUNT', '''SELECT COUNT(*) as total, SUM(CASE WHEN tracking_url IS NOT NULL AND tracking_url!='' THEN 1 ELSE 0 END) as with_link
   FROM yp_products p WHERE p.merchant_id=%s''', (mid,))
t('商品列表 LIMIT50', '''SELECT p.asin, p.product_name, p.price, d.rating, d.main_image_url
   FROM yp_products p LEFT JOIN amazon_product_details d ON p.asin=d.asin
   WHERE p.merchant_id=%s AND p.tracking_url IS NOT NULL AND p.tracking_url!=''
   ORDER BY p.id DESC LIMIT 50''', (mid,))
t('关键词', 'SELECT keyword, keyword_source FROM ads_merchant_keywords WHERE merchant_id=%s ORDER BY keyword_source', (str(mid),))
t('ads_plans 计数', 'SELECT COUNT(*) cnt FROM ads_plans ap JOIN yp_products p ON ap.asin=p.asin WHERE p.merchant_id=%s', (mid,))

print()
print('=== 商户列表 qs_dashboard 路由核心 API ===')
t('qs_dashboard 数据 API', '''SELECT ap.asin, ap.product_name, ap.plan_status, ap.avg_quality_score
   FROM ads_plans ap ORDER BY ap.id DESC LIMIT 50''')

print()
print('=== competitor_ads 路由核心 API ===')
t('semrush_competitor_data 查询', '''SELECT merchant_id, domain, monthly_visits, organic_traffic
   FROM semrush_competitor_data ORDER BY scraped_at DESC LIMIT 20''')

conn.close()
print()
print('测试完成')
