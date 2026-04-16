# -*- coding: utf-8 -*-
"""诊断某个空数据 ASIN 的实际页面内容"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
# 取一个空数据的 ASIN 诊断
TEST_URL = 'https://www.amazon.com/dp/B087TJZ4SS?maas=maas_adg_api_594018816858204846_static'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    print(f'[1] 访问: {TEST_URL}')
    try:
        page.goto(TEST_URL, wait_until='domcontentloaded', timeout=20000)
    except Exception as e:
        print(f'  超时（继续）: {e}')
    time.sleep(3)

    final_url = page.url
    print(f'[2] 最终 URL: {final_url}')
    print(f'[3] 页面 title tag: {page.title()}')

    # 检查是否跳转到了非商品页
    if 'captcha' in final_url.lower():
        print('!!! 跳到了验证码页面 !!!')
    elif 'signin' in final_url.lower():
        print('!!! 跳到了登录页 !!!')
    elif '/dp/' not in final_url and '/gp/product' not in final_url:
        print(f'!!! 不是商品页，实际跳转到: {final_url}')

    # 检查关键 selector
    checks = [
        ('#productTitle', '商品标题'),
        ('#price', '价格1'),
        ('.a-price .a-offscreen', '价格2'),
        ('#feature-bullets', 'Bullet Points'),
        ('#buybox', 'Buy Box'),
        ('#availability', '库存'),
        ('#dp-container', '商品详情容器'),
        ('#outOfStockBuyBox_feature_div', '缺货提示'),
        ('#title', '标题区域'),
        ('h1', 'H1标签'),
    ]
    print('\n[4] 关键 selector 检查:')
    for sel, name in checks:
        try:
            el = page.locator(sel).first
            txt = el.text_content(timeout=2000)
            visible = el.is_visible(timeout=1000)
            print(f'  {"✅" if txt and txt.strip() else "⬜"} {name:<20} text="{(txt or "").strip()[:60]}"  visible={visible}')
        except Exception:
            print(f'  ❌ {name:<20} (not found)')

    # 页面主要内容区域
    page_text_sample = page.evaluate("() => document.body.innerText.substring(0, 500)")
    print(f'\n[5] 页面正文前500字:\n{page_text_sample}')
