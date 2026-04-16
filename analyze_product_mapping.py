"""
进一步分析 brand_detail 页面，弄清楚如何把 ASIN 和 tracking link 对应起来
以及研究分页机制
"""
import re, json, sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 70)
print("brand_detail 商品-投放链接 对应关系分析")
print("=" * 70)

with open("output/page_brand_detail_nortiv8.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 找到包含商品行的主容器
# 每行应该同时包含 ASIN div 和 tracking link
# 先看看 asin-code 的父结构层次

asin_divs = soup.find_all(class_="asin-code")
print(f"\nTotal asin-code divs: {len(asin_divs)}")

# 找到所有商品行的公共父节点
# 向上找直到找到包含 tracking link 的节点

products_extracted = []

for i, asin_div in enumerate(asin_divs):
    asin = asin_div.get_text(strip=True)
    
    # 向上逐级找包含 track 链接的父节点
    parent = asin_div
    found_track = None
    for level in range(15):
        parent = parent.parent
        if parent is None:
            break
        parent_html = str(parent)
        track_match = re.search(r'track=([a-f0-9]+).*?pid=(\d+)', parent_html)
        if track_match and level >= 2:  # 至少向上 2 级
            found_track = track_match
            # 提取这个商品行的所有信息
            product_name_div = parent.find(class_=re.compile(r'product-name'))
            if product_name_div:
                name_div = product_name_div.find('div')
                name = name_div.get_text(strip=True) if name_div else ''
            else:
                # 找最近的长文本
                all_texts = [t.strip() for t in parent.strings if len(t.strip()) > 20]
                name = all_texts[0] if all_texts else ''
            
            # 找价格
            price_el = parent.find(class_=re.compile(r'price'))
            price = price_el.get_text(strip=True) if price_el else ''
            
            # 找图片
            img_el = parent.find('img')
            img = img_el.get('src', '') if img_el else ''
            
            # 找评分
            review_match = re.search(r'\((\d[\d,]*)\)', str(parent))
            reviews = review_match.group(1) if review_match else ''
            
            # 找 amazon 链接
            amazon_link = ''
            for a in parent.find_all('a'):
                href = a.get('href', '')
                if 'amazon' in href:
                    amazon_link = href
                    break
            
            tracking_url = f"https://yeahpromos.com/index/index/openurlproduct?track={found_track.group(1)}&pid={found_track.group(2)}"
            
            products_extracted.append({
                'index': i + 1,
                'asin': asin,
                'name': name[:100],
                'price': price,
                'reviews': reviews,
                'img': img,
                'amazon_link': amazon_link,
                'track': found_track.group(1),
                'pid': found_track.group(2),
                'tracking_url': tracking_url,
            })
            break

print(f"\nExtracted products: {len(products_extracted)}")
for p in products_extracted[:5]:
    print(f"\n  [{p['index']}] ASIN={p['asin']}")
    print(f"       Name: {p['name'][:60]}")
    print(f"       Price: {p['price']}, Reviews: {p['reviews']}")
    print(f"       Track: {p['track']}, PID: {p['pid']}")
    print(f"       Tracking URL: {p['tracking_url']}")

# 保存
with open("output/nortiv8_products_extracted.json", "w", encoding="utf-8") as f:
    json.dump(products_extracted, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(products_extracted)} products to output/nortiv8_products_extracted.json")

# 检查页面是否有更多页
print("\n\n分页分析:")
# 找 brand_detail 的分页
pagination = soup.find(class_=re.compile(r'paginat'))
if pagination:
    print(f"Pagination HTML: {str(pagination)[:500]}")
else:
    print("No pagination element found!")
    
# 找 page/total 信息
total_patterns = re.findall(r'total["\s:=]+(\d+)', html)
page_patterns = re.findall(r'page["\s:=]+(\d+)', html)
print(f"total: {total_patterns[:5]}")
print(f"page: {page_patterns[:5]}")

# 找分页 URL
page_nav = soup.find_all('a', href=re.compile(r'brand_detail.*page='))
print(f"Page nav links: {len(page_nav)}")
for p in page_nav[:5]:
    print(f"  {p.get('href','')} => {p.get_text(strip=True)}")

# 找 "下一页" 或 "Next" 按钮
nav_btns = soup.find_all('a', string=re.compile(r'Next|下一页|›|»|\d+'))
print(f"\nNavigation buttons: {len(nav_btns)}")
for btn in nav_btns[:10]:
    print(f"  {btn.get('href','')} => {repr(btn.get_text(strip=True))}")

# 查找第几页，共几页
page_info_texts = re.findall(r'第\s*\d+\s*页|共\s*\d+\s*页|Page\s*\d+\s*of\s*\d+', html, re.IGNORECASE)
print(f"\nPage info: {page_info_texts}")

# 检查 HTML 底部是否有分页组件
# 找 ul.pagination
ul_pagination = soup.find_all('ul', class_=re.compile(r'paginat'))
print(f"\nul.pagination: {len(ul_pagination)}")
for ul in ul_pagination:
    print(f"  {str(ul)[:300]}")

# 找所有 /index/offer/brand_detail 链接
brand_detail_links = [a.get('href','') for a in soup.find_all('a', href=re.compile(r'brand_detail'))]
print(f"\nbrand_detail links on this page: {len(brand_detail_links)}")
for l in brand_detail_links[:5]:
    print(f"  {l}")
