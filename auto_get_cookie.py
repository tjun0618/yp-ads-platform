"""
自动登录 YP 平台并获取新的 PHPSESSID Cookie
"""
import asyncio
from playwright.async_api import async_playwright
import json

async def get_new_cookie():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # 有界面，方便看验证码
        context = await browser.new_context()
        page = await context.new_page()
        
        print("正在打开 YP 登录页...")
        await page.goto('https://www.yeahpromos.com/index/login/index', timeout=30000)
        await page.wait_for_load_state('networkidle')
        
        # 截图看一下页面
        await page.screenshot(path='output/yp_login_page.png')
        print("已截图：output/yp_login_page.png")
        
        # 获取当前 cookies（未登录状态）
        cookies = await context.cookies()
        print(f"当前 cookies: {cookies}")
        
        # 等待用户手动登录（30秒内）
        print("\n请在弹出的浏览器窗口中手动登录...")
        print("登录完成后会自动获取新 Cookie")
        
        # 等待页面跳转到登录后的页面
        try:
            await page.wait_for_url('**/index/index/**', timeout=60000)
            print("检测到登录成功！")
        except:
            # 也许 URL 不变，检查 PHPSESSID
            await asyncio.sleep(5)
        
        # 获取登录后的 cookies
        cookies_after = await context.cookies()
        print(f"\n登录后 cookies 数量: {len(cookies_after)}")
        
        phpsessid = None
        for c in cookies_after:
            print(f"  {c['name']} = {c['value'][:30]}...")
            if c['name'] == 'PHPSESSID':
                phpsessid = c['value']
        
        if phpsessid:
            print(f"\n✅ 获取到新 PHPSESSID: {phpsessid}")
            # 保存到文件
            with open('output/new_phpsessid.txt', 'w') as f:
                f.write(phpsessid)
            print("已保存到 output/new_phpsessid.txt")
        else:
            print("❌ 未找到 PHPSESSID，请确认已登录")
        
        await browser.close()
        return phpsessid

asyncio.run(get_new_cookie())
