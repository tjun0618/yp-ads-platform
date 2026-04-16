"""
从 amazon_product_details 取一条完整有效的数据，格式化输出
"""
import mysql.connector, json

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor(dictionary=True)

# 总体统计
cur.execute("SELECT COUNT(*) as total FROM amazon_product_details")
total = cur.fetchone()['total']

cur.execute("SELECT COUNT(*) as ok FROM amazon_product_details WHERE title IS NOT NULL AND title != '' AND title != '__404__'")
ok = cur.fetchone()['ok']

cur.execute("SELECT COUNT(*) as f404 FROM amazon_product_details WHERE title = '__404__'")
f404 = cur.fetchone()['f404']

print(f"===== amazon_product_details 统计 =====")
print(f"总记录数 : {total}")
print(f"有效数据 : {ok}")
print(f"404下架  : {f404}")
print(f"空/其他  : {total - ok - f404}")
print()

# 取最新一条有效数据
cur.execute("""
    SELECT * FROM amazon_product_details
    WHERE title IS NOT NULL AND title != '' AND title != '__404__'
    ORDER BY scraped_at DESC
    LIMIT 1
""")
row = cur.fetchone()

if not row:
    print("暂无有效数据")
    db.close()
    exit()

print("=" * 70)
print(f"ASIN           : {row['asin']}")
print(f"Amazon URL     : {(row['amazon_url'] or '')[:100]}")
print(f"标题           : {row['title']}")
print(f"品牌           : {row['brand']}")
print(f"价格           : {row['price']}")
print(f"原价           : {row['original_price']}")
print(f"评分           : {row['rating']}")
print(f"评论数         : {row['review_count']}")
print(f"库存状态       : {row['availability']}")
print(f"分类路径       : {row['category_path']}")
print(f"图片数量       : {len(json.loads(row['image_urls'])) if row.get('image_urls') else 0} 张")
print(f"页面语言       : {row['page_language']}")
print(f"采集时间       : {row['scraped_at']}")
print()

# Bullet Points
if row.get('bullet_points'):
    bullets = json.loads(row['bullet_points'])
    print(f"── Bullet Points（{len(bullets)} 条）──────────────────────────")
    for i, b in enumerate(bullets, 1):
        print(f"  {i}. {b[:120]}")
    print()

# 商品描述
if row.get('description'):
    desc = row['description']
    print(f"── 商品描述（前 200 字符）────────────────────────────────────")
    print(f"  {desc[:200]}")
    print()

# 规格参数
if row.get('product_details'):
    details = json.loads(row['product_details'])
    print(f"── 商品规格（{len(details)} 项）──────────────────────────────")
    for k, v in list(details.items())[:8]:
        print(f"  {k}: {v}")
    if len(details) > 8:
        print(f"  ... 等共 {len(details)} 项")
    print()

# Top Reviews
if row.get('top_reviews'):
    reviews = json.loads(row['top_reviews'])
    print(f"── Top Reviews（{len(reviews)} 条）──────────────────────────")
    for rev in reviews[:3]:
        print(f"  [{rev.get('rating','?')}] {rev.get('title','')}")
        print(f"       {rev.get('body','')[:120]}")
    print()

# 关键词
if row.get('keywords'):
    kws = json.loads(row['keywords'])
    print(f"── 关键词（{len(kws)} 个）────────────────────────────────────")
    print(f"  {', '.join(kws[:15])}")
    print()

print("=" * 70)
db.close()
