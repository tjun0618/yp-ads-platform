#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
用 requests + Cookie 直接请求 export_advert_products 接口，检查返回内容
"""
import requests
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "output"
COOKIE_FILE = OUTPUT_DIR / "cookies_from_browser.json"
BASE_URL = "https://www.yeahpromos.com"
SITE_ID = "12002"

# 读取 Cookie
cookie_val = None
if COOKIE_FILE.exists():
    with open(COOKIE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        for c in data:
            if c.get("name") == "PHPSESSID":
                cookie_val = c.get("value")
                break
    elif isinstance(data, dict):
        cookie_val = data.get("PHPSESSID") or data.get("value")

print(f"PHPSESSID: {cookie_val[:10]}..." if cookie_val else "❌ 未找到 Cookie")

# 也尝试通过 CDP 直接拿 Cookie
try:
    import urllib.request
    resp = urllib.request.urlopen("http://localhost:9222/json", timeout=3)
    tabs = json.loads(resp.read())
    print(f"\nChrome 当前 Tab 数: {len(tabs)}")
    for t in tabs[:3]:
        print(f"  [{t.get('type','')}] {t.get('url','')[:80]}")
except Exception as e:
    print(f"CDP 查询失败: {e}")

if not cookie_val:
    print("\n⚠️ 无法获取 Cookie，尝试使用 CDP 拿 Cookie...")
    # 尝试 CDP 接口
    try:
        import urllib.request
        # 获取 Storage Cookies
        req_data = json.dumps({
            "id": 1,
            "method": "Network.getAllCookies"
        }).encode()
        # 获取第一个 Tab 的 websocket
        resp = urllib.request.urlopen("http://localhost:9222/json", timeout=3)
        tabs = json.loads(resp.read())
        yp_tab = next((t for t in tabs if "yeahpromos" in t.get("url", "")), tabs[0] if tabs else None)
        if yp_tab:
            print(f"  目标 Tab: {yp_tab.get('url','')[:80]}")
    except Exception as e:
        print(f"CDP: {e}")
    print("\n请提供 Chrome 中 yeahpromos.com 的 PHPSESSID Cookie 值")
    exit(1)

# 测试几个出错的商户
test_mids = [
    ("366088", "LICORNE"),
    ("366089", "LIFE SKY"),
    ("366096", "LITTMA"),
]

session = requests.Session()
session.cookies.set("PHPSESSID", cookie_val, domain="www.yeahpromos.com")
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.yeahpromos.com/index/offer/brands",
})

for mid, name in test_mids:
    print(f"\n{'='*50}")
    print(f"商户: {name} (mid={mid})")

    # 先访问商户页，找到 export 链接
    brand_url = f"{BASE_URL}/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}"
    r = session.get(brand_url, timeout=20)
    print(f"  brand_detail 状态码: {r.status_code}")

    import re
    export_links = re.findall(r'href="([^"]*export_advert_products[^"]*)"', r.text)
    print(f"  找到 export 链接: {export_links}")

    if not export_links:
        # 也找 JS 里的
        export_links = re.findall(r"'([^']*export_advert_products[^']*)'", r.text)
        print(f"  JS 中的 export 链接: {export_links}")

    if export_links:
        export_url = BASE_URL + export_links[0] if export_links[0].startswith("/") else export_links[0]
        print(f"  请求: {export_url}")
        dr = session.get(export_url, timeout=30, allow_redirects=True)
        print(f"  响应状态: {dr.status_code}")
        print(f"  Content-Type: {dr.headers.get('Content-Type', '?')}")
        print(f"  Content-Length: {dr.headers.get('Content-Length', '?')}")
        content = dr.content
        print(f"  实际大小: {len(content)} bytes")
        print(f"  文件头(hex): {content[:20].hex()}")

        if content[:2] == b'PK':
            print("  ✅ 真正的 xlsx (ZIP 格式)")
        elif content[:1] == b'<':
            print("  ❌ HTML/XML 内容！")
            print(f"  内容: {dr.text[:300]}")
        elif len(content) == 0:
            print("  ❌ 空文件！")
        else:
            print(f"  ❓ 未知: {repr(content[:50])}")
