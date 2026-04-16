#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查 brand_detail 页面的下载按钮结构
优先用 requests 直接获取，不占 Chrome
"""
import re, json, time, os
from pathlib import Path

# ── 方法1：用 requests + PHPSESSID 直接获取（不需要 Playwright）──────────────
# 先尝试从浏览器抓 Cookie，找 PHPSESSID
# 用方法2（Playwright）备用

# 先用 Playwright 获取 Cookie 和 HTML
from playwright.sync_api import sync_playwright

MID     = "363722"   # Aerotrunk，已确认有商品
SITE_ID = "12002"
URL     = f"https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={MID}&site_id={SITE_ID}"
OUT_DIR = Path(r"c:\Users\wuhj\WorkBuddy\20260322085355")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx  = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    print(f"打开: {URL}")
    page.goto(URL, timeout=30000, wait_until="domcontentloaded")
    time.sleep(3)
    print(f"当前URL: {page.url}")

    # 获取 HTML
    html = page.content()
    (OUT_DIR / "brand_detail_check.html").write_text(html, encoding="utf-8")
    print(f"HTML 长度: {len(html)} chars → 已保存 brand_detail_check.html")

    # 打印所有按钮
    btns = page.query_selector_all("a, button")
    print(f"\n=== 页面 a/button 共 {len(btns)} 个 ===")
    for b in btns:
        try:
            txt     = (b.inner_text() or "").strip()[:60]
            href    = b.get_attribute("href") or ""
            cls     = b.get_attribute("class") or ""
            onclick = b.get_attribute("onclick") or ""
            tag     = b.evaluate("el => el.tagName")
            if txt or href:
                print(f"  [{tag}] text={txt!r:40} href={href[:70]}")
        except Exception:
            pass

    # 找 download/export/excel 的 href
    dl_hrefs = re.findall(r'href=["\']([^"\']*(?:export|download|excel)[^"\']*)["\']', html, re.IGNORECASE)
    print(f"\n=== href 含 export/download/excel ({len(dl_hrefs)}) ===")
    for h in dl_hrefs[:15]:
        print(" ", h)

    # 打印 "Download" 文字附近 HTML（最关键）
    idx = html.find("Download")
    if idx > -1:
        snippet = html[max(0, idx-200):idx+300]
        print(f"\n=== 'Download' 附近 HTML ===\n{snippet}")

    # 获取 Cookie
    cookies = ctx.cookies()
    sess = next((c for c in cookies if c["name"] == "PHPSESSID"), None)
    if sess:
        print(f"\n=== PHPSESSID: {sess['value'][:20]}... ===")
        # 保存供后续 requests 使用
        (OUT_DIR / "yp_to_feishu/output/yp_cookie.json").write_text(
            json.dumps({"PHPSESSID": sess["value"]}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print("Cookie 已保存 → output/yp_cookie.json")
