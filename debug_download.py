#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试：手动触发一次下载，看文件真实内容
"""
import os, time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
DOWNLOAD_DIR = str(SCRIPT_DIR / "output" / "downloads_debug")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 用日志里出现过 "File is not a zip file" 的商户
TEST_MID = "366088"  # LICORNE
TEST_MID2 = "366089"  # LIFE SKY
BASE_URL = "https://www.yeahpromos.com"
SITE_ID = "12002"

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    for mid in [TEST_MID, TEST_MID2]:
        print(f"\n{'='*50}")
        print(f"测试商户 mid={mid}")
        url = f"{BASE_URL}/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}"
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        time.sleep(2)

        # 检查登录状态
        html = page.content()
        if "Login" in html and "login" in page.url.lower():
            print("  ❌ 未登录！")
            break

        # 检查下载按钮
        has_btn = page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const dl = links.find(a => a.href && a.href.includes('export_advert_products'));
                return dl ? dl.href : null;
            }
        """)
        print(f"  下载按钮 href: {has_btn}")

        if not has_btn:
            print("  无下载按钮，跳过")
            continue

        # 触发下载，保留文件
        save_path = os.path.join(DOWNLOAD_DIR, f"debug_{mid}.xlsx")
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
            dl.save_as(save_path)
            size = os.path.getsize(save_path)
            print(f"  文件大小: {size} bytes")

            # 读前 20 字节判断文件类型
            with open(save_path, 'rb') as f:
                header = f.read(20)
            print(f"  文件头(hex): {header.hex()}")
            print(f"  文件头(str): {repr(header)}")

            # 尝试判断
            if header.startswith(b'PK'):
                print("  ✅ 是真正的 xlsx (ZIP格式)")
            elif header.startswith(b'<'):
                print("  ❌ 是 HTML/XML 文件！（可能是错误页）")
                # 打印前500字符
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(500)
                print(f"  内容预览:\n{content}")
            else:
                print(f"  ❓ 未知格式")
                with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                    print(f.read(300))

        except Exception as e:
            print(f"  下载异常: {type(e).__name__}: {e}")
