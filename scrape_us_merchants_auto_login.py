"""
用 Playwright 批量抓取 APPROVED US 商户
特点：自动检测登录状态、定期重新登录、断点续传
"""
import asyncio
import json
import time
import re
from playwright.async_api import async_playwright
from datetime import datetime
from pathlib import Path

# 配置
SITE_ID = "12002"
STATE_FILE = "output/scrape_state_auto.json"
OUTPUT_FILE = "output/us_merchants_products.json"
MAX_RETRIES = 3

def load_state():
    """加载断点状态"""
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed_mids": [], "failed_mids": [], "products": [], "last_updated": None}

def save_state(state):
    """保存断点状态"""
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def parse_brand_detail(html, mid, merchant_name):
    """解析 brand_detail 页面"""
    asin_pattern = r'<div class="asin-code">([^<]+)</div>'
    asins = re.findall(asin_pattern, html)

    link_pattern = r"ClipboardJS\.copy\('([^']+)'\)"
    links = re.findall(link_pattern, html)
    links = [link.replace("&amp;", "&") for link in links]

    products = []
    for i, asin in enumerate(asins):
        if i < len(links):
            link = links[i]
            track = re.search(r'track=([^&]+)', link)
            pid = re.search(r'pid=(\d+)', link)

            # 尝试提取商品名
            name_pattern = rf'<div class="asin-code">{re.escape(asin)}</div>\s*<div[^>]*class="[^"]*product-name[^"]*"[^>]*>([^<]+)</div>'
            name_match = re.search(name_pattern, html, re.MULTILINE | re.DOTALL)
            product_name = name_match.group(1).strip() if name_match else f"Product {asin}"

            products.append({
                "asin": asin,
                "merchant_id": mid,
                "merchant_name": merchant_name,
                "product_name": product_name,
                "track": track.group(1) if track else None,
                "pid": pid.group(1) if pid else None,
                "tracking_url": link if track and pid else None,
                "scraped_at": datetime.now().isoformat()
            })

    return products

async def check_login(page):
    """检查是否已登录"""
    try:
        # 访问首页或任意已登录页面
        await page.goto('https://www.yeahpromos.com/index/advert/index', timeout=15000)
        content = await page.content()
        return 'Login name cannot be empty' not in content
    except:
        return False

async def login(page):
    """登录"""
    print("\n" + "=" * 60)
    print("=== 正在打开 YP 登录页 ===")
    print("=" * 60)

    # 修正 URL
    await page.goto('https://www.yeahpromos.com/index/login/login', timeout=30000)

    print("\n请手动登录：")
    print("1. 在弹出的浏览器窗口中输入账号密码")
    print("2. 完成验证码（如有）")
    print("3. 登录成功后，回到【这个命令行窗口】按 Enter 键继续")
    print("\n⚠️ 脚本会无限等待，直到你按 Enter 键...")

    # 等待用户按 Enter 继续
    input()

    # 验证是否登录成功
    current_url = page.url
    print(f"\n浏览器当前页面: {current_url}")

    # 如果还在登录页，提示
    if 'login' in current_url.lower():
        print("⚠️ 检测到你还在登录页，请先登录！")
        print("登录完成后，回到这里按 Enter 继续...")
        input()

    # 等待页面加载
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

    print("✅ 登录确认完成，开始抓取...")

async def scrape_merchant(page, mid, merchant_name, retry_count=0):
    """抓取单个商户"""
    url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page=1'
    await page.goto(url, timeout=30000)
    await page.wait_for_load_state('networkidle')

    # 检查登录状态
    content = await page.content()
    if 'Login name cannot be empty' in content:
        print("  ⚠️ Session 失效，需要重新登录")
        return None

    # 获取总页数
    last_page_el = await page.query_selector('.layui-laypage-last')
    total_pages = 1
    if last_page_el:
        total_pages = int((await last_page_el.text_content()).strip())

    print(f"  共 {total_pages} 页")

    all_products = []

    for page_num in range(1, total_pages + 1):
        if page_num > 1:
            url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page={page_num}'
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle')

        html = await page.content()

        # 再次检查登录
        if 'Login name cannot be empty' in html:
            print(f"  ❌ 第 {page_num} 页时 session 失效")
            return None

        products = parse_brand_detail(html, mid, merchant_name)
        all_products.extend(products)

        print(f"  第 {page_num}/{total_pages} 页: {len(products)} 条")

        await asyncio.sleep(0.5)

    return all_products

async def main():
    # 加载商户列表
    with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
        us_data = json.load(f)

    approved_merchants = us_data['approved_list']
    print(f"待抓取商户: {len(approved_merchants)}")

    # 加载状态
    state = load_state()
    completed_mids = set(state.get('completed_mids', []))
    failed_mids = set(state.get('failed_mids', []))
    all_products = state.get('products', [])

    print(f"已完成: {len(completed_mids)}, 失败: {len(failed_mids)}, 已抓商品: {len(all_products)}")

    pending_merchants = [m for m in approved_merchants if m['mid'] not in completed_mids]
    print(f"待处理: {len(pending_merchants)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 首次登录
        await login(page)

        merchant_count = 0

        for idx, merchant in enumerate(pending_merchants):
            mid = merchant['mid']
            name = merchant['name']

            print(f"\n[{idx+1}/{len(pending_merchants)}] {name} (mid={mid})")

            # 定期检查并重新登录（每 50 个商户）
            if merchant_count > 0 and merchant_count % 50 == 0:
                print(f"\n=== 已抓取 {merchant_count} 个商户，检查登录状态 ===")
                is_logged = await check_login(page)
                if not is_logged:
                    await login(page)

            # 抓取商户
            products = await scrape_merchant(page, mid, name)

            if products:
                all_products.extend(products)
                completed_mids.add(mid)
                merchant_count += 1

                print(f"✅ 成功: {len(products)} 条")

                # 更新状态
                state['completed_mids'] = list(completed_mids)
                state['products'] = all_products
                save_state(state)
            else:
                # 失败：可能是 session 失效
                print(f"❌ 失败，尝试重新登录后重试...")

                # 重新登录
                await login(page)

                # 重试一次
                products = await scrape_merchant(page, mid, name)
                if products:
                    all_products.extend(products)
                    completed_mids.add(mid)
                    merchant_count += 1
                    state['completed_mids'] = list(completed_mids)
                    state['products'] = all_products
                    save_state(state)
                    print(f"✅ 重试成功: {len(products)} 条")
                else:
                    print(f"❌ 重试失败")
                    failed_mids.add(mid)
                    state['failed_mids'] = list(failed_mids)
                    save_state(state)

            # 保存进度
            if merchant_count % 100 == 0:
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, ensure_ascii=False, indent=2)
                print(f"📁 已保存 {len(all_products)} 条商品到文件")

            await asyncio.sleep(1)

        # 最终保存
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

        await browser.close()

    print(f"\n========== 抓取完成 ==========")
    print(f"成功商户: {len(completed_mids)}")
    print(f"失败商户: {len(failed_mids)}")
    print(f"总商品数: {len(all_products)}")
    print(f"结果: {OUTPUT_FILE}")

asyncio.run(main())
