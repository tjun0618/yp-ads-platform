# -*- coding: utf-8 -*-
"""
快速扫描亚马逊页面上的语言切换元素（无截图，避免超时）
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

    # ---------- 步骤1：切换地址到中国 ----------
    print("\n[步骤1] 打开亚马逊首页并切换地址到中国")
    page.goto("https://www.amazon.com/", wait_until='domcontentloaded', timeout=20000)
    time.sleep(2)

    try:
        page.locator('#nav-global-location-popover-link').first.click(timeout=5000)
        time.sleep(2)
        print("[步骤1] 地址弹窗已打开")

        page.wait_for_selector('#GLUXCountryList', timeout=5000)
        page.select_option('#GLUXCountryList', value='CN')
        print("[步骤1] 已选择 CN（中国）")
        time.sleep(1)

        # 点击确认
        for btn_sel in [
            '.a-popover-footer .a-button-primary input',
            '#GLUXLocationUpdateButton input',
            '#GLUXLocationUpdateButton .a-button-input',
            '.a-popover-footer .a-button-input',
        ]:
            try:
                page.locator(btn_sel).first.click(timeout=2000)
                print(f"[步骤1] 确认按钮点击成功: {btn_sel}")
                time.sleep(3)
                break
            except Exception:
                pass

        # 读取当前地址显示
        for sel in ['#glow-ingress-line1', '#glow-ingress-line2', '#nav-global-location-slot']:
            try:
                txt = page.locator(sel).first.text_content(timeout=2000)
                if txt and txt.strip():
                    print(f"[步骤1] 地址显示: {sel} => {txt.strip()}")
            except Exception:
                pass

    except Exception as e:
        print(f"[步骤1] 切换地址失败: {e}")

    # ---------- 步骤2：访问商品页面扫描语言元素 ----------
    print(f"\n[步骤2] 访问商品页: {TEST_URL}")
    try:
        page.goto(TEST_URL, wait_until='domcontentloaded', timeout=20000)
    except Exception as e:
        print(f"[步骤2] 页面加载超时（继续）: {e}")
    time.sleep(3)

    print(f"[步骤2] 当前 URL: {page.url}")

    # JS 扫描语言相关元素（顶部 + 底部）
    result = page.evaluate("""
    () => {
        const out = [];
        const sels = [
            '[id*="lang"]',
            '[id*="language"]',
            '[name*="language"]',
            '[class*="language"]',
            'a[href*="language="]',
            'a[href*="lang="]',
            'select',
            '#icp-touch-link-language',
            '.icp-language-switcher',
        ];
        for (const s of sels) {
            for (const el of document.querySelectorAll(s)) {
                const rect = el.getBoundingClientRect();
                out.push({
                    sel: s,
                    tag: el.tagName,
                    id: el.id || '',
                    cls: (el.className || '').substring(0, 60),
                    text: (el.textContent || '').trim().substring(0, 80),
                    href: (el.href || '').substring(0, 100),
                    visible: rect.width > 0 && rect.height > 0,
                    y: Math.round(rect.top + window.scrollY),
                });
            }
        }
        return out;
    }
    """)

    print("\n[步骤2] 页面上与语言相关的元素（共 %d 个）：" % len(result))
    for el in result:
        vis = "✅" if el['visible'] else "⬜"
        print(f"  {vis} tag={el['tag']:<4} id={el['id']:<30} text={el['text'][:50]:<50} href={el['href'][:70]}")

    # 特别扫描 footer 区域
    print("\n[步骤2] 扫描 footer 区域的所有链接和下拉...")
    footer_els = page.evaluate("""
    () => {
        const footer = document.querySelector('#navFooter, footer, #site-below-the-fold, #nav-wishlist-flyout');
        if (!footer) return [{info: '未找到 footer 元素'}];
        const out = [];
        for (const el of footer.querySelectorAll('a, select, button')) {
            const text = (el.textContent || '').trim().substring(0, 60);
            const href = (el.href || '').substring(0, 100);
            const id = el.id || '';
            if (text || href) {
                out.push({tag: el.tagName, id, text, href});
            }
        }
        return out.slice(0, 30);
    }
    """)

    print("  Footer 元素（前30个）：")
    for el in footer_els:
        print(f"    tag={el.get('tag','?'):<6} id={el.get('id',''):<30} text={el.get('text',''):<50} href={el.get('href','')[:60]}")

    print("\n[完成] 扫描结束，请根据上面结果确认语言切换元素")
