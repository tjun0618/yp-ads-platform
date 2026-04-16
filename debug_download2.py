#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用 Playwright 连接 Chrome，手动触发一次下载，保留文件查看真实内容
"""
import os, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

SCRIPT_DIR = Path(__file__).parent.resolve()
DEBUG_DIR = SCRIPT_DIR / "output" / "downloads_debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.yeahpromos.com"
SITE_ID = "12002"

# 用已知"有下载按钮但解析失败"的商户
TEST_CASES = [
    ("366088", "LICORNE"),
    ("366089", "LIFE SKY"),
]

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    for mid, name in TEST_CASES:
        print(f"\n{'='*55}")
        print(f"商户: {name} (mid={mid})")
        url = f"{BASE_URL}/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}"

        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(2)

        # 检查是否有下载按钮
        btn_href = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const dl = links.find(a => a.href && a.href.includes('export_advert_products'));
                return dl ? dl.outerHTML : null;
            }
        """)
        print(f"  按钮 HTML: {btn_href}")

        if not btn_href:
            print("  → 无下载按钮，跳过")
            continue

        # 触发下载，保存文件
        save_path = str(DEBUG_DIR / f"debug_{mid}.bin")
        try:
            with page.expect_download(timeout=20000) as dl_info:
                page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a'));
                        const dl = links.find(a => a.href && a.href.includes('export_advert_products'));
                        if (dl) dl.click();
                    }
                """)
            dl = dl_info.value
            print(f"  下载文件名(建议): {dl.suggested_filename}")
            dl.save_as(save_path)
            size = os.path.getsize(save_path)
            print(f"  文件大小: {size} bytes")

            with open(save_path, 'rb') as f:
                header = f.read(50)
            print(f"  头部 hex: {header.hex()}")

            if header[:2] == b'PK':
                print("  ✅ 真正的 xlsx")
            elif header[:1] == b'<':
                print("  ❌ 是 HTML！内容:")
                with open(save_path, encoding='utf-8', errors='ignore') as f:
                    print(f.read(400))
            elif size == 0:
                print("  ❌ 空文件")
            else:
                print(f"  ❓ 未知: {repr(header)}")

        except Exception as e:
            print(f"  异常: {type(e).__name__}: {e}")
