"""
用飞书下载的10020个商户MID进行网页端抓取
建立 ASIN -> 商品投放链接 映射（使用 asin-code div 提取ASIN）
"""
import requests
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup

# Cookie 配置
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.yeahpromos.com/"
}

SITE_ID = "12002"
ASIN_MAP_FILE = "output/asin_merchant_map.json"
STATE_FILE = "output/web_scrape_state.json"
MERCHANTS_MID_FILE = "output/merchants_mid_list.json"


def load_merchants():
    """从 merchants_mid_list.json 加载商户 MID 列表"""
    with open(MERCHANTS_MID_FILE, "r", encoding="utf-8") as f:
        merchants = json.load(f)
    # 去重
    seen = set()
    unique = []
    for m in merchants:
        mid = m.get("mid")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)
    return unique


def load_asin_map():
    try:
        with open(ASIN_MAP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_asin_map(asin_map):
    with open(ASIN_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(asin_map, f, ensure_ascii=False, indent=2)


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {"last_index": 0, "total_asin": 0, "last_update": ""}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def scrape_merchant_products(mid, name):
    """
    抓取单个商户的所有商品及投放链接
    页面结构：
    - <div class="asin-code">B0XXXXXXXX</div> 包含ASIN
    - ClipboardJS.copy('https://yeahpromos.com/...?track=xxx&pid=yyy') 包含投放链接
    每个产品行包含图片、产品名、asin-code、价格、佣金率、Copy按钮
    """
    url = ("https://www.yeahpromos.com/index/offer/brand_detail"
           "?advert_id=" + str(mid) + "&site_id=" + SITE_ID)
    
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=30)
        
        if resp.status_code != 200:
            return []
        
        html = resp.text
        
        # 提取 track token
        track_match = re.search(r"track=([a-f0-9]{16})", html)
        track = track_match.group(1) if track_match else None
        
        # 解析产品列表
        # 每个产品行: product-line div
        # 包含: asin-code div + Copy按钮中的 pid
        products = []
        
        # 用BeautifulSoup解析
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 找所有产品行
            product_lines = soup.find_all("div", class_="product-line")
            
            for line in product_lines:
                # 提取ASIN
                asin_div = line.find("div", class_="asin-code")
                asin = asin_div.get_text(strip=True) if asin_div else None
                
                # 提取投放链接（从Copy按钮的onclick中）
                copy_btn = line.find("p", class_="adv-btn")
                tracking_url = None
                pid = None
                if copy_btn:
                    onclick = copy_btn.get("onclick", "")
                    url_match = re.search(r"ClipboardJS\.copy\('([^']+)'\)", onclick)
                    if url_match:
                        tracking_url = url_match.group(1).replace("&amp;", "&")
                        pid_match = re.search(r"pid=(\d+)", tracking_url)
                        pid = pid_match.group(1) if pid_match else None
                
                # 提取产品名称
                name_div = line.find("div", class_="product-name")
                product_name = ""
                if name_div:
                    # 第一个div文本是产品名
                    divs = name_div.find_all("div", recursive=False)
                    if divs:
                        product_name = divs[0].get_text(strip=True)
                
                if asin and len(asin) == 10:
                    products.append({
                        "asin": asin,
                        "pid": pid,
                        "tracking_url": tracking_url,
                        "track": track,
                        "product_name": product_name[:100] if product_name else ""
                    })
        
        except Exception as e:
            # 备用方案：正则提取
            asin_codes = re.findall(r'class="asin-code">([A-Z0-9]{10})<', html)
            clipboard_urls = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
            
            for i, asin in enumerate(asin_codes):
                tracking_url = None
                pid = None
                if i < len(clipboard_urls):
                    tracking_url = clipboard_urls[i].replace("&amp;", "&")
                    pid_match = re.search(r"pid=(\d+)", tracking_url)
                    pid = pid_match.group(1) if pid_match else None
                
                products.append({
                    "asin": asin,
                    "pid": pid,
                    "tracking_url": tracking_url,
                    "track": track,
                    "product_name": ""
                })
        
        return products
    
    except Exception as e:
        return []


def main():
    print("=" * 60)
    print("网页端抓取商品投放链接（10020个商户MID）")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 安装beautifulsoup4如果需要
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("安装 beautifulsoup4...")
        import subprocess
        subprocess.run(["pip", "install", "beautifulsoup4", "-q"])
    
    # 加载商户列表
    print("加载商户列表...")
    merchants = load_merchants()
    print(f"商户总数: {len(merchants)}")
    
    # 加载现有ASIN映射
    asin_map = load_asin_map()
    print(f"现有ASIN映射: {len(asin_map)} 条")
    
    # 加载抓取状态
    state = load_state()
    start_index = state.get("last_index", 0)
    print(f"从索引 {start_index} 继续 (已处理 {start_index}/{len(merchants)} 个商户)")
    print()
    
    # 统计
    new_count = 0
    processed = 0
    merchants_with_products = 0
    
    for i in range(start_index, len(merchants)):
        m = merchants[i]
        mid = m["mid"]
        name = m.get("name", "Unknown")
        
        # 进度显示（每50个）
        if i % 50 == 0 and i > start_index:
            elapsed_pct = (i - start_index) / max(len(merchants) - start_index, 1) * 100
            print(f"\n[进度] {i}/{len(merchants)} ({elapsed_pct:.1f}%) | "
                  f"有商品商户: {merchants_with_products} | "
                  f"新ASIN: {new_count} | "
                  f"总ASIN: {len(asin_map)}")
        
        # 抓取商品
        products = scrape_merchant_products(mid, name)
        
        if products:
            merchants_with_products += 1
            page_new = 0
            for p in products:
                asin = p.get("asin")
                if asin and asin not in asin_map:
                    asin_map[asin] = {
                        "merchant_id": mid,
                        "merchant_name": name,
                        "pid": p.get("pid"),
                        "tracking_url": p.get("tracking_url"),
                        "track": p.get("track"),
                        "product_name": p.get("product_name", ""),
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    page_new += 1
                    new_count += 1
            
            if page_new > 0:
                print(f"[{i:5d}] {name[:35]:35s} MID={mid:6s} +{page_new:2d} ASIN (total={len(asin_map)})")
        
        processed += 1
        
        # 每100个保存一次
        if processed % 100 == 0:
            save_asin_map(asin_map)
            state["last_index"] = i + 1
            state["total_asin"] = len(asin_map)
            state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_state(state)
        
        time.sleep(0.3)  # 间隔300ms，避免频率过高
    
    # 最终保存
    save_asin_map(asin_map)
    state["last_index"] = len(merchants)
    state["total_asin"] = len(asin_map)
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_state(state)
    
    print(f"\n{'=' * 60}")
    print(f"抓取完成!")
    print(f"处理商户: {processed}")
    print(f"有商品商户: {merchants_with_products}")
    print(f"新增ASIN: {new_count}")
    print(f"ASIN总数: {len(asin_map)}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
