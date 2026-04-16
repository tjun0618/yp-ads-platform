#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用 Playwright 拦截真实请求头（含Cookie），然后用 requests 重放下载
测试单个商户
"""
import time, json, io
from pathlib import Path
from playwright.sync_api import sync_playwright

MID     = "363722"
SITE_ID = "12002"
OUT     = Path(r"c:\Users\wuhj\WorkBuddy\20260322085355")

captured_headers = {}

def on_request(req):
    if "export_advert_products" in req.url:
        captured_headers.update(dict(req.headers))
        print(f"拦截到真实请求头:")
        for k, v in req.headers.items():
            print(f"  {k}: {v[:80]}")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx  = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    # 监听请求
    page.on("request", on_request)

    # 打开 brand_detail 页面
    brand_url = f"https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={MID}&site_id={SITE_ID}"
    page.goto(brand_url, timeout=30000, wait_until="domcontentloaded")
    time.sleep(2)

    # 用 expect_download 监听下载，然后用 JS 触发点击
    try:
        with page.expect_download(timeout=30000) as dl_info:
            page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a'));
                    const dl = links.find(a => a.href && a.href.includes('export_advert_products'));
                    if (dl) dl.click();
                }
            """)
        dl = dl_info.value
        print(f"\n✅ 下载成功!")
        print(f"  文件名: {dl.suggested_filename}")
        save_path = str(OUT / "test_download.xlsx")
        dl.save_as(save_path)
        size = Path(save_path).stat().st_size
        print(f"  保存到: {save_path} ({size} bytes)")

        # 解析 Excel
        import openpyxl
        wb = openpyxl.load_workbook(save_path, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        print(f"  行数: {len(rows)}")
        if rows:
            print(f"  标题行: {rows[0]}")
        if len(rows) > 1:
            print(f"  第1行: {rows[1]}")
        wb.close()
    except Exception as e:
        print(f"下载失败: {e}")

    # 保存请求头供后续使用
    if captured_headers:
        (OUT / "yp_to_feishu/output/yp_request_headers.json").write_text(
            json.dumps(captured_headers, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n请求头已保存 → output/yp_request_headers.json")
