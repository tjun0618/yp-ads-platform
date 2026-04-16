# -*- coding: utf-8 -*-
"""
测试脚本：切换配送地址到中国
运行后会在调试 Chrome 中打开亚马逊首页并尝试切换配送地址到中国
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS   = 'http://localhost:9222'
PAGE_TIMEOUT = 20000

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    contexts = browser.contexts
    ctx  = contexts[0] if contexts else browser.new_context()
    page = ctx.new_page()

    print("[step1] 打开亚马逊首页...")
    page.goto("https://www.amazon.com/", wait_until='domcontentloaded', timeout=PAGE_TIMEOUT)
    time.sleep(2)

    print("[step1] 当前 URL:", page.url)
    print("[step1] 点击配送地址选择器...")

    clicked = False
    for sel in ['#nav-global-location-popover-link', '#glow-ingress-block', '#nav-packard-glow-loc-icon']:
        try:
            page.locator(sel).first.click(timeout=4000)
            print(f"[step1] 点击成功: {sel}")
            clicked = True
            time.sleep(2)
            break
        except Exception as e:
            print(f"[step1] {sel} 未找到: {e}")

    if not clicked:
        print("[ERROR] 找不到配送地址入口，请检查页面")
    else:
        # 截图看弹窗内容
        page.screenshot(path="test_address_popup.png")
        print("[step1] 截图已保存: test_address_popup.png")

        # 列出弹窗中所有可见元素
        print("\n[step1] 弹窗中可见的 select/input/button:")
        for sel in ['select', 'input', 'button', '[id*="Country"]', '[id*="country"]',
                    '[id*="GLUXCountry"]', '#GLUXCountryList', '#GLUXZipUpdateInput']:
            try:
                els = page.locator(sel).all()
                for el in els[:3]:
                    try:
                        txt = el.text_content(timeout=1000) or ''
                        id_ = el.get_attribute('id') or ''
                        cls = el.get_attribute('class') or ''
                        vis = el.is_visible()
                        if vis:
                            print(f"  selector={sel}  id={id_}  class={cls[:40]}  text={txt.strip()[:40]}")
                    except Exception:
                        pass
            except Exception:
                pass

        time.sleep(1)
        # 尝试选国家
        try:
            page.wait_for_selector('#GLUXCountryList', timeout=5000)
            options = page.eval_on_selector_all('#GLUXCountryList option', 'els => els.map(o => o.value + "=" + o.text)')
            print("\n[step1] 国家下拉选项（前10）:", options[:10])

            page.select_option('#GLUXCountryList', value='CN')
            print("[step1] 已选择 CN（中国）")
            time.sleep(1)
            page.screenshot(path="test_address_cn_selected.png")
            print("[step1] 截图已保存: test_address_cn_selected.png")

            # 点击确认
            for btn_sel in ['#GLUXLocationUpdateButton .a-button-input',
                            '#GLUXLocationUpdateButton input',
                            '.a-popover-footer .a-button-primary',
                            '#GLUXConfirmClose']:
                try:
                    page.locator(btn_sel).first.click(timeout=2000)
                    print(f"[step1] 确认按钮点击成功: {btn_sel}")
                    time.sleep(2)
                    break
                except Exception:
                    pass

            page.screenshot(path="test_address_done.png")
            print("[step1] 最终截图已保存: test_address_done.png")

            # 读取当前配送地址文字
            for addr_sel in ['#glow-ingress-line1', '#glow-ingress-line2', '#nav-global-location-slot']:
                try:
                    txt = page.locator(addr_sel).first.text_content(timeout=2000)
                    if txt:
                        print(f"[step1] 当前配送地址显示: {addr_sel} => {txt.strip()}")
                except Exception:
                    pass

        except Exception as e:
            print(f"[step1] 未找到国家下拉 #GLUXCountryList: {e}")
            page.screenshot(path="test_address_popup.png")
            print("[step1] 截图已保存，请查看 test_address_popup.png")

    print("\n[DONE] 第一步完成，请查看截图确认页面显示是否正确")
    input("按回车键关闭...")
