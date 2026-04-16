import requests
import json
from bs4 import BeautifulSoup

COOKIES = {"PHPSESSID": "e0e843912927091a065576783f332db5"}
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

with open('output/merchants_mid_list.json', 'r', encoding='utf-8') as f:
    merchants = json.load(f)

unapplied_us = [m for m in merchants if 'United States' in m.get('country', '') and m.get('status') == 'UNAPPLIED']
approved_us = [m for m in merchants if 'United States' in m.get('country', '') and m.get('status') == 'APPROVED']

def test_merchant(merchant):
    mid = merchant['mid']
    name = merchant['name']
    url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id=12002&page=1'
    print(f"\n--- {name} (mid={mid}, status={merchant['status']}) ---")

    resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=15)
    print(f"状态码: {resp.status_code}, 大小: {len(resp.text)} bytes")

    # 判断是否被重定向到登录页
    if 'Login name cannot be empty' in resp.text or 'login/index' in resp.url:
        print("❌ Cookie 无效，被重定向到登录页！")
        return -1, -1

    soup = BeautifulSoup(resp.text, 'html.parser')
    asins = soup.select('div.asin-code')
    links = soup.select('a[href*="openurlproduct"]')

    print(f"✅ Cookie 有效！ASIN 数量: {len(asins)}, 投放链接数量: {len(links)}")

    if asins:
        print(f"   第一个 ASIN: {asins[0].get_text(strip=True)}")
    if links:
        print(f"   第一个链接: {links[0].get('href','')[:120]}")

    # 分页总数
    last_page_el = soup.select_one('.layui-laypage-last')
    if last_page_el:
        print(f"   总页数: {last_page_el.get_text(strip=True)}")

    return len(asins), len(links)

print("=== Cookie 有效性验证 ===")
# 先测一个 APPROVED 确认 Cookie 有效
r = test_merchant(approved_us[0])
if r[0] == -1:
    print("\n⛔ Cookie 已过期，请重新登录获取新 PHPSESSID")
else:
    print("\n=== 测试 UNAPPLIED 商户 ===")
    for m in unapplied_us[:3]:
        test_merchant(m)

    print("\n=== 测试 APPROVED 商户 (再验证2个) ===")
    for m in approved_us[1:3]:
        test_merchant(m)
