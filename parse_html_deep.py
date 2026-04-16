"""
深度解析 brand_detail 页面商品结构 + brands 页面品牌列表
输出到 JSON 文件规避编码问题
"""
import re, json, sys
from bs4 import BeautifulSoup

# 强制 UTF-8 输出
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("brand_detail 页面商品结构分析")
print("=" * 70)

with open("output/page_brand_detail_nortiv8.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 找到 div.asin-code 的父级结构
asin_divs = soup.find_all(class_="asin-code")
print(f"\ndiv.asin-code 数量: {len(asin_divs)}")

# 找第一个商品的完整结构
if asin_divs:
    sample = asin_divs[0]
    # 向上找到商品容器
    parent = sample
    for i in range(10):
        parent = parent.parent
        cls = ' '.join(parent.get('class', [])) if parent else ''
        # print(f"  Level {i+1}: {parent.name}.{cls[:40]}")
        if 'item' in cls or 'product' in cls or 'offer' in cls or 'brand' in cls:
            break
    
    # 显示完整容器的 HTML
    print(f"\nSample product container ({parent.name}.{' '.join(parent.get('class',[]))}):")
    print(parent.prettify()[:2000])

# 提取所有商品数据
print("\n\n提取所有商品数据:")
products = []

# 找所有包含 asin-code 的父级商品容器
# 先找最近的公共父级
asin_containers = set()
for asin_div in asin_divs:
    # 向上5层找容器
    p = asin_div
    for _ in range(8):
        p = p.parent
        if p is None:
            break
        cls = ' '.join(p.get('class', []))
        if any(x in cls for x in ['item', 'product', 'offer-card', 'pro-']):
            asin_containers.add(p)
            break

print(f"Product containers found: {len(asin_containers)}")

# 提取每个商品容器的数据
for container in list(asin_containers)[:3]:
    texts = [t.strip() for t in container.strings if t.strip()]
    print(f"\nContainer texts: {texts[:15]}")
    
    # 找链接
    links_in_container = [a.get('href','') for a in container.find_all('a')]
    print(f"Links: {links_in_container[:5]}")
    
    # 找 track 链接
    track_matches = re.findall(r'track=([^&]+).*?pid=(\d+)', str(container))
    print(f"Track links: {track_matches[:3]}")

# 用正则更暴力地提取所有商品行
print("\n\n暴力正则提取所有商品数据:")
# 找所有 track+pid 组合
all_tracking = re.findall(r'track=([a-f0-9]+).*?pid=(\d+)', html)
print(f"Tracking combos: {len(all_tracking)}")

# 同时找同一区域的 ASIN
# 策略：找 track 链接所在的 ~500 字节范围内的 ASIN
all_products_raw = []
for m in re.finditer(r'track=([a-f0-9]+)[^"]*pid=(\d+)', html):
    start = max(0, m.start() - 500)
    end = min(len(html), m.end() + 500)
    region = html[start:end]
    
    # 找 ASIN
    asins = re.findall(r'B0[A-Z0-9]{8}', region)
    
    # 找价格
    prices = re.findall(r'\$[\d,.]+', region)
    
    # 找商品名（长文本）
    names = re.findall(r'"product[_-]?name"[:\s]+"([^"]+)"', region, re.IGNORECASE)
    
    track = m.group(1)
    pid = m.group(2)
    
    if asins:
        all_products_raw.append({
            'track': track,
            'pid': pid,
            'asin': asins[0] if asins else None,
            'prices': prices[:3],
        })

print(f"Products with ASIN: {len(all_products_raw)}")
for p in all_products_raw[:5]:
    print(f"  {p}")

# 保存到 JSON
with open("output/brand_detail_products.json", "w", encoding="utf-8") as f:
    json.dump(all_products_raw, f, ensure_ascii=False, indent=2)
print("\nSaved to output/brand_detail_products.json")

print("\n\n" + "=" * 70)
print("brands 页面品牌列表分析")
print("=" * 70)

with open("output/page_brands.html", "r", encoding="utf-8") as f:
    brands_html = f.read()

brands_soup = BeautifulSoup(brands_html, "html.parser")

# 提取总数
total_match = re.search(r'(\d+)\s*Brands', brands_html, re.IGNORECASE)
total_match2 = re.search(r'total["\s:=]+(\d+)', brands_html)
if total_match:
    print(f"\n总品牌数 (from text): {total_match.group(1)}")
if total_match2:
    print(f"总品牌数 (from JSON): {total_match2.group(1)}")

# 找分页
page_info = re.findall(r'"last_page"\s*:\s*(\d+)', brands_html)
current_page = re.findall(r'"current_page"\s*:\s*(\d+)', brands_html)
per_page = re.findall(r'"per_page"\s*:\s*(\d+)', brands_html)
print(f"last_page: {page_info}, current_page: {current_page}, per_page: {per_page}")

# 看看有多少 brand_detail 链接
brand_links = [a.get('href','') for a in brands_soup.find_all('a', href=re.compile(r'brand_detail'))]
unique_brand_links = list(dict.fromkeys(brand_links))
print(f"\n品牌详情链接数: {len(unique_brand_links)}")
print(f"First 10: {unique_brand_links[:10]}")

# 解析分页 HTML
pager = brands_soup.find(class_=re.compile(r'paginat|pager'))
if pager:
    print(f"\nPagination HTML: {str(pager)[:500]}")

# 找所有页码链接
page_links = brands_soup.find_all('a', href=re.compile(r'page=\d+'))
page_nums = [re.search(r'page=(\d+)', a.get('href','')).group(1) 
             for a in page_links if re.search(r'page=(\d+)', a.get('href',''))]
print(f"\nPage numbers in pagination: {list(set(page_nums))[:20]}")

# 看看 brands 页面的 URL 参数能不能做分页
# 找最大页码
if page_nums:
    max_page = max(int(p) for p in page_nums)
    print(f"Max page: {max_page}")

# 提取所有 advert_id
advert_ids = re.findall(r'advert_id=(\d+)', brands_html)
unique_advert_ids = list(dict.fromkeys(advert_ids))
print(f"\nUnique advert_ids on this page: {len(unique_advert_ids)}")
print(f"Values: {unique_advert_ids[:20]}")

# 是否有下一页按钮
next_btn = brands_soup.find('a', string=re.compile(r'Next|下一页|›|»'))
print(f"\nNext page button: {next_btn}")

# 找其他分页按钮
nav_links = brands_soup.find_all('a', href=re.compile(r'/index/offer/brands\?'))
print(f"\nBrands page nav links: {len(nav_links)}")
for nl in nav_links[:10]:
    print(f"  {nl.get('href','')} => {nl.get_text(strip=True)[:20]}")

# 输出摘要
result = {
    "brand_detail_products_count": len(all_products_raw),
    "brands_page_brand_count": len(unique_advert_ids),
    "brands_page_advert_ids": unique_advert_ids,
    "pagination": {
        "last_page": page_info,
        "current_page": current_page,
        "per_page": per_page,
    }
}
with open("output/page_analysis_summary.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("\n\nSummary saved to output/page_analysis_summary.json")
