# -*- coding: utf-8 -*-
"""
调试脚本：连接 Chrome，截图确认页面内容，并打印关键选择器的文本
"""
import time
from playwright.sync_api import sync_playwright

ASIN = 'B0CPW78492'
URL = f'https://www.amazon.com/dp/{ASIN}?language=en_US'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp('http://localhost:9222')
    contexts = browser.contexts
    print(f"contexts: {len(contexts)}")
    for i, ctx in enumerate(contexts):
        print(f"  context[{i}]: {len(ctx.pages)} pages")
        for j, p in enumerate(ctx.pages):
            print(f"    page[{j}]: {p.url[:80]}")

    # 新建独立 Tab（不复用 YP Tab，避免 Service Worker 拦截）
    ctx = contexts[0]
    page = ctx.new_page()
    print("新建独立 Tab")
    
    print(f"\n正在导航到: {URL}")
    page.goto(URL, wait_until='networkidle', timeout=30000)
    time.sleep(3)
    
    current_url = page.url
    title_tag = page.title()
    print(f"当前 URL: {current_url[:100]}")
    print(f"页面 Title: {title_tag}")
    
    # 截图
    page.screenshot(path='output/amazon_debug.png', full_page=False)
    print("截图已保存到 output/amazon_debug.png")
    
    # 检测关键选择器
    selectors = [
        '#productTitle',
        '#bylineInfo',
        '.a-price .a-offscreen',
        '#acrPopover .a-icon-alt',
        '#feature-bullets li span.a-list-item',
        '#productDescription p',
        '#detailBullets_feature_div li .a-list-item',
        '#productDetails_techSpec_section_1 tr',
    ]
    
    print("\n选择器检测:")
    for sel in selectors:
        try:
            els = page.locator(sel).all()
            if els:
                first_text = els[0].text_content(timeout=2000)
                print(f"  ✅ {sel:<50s} count={len(els)}  text={repr(first_text[:60] if first_text else '')}")
            else:
                print(f"  ❌ {sel:<50s} 未找到")
        except Exception as e:
            print(f"  ⚠ {sel:<50s} 错误: {str(e)[:40]}")
    
    browser.close()
