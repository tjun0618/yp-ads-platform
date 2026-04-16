# -*- coding: utf-8 -*-
"""
探测语言设置页结构，找到「已选英语」的单选按钮，并完成保存
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CHROME_WS)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 直接访问语言设置页
    PREF_URL = 'https://www.amazon.com/customer-preferences/edit?ie=UTF8&preferencesReturnUrl=%2F&ref_=topnav_lang_ais'
    print(f"[1] 访问语言设置页: {PREF_URL}")
    try:
        page.goto(PREF_URL, wait_until='domcontentloaded', timeout=20000)
    except Exception as e:
        print(f"  超时（继续）: {e}")
    time.sleep(3)

    # 获取所有语言选项
    lang_options = page.evaluate("""
    () => {
        const out = [];
        // 找语言单选按钮
        for (const radio of document.querySelectorAll('input[name*="language"], input[type="radio"]')) {
            const label = document.querySelector('label[for="' + radio.id + '"]');
            const labelText = label ? label.textContent.trim().substring(0, 80) : '';
            out.push({
                id: radio.id,
                name: radio.name,
                value: radio.value,
                checked: radio.checked,
                labelText,
            });
        }
        // 找语言相关的 <span> 或 <div> 中的文字
        if (out.length === 0) {
            for (const el of document.querySelectorAll('[class*="icp-language"]')) {
                out.push({tag: el.tagName, cls: el.className, text: el.textContent.trim().substring(0,100)});
            }
        }
        return out;
    }
    """)

    print("\n[2] 语言选项（单选按钮）：")
    for opt in lang_options:
        checked_str = "✅ CHECKED" if opt.get('checked') else "  "
        print(f"  {checked_str} id={opt.get('id',''):<20} value={opt.get('value',''):<20} label={opt.get('labelText','')[:50]}")

    # 找 Save 按钮
    save_btns = page.evaluate("""
    () => {
        const out = [];
        for (const el of document.querySelectorAll('input[type="submit"], button[type="submit"], .a-button-primary input, #icp-btn-save, [id*="save"]')) {
            const rect = el.getBoundingClientRect();
            out.push({tag: el.tagName, id: el.id, value: el.value || '', text: el.textContent.trim().substring(0,50), visible: rect.width > 0});
        }
        return out;
    }
    """)
    print("\n[3] 保存按钮：")
    for btn in save_btns:
        print(f"  tag={btn['tag']:<8} id={btn['id']:<20} value={btn['value']:<20} text={btn['text']}")

    # 尝试找 English 的单选，如果已选中就直接 Save；如果未选中就先选再 Save
    print("\n[4] 尝试确认英语已选并点击 Save...")
    
    # 找 en_US 或 English 的 radio
    en_radio = page.evaluate("""
    () => {
        for (const radio of document.querySelectorAll('input[type="radio"]')) {
            if (radio.value.includes('en_US') || radio.value.includes('en-US') || radio.value === 'en') {
                return {id: radio.id, value: radio.value, checked: radio.checked};
            }
            const label = document.querySelector('label[for="' + radio.id + '"]');
            const labelText = label ? label.textContent.trim() : '';
            if (labelText.toLowerCase().startsWith('english')) {
                return {id: radio.id, value: radio.value, checked: radio.checked, labelText};
            }
        }
        return null;
    }
    """)

    if en_radio:
        print(f"  找到英语单选: {en_radio}")
        if not en_radio.get('checked'):
            try:
                page.click(f'#{ en_radio["id"] }', timeout=3000)
                print("  已点击英语选项")
                time.sleep(1)
            except Exception as e:
                print(f"  点击英语选项失败: {e}")
        else:
            print("  英语已是选中状态，无需切换")
    else:
        print("  未找到英语单选按钮")

    # 尝试点击 Save
    for save_sel in ['#icp-btn-save input', '#icp-btn-save', 'input[id*="save"]', '.a-button-primary input[type="submit"]']:
        try:
            page.locator(save_sel).first.click(timeout=3000)
            print(f"  Save 按钮点击成功: {save_sel}")
            time.sleep(3)
            print(f"  保存后 URL: {page.url}")
            break
        except Exception:
            pass

    print("\n[完成]")
