"""
深度调试：输出亚马逊页面关键区域的 HTML，帮助找到正确的 selector
"""
import sys
import os
import time
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu")

from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
TEST_URL = "https://www.amazon.com/dp/B0BB81YX1V?language=en_US"

OUTPUT_FILE = "amazon_debug_html.txt"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    
    print(f"Navigating to {TEST_URL}")
    page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    
    print(f"Page title: {page.title()}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Page URL: {page.url}\n")
        f.write(f"=== Page Title: {page.title()}\n\n")
        
        # 1. 价格区域
        f.write("=" * 60 + "\n")
        f.write("PRICE AREA\n")
        f.write("=" * 60 + "\n")
        for sel in ['#corePriceDisplay_desktop_feature_div', '#corePrice_feature_div',
                    '#apex_desktop', '.a-price', '#buybox', '#ppd']:
            try:
                el = page.query_selector(sel)
                if el:
                    html = el.inner_html()
                    f.write(f"\n[{sel}] FOUND ({len(html)} chars):\n")
                    f.write(html[:500] + "\n")
                else:
                    f.write(f"\n[{sel}] NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}] ERROR: {e}\n")
        
        # 2. 评分区域
        f.write("\n" + "=" * 60 + "\n")
        f.write("RATING AREA\n")
        f.write("=" * 60 + "\n")
        for sel in ['#averageCustomerReviews', '#acrPopover', 
                    '[data-feature-name="averageCustomerReviews"]',
                    '#reviewsMedley', '.a-star-5']:
            try:
                el = page.query_selector(sel)
                if el:
                    html = el.inner_html()
                    f.write(f"\n[{sel}] FOUND ({len(html)} chars):\n")
                    f.write(html[:300] + "\n")
                else:
                    f.write(f"\n[{sel}] NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}] ERROR: {e}\n")
        
        # 3. Bullet points 区域
        f.write("\n" + "=" * 60 + "\n")
        f.write("BULLET POINTS AREA\n")
        f.write("=" * 60 + "\n")
        for sel in ['#feature-bullets', '#productFactsDesktopExpander',
                    '[data-feature-name="featurebullets"]',
                    '.a-unordered-list.a-vertical.a-spacing-mini']:
            try:
                el = page.query_selector(sel)
                if el:
                    html = el.inner_html()
                    f.write(f"\n[{sel}] FOUND ({len(html)} chars):\n")
                    f.write(html[:800] + "\n")
                else:
                    f.write(f"\n[{sel}] NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}] ERROR: {e}\n")
        
        # 4. 技术规格
        f.write("\n" + "=" * 60 + "\n")
        f.write("PRODUCT DETAILS AREA\n")
        f.write("=" * 60 + "\n")
        for sel in ['#detailBullets_feature_div', '#productDetails_feature_div',
                    '#productDetails_techSpec_section_1',
                    '#detailBulletsWrapper_feature_div']:
            try:
                el = page.query_selector(sel)
                if el:
                    html = el.inner_html()
                    f.write(f"\n[{sel}] FOUND ({len(html)} chars):\n")
                    f.write(html[:800] + "\n")
                else:
                    f.write(f"\n[{sel}] NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}] ERROR: {e}\n")
        
        # 5. 商品标题和品牌（再确认）
        f.write("\n" + "=" * 60 + "\n")
        f.write("TITLE & BRAND\n")
        f.write("=" * 60 + "\n")
        for sel in ['#productTitle', '#bylineInfo', '.product-title-word-break']:
            try:
                el = page.query_selector(sel)
                if el:
                    txt = el.inner_text()
                    f.write(f"\n[{sel}]: {txt[:200]}\n")
                else:
                    f.write(f"\n[{sel}]: NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}]: ERROR: {e}\n")
        
        # 6. 从 body 文本中搜索关键词
        f.write("\n" + "=" * 60 + "\n")
        f.write("BODY TEXT SNIPPET (first 1000 chars)\n")
        f.write("=" * 60 + "\n")
        body_text = page.inner_text('body')
        f.write(body_text[:2000] + "\n")
    
    page.close()

print(f"\n[DONE] HTML debug written to {OUTPUT_FILE}")
print(f"File size: {os.path.getsize(OUTPUT_FILE)} bytes")
