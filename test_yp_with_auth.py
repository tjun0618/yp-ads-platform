"""
YP 平台商家数据采集测试（带登录认证）
使用浏览器自动化获取登录后的 cookie
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def login_and_get_cookies():
    """登录 YP 平台并获取 cookies"""

    print("=" * 60)
    print("YP 平台登录")
    print("=" * 60)
    print()

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # 启动浏览器（有头模式，方便用户登录）
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()

        print("正在打开 YP 登录页面...")
        print()

        # 打开登录页面
        page = await context.new_page()
        await page.goto("https://yeahpromos.com/index/login/login")

        print("请在浏览器中完成登录:")
        print("  1. 输入用户名和密码")
        print("  2. 完成验证码")
        print("  3. 点击登录按钮")
        print()
        print("登录成功后，请在命令行按回车键继续...")
        print()

        # 等待用户登录
        input("按回车键继续...")

        # 获取 cookies
        cookies = await context.cookies()

        # 检查是否登录成功（访问需要认证的页面）
        test_page = await context.new_page()
        await test_page.goto("https://yeahpromos.com/index/tools/select")

        page_title = await test_page.title()
        print(f"页面标题: {page_title}")

        # 如果页面重定向到登录页，说明登录失败
        if "login" in page_title.lower() or "login" in test_page.url.lower():
            print("ERROR: 登录失败，请重试")
            await browser.close()
            return None

        # 保存 cookies
        cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}

        print(f"成功获取 {len(cookies)} 个 cookies")

        # 保存 cookies 到文件
        output_dir = project_root / "output"
        output_dir.mkdir(exist_ok=True)

        cookies_file = output_dir / "yp_cookies.json"
        with open(cookies_file, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"Cookies 已保存到: {cookies_file}")
        print()

        await browser.close()

        return cookies_dict


def test_yp_collection_with_cookies(cookies_dict):
    """使用 cookies 测试 YP 商家数据采集"""

    print("=" * 60)
    print("YP 平台商家数据采集测试（使用认证）")
    print("=" * 60)
    print()

    from src.yp_api.merchant_collector import YPMerchantCollector

    # 初始化采集器
    collector = YPMerchantCollector(
        api_base="https://yeahpromos.com",
        api_endpoint="/index/getadvert/getadvert",
        rate_limit=10,
        timeout=30,
        retry_times=3
    )

    # 设置 cookies
    collector.session.cookies.update(cookies_dict)

    try:
        print("[1/2] 开始采集商家数据...")
        print()

        # 获取商家数据
        merchants = collector.get_all_merchants(
            start_page=1,
            max_pages=1  # 先只测试第一页
        )

        print()
        print(f"SUCCESS: 成功采集 {len(merchants)} 个商家")
        print()

        if merchants:
            print("[2/2] 显示前 3 个商家信息:")
            print()

            for i, merchant in enumerate(merchants[:3], 1):
                print(f"商家 {i}:")
                print(f"  ID: {merchant.merchant_id}")
                print(f"  名称: {merchant.merchant_name}")
                print(f"  佣金率: {merchant.commission_rate}")
                print(f"  追踪链接: {merchant.tracking_link[:60]}...")
                print()

            # 保存数据到文件
            output_dir = project_root / "output"
            output_file = output_dir / f"merchants_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump([m.to_dict() for m in merchants], f, indent=2, ensure_ascii=False)

            print(f"SUCCESS: 数据已保存到: {output_file}")
            print()
        else:
            print("WARNING: 未采集到商家数据")
            print("可能原因:")
            print("  1. Cookies 已过期")
            print("  2. API 端点不正确")
            print("  3. 网络连接问题")
            print()

        return len(merchants) > 0

    except Exception as e:
        print(f"ERROR: 采集失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        collector.close()


async def main():
    """主函数"""

    # 步骤 1: 登录并获取 cookies
    cookies = await login_and_get_cookies()

    if not cookies:
        print("=" * 60)
        print("ERROR: 无法获取登录凭证")
        print("=" * 60)
        return

    # 步骤 2: 使用 cookies 采集数据
    success = test_yp_collection_with_cookies(cookies)

    print("=" * 60)
    if success:
        print("SUCCESS: 测试通过！可以继续下一步")
        print()
        print("下一步:")
        print("  1. 查看 output/ 目录下的商家数据")
        print("  2. 确认数据正确后，运行完整采集流程")
    else:
        print("ERROR: 测试失败，请检查错误信息")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
