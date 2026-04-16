# -*- coding: utf-8 -*-
"""
探测 #icp-touch-link-language 的结构，并尝试点击触发语言切换
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
TEST_ASIN  = 'B09G1Z83GM'
TEST_URL   = f'https://www.amazon.com/dp/{TEST_ASIN}'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 访问商品页（已经是 China 地址）
    print(f"[1] 访问商品页: {TEST_URL}")
    try:
        page.goto(TEST_URL, wait_until='domcontentloaded', timeout=20000)
    except Exception as e:
        print(f"  加载超时（继续）: {e}")
    time.sleep(3)
    print(f"[1] URL: {page.url}")

    # 获取 #icp-touch-link-language 的详细 HTML
    detail = page.evaluate("""
    () => {
        const els = document.querySelectorAll('#icp-touch-link-language');
        const out = [];
        for (const el of els) {
            out.push({
                outerHTML: el.outerHTML.substring(0, 300),
                parent: el.parentElement ? el.parentElement.outerHTML.substring(0, 400) : '',
            });
        }
        return out;
    }
    """)
    print("\n[2] #icp-touch-link-language 详细 HTML：")
    for i, d in enumerate(detail):
        print(f"  [{i}] outerHTML: {d['outerHTML']}")
        print(f"       parent: {d['parent']}")
        print()

    # 获取语言相关链接 (customer-preferences)
    pref_link = page.evaluate("""
    () => {
        const a = document.querySelector('a[href*="customer-preferences"]');
        return a ? {href: a.href, text: a.textContent.trim(), outerHTML: a.outerHTML.substring(0, 400)} : null;
    }
    """)
    if pref_link:
        print(f"\n[3] customer-preferences 链接: {pref_link['href']}")
        print(f"    text: {pref_link['text']}")
        print(f"    HTML: {pref_link['outerHTML']}")

    # 尝试点击第一个 #icp-touch-link-language
    print("\n[4] 尝试点击 #icp-touch-link-language...")
    try:
        el = page.locator('#icp-touch-link-language').first
        el.scroll_into_view_if_needed(timeout=3000)
        time.sleep(1)
        el.click(timeout=5000)
        time.sleep(2)
        print(f"  点击后 URL: {page.url}")
        
        # 检查是否弹出语言选择面板
        after_html = page.evaluate("""
        () => {
            const visible = [];
            for (const el of document.querySelectorAll('[id*="lang"], [id*="language"], [class*="language-flyout"], [class*="icp"]')) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 10) {
                    visible.push({id: el.id, cls: el.className.substring(0,60), text: el.textContent.trim().substring(0,80)});
                }
            }
            return visible;
        }
        """)
        print("  点击后出现的语言相关元素：")
        for el in after_html:
            print(f"    id={el['id']:<30} cls={el['cls']:<50} text={el['text'][:60]}")
            
    except Exception as e:
        print(f"  点击失败: {e}")

    print("\n[完成]")
