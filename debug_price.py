"""
通过 URL 参数 glIncludes=1 + 切换配送地址到美国来获取价格
同时深度调试价格的实际 HTML 结构
"""
import sys
import os
import time
sys.stdout.reconfigure(encoding='utf-8')
os.chdir(r"C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu")

from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'

# 使用一个有 bullet points 和评分的 ASIN
TEST_ASIN = "B09G1Z83GM"
# 加上美国地址相关参数
TEST_URL = f"https://www.amazon.com/dp/{TEST_ASIN}?language=en_US"

OUTPUT_FILE = "price_debug.txt"

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0]
    page = ctx.new_page()
    
    print(f"Step 1: 导航到商品页（语言=英文）")
    page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    print(f"Title: {page.title()[:80]}")
    
    # 尝试切换配送地址到美国
    print(f"\nStep 2: 尝试切换配送地址到美国")
    try:
        # 点击地址选择器
        page.locator('#nav-global-location-popover-link, #glow-ingress-block').first.click(timeout=5000)
        time.sleep(1.5)
        
        # 输入美国邮编
        zipcode_input = page.query_selector('#GLUXZipUpdateInput')
        if zipcode_input:
            zipcode_input.fill("10001")  # 纽约邮编
            page.locator('#GLUXZipUpdate button[type="submit"], #GLUXZipUpdate .a-button-input').first.click(timeout=3000)
            time.sleep(2)
            print("  ZIP code 10001 submitted")
        else:
            print("  ZIP input not found, trying country selector")
            # 尝试找国家选择
            country_sel = page.query_selector('#GLUXCountryListDropdown')
            if country_sel:
                country_sel.select_option('US')
                time.sleep(1)
                print("  Country set to US")
        
        # 点击完成/确认
        for done_sel in ['#GLUXConfirmClose', '.a-popover-footer button', 
                          '#GLUXZipConfirm', 'input[data-action-type="GLUXZipConfirm"]']:
            try:
                page.locator(done_sel).first.click(timeout=2000)
                time.sleep(1)
                print(f"  Clicked done: {done_sel}")
                break
            except: pass
        
        time.sleep(2)
        
    except Exception as e:
        print(f"  Address switch error: {e}")
    
    # 重新加载页面
    print(f"\nStep 3: 重新加载页面")
    page.reload(wait_until='domcontentloaded', timeout=30000)
    time.sleep(3)
    print(f"New title: {page.title()[:80]}")
    
    # 检查配送地址变化
    try:
        addr = page.query_selector('#glow-ingress-line2')
        if addr:
            print(f"Delivery to: {addr.text_content().strip()}")
    except: pass
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== ASIN: {TEST_ASIN}\n")
        f.write(f"=== URL: {page.url}\n\n")
        
        # 输出价格区域完整 HTML
        for sel in ['#buybox', '#corePriceDisplay_desktop_feature_div', 
                    '#corePrice_feature_div', '#price', 
                    '#rightCol', '#apex_desktop .a-price']:
            try:
                el = page.query_selector(sel)
                if el:
                    html = el.inner_html()
                    f.write(f"\n[{sel}] ({len(html)} chars):\n{html[:2000]}\n")
                else:
                    f.write(f"\n[{sel}]: NOT FOUND\n")
            except Exception as e:
                f.write(f"\n[{sel}]: ERROR {e}\n")
        
        # 搜索所有包含 $ 的文本元素
        f.write("\n\n=== ELEMENTS CONTAINING '$' ===\n")
        try:
            dollar_els = page.query_selector_all('span, div')
            count = 0
            for el in dollar_els:
                try:
                    text = el.text_content()
                    if text and '$' in text and len(text.strip()) < 20:
                        elem_class = el.get_attribute('class') or ''
                        elem_id = el.get_attribute('id') or ''
                        f.write(f"  [{elem_id}] .{elem_class[:50]}: {text.strip()[:30]}\n")
                        count += 1
                        if count > 30:
                            break
                except: pass
        except Exception as e:
            f.write(f"Error: {e}\n")
    
    page.close()

print(f"\n[DONE] Written to {OUTPUT_FILE}")
