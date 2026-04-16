#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拦截 YP 下载请求，分析真实的 HTTP 请求结构
"""
import time, json
from playwright.sync_api import sync_playwright

MID     = "363722"
SITE_ID = "12002"
URL     = f"https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={MID}&site_id={SITE_ID}"

captured = []

def handle_request(request):
    if "export" in request.url or "download" in request.url:
        captured.append({
            "url":    request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
        })
        print(f"\n🎯 拦截到请求!")
        print(f"  URL:    {request.url}")
        print(f"  Method: {request.method}")
        print(f"  Headers: {json.dumps(dict(request.headers), indent=2)}")
        if request.post_data:
            print(f"  POST: {request.post_data}")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    ctx  = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    # 监听所有请求
    page.on("request", handle_request)

    print(f"打开页面...")
    page.goto(URL, timeout=30000, wait_until="domcontentloaded")
    time.sleep(2)

    # 直接用 JavaScript 点击下载按钮（强制，绕过遮挡）
    print("用 JS 点击下载按钮...")
    result = page.evaluate("""
        () => {
            const links = document.querySelectorAll('a');
            for (const a of links) {
                if (a.href && (a.href.includes('export') || a.href.includes('download'))) {
                    console.log('Found:', a.href, a.textContent);
                    // 不实际点击，先返回 href
                    return {href: a.href, text: a.textContent.trim()};
                }
            }
            return null;
        }
    """)
    print(f"JS 找到链接: {result}")

    if result and result.get("href"):
        href = result["href"]
        print(f"\n直接访问下载链接: {href}")
        # 新建页面访问，监听响应
        page2 = ctx.new_page()
        page2.on("request", handle_request)

        resp = page2.goto(href, timeout=30000)
        time.sleep(2)
        print(f"响应状态: {resp.status if resp else 'None'}")
        if resp:
            ct = resp.headers.get("content-type","")
            cl = resp.headers.get("content-length","?")
            print(f"Content-Type: {ct}")
            print(f"Content-Length: {cl}")
            print(f"URL: {resp.url}")
        page2.close()

    print(f"\n共拦截到 {len(captured)} 个 export/download 请求")
    for c in captured:
        print(json.dumps(c, indent=2))
