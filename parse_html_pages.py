"""
深度解析 brand_detail 和 brands 两个页面的 HTML 结构
提取所有商品数据、品牌列表、分页信息
"""
import re, json
from bs4 import BeautifulSoup

print("=" * 70)
print("PART 1: brand_detail 页面 - 提取完整商品数据")
print("=" * 70)

with open("output/page_brand_detail_nortiv8.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 1. 提取所有投放链接（ClipboardJS）
print("\n[1] 投放链接提取")
clipboard_links = re.findall(r'ClipboardJS\.copy\(&#039;([^&#]+)&#039;\)', html)
clipboard_links2 = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
clipboard_links3 = re.findall(r'data-clipboard-text="([^"]+)"', html)
all_tracking = list(set(clipboard_links + clipboard_links2 + clipboard_links3))
print(f"  Total tracking links: {len(all_tracking)}")
for link in all_tracking[:5]:
    print(f"    {link}")
# 提取 track token 和 pid
for link in all_tracking[:3]:
    m = re.search(r'track=([^&]+)&.*?pid=(\d+)', link)
    if m:
        print(f"    => track={m.group(1)}, pid={m.group(2)}")

# 2. 提取所有 ASIN 及其上下文
print("\n[2] ASIN 及商品信息提取")
# 找含有 ASIN 的行
asin_pattern = re.compile(r'B0[A-Z0-9]{8}')

# 找包含 ASIN 的 <td> 或 <div>
asin_elements = soup.find_all(string=asin_pattern)
print(f"  Elements containing ASIN: {len(asin_elements)}")
for el in asin_elements[:5]:
    parent = el.parent
    print(f"    [{parent.name}] {el.strip()[:80]}")

# 3. 尝试找商品行（tr 或 div 的重复结构）
print("\n[3] 商品行结构分析")
# 找所有 tr
all_trs = soup.find_all("tr")
print(f"  Total <tr>: {len(all_trs)}")

# 找带有 amazon 链接的元素
amazon_links = soup.find_all("a", href=re.compile(r'amazon\.com'))
print(f"  Amazon links: {len(amazon_links)}")
for link in amazon_links[:3]:
    print(f"    {link.get('href', '')[:80]}")

# 4. 查找重复模式的 div（商品卡片）
print("\n[4] 商品卡片识别")
# 找有 ASIN 的 div/span
for asin_el in asin_elements[:3]:
    # 找最近的父容器
    parent = asin_el.parent
    for _ in range(5):
        if parent and parent.name in ['div', 'li', 'article']:
            print(f"  Container: {parent.name}.{' '.join(parent.get('class', []))}")
            # 提取这个容器里的文本
            texts = [t.strip() for t in parent.strings if t.strip() and len(t.strip()) > 2]
            print(f"  Texts: {texts[:8]}")
            # 提取链接
            links = [a.get('href','') for a in parent.find_all('a')]
            print(f"  Links: {links[:3]}")
            break
        parent = parent.parent if parent else None

# 5. 找分页信息
print("\n[5] 分页信息")
# 找 pagination
pagination = soup.find_all(class_=re.compile(r'pag|page'))
for p in pagination[:3]:
    print(f"  {p.name}.{p.get('class')} : {p.get_text(strip=True)[:80]}")

# 找 total/count 数字
total_patterns = re.findall(r'total["\s:=]+(\d+)', html, re.IGNORECASE)
count_patterns = re.findall(r'count["\s:=]+(\d+)', html, re.IGNORECASE)
print(f"  total patterns: {total_patterns[:5]}")
print(f"  count patterns: {count_patterns[:5]}")

# 查找 PHP 注入的变量
php_vars = re.findall(r'var\s+(\w+)\s*=\s*(\{[^;]+\}|\[[^\]]+\]|["\d][^;]{0,100}?);', html)
print(f"\n  JS vars: {len(php_vars)}")
for k, v in php_vars[:10]:
    print(f"    {k} = {v[:60]}")

# 6. 提取 JSON 嵌入数据
print("\n[6] 页面嵌入 JSON 数据")
json_patterns = [
    r'window\.__INITIAL_STATE__\s*=\s*(\{.+?\});',
    r'window\.__data__\s*=\s*(\{.+?\});',
    r'var\s+pageData\s*=\s*(\{.+?\});',
    r'var\s+listData\s*=\s*(\{.+?\});',
    r'var\s+productList\s*=\s*(\[.+?\]);',
]
for pattern in json_patterns:
    match = re.search(pattern, html, re.DOTALL)
    if match:
        print(f"  Found: {pattern[:40]}")
        try:
            data = json.loads(match.group(1))
            print(f"  Keys: {list(data.keys())[:10]}")
        except:
            print(f"  Raw: {match.group(1)[:100]}")

# 7. 显示 HTML 中关键的结构
print("\n[7] 找包含 track 的代码段")
track_sections = re.findall(r'.{100}track.{100}', html)
for s in track_sections[:3]:
    print(f"  ...{s}...")

print("\n\n" + "=" * 70)
print("PART 2: brands 页面 - 提取品牌列表")
print("=" * 70)

with open("output/page_brands.html", "r", encoding="utf-8") as f:
    brands_html = f.read()

brands_soup = BeautifulSoup(brands_html, "html.parser")

# 提取分页 / 总数
print("\n[1] 品牌总数和分页")
page_info = re.findall(r'共[^\d]*(\d+)[^\d]*条', brands_html)
total_info = re.findall(r'"total"\s*:\s*(\d+)', brands_html)
page_count = re.findall(r'"last_page"\s*:\s*(\d+)', brands_html)
print(f"  共...条: {page_info}")
print(f"  total: {total_info}")
print(f"  last_page: {page_count}")

# 找 advert_id
advert_ids = re.findall(r'advert_id[="\s:]+(\d+)', brands_html)
unique_ids = list(dict.fromkeys(advert_ids))
print(f"\n[2] 找到的 advert_id: {len(unique_ids)}")
print(f"  First 20: {unique_ids[:20]}")

# 找品牌名称 - 找 href 包含 brand_detail 的链接
brand_links = brands_soup.find_all("a", href=re.compile(r'brand_detail'))
print(f"\n[3] 品牌详情链接: {len(brand_links)}")
for bl in brand_links[:5]:
    href = bl.get('href','')
    text = bl.get_text(strip=True)[:30]
    print(f"  {href} => {text}")

# 找分页链接
page_links = brands_soup.find_all("a", href=re.compile(r'page=|\?p=|/page/'))
print(f"\n[4] 分页链接: {len(page_links)}")
for pl in page_links[:5]:
    print(f"  {pl.get('href','')} => {pl.get_text(strip=True)[:20]}")

# 找所有包含 brand_detail 的链接
all_brand_hrefs = list(set([
    a.get('href','') for a in brands_soup.find_all('a', href=re.compile(r'brand_detail'))
]))
print(f"\n[5] 唯一品牌链接: {len(all_brand_hrefs)}")
for href in all_brand_hrefs[:10]:
    print(f"  {href}")

# 提取每个品牌卡片的完整信息
print("\n[6] 品牌卡片数据")
# 找 brand_detail 链接的父容器
brand_cards = []
for a in brands_soup.find_all('a', href=re.compile(r'brand_detail')):
    # 向上找 4 层，找到最近的 div
    container = a
    for _ in range(6):
        container = container.parent
        if container and container.name == 'div' and container.get('class'):
            cls = ' '.join(container.get('class',[]))
            if any(x in cls for x in ['card', 'item', 'brand', 'col-', 'list']):
                texts = [t.strip() for t in container.strings if t.strip() and len(t.strip()) > 1]
                mid = re.search(r'advert_id=(\d+)', a.get('href',''))
                brand_cards.append({
                    'advert_id': mid.group(1) if mid else None,
                    'texts': texts[:5],
                    'href': a.get('href','')
                })
                break

print(f"  Brand cards found: {len(brand_cards)}")
for card in brand_cards[:5]:
    print(f"  advert_id={card['advert_id']}: {card['texts']}")
