"""
在已登录的 Playwright context 中直接测试 brand_detail 页面
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def test_with_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 加载已保存的 cookies
        with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
            us_data = json.load(f)
        
        # 手动登录 YP
        print("正在打开 YP 登录页...")
        await page.goto('https://www.yeahpromos.com/index/login/index', timeout=30000)
        
        print("请在弹出的浏览器窗口中登录...")
        # 等待登录后跳转
        await page.wait_for_url('**/index/index/**', timeout=120000)
        print("✅ 登录成功！")
        
        # 获取所有已登录的 cookies
        cookies = await context.cookies()
        print(f"登录后 cookies: {len(cookies)} 个")
        
        # 测试一个 APPROVED 商户
        approved_us = us_data['approved_list']
        merchant = approved_us[0]  # Amazon US
        mid = merchant['mid']
        name = merchant['name']
        
        url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id=12002&page=1'
        print(f"\n正在测试: {name} (mid={mid})")
        print(f"URL: {url}")
        
        await page.goto(url, timeout=30000)
        await page.wait_for_load_state('networkidle')
        
        # 截图
        await page.screenshot(path='output/test_approved_merchant.png', full_page=True)
        print("已截图: output/test_approved_merchant.png")
        
        # 检查页面内容
        asin_elements = await page.query_selector_all('div.asin-code')
        link_elements = await page.query_selector_all('a[href*="openurlproduct"]')
        
        print(f"\nASIN 数量: {len(asin_elements)}")
        print(f"投放链接数量: {len(link_elements)}")
        
        if asin_elements:
            first_asin = await asin_elements[0].text_content()
            print(f"第一个 ASIN: {first_asin.strip()}")
        
        if link_elements:
            first_link = await link_elements[0].get_attribute('href')
            print(f"第一个链接: {first_link[:120]}...")
        
        # 测试 UNAPPLIED 商户
        unapplied_us = us_data['unapplied_list']
        merchant2 = unapplied_us[0]
        mid2 = merchant2['mid']
        name2 = merchant2['name']
        
        url2 = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid2}&site_id=12002&page=1'
        print(f"\n正在测试: {name2} (mid={mid2}, status=UNAPPLIED)")
        
        await page.goto(url2, timeout=30000)
        await page.wait_for_load_state('networkidle')
        await page.screenshot(path='output/test_unapplied_merchant.png', full_page=True)
        print("已截图: output/test_unapplied_merchant.png")
        
        asin2 = await page.query_selector_all('div.asin-code')
        link2 = await page.query_selector_all('a[href*="openurlproduct"]')
        
        print(f"ASIN 数量: {len(asin2)}, 投放链接数量: {len(link2)}")
        
        # 获取页码信息
        last_page = await page.query_selector('.layui-laypage-last')
        if last_page:
            total_pages = await last_page.text_content()
            print(f"总页数: {total_pages.strip()}")
        
        # 提示保持浏览器打开
        print("\n浏览器将保持打开 10 秒以便检查...")
        await asyncio.sleep(10)
        
        await browser.close()

asyncio.run(test_with_playwright())
