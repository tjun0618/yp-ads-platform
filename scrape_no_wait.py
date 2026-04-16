"""
连接到用户已打开的 Chrome 浏览器进行抓取（非交互版本）
"""
import json
import re
import time
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path

SITE_ID = "12002"
STATE_FILE = "output/scrape_state_manual.json"
OUTPUT_FILE = "output/us_merchants_products.json"

def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed_mids": [], "failed_mids": [], "products": [], "last_updated": None}

def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def parse_brand_detail(html, mid, merchant_name):
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

def main():
    print("=" * 70)
    print("YP US 商户商品批量抓取工具（连接真实浏览器）")
    print("=" * 70)

    with open('output/us_merchants_clean.json', 'r', encoding='utf-8') as f:
        us_data = json.load(f)

    approved_merchants = us_data['approved_list']
    print(f"\n待抓取 APPROVED US 商户数: {len(approved_merchants)}")

    state = load_state()
    completed_mids = set(state.get('completed_mids', []))
    failed_mids = set(state.get('failed_mids', []))
    all_products = state.get('products', [])

    print(f"已完成: {len(completed_mids)}, 失败: {len(failed_mids)}, 已抓商品: {len(all_products)}")

    pending_merchants = [m for m in approved_merchants if m['mid'] not in completed_mids]
    print(f"待处理: {len(pending_merchants)}")

    print("\n正在尝试连接浏览器...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ 成功连接到浏览器！")
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("\n需要你以调试模式启动 Chrome。请按以下步骤操作：")
            print("1. 完全关闭所有 Chrome 浏览器窗口")
            print("2. 打开 CMD，运行以下命令:")
            print("   chrome.exe --remote-debugging-port=9222")
            print("3. 在启动的 Chrome 中登录 YP")
            print("4. 登录完成后，脚本会自动开始抓取")
            print("\n⚠️ 如果脚本连接失败，请确保 Chrome 正在调试模式下运行")
            return

        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = browser.new_context()
        
        pages = context.pages
        if pages:
            page = pages[0]
        else:
            page = context.new_page()

        merchant_count = 0
        start_time = time.time()

        for idx, merchant in enumerate(pending_merchants):
            mid = merchant['mid']
            name = merchant['name']

            elapsed = int(time.time() - start_time)
            elapsed_min = elapsed // 60
            elapsed_sec = elapsed % 60

            print(f"\n[{idx+1}/{len(pending_merchants)}] {name} (mid={mid}) | 已用时 {elapsed_min}分{elapsed_sec}秒")

            try:
                url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page=1'
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle')

                html = page.content()

                if 'Login name cannot be empty' in html:
                    print("  ❌ 未登录！等待 30 秒让你登录...")
                    time.sleep(30)
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state('networkidle')
                    html = page.content()

                    if 'Login name cannot be empty' in html:
                        print("  ❌ 仍然未登录，跳过此商户")
                        failed_mids.add(mid)
                        save_state({"completed_mids": list(completed_mids), "failed_mids": list(failed_mids), "products": all_products})
                        continue

                last_page_el = page.query_selector('.layui-laypage-last')
                total_pages = 1
                if last_page_el:
                    total_pages = int(last_page_el.inner_text().strip())

                print(f"  总页数: {total_pages}")

                all_merchant_products = []

                for page_num in range(1, total_pages + 1):
                    if page_num > 1:
                        url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page={page_num}'
                        page.goto(url, timeout=30000)
                        page.wait_for_load_state('networkidle')
                        html = page.content()

                    products = parse_brand_detail(html, mid, name)
                    all_merchant_products.extend(products)

                    print(f"    第 {page_num}/{total_pages} 页: {len(products)} 条商品")

                    time.sleep(0.5)

                all_products.extend(all_merchant_products)
                completed_mids.add(mid)
                merchant_count += 1

                print(f"  ✅ 成功: {len(all_merchant_products)} 条")

                state = {
                    "completed_mids": list(completed_mids),
                    "failed_mids": list(failed_mids),
                    "products": all_products
                }
                save_state(state)

                if merchant_count % 100 == 0:
                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_products, f, ensure_ascii=False, indent=2)
                    print(f"  📁 已保存 {len(all_products)} 条商品到文件")

                time.sleep(1)

            except Exception as e:
                print(f"  ❌ 抓取失败: {e}")
                failed_mids.add(mid)
                state = {
                    "completed_mids": list(completed_mids),
                    "failed_mids": list(failed_mids),
                    "products": all_products
                }
                save_state(state)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

        browser.close()

    total_time = time.time() - start_time
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)

    print("\n" + "=" * 70)
    print("========== 抓取完成 ==========")
    print(f"成功商户: {len(completed_mids)}")
    print(f"失败商户: {len(failed_mids)}")
    print(f"总商品数: {len(all_products)}")
    print(f"总用时: {hours}小时{minutes}分钟")
    print(f"结果已保存到: {OUTPUT_FILE}")
    print(f"状态文件: {STATE_FILE}")
    print("=" * 70)

if __name__ == "__main__":
    main()
