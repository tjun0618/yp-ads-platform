#!/usr/bin/env python3
"""
智能匹配策略：
1. 从飞书Offers表取商品名称
2. 提取品牌词，与merchants_mid_list做模糊匹配
3. 找到的商户立即抓取页面，获取ASIN和投放链接
4. 更新asin_merchant_map.json
5. 剩余未匹配的ASIN继续靠全量遍历覆盖
"""
import json
import re
import time
import requests
from bs4 import BeautifulSoup

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
OFFERS_TABLE_ID = "tblMCbaHhP88sgeS"

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def get_feishu_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    return resp.json()["tenant_access_token"]

def get_feishu_offers(token):
    """获取飞书Offers表所有商品"""
    records = []
    page_token = None
    headers = {"Authorization": f"Bearer {token}"}
    
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{OFFERS_TABLE_ID}/records",
            headers=headers, params=params
        )
        result = resp.json()
        
        if result.get("code") != 0:
            print(f"Error: {result}")
            break
        
        records.extend(result["data"]["items"])
        if not result["data"].get("has_more"):
            break
        page_token = result["data"].get("page_token")
    
    return records

def extract_brand_candidates(product_name):
    """从商品名中提取可能的品牌词（更智能的提取）"""
    if not product_name:
        return []
    
    candidates = []
    
    # 清理特殊字符
    name = product_name.strip()
    
    # 策略1: 如果有品牌分隔符如 "Brand - Product" 或 "Brand: Product"
    sep_match = re.match(r'^([^:-|]+?)[\s]*[-:|]\s', name)
    if sep_match:
        brand = sep_match.group(1).strip()
        if 2 <= len(brand) <= 30:
            candidates.append(brand)
    
    # 策略2: 全大写单词（常见品牌缩写）
    words = name.split()
    for word in words[:3]:
        clean = re.sub(r'[^A-Za-z0-9]', '', word)
        if clean.isupper() and len(clean) >= 3:
            candidates.append(clean)
            break
    
    # 策略3: 第一个首字母大写的单词（最常见）
    if words and words[0][0].isupper() if words else False:
        first = re.sub(r'[^A-Za-z0-9]', '', words[0])
        if len(first) >= 3:
            candidates.append(first)
    
    # 策略4: 前两个词作为品牌名（如 "TruSkin Vitamin C"）
    if len(words) >= 2:
        two_words = f"{words[0]} {words[1]}"
        two_clean = re.sub(r'[^A-Za-z0-9 ]', '', two_words).strip()
        if len(two_clean) >= 5:
            candidates.append(two_clean)
    
    # 去重并返回
    seen = set()
    unique = []
    for c in candidates:
        lower = c.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(c)
    
    return unique

def fuzzy_match_merchant(brand, merchants):
    """模糊匹配商户名"""
    brand_lower = brand.lower().strip()
    brand_words = set(brand_lower.split())
    
    best_match = None
    best_score = 0
    
    for m in merchants:
        merchant_name = m.get("name", "").lower()
        
        # 精确包含
        if brand_lower in merchant_name or merchant_name in brand_lower:
            return m, 1.0
        
        # 单词重叠
        merchant_words = set(merchant_name.split())
        overlap = brand_words.intersection(merchant_words)
        if overlap and len(overlap) / max(len(brand_words), 1) > 0.5:
            score = len(overlap) / max(len(brand_words), len(merchant_words))
            if score > best_score:
                best_score = score
                best_match = m
    
    if best_score >= 0.5:
        return best_match, best_score
    return None, 0

def scrape_merchant_page(mid, merchant_name):
    """抓取商户页面，提取ASIN和投放链接"""
    url = f"https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id=12002"
    
    try:
        resp = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=15)
        if resp.status_code != 200:
            return {}
        
        soup = BeautifulSoup(resp.text, "html.parser")
        products = {}
        
        # 方式1: 查找 product-line 元素
        product_lines = soup.find_all("div", class_="product-line")
        for line in product_lines:
            asin_div = line.find("div", class_="asin-code")
            asin = asin_div.get_text(strip=True) if asin_div else None
            if not asin:
                continue
            
            tracking_url = None
            pid = None
            track = None
            
            # 查找 ClipboardJS.copy
            copy_btn = line.find("p", class_="adv-btn")
            if copy_btn:
                onclick = copy_btn.get("onclick", "")
                url_match = re.search(r"ClipboardJS\.copy\('([^']+)'\)", onclick)
                if url_match:
                    tracking_url = url_match.group(1).replace("&amp;", "&")
                    pid_match = re.search(r"pid=(\d+)", tracking_url)
                    track_match = re.search(r"track=([a-f0-9]+)", tracking_url)
                    pid = pid_match.group(1) if pid_match else None
                    track = track_match.group(1) if track_match else None
            
            # 商品名称
            name_div = line.find("div", class_="product-name") or line.find("h3") or line.find("p", class_="product-title")
            product_name = name_div.get_text(strip=True) if name_div else ""
            
            products[asin] = {
                "merchant_id": str(mid),
                "merchant_name": merchant_name,
                "pid": pid,
                "tracking_url": tracking_url,
                "track": track,
                "product_name": product_name[:100],
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        
        # 方式2: 直接搜索所有ClipboardJS
        if not products:
            scripts = soup.find_all(string=re.compile(r"ClipboardJS\.copy"))
            asins = re.findall(r'asin["\s]*[=:]\s*["\']?([A-Z0-9]{10})', resp.text, re.IGNORECASE)
            copy_urls = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", resp.text)
            
            for i, (asin, url_str) in enumerate(zip(asins, copy_urls)):
                url_clean = url_str.replace("&amp;", "&")
                pid_m = re.search(r"pid=(\d+)", url_clean)
                track_m = re.search(r"track=([a-f0-9]+)", url_clean)
                products[asin] = {
                    "merchant_id": str(mid),
                    "merchant_name": merchant_name,
                    "pid": pid_m.group(1) if pid_m else None,
                    "tracking_url": url_clean,
                    "track": track_m.group(1) if track_m else None,
                    "product_name": "",
                    "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
        
        return products
    
    except Exception as e:
        print(f"  抓取失败 MID={mid}: {e}")
        return {}

def main():
    print("=" * 70)
    print("智能品牌匹配 + 精准页面抓取")
    print("=" * 70)
    
    # 加载现有ASIN映射
    try:
        with open("output/asin_merchant_map.json", "r", encoding="utf-8") as f:
            asin_map = json.load(f)
        print(f"\n[1] 已有ASIN映射: {len(asin_map)} 个")
    except:
        asin_map = {}
    
    # 加载飞书ASIN列表
    try:
        with open("output/feishu_offers_asins.json", "r", encoding="utf-8") as f:
            feishu_asins = set(json.load(f))
        print(f"飞书Offers ASIN: {len(feishu_asins)} 个")
    except:
        print("未找到feishu_offers_asins.json，重新获取...")
        token = get_feishu_token()
        offers = get_feishu_offers(token)
        feishu_asins = set()
        for item in offers:
            asin = item.get("fields", {}).get("ASIN", "")
            if isinstance(asin, list): asin = asin[0] if asin else ""
            if asin: feishu_asins.add(str(asin).strip())
        with open("output/feishu_offers_asins.json", "w", encoding="utf-8") as f:
            json.dump(list(feishu_asins), f, ensure_ascii=False, indent=2)
        print(f"飞书Offers ASIN: {len(feishu_asins)} 个")
    
    # 未匹配的ASIN
    unmatched_asins = feishu_asins - set(asin_map.keys())
    print(f"未匹配ASIN: {len(unmatched_asins)} 个")
    
    # 加载飞书Offers完整数据（含商品名）
    print("\n[2] 获取飞书Offers商品名称...")
    token = get_feishu_token()
    offers_records = get_feishu_offers(token)
    
    # 建立 ASIN -> 商品名 映射
    asin_to_name = {}
    for item in offers_records:
        fields = item.get("fields", {})
        asin = fields.get("ASIN", "")
        if isinstance(asin, list): asin = asin[0] if asin else ""
        asin = str(asin).strip()
        name = fields.get("Product Name", "") or fields.get("product_name", "")
        if isinstance(name, list): name = name[0] if name else ""
        if asin and name:
            asin_to_name[asin] = str(name)
    
    print(f"ASIN-商品名映射: {len(asin_to_name)} 个")
    
    # 加载商户列表
    print("\n[3] 加载商户MID列表...")
    with open("output/merchants_mid_list.json", "r", encoding="utf-8") as f:
        merchants = json.load(f)
    print(f"商户数量: {len(merchants)}")
    
    # 已抓取的商户MID（不重复抓取）
    scraped_mids = set()
    for v in asin_map.values():
        mid = v.get("merchant_id")
        if mid:
            scraped_mids.add(str(mid))
    print(f"已抓取商户MID数: {len(scraped_mids)}")
    
    # 品牌匹配
    print("\n[4] 品牌词提取 + 商户匹配...")
    mid_to_scrape = {}  # mid -> merchant_name
    match_log = []
    
    for asin in list(unmatched_asins):
        name = asin_to_name.get(asin, "")
        if not name:
            continue
        
        brands = extract_brand_candidates(name)
        
        for brand in brands:
            merchant, score = fuzzy_match_merchant(brand, merchants)
            if merchant:
                mid = str(merchant.get("mid", ""))
                mname = merchant.get("name", "")
                if mid and mid not in scraped_mids:
                    mid_to_scrape[mid] = mname
                    match_log.append({
                        "asin": asin, 
                        "product_name": name[:60],
                        "brand": brand,
                        "merchant_name": mname,
                        "mid": mid,
                        "score": round(score, 2)
                    })
                    break
    
    print(f"品牌匹配到商户: {len(mid_to_scrape)} 个唯一商户")
    print(f"匹配记录: {len(match_log)} 条")
    
    # 显示匹配样本
    print("\n匹配样本（前20条）:")
    for log in match_log[:20]:
        brand = log['brand'].encode('ascii', 'ignore').decode('ascii')
        merchant = log['merchant_name'].encode('ascii', 'ignore').decode('ascii')
        asin = log['asin']
        score = log['score']
        print(f"  [{score:.2f}] {brand} -> {merchant} (MID:{log['mid']}) for {asin}")
    
    # 保存匹配日志
    with open("output/smart_match_log.json", "w", encoding="utf-8") as f:
        json.dump(match_log, f, ensure_ascii=False, indent=2)
    print(f"\n匹配日志已保存: output/smart_match_log.json")
    
    if not mid_to_scrape:
        print("\n没有新商户需要抓取")
        return
    
    # 抓取匹配到的商户页面
    print(f"\n[5] 抓取 {len(mid_to_scrape)} 个商户页面...")
    new_asins = 0
    error_count = 0
    
    for i, (mid, mname) in enumerate(mid_to_scrape.items()):
        mname_safe = mname.encode('ascii', 'ignore').decode('ascii')
        print(f"  [{i+1}/{len(mid_to_scrape)}] MID={mid} {mname_safe}")
        
        products = scrape_merchant_page(mid, mname)
        
        if products:
            for asin, data in products.items():
                if asin not in asin_map:
                    asin_map[asin] = data
                    new_asins += 1
            print(f"    找到 {len(products)} 个产品")
        else:
            error_count += 1
            print(f"    未找到产品")
        
        scraped_mids.add(mid)
        time.sleep(0.5)
        
        # 每10个保存一次
        if (i + 1) % 10 == 0:
            with open("output/asin_merchant_map.json", "w", encoding="utf-8") as f:
                json.dump(asin_map, f, ensure_ascii=False, indent=2)
            print(f"    已保存，新增ASIN: {new_asins}")
    
    # 最终保存
    with open("output/asin_merchant_map.json", "w", encoding="utf-8") as f:
        json.dump(asin_map, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("完成统计:")
    print(f"  抓取商户数: {len(mid_to_scrape)}")
    print(f"  新增ASIN映射: {new_asins}")
    print(f"  抓取错误: {error_count}")
    print(f"  总ASIN映射: {len(asin_map)}")
    
    # 重新检查飞书ASIN覆盖率
    matched_now = feishu_asins.intersection(set(asin_map.keys()))
    print(f"\n飞书ASIN覆盖率: {len(matched_now)}/{len(feishu_asins)} ({len(matched_now)/len(feishu_asins)*100:.1f}%)")
    still_unmatched = feishu_asins - set(asin_map.keys())
    print(f"仍未匹配: {len(still_unmatched)} 个")

if __name__ == "__main__":
    main()
