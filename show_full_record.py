"""
清理异常数据，完整输出一条有效记录的所有字段
"""
import mysql.connector, json

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor(dictionary=True)

# 删除空/异常数据（title为空、__404__、或关键字段全空）
cur.execute("""
    DELETE FROM amazon_product_details
    WHERE title IS NULL OR title = '' OR title = '__404__'
""")
db.commit()
print(f"已删除异常记录: {cur.rowcount} 条\n")

# 统计
cur.execute("SELECT COUNT(*) as cnt FROM amazon_product_details")
print(f"剩余有效记录: {cur.fetchone()['cnt']} 条\n")

# 取最新一条完整输出所有字段
cur.execute("""
    SELECT * FROM amazon_product_details
    WHERE title IS NOT NULL AND title != ''
    ORDER BY scraped_at DESC LIMIT 1
""")
row = cur.fetchone()
db.close()

if not row:
    print("无数据")
    exit()

sep = "=" * 72

print(sep)
print("【基础信息】")
print(f"  ASIN         : {row['asin']}")
print(f"  amazon_url   : {row['amazon_url']}")
print(f"  title        : {row['title']}")
print(f"  brand        : {row['brand']}")
print(f"  price        : {row['price']}")
print(f"  original_price: {row['original_price']}")
print(f"  rating       : {row['rating']}")
print(f"  review_count : {row['review_count']}")
print(f"  availability : {row['availability']}")
print(f"  category_path: {row['category_path']}")
print(f"  page_language: {row['page_language']}")
print(f"  scraped_at   : {row['scraped_at']}")

print()
print("【图片 image_urls】")
if row.get('image_urls'):
    imgs = json.loads(row['image_urls'])
    print(f"  共 {len(imgs)} 张")
    for i, url in enumerate(imgs, 1):
        print(f"  {i}. {url[:120]}")
else:
    print("  (空)")

print()
print("【Bullet Points】")
if row.get('bullet_points'):
    bullets = json.loads(row['bullet_points'])
    print(f"  共 {len(bullets)} 条")
    for i, b in enumerate(bullets, 1):
        print(f"  {i}. {b}")
else:
    print("  (空)")

print()
print("【商品描述 description】")
if row.get('description'):
    print(f"  {row['description']}")
else:
    print("  (空)")

print()
print("【规格参数 product_details】")
if row.get('product_details'):
    details = json.loads(row['product_details'])
    print(f"  共 {len(details)} 项")
    for k, v in details.items():
        # 跳过含 JS 代码的字段
        v_str = str(v)
        if 'P.when' in v_str or len(v_str) > 300:
            v_str = v_str[:200] + "...[截断]"
        print(f"  {k}: {v_str}")
else:
    print("  (空)")

print()
print("【Top Reviews】")
if row.get('top_reviews'):
    reviews = json.loads(row['top_reviews'])
    print(f"  共 {len(reviews)} 条")
    for i, rev in enumerate(reviews, 1):
        print(f"  [{i}] 评分: {rev.get('rating','')}")
        print(f"       标题: {rev.get('title','')}")
        print(f"       正文: {rev.get('body','')[:200]}")
        print(f"       作者: {rev.get('author','')}  日期: {rev.get('date','')}")
else:
    print("  (空)")

print()
print("【关键词 keywords】")
if row.get('keywords'):
    kws = json.loads(row['keywords'])
    print(f"  共 {len(kws)} 个: {', '.join(kws)}")
else:
    print("  (空)")

print(sep)
