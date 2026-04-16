# -*- coding: utf-8 -*-
"""
测试脚本：
第一步：切换配送地址到中国
第二步：访问亚马逊商品，通过页面语言选项切换为英语，然后采集
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS    = 'http://localhost:9222'
PAGE_TIMEOUT = 20000
TEST_ASIN    = 'B09G1Z83GM'
TEST_URL     = f'https://www.amazon.com/dp/{TEST_ASIN}'

def switch_to_china(page):
    """切换配送地址到中国"""
    print("\n[步骤1] 切换配送地址到中国...")
    page.goto("https://www.amazon.com/", wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
    time.sleep(2)
    
    # 点击配送地址按钮
    try:
        page.locator('#nav-global-location-popover-link').first.click(timeout=5000)
        time.sleep(2)
        print("[步骤1] 弹窗已打开")
    except Exception as e:
        print(f"[步骤1] 点击地址入口失败: {e}")
        return False
    
    # 选择中国
    try:
        page.wait_for_selector('#GLUXCountryList', timeout=5000)
        page.select_option('#GLUXCountryList', value='CN')
        print("[步骤1] 已选择 CN（中国）")
        time.sleep(1)
    except Exception as e:
        print(f"[步骤1] 选择国家失败: {e}")
        return False
    
    # 点击确认按钮
    for btn_sel in ['.a-popover-footer .a-button-primary',
                    '#GLUXLocationUpdateButton .a-button-input',
                    '#GLUXLocationUpdateButton input']:
        try:
            page.locator(btn_sel).first.click(timeout=2000)
            print(f"[步骤1] 确认按钮点击成功: {btn_sel}")
            time.sleep(3)
            break
        except Exception:
            pass
    
    # 截图确认
    page.screenshot(path="test_step1_done.png")
    
    # 读取当前地址
    for sel in ['#glow-ingress-line1', '#glow-ingress-line2']:
        try:
            txt = page.locator(sel).first.text_content(timeout=2000)
            if txt:
                print(f"[步骤1] 地址显示: {sel} => {txt.strip()}")
        except Exception:
            pass
    
    return True


def switch_language_via_page(page):
    """通过页面上的语言选项将语言切换为英语"""
    print("\n[步骤2] 访问商品页面，切换语言为英语...")
    
    # 访问商品
    page.goto(TEST_URL, wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
    time.sleep(3)
    
    print(f"[步骤2] 当前 URL: {page.url}")
    page.screenshot(path="test_step2_before_lang.png")
    
    # 找页面底部的语言切换区域
    # 亚马逊通常在底部 footer 有 "Change language" 链接或下拉
    print("\n[步骤2] 寻找页面语言切换选项...")
    
    # 常见的语言切换选择器
    lang_selectors = [
        # 底部 footer 语言按钮
        '#icp-touch-link-language',
        '#nav-footer .icp-language-switcher',
        '[data-action="icp-language-switcher"]',
        '#icp-language-settings',
        '.a-dropdown-container select[name="language"]',
        '#language_picker_select',
        'select[name*="language"]',
        'a[href*="language=en"]',
        '#icp-lang-flap-link',
        '#icp-touch-language',
        '#icp-language',
        # 导航栏中
        '#nav-tools .icp-language-switcher',
        '#a-touch-link-language',
    ]
    
    found_sel = None
    for sel in lang_selectors:
        try:
            els = page.locator(sel).all()
            for el in els:
                try:
                    if el.is_visible(timeout=1000):
                        txt = el.text_content(timeout=1000) or ''
                        print(f"  ✅ 找到: {sel}  text='{txt.strip()[:50]}'  visible=True")
                        found_sel = sel
                except Exception:
                    pass
        except Exception:
            pass
    
    if not found_sel:
        print("[步骤2] 未通过常规选择器找到语言切换，尝试扫描所有包含 language 的元素...")
        
        # 通过 JS 查找包含 language 的元素
        lang_elements = page.evaluate("""
            () => {
                const results = [];
                const els = document.querySelectorAll('[id*="lang"], [id*="language"], [name*="language"], [class*="language"], a[href*="language="]');
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({
                            tag: el.tagName,
                            id: el.id,
                            className: el.className.substring(0, 60),
                            text: el.textContent.trim().substring(0, 50),
                            href: el.href || ''
                        });
                    }
                }
                return results.slice(0, 20);
            }
        """)
        
        print("\n[步骤2] 页面上与 language 相关的可见元素:")
        for el in lang_elements:
            print(f"  tag={el['tag']}  id={el['id']}  class={el['className']}  text={el['text']}  href={el['href'][:60]}")
    
    # 尝试滚动到页面底部，有时语言选项在底部
    print("\n[步骤2] 滚动到页面底部查找语言选项...")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(2)
    page.screenshot(path="test_step2_footer.png")
    print("[步骤2] 页面底部截图已保存: test_step2_footer.png")
    
    # 再次扫描
    lang_elements2 = page.evaluate("""
        () => {
            const results = [];
            const els = document.querySelectorAll('[id*="lang"], [id*="language"], select, a[href*="language="]');
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0) {
                    results.push({
                        tag: el.tagName,
                        id: el.id,
                        className: el.className.substring(0, 60),
                        text: el.textContent.trim().substring(0, 50),
                        href: el.href || ''
                    });
                }
            }
            return results.slice(0, 30);
        }
    """)
    
    print("\n[步骤2] 滚动后找到的 language 相关元素:")
    for el in lang_elements2:
        print(f"  tag={el['tag']}  id={el['id']}  text={el['text']}  href={el['href'][:60]}")
    
    print("\n[DONE] 请查看截图，并告知页面上语言切换选项的位置")


with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    contexts = browser.contexts
    ctx = contexts[0] if contexts else browser.new_context()
    page = ctx.new_page()
    
    # 步骤1：切换地址到中国
    switch_to_china(page)
    
    # 步骤2：切换语言
    switch_language_via_page(page)
    
    print("\n脚本完成，请查看截图文件")
