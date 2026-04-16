"""
用 Playwright 批量抓取 APPROVED US 商户的所有商品
特点：自动登录、断点续传、实时写入飞书
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
STATE_FILE = "output/scrape_state_playwright.json"
OUTPUT_FILE = "output/us_merchants_products.json"
# 飞书配置（待填）
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
FEISHU_TABLE_ID = "tblMCbaHhP88sgeS"

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
    """解析 brand_detail 页面，提取商品数据"""
    # 提取 ASIN
    asin_pattern = r'<div class="asin-code">([^<]+)</div>'
    asins = re.findall(asin_pattern, html)

    # 提取投放链接（ClipboardJS.copy）
    link_pattern = r"ClipboardJS\.copy\('([^']+)'\)"
    links = re.findall(link_pattern, html)
    links = [link.replace("&amp;", "&") for link in links]

    # 提取商品名（从 ClipboardJS 调用中的商品名）
    # 格式通常：ClipboardJS.copy('url') 旁边有商品名
    products = []
    for i, asin in enumerate(asins):
        if i < len(links):
            link = links[i]
            # 提取 track 和 pid
            track = re.search(r'track=([^&]+)', link)
            pid = re.search(r'pid=(\d+)', link)

            # 尝试提取商品名（在 ASIN 附近）
            name_match = re.search(rf'<div class="asin-code">{asin}</div>\s*<div[^>]*class="[^"]*product-name[^"]*"[^>]*>([^<]+)</div>', html, re.MULTILINE | re.DOTALL)
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

async def login_to_yp(page):
    """登录 YP"""
    print("正在打开登录页...")
    await page.goto('https://www.yeahpromos.com/index/login/index', timeout=30000)

    print("请在弹出的浏览器窗口中登录 YP...")
    print("（输入账号密码后等待脚本自动继续）")

    # 等待登录成功（跳转到任何 /index/ 页面）
    await page.wait_for_url('**/index/**', timeout=120000)
    print(f"✅ 登录成功！当前 URL: {page.url}")

    # 等待页面完全加载
    await page.wait_for_load_state('networkidle')
    await asyncio.sleep(2)

async def scrape_merchant_products(page, mid, merchant_name):
    """抓取单个商户的所有商品"""
    # 获取总页数
    url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page=1'
    await page.goto(url, timeout=30000)
    await page.wait_for_load_state('networkidle')

    # 检查是否被重定向到登录页
    if 'Login name cannot be empty' in await page.content():
        print("❌ Session 失效，需要重新登录")
        return None

    # 获取总页数
    last_page_el = await page.query_selector('.layui-laypage-last')
    total_pages = 1
    if last_page_el:
        total_pages_text = await last_page_el.text_content()
        total_pages = int(total_pages_text.strip())

    print(f"商户 {merchant_name} (mid={mid}) 共 {total_pages} 页")

    all_products = []

    # 分页抓取
    for page_num in range(1, total_pages + 1):
        if page_num > 1:
            url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page={page_num}'
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle')

        html = await page.content()
        products = parse_brand_detail(html, mid, merchant_name)
        all_products.extend(products)

        print(f"  第 {page_num}/{total_pages} 页: {len(products)} 条商品")

        # 延迟避免过快
        await asyncio.sleep(1)

    return all_products

async def main():
    # 加载 US 商户列表
    with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
        us_data = json.load(f)

    approved_merchants = us_data['approved_list']
    print(f"待抓取商户数: {len(approved_merchants)}")

    # 加载状态
    state = load_state()
    completed_mids = set(state.get('completed_mids', []))
    failed_mids = set(state.get('failed_mids', []))
    all_products = state.get('products', [])

    print(f"已完成: {len(completed_mids)}, 失败: {len(failed_mids)}, 已抓商品: {len(all_products)}")

    # 过滤待处理商户
    pending_merchants = [m for m in approved_merchants if m['mid'] not in completed_mids]
    print(f"待处理商户: {len(pending_merchants)}")

    async with async_playwright() as p:
        # 每次启动新浏览器都登录一次
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 登录
        await login_to_yp(page)

        # 批量抓取
        for idx, merchant in enumerate(pending_merchants):
            mid = merchant['mid']
            name = merchant['name']

            print(f"\n[{idx+1}/{len(pending_merchants)}] 抓取: {name} (mid={mid})")

            try:
                products = await scrape_merchant_products(page, mid, name)

                if products:
                    all_products.extend(products)
                    completed_mids.add(mid)
                    state['completed_mids'] = list(completed_mids)
                    state['products'] = all_products
                    save_state(state)

                    print(f"✅ 成功抓取 {len(products)} 条商品")
                else:
                    print(f"⚠️ 未找到商品")
                    failed_mids.add(mid)

            except Exception as e:
                print(f"❌ 抓取失败: {e}")
                failed_mids.add(mid)
                state['failed_mids'] = list(failed_mids)
                save_state(state)

            # 每 50 个商户保存一次完整数据
            if (idx + 1) % 50 == 0:
                print(f"\n保存进度...已抓 {len(all_products)} 条商品")
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, ensure_ascii=False, indent=2)

            # 避免过快
            await asyncio.sleep(2)

        # 保存最终结果
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

        await browser.close()

    print(f"\n抓取完成！")
    print(f"成功商户: {len(completed_mids)}")
    print(f"失败商户: {len(failed_mids)}")
    print(f"总商品数: {len(all_products)}")
    print(f"结果已保存到: {OUTPUT_FILE}")

asyncio.run(main())
