"""
通过 Playwright 连接到调试模式 Chrome，下载商户 Excel 并读取
思路：访问每个商户的 brand_detail 页面 → 点击 Download Products → 读取下载的 Excel
"""
import json
import time
import os
import glob
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from pathlib import Path

SITE_ID = "12002"
OUTPUT_DIR = "output"
STATE_FILE = os.path.join(OUTPUT_DIR, "download_state.json")
RESULTS_FILE = os.path.join(OUTPUT_DIR, "downloaded_products.json")
DOWNLOAD_DIR = os.path.join(OUTPUT_DIR, "downloads")

def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed_mids": [], "failed_mids": [], "products": [], "last_updated": None}

def save_state(state):
    state["last_updated"] = datetime.now().isoformat()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def read_excel(filepath):
    """读取下载的 Excel 文件"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        ws = wb.active
        
        products = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0]:
                asin = str(row[0]).strip()
                if not asin or len(asin) != 10:
                    continue
                products.append({
                    "asin": asin,
                    "product_name": str(row[1])[:200] if row[1] else "",
                    "category": str(row[2]) if row[2] else "",
                    "commission": str(row[3]) if row[3] else "",
                    "price": str(row[4]) if row[4] else "",
                    "tracking_link": str(row[5]) if row[5] else "",
                })
        wb.close()
        return products
    except Exception as e:
        print(f"    读取 Excel 失败: {e}")
        return []

def wait_for_download(download_dir, timeout=60):
    """等待下载完成"""
    start = time.time()
    while time.time() - start < timeout:
        xlsx_files = glob.glob(os.path.join(download_dir, "*.xlsx"))
        for f in xlsx_files:
            # 确保文件不是临时文件（.crdownload）
            if not f.endswith('.crdownload') and os.path.getsize(f) > 1000:
                return f
        time.sleep(1)
    return None

def main():
    print("=" * 70)
    print("YP US 商户商品下载工具（Excel Download 版本）")
    print("=" * 70)

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, 'us_merchants_clean.json'), 'r', encoding='utf-8') as f:
        us_data = json.load(f)

    approved_merchants = us_data['approved_list']
    print(f"\n待处理 APPROVED US 商户数: {len(approved_merchants)}")

    state = load_state()
    completed_mids = set(state.get('completed_mids', []))
    failed_mids = set(state.get('failed_mids', []))
    all_products = state.get('products', [])

    print(f"已完成: {len(completed_mids)}, 失败: {len(failed_mids)}, 已抓商品: {len(all_products)}")

    pending_merchants = [m for m in approved_merchants if m['mid'] not in completed_mids]
    print(f"待处理: {len(pending_merchants)}")

    print("\n正在连接浏览器...")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ 成功连接到浏览器！")
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            print("请确保 Chrome 以调试模式运行：")
            print('  & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\\Users\\wuhj\\Chrome_Debug"')
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

            print(f"\n[{idx+1}/{len(pending_merchants)}] {name} (mid={mid}) | {elapsed_min}分{elapsed_sec}秒")

            try:
                # 访问商户品牌页
                url = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}'
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle')

                html = page.content()

                # 检查登录状态
                if 'Login name cannot be empty' in html or 'login' in page.url.lower():
                    print("  ⚠️ 未登录，等待 60 秒...")
                    time.sleep(60)
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state('networkidle')
                    html = page.content()
                    if 'Login name cannot be empty' in html:
                        print("  ❌ 仍然未登录，跳过")
                        failed_mids.add(mid)
                        save_state({"completed_mids": list(completed_mids), "failed_mids": list(failed_mids), "products": all_products})
                        continue

                # 查找 Download Products 按钮
                download_btn = page.query_selector('a:has-text("Download"), button:has-text("Download"), a:has-text("Export"), button:has-text("Export"), a[href*="export"], a[href*="download"]')

                if download_btn:
                    print("  📥 找到下载按钮，点击下载...")
                    
                    # 设置下载路径
                    with page.expect_download(timeout=60000) as download_info:
                        download_btn.click()
                    
                    download = download_info.value
                    
                    # 保存到指定目录
                    save_path = os.path.join(DOWNLOAD_DIR, f"offer_{mid}_{name.replace('/', '_')[:30]}.xlsx")
                    download.save_as(save_path)
                    print(f"  ✅ 已下载: {os.path.basename(save_path)}")

                    # 读取 Excel
                    products = read_excel(save_path)
                    if products:
                        for prod in products:
                            prod["merchant_id"] = mid
                            prod["merchant_name"] = name
                            prod["scraped_at"] = datetime.now().isoformat()
                        all_products.extend(products)
                        print(f"  📊 读取到 {len(products)} 条商品")
                    else:
                        print(f"  ⚠️ Excel 为空或读取失败")

                    # 删除已处理的下载文件
                    try:
                        os.remove(save_path)
                    except:
                        pass

                else:
                    # 没有 Download 按钮，直接从页面解析
                    print("  ⚠️ 未找到下载按钮，尝试页面解析...")
                    
                    asin_pattern = r'<div class="asin-code">([^<]+)</div>'
                    asins = re.findall(asin_pattern, html)
                    link_pattern = r"ClipboardJS\.copy\('([^']+)'\)"
                    links = re.findall(link_pattern, html)
                    links = [link.replace("&amp;", "&") for link in links]

                    for i, asin in enumerate(asins):
                        if i < len(links):
                            link = links[i]
                            track = re.search(r'track=([^&]+)', link)
                            pid = re.search(r'pid=(\d+)', link)
                            all_products.append({
                                "asin": asin,
                                "merchant_id": mid,
                                "merchant_name": name,
                                "product_name": f"Product {asin}",
                                "tracking_url": link if track and pid else None,
                                "track": track.group(1) if track else None,
                                "pid": pid.group(1) if pid else None,
                                "source": "page_parse",
                                "scraped_at": datetime.now().isoformat()
                            })
                    print(f"  📊 页面解析到 {len(asins)} 条商品")

                completed_mids.add(mid)
                merchant_count += 1

                state = {
                    "completed_mids": list(completed_mids),
                    "failed_mids": list(failed_mids),
                    "products": all_products
                }
                save_state(state)

                if merchant_count % 50 == 0:
                    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(all_products, f, ensure_ascii=False, indent=2)
                    print(f"  📁 已保存 {len(all_products)} 条商品")

                time.sleep(1)

            except Exception as e:
                print(f"  ❌ 失败: {e}")
                failed_mids.add(mid)
                state = {
                    "completed_mids": list(completed_mids),
                    "failed_mids": list(failed_mids),
                    "products": all_products
                }
                save_state(state)

        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_products, f, ensure_ascii=False, indent=2)

    total_time = time.time() - start_time
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)

    print("\n" + "=" * 70)
    print("========== 下载完成 ==========")
    print(f"成功商户: {len(completed_mids)}")
    print(f"失败商户: {len(failed_mids)}")
    print(f"总商品数: {len(all_products)}")
    print(f"总用时: {hours}小时{minutes}分钟")
    print(f"结果: {RESULTS_FILE}")
    print("=" * 70)

if __name__ == "__main__":
    main()
