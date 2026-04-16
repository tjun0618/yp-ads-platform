"""
完整输出指定 ASIN 的所有字段原始内容，不截断
"""
import mysql.connector, json

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor(dictionary=True)

ASIN = 'B09NVYQGXS'
cur.execute("SELECT * FROM amazon_product_details WHERE asin = %s", (ASIN,))
row = cur.fetchone()
db.close()

if not row:
    print("未找到该 ASIN")
    exit()

sep = "=" * 80

print(sep)
print(f"ASIN: {row['asin']}")
print(f"采集时间: {row['scraped_at']}")
print(sep)

print("\n【标题 title】")
print(row['title'])

print("\n【品牌 brand】")
print(row['brand'])

print("\n【价格 price】")
print(row['price'])

print("\n【原价 original_price】")
print(row['original_price'])

print("\n【评分 rating】")
print(row['rating'])

print("\n【评论数 review_count】")
print(row['review_count'])

print("\n【库存状态 availability】")
print(row['availability'])

print("\n【分类路径 category_path】")
print(row['category_path'])

print("\n【页面语言 page_language】")
print(row['page_language'])

print("\n【Amazon URL】")
print(row['amazon_url'])

print("\n" + sep)
print("【Bullet Points 完整内容】")
print(sep)
if row.get('bullet_points'):
    bullets = json.loads(row['bullet_points'])
    for i, b in enumerate(bullets, 1):
        print(f"\n第{i}条:")
        print(b)
else:
    print("(空)")

print("\n" + sep)
print("【商品描述 description 完整内容】")
print(sep)
if row.get('description'):
    print(row['description'])
else:
    print("(空)")

print("\n" + sep)
print("【规格参数 product_details 完整内容】")
print(sep)
if row.get('product_details'):
    details = json.loads(row['product_details'])
    for k, v in details.items():
        print(f"\n  [{k}]")
        print(f"  {v}")
else:
    print("(空)")

print("\n" + sep)
print("【Top Reviews 完整内容】")
print(sep)
if row.get('top_reviews'):
    reviews = json.loads(row['top_reviews'])
    for i, rev in enumerate(reviews, 1):
        print(f"\n── 评论 {i} ──")
        print(f"  评分  : {rev.get('rating', '')}")
        print(f"  标题  : {rev.get('title', '')}")
        print(f"  作者  : {rev.get('author', '')}")
        print(f"  日期  : {rev.get('date', '')}")
        print(f"  正文  :")
        print(f"  {rev.get('body', '')}")
else:
    print("(空)")

print("\n" + sep)
print("【关键词 keywords 完整内容】")
print(sep)
if row.get('keywords'):
    kws = json.loads(row['keywords'])
    print(f"共 {len(kws)} 个:")
    print(', '.join(kws))
else:
    print("(空)")

print("\n" + sep)
print("【图片 image_urls】")
print(sep)
if row.get('image_urls'):
    imgs = json.loads(row['image_urls'])
    print(f"共 {len(imgs)} 张:")
    for i, url in enumerate(imgs, 1):
        print(f"  {i}. {url}")
else:
    print("(空)")
