"""
单个ASIN测试脚本，避免emoji编码问题，输出到文件
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

# 切换到脚本目录
os.chdir(r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu")

# 导入并运行
import json
import re
import time
from datetime import datetime
import mysql.connector
from playwright.sync_api import sync_playwright

DB_CONFIG = dict(host='localhost', user='root', password='admin',
                 database='affiliate_marketing', charset='utf8mb4')
CHROME_WS = 'http://localhost:9222'
PAGE_TIMEOUT = 25000
NAV_DELAY = 2.5

TEST_ASIN = "B0BB81YX1V"

def scrape_product(page, amazon_url: str, asin: str) -> dict:
    page.goto(amazon_url, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
    time.sleep(2)
    landed_url = page.url
    print(f"[LANDED] {landed_url[:120]}")
    
    if 'amazon.com' not in landed_url:
        raise Exception(f"Not on Amazon: {landed_url[:80]}")

    if 'language=en_US' not in landed_url:
        en_url = (landed_url + '&language=en_US') if '?' in landed_url else (landed_url + '?language=en_US')
        page.goto(en_url, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
        time.sleep(NAV_DELAY)
    time.sleep(NAV_DELAY)

    print(f"[TITLE] {page.title()}")

    data = {'asin': asin, 'amazon_url': amazon_url}

    # 标题
    for sel in ['#productTitle', 'h1.a-size-large', 'h1#title']:
        try:
            t = page.locator(sel).first.text_content(timeout=3000)
            if t and t.strip():
                data['title'] = t.strip()
                print(f"[title] {t.strip()[:80]}")
                break
        except: pass

    # 品牌
    for sel in ['#bylineInfo', 'a#bylineInfo', 'tr.po-brand td.a-span9 span']:
        try:
            b = page.locator(sel).first.text_content(timeout=3000)
            if b:
                brand = re.sub(r'^(Brand:|Visit the|Store)', '', b, flags=re.I).strip()
                data['brand'] = brand
                print(f"[brand] {brand}")
                break
        except: pass

    # 价格
    for sel in ['.a-price .a-offscreen', '#priceblock_ourprice',
                '#corePrice_feature_div .a-price .a-offscreen',
                '#apex_desktop .a-price .a-offscreen']:
        try:
            pels = page.locator(sel).all()
            for el in pels:
                p = el.text_content(timeout=2000)
                if p and '$' in p:
                    data['price'] = p.strip()
                    print(f"[price] {p.strip()}")
                    break
            if data.get('price'):
                break
        except: pass

    # 评分
    try:
        r = page.locator('#acrPopover .a-icon-alt').first.text_content(timeout=3000)
        if r:
            data['rating'] = r.strip()
            print(f"[rating] {r.strip()}")
    except: pass

    # 评论数
    try:
        rc = page.locator('#acrCustomerReviewText').first.text_content(timeout=3000)
        if rc:
            data['review_count'] = rc.strip()
            print(f"[reviews] {rc.strip()}")
    except: pass

    # 库存
    try:
        av = page.locator('#availability span').first.text_content(timeout=3000)
        if av:
            data['availability'] = av.strip()[:255]
            print(f"[avail] {av.strip()[:60]}")
    except: pass

    # Bullets
    bullets = []
    try:
        bels = page.locator('#feature-bullets li:not(.aok-hidden) span.a-list-item').all()
        for el in bels:
            t = el.text_content(timeout=2000)
            if t and t.strip() and len(t.strip()) > 3:
                bullets.append(t.strip())
    except: pass
    if bullets:
        data['bullet_points'] = json.dumps(bullets, ensure_ascii=False)
        print(f"[bullets] {len(bullets)} items")

    # 描述
    desc_parts = []
    for sel in ['#productDescription p', '#productDescription span']:
        try:
            dels = page.locator(sel).all()
            for el in dels:
                t = el.text_content(timeout=2000)
                if t and t.strip():
                    desc_parts.append(t.strip())
        except: pass
        if desc_parts: break
    if desc_parts:
        data['description'] = '\n\n'.join(desc_parts)[:50000]
        print(f"[desc] {len(desc_parts)} paragraphs, {len(data['description'])} chars")

    # 规格参数
    details = {}
    try:
        rows = page.locator('#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr').all()
        for row in rows:
            cells = row.locator('td, th').all()
            if len(cells) >= 2:
                k = cells[0].text_content(timeout=2000)
                v = cells[1].text_content(timeout=2000)
                if k and v:
                    details[k.strip()] = v.strip()
    except: pass
    if not details:
        try:
            items = page.locator('#detailBullets_feature_div li .a-list-item').all()
            for item in items:
                t = item.text_content(timeout=2000)
                if t and ':' in t:
                    parts = t.split(':', 1)
                    if len(parts) == 2:
                        details[parts[0].strip()] = parts[1].strip()
        except: pass
    if details:
        data['product_details'] = json.dumps(details, ensure_ascii=False)
        print(f"[details] {len(details)} fields")

    # 主图
    try:
        img = page.locator('#imgTagWrapperId img, #landingImage').first.get_attribute('src', timeout=3000)
        if img and not img.startswith('data:'):
            data['main_image_url'] = img
            print(f"[img] {img[:80]}")
    except: pass

    data['page_language'] = 'en-US'
    data['scraped_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return data


UPSERT_SQL = """
INSERT INTO amazon_product_details
    (asin, title, brand, price, original_price, rating, review_count,
     availability, bullet_points, description, product_details, category_path,
     main_image_url, image_urls, top_reviews, keywords, amazon_url,
     page_language, scraped_at)
VALUES
    (%(asin)s, %(title)s, %(brand)s, %(price)s, %(original_price)s, %(rating)s,
     %(review_count)s, %(availability)s, %(bullet_points)s, %(description)s,
     %(product_details)s, %(category_path)s, %(main_image_url)s, %(image_urls)s,
     %(top_reviews)s, %(keywords)s, %(amazon_url)s, %(page_language)s, %(scraped_at)s)
ON DUPLICATE KEY UPDATE
    title=VALUES(title), brand=VALUES(brand), price=VALUES(price),
    rating=VALUES(rating), review_count=VALUES(review_count),
    availability=VALUES(availability), bullet_points=VALUES(bullet_points),
    description=VALUES(description), product_details=VALUES(product_details),
    main_image_url=VALUES(main_image_url), scraped_at=VALUES(scraped_at)
"""

ALL_FIELDS = ['asin','title','brand','price','original_price','rating','review_count',
              'availability','bullet_points','description','product_details','category_path',
              'main_image_url','image_urls','top_reviews','keywords','amazon_url','page_language','scraped_at']

def ensure_field(d, fields):
    for f in fields:
        d.setdefault(f, None)
    return d

# 获取 amazon_url
db = mysql.connector.connect(**DB_CONFIG)
cur = db.cursor(dictionary=True)
cur.execute("SELECT asin, amazon_url FROM yp_products WHERE asin=%s AND amazon_url IS NOT NULL LIMIT 1", (TEST_ASIN,))
row = cur.fetchone()
if not row:
    print(f"[ERROR] ASIN {TEST_ASIN} not found in DB")
    db.close()
    sys.exit(1)

print(f"\n=== Testing ASIN: {TEST_ASIN} ===")
print(f"URL: {row['amazon_url'][:100]}\n")

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    
    try:
        detail = scrape_product(page, row['amazon_url'], TEST_ASIN)
        detail = ensure_field(detail, ALL_FIELDS)
        cur.execute(UPSERT_SQL, detail)
        db.commit()
        print(f"\n[DB WRITE] SUCCESS")
        print(f"\n=== SUMMARY ===")
        for k,v in detail.items():
            if v and k not in ('amazon_url', 'bullet_points', 'description', 'product_details', 'keywords', 'image_urls', 'top_reviews'):
                print(f"  {k}: {str(v)[:100]}")
        if detail.get('bullet_points'):
            bullets = json.loads(detail['bullet_points'])
            print(f"  bullet_points: [{len(bullets)} items] {bullets[0][:60]}...")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback; traceback.print_exc()
    finally:
        page.close()

db.close()
print("\n[DONE]")
