"""
找一个有效且有库存的 ASIN 进行测试
"""
import sys
import os
import time
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu")

from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'

# 尝试多个 ASIN，找到有价格的那个
ASINS_TO_TRY = [
    ("B09G1Z83GM", "https://www.amazon.com/dp/B09G1Z83GM"),  # PepperMate 切菜板
    ("B0DDPH3RBH", "https://www.amazon.com/dp/B0DDPH3RBH"),  # Ninabella 发刷
    ("B07FN6GG5T", "https://www.amazon.com/dp/B07FN6GG5T"),  # MEVA 玩具
    ("B0CLZD37PD", "https://www.amazon.com/dp/B0CLZD37PD"),  # 玻璃杯
]

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    
    for asin, base_url in ASINS_TO_TRY:
        url = base_url + "?language=en_US"
        print(f"\n--- Testing ASIN: {asin} ---")
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)
        
        title = page.title()
        print(f"Title: {title[:80]}")
        
        # 检查是否有价格
        price_found = False
        for sel in ['.a-price .a-offscreen', '#priceblock_ourprice', 
                    '#corePriceDisplay_desktop_feature_div .a-offscreen',
                    '#corePrice_feature_div .a-offscreen']:
            try:
                el = page.query_selector(sel)
                if el:
                    p = el.text_content()
                    if p and '$' in p:
                        print(f"PRICE FOUND [{sel}]: {p.strip()}")
                        price_found = True
                        break
            except: pass
        
        if not price_found:
            print("PRICE: not found")
        
        # 检查库存
        try:
            av = page.query_selector('#availability span')
            if av:
                print(f"AVAIL: {av.text_content().strip()[:80]}")
        except: pass
        
        # 检查 bullet points
        try:
            bels = page.query_selector_all('#feature-bullets li span.a-list-item')
            if bels:
                print(f"BULLETS: {len(bels)} items found")
                print(f"  First: {bels[0].text_content().strip()[:80]}")
            else:
                print("BULLETS: not found")
        except: pass
        
        # 检查评分
        try:
            r = page.query_selector('.a-icon-alt')
            if r:
                rt = r.text_content()
                if 'star' in rt.lower():
                    print(f"RATING: {rt.strip()}")
        except: pass
        
        if price_found:
            print(f"\n>>> Found valid ASIN with price: {asin} <<<")
            break
    
    page.close()
print("\n[DONE]")
