"""
完整输出指定 ASIN 的所有字段原始内容，写入文件避免乱码
"""
import mysql.connector, json, sys

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor(dictionary=True)

ASIN = 'B09NVYQGXS'
cur.execute("SELECT * FROM amazon_product_details WHERE asin = %s", (ASIN,))
row = cur.fetchone()
db.close()

out = []

def p(s=""):
    out.append(str(s))

sep = "=" * 80

p(sep)
p(f"ASIN: {row['asin']}    采集时间: {row['scraped_at']}")
p(sep)

p("\n【标题 title】")
p(row['title'])

p("\n【品牌 brand】")
p(row['brand'])

p("\n【价格 price / 原价 original_price】")
p(f"  现价: {row['price']}    原价: {row['original_price']}")

p("\n【评分 rating / 评论数 review_count】")
p(f"  {row['rating']}  {row['review_count']}")

p("\n【库存状态 availability】")
p(row['availability'])

p("\n【分类路径 category_path】")
p(row['category_path'])

p("\n【页面语言 page_language】")
p(row['page_language'])

p("\n【Amazon URL】")
p(row['amazon_url'])

p("\n" + sep)
p("【Bullet Points — 完整内容】")
p(sep)
if row.get('bullet_points'):
    bullets = json.loads(row['bullet_points'])
    for i, b in enumerate(bullets, 1):
        p(f"\n  [{i}] {b}")
else:
    p("  (空)")

p("\n" + sep)
p("【商品描述 description — 完整内容】")
p(sep)
p(row.get('description') or "(空)")

p("\n" + sep)
p("【规格参数 product_details — 完整内容】")
p(sep)
if row.get('product_details'):
    details = json.loads(row['product_details'])
    for k, v in details.items():
        p(f"\n  ● {k}")
        p(f"    {v}")
else:
    p("  (空)")

p("\n" + sep)
p("【Top Reviews — 完整内容（共5条）】")
p(sep)
if row.get('top_reviews'):
    reviews = json.loads(row['top_reviews'])
    for i, rev in enumerate(reviews, 1):
        p(f"\n  ── 评论 {i} ──────────────────────────────")
        p(f"  评分: {rev.get('rating', '')}")
        p(f"  标题: {rev.get('title', '')}")
        p(f"  作者: {rev.get('author', '')}")
        p(f"  日期: {rev.get('date', '')}")
        p(f"  正文:\n  {rev.get('body', '')}")
else:
    p("  (空)")

p("\n" + sep)
p("【关键词 keywords】")
p(sep)
if row.get('keywords'):
    kws = json.loads(row['keywords'])
    p(f"  共 {len(kws)} 个: {', '.join(kws)}")
else:
    p("  (空)")

p("\n" + sep)
p("【图片 image_urls】")
p(sep)
if row.get('image_urls'):
    imgs = json.loads(row['image_urls'])
    for i, url in enumerate(imgs, 1):
        p(f"  {i}. {url}")
else:
    p("  (空 — 图片selector未采集到)")

content = "\n".join(out)

with open("asin_detail_output.txt", "w", encoding="utf-8") as f:
    f.write(content)

print("已写入 asin_detail_output.txt")
