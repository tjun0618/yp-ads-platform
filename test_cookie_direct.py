"""
在登录后的 Playwright context 中获取 Cookie，然后直接用 requests 测试
"""
import asyncio
import requests
from playwright.async_api import async_playwright
import json

async def get_and_test_cookie():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("请手动登录 YP...")
        await page.goto('https://www.yeahpromos.com/index/login/index', timeout=30000)

        # 等待登录成功（跳转到任何非登录页）
        await page.wait_for_url('**/index/**', timeout=120000)
        print(f"✅ 登录成功！当前 URL: {page.url}")

        # 获取所有 cookies
        cookies = await context.cookies()

        # 找出 PHPSESSID 和其他关键 cookies
        cookies_dict = {}
        for c in cookies:
            cookies_dict[c['name']] = c['value']
            if c['name'] in ['PHPSESSID', 'think_var', 'think_lang']:
                print(f"{c['name']} = {c['value']}")

        # 保存到文件
        with open('output/cookies_fresh.json', 'w') as f:
            json.dump(cookies_dict, f, indent=2)
        print(f"\n已保存 {len(cookies_dict)} 个 cookies 到 output/cookies_fresh.json")

        # 在同一 context 中测试访问 brand_detail
        with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
            us_data = json.load(f)

        approved = us_data['approved_list'][0]  # Amazon US
        mid = approved['mid']
        url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id=12002&page=1'

        print(f"\n在 Playwright 中访问: {approved['name']} (mid={mid})")
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state('networkidle')

        # 截图
        await page.screenshot(path='output/playwright_test.png', full_page=True)
        print("已截图: output/playwright_test.png")

        # 用 Playwright 提取数据
        asins = await page.query_selector_all('div.asin-code')
        print(f"Playwright 解析 ASIN 数量: {len(asins)}")

        # 用 requests 测试同一个 Cookie
        print("\n--- 用 requests 测试同一个 Cookie ---")
        resp = requests.get(url, cookies=cookies_dict, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        print(f"状态码: {resp.status_code}")
        print(f"响应大小: {len(resp.text):,} bytes")

        if 'Login name cannot be empty' in resp.text:
            print("❌ requests 测试失败：被重定向到登录页")
            print("Cookie 请求头检查:")
            headers = {'Cookie': '; '.join([f"{k}={v}" for k, v in cookies_dict.items()])}
            print(headers['Cookie'][:200] + "...")
        else:
            print("✅ requests 测试成功！Cookie 可用")

            # 用 requests 解析
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            asins_req = soup.select('div.asin-code')
            print(f"requests 解析 ASIN 数量: {len(asins_req)}")

            import re
            clipboard = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", resp.text)
            print(f"requests 解析投放链接数量: {len(clipboard)}")

        await asyncio.sleep(5)
        await browser.close()

asyncio.run(get_and_test_cookie())
