"""
启动一个浏览器，等用户手动登录后导出 cookies
"""
import asyncio
from playwright.async_api import async_playwright

async def export_cookies():
    async with async_playwright() as p:
        # 启动浏览器并使用用户数据目录（可以复用现有浏览器）
        browser = await p.chromium.launch_persistent_context(
            user_data_dir='./yp_browser_data',
            headless=False,
            viewport={'width': 1280, 'height': 720}
        )

        pages = browser.pages
        page = pages[0] if pages else await browser.new_page()

        # 打开 YP
        await page.goto('https://www.yeahpromos.com/index/login/index', timeout=30000)

        print("浏览器已打开，请在窗口中登录 YP...")
        print("登录成功后，按 Ctrl+C 停止脚本（脚本会自动保存 cookies）")

        # 等待用户登录（不超时）
        try:
            await page.wait_for_url('**/index/**', timeout=0)  # 无限等待
        except:
            pass  # 用户手动终止

        # 保存 cookies
        cookies = await browser.cookies()

        import json
        cookies_dict = {c['name']: c['value'] for c in cookies}
        with open('output/cookies_from_browser.json', 'w') as f:
            json.dump(cookies_dict, f, indent=2)

        print(f"\n✅ 已保存 {len(cookies)} 个 cookies 到 output/cookies_from_browser.json")

        # 导出 ASIN
        for c in cookies:
            if c['name'] in ['PHPSESSID']:
                print(f"{c['name']} = {c['value']}")

        await asyncio.sleep(3)
        await browser.close()

asyncio.run(export_cookies())
