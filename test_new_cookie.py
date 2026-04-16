import requests
import json
from bs4 import BeautifulSoup

# 加载新 Cookie
with open('output/cookies_from_browser.json', 'r') as f:
    COOKIES = json.load(f)

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# 加载商户列表
with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
    us_data = json.load(f)

approved = us_data['approved_list']

print("=" * 60)
print(f"测试新 Cookie: PHPSESSID = {COOKIES.get('PHPSESSID', 'N/A')[:30]}...")
print("=" * 60)

# 测试几个 APPROVED 商户
for i, merchant in enumerate(approved[:5]):
    mid = merchant['mid']
    name = merchant['name']
    url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id=12002&page=1'

    print(f"\n[{i+1}] {name} (mid={mid})")

    resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=15)
    print(f"    状态码: {resp.status_code}, 大小: {len(resp.text):,} bytes")

    # 检查是否被重定向
    if 'Login name cannot be empty' in resp.text:
        print(f"    ❌ Cookie 无效")
        break
    elif len(resp.text) < 22000:  # 正常的 brand_detail 页面应该在 80-100KB
        print(f"    ⚠️ 页面太小，可能有问题")
        continue

    # 解析
    import re
    clipboard = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", resp.text)
    asins = re.findall(r'<div class="asin-code">([^<]+)</div>', resp.text)

    print(f"    ✅ Cookie 有效！")
    print(f"    ASIN: {len(asins)}, 投放链接: {len(clipboard)}")

    if asins:
        print(f"    第一个 ASIN: {asins[0]}")
    if clipboard:
        url_clean = clipboard[0].replace("&amp;", "&")
        print(f"    第一个链接: {url_clean[:80]}...")

print("\n" + "=" * 60)
print("测试完成！")
