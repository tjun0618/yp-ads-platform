"""
1. 解析 brand_detail 和 brands 页面的 HTML，提取数据
2. 测试 injoin/injoin2 API 端点的参数和返回值
3. 深度分析 JS 中所有 API 端点
"""
import requests, json, re
from bs4 import BeautifulSoup

PHPSESSID = "932a965dc80f3c5bc7fe2226771950fc"
BASE = "https://yeahpromos.com"
HEADERS = {
    "Cookie": f"PHPSESSID={PHPSESSID}; user_id=2864; user_name=Tong+Jun; think_lang=zh-cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://yeahpromos.com/index/offer/brand_detail?advert_id=362548",
}

print("=" * 70)
print("Part 1: 深度解析 brand_detail HTML")
print("=" * 70)

with open("output/page_brand_detail_nortiv8.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

# 1. 提取所有 script 标签
print("\n[A] Script 标签分析")
scripts = soup.find_all("script")
print(f"  总 script 数: {len(scripts)}")

all_api_endpoints = set()
all_vars = {}

for i, s in enumerate(scripts):
    src = s.get("src", "")
    content = s.string or ""
    
    if src:
        # 外部脚本
        if "yeahpromos" in src:
            print(f"  Script[{i}] src={src}")
    else:
        # 内联脚本
        if len(content) > 50:
            # 查找 /index/ 路径
            apis = re.findall(r'["\'](/index/[a-zA-Z0-9_/]+)["\']', content)
            for a in apis:
                all_api_endpoints.add(a)
            
            # 查找变量赋值
            vars_found = re.findall(r'var\s+(\w+)\s*=\s*(.{1,100}?);', content)
            for k, v in vars_found[:5]:
                all_vars[k] = v.strip()
            
            # 查找 $.get/$.post/$.ajax/fetch 调用
            ajax_calls = re.findall(r'(?:url\s*:\s*|["\']url["\']\s*:\s*)["\']([^"\']+)["\']', content)
            for call in ajax_calls:
                if '/index/' in call:
                    all_api_endpoints.add(call)
                    print(f"  AJAX call found: {call}")
            
            # 查找 fetch(
            fetch_calls = re.findall(r'fetch\(["\']([^"\']+)["\']', content)
            for call in fetch_calls:
                if 'yeahpromos' in call or call.startswith('/'):
                    print(f"  fetch() call: {call}")

print(f"\n  All /index/ endpoints found in scripts:")
for ep in sorted(all_api_endpoints):
    print(f"    {ep}")

print(f"\n  Variables found: {list(all_vars.keys())[:20]}")
for k, v in list(all_vars.items())[:10]:
    print(f"    {k} = {v[:60]}")

# 2. 提取表格数据（商品列表）
print("\n[B] 提取页面中的数据表格")
tables = soup.find_all("table")
print(f"  找到 {len(tables)} 个表格")
for i, table in enumerate(tables):
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    rows = table.find_all("tr")
    print(f"  Table[{i}]: {len(rows)} rows, headers={headers[:10]}")
    # 提取前3行数据
    data_rows = table.find_all("tr")[1:4]
    for row in data_rows:
        cells = [td.get_text(strip=True)[:30] for td in row.find_all("td")]
        if cells:
            print(f"    Row: {cells[:6]}")

# 3. 提取包含商品数据的 div
print("\n[C] 查找商品列表容器")
# 查找 data-* 属性
data_elements = soup.find_all(attrs={"data-id": True})
print(f"  data-id 元素: {len(data_elements)}")
for el in data_elements[:5]:
    print(f"    {el.name} data-id={el.get('data-id')} class={el.get('class')}")

# 查找 ASIN 相关内容
asin_pattern = re.compile(r'B0[A-Z0-9]{8}')
asins_in_html = asin_pattern.findall(html)
unique_asins = list(set(asins_in_html))
print(f"\n  ASINs found in HTML: {len(unique_asins)}")
for a in unique_asins[:10]:
    print(f"    {a}")

# 4. 查找 ClipboardJS 的链接
print("\n[D] 投放链接 (ClipboardJS)")
clipboard_links = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
clipboard_links2 = re.findall(r'data-clipboard-text="([^"]+)"', html)
all_links = list(set(clipboard_links + clipboard_links2))
print(f"  Found {len(all_links)} clipboard links")
for link in all_links[:5]:
    print(f"    {link[:100]}")

print("\n" + "=" * 70)
print("Part 2: 解析 brands 页面 HTML")
print("=" * 70)

with open("output/page_brands.html", "r", encoding="utf-8") as f:
    brands_html = f.read()

brands_soup = BeautifulSoup(brands_html, "html.parser")

# 提取 Script 中的 API 端点
brands_scripts = brands_soup.find_all("script")
brands_apis = set()
for s in brands_scripts:
    content = s.string or ""
    apis = re.findall(r'["\'](/index/[a-zA-Z0-9_/]+)["\']', content)
    for a in apis:
        brands_apis.add(a)
    # 查找 AJAX URL
    ajax = re.findall(r'(?:url\s*:\s*)["\']([^"\']+)["\']', content)
    for a in ajax:
        if '/index/' in a:
            brands_apis.add(a)
            print(f"  AJAX: {a}")

print(f"\nBrands page APIs:")
for a in sorted(brands_apis):
    print(f"  {a}")

# 提取 brands 列表
brand_items = brands_soup.select('.brand-item, .advert-item, [data-advert-id], [data-mid]')
print(f"\nBrand items found: {len(brand_items)}")
for item in brand_items[:3]:
    print(f"  {item.get('data-advert-id') or item.get('data-mid')} {item.get_text(strip=True)[:50]}")

# 查找 brands 页面的商户卡片
cards = brands_soup.select('.col-md-3, .col-sm-6, .card')
print(f"\nCards/columns: {len(cards)}")

print("\n" + "=" * 70)
print("Part 3: 测试新发现的 API 端点")
print("=" * 70)

def test_api(method, url, params=None, data=None, extra_headers=None):
    h = {**HEADERS}
    if extra_headers:
        h.update(extra_headers)
    try:
        if method == "GET":
            resp = requests.get(url, headers=h, params=params, timeout=10)
        else:
            resp = requests.post(url, headers=h, data=data, timeout=10)
        ct = resp.headers.get("content-type", "")
        print(f"  Status: {resp.status_code}, CT: {ct[:40]}, Size: {len(resp.text)}")
        if "json" in ct:
            j = resp.json()
            print(f"  JSON: {str(j)[:200]}")
            return j
        elif resp.status_code == 200 and len(resp.text) < 500:
            print(f"  Body: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

# 测试 injoin（申请加入商户）
print("\n[1] /index/advert/injoin - POST (申请加入某商户)")
result = test_api("POST", f"{BASE}/index/advert/injoin", 
                  data={"advert_id": "362548", "site_id": "12002"})

print("\n[2] /index/advert/injoin2 - POST (申请加入，另一个版本?)")
result = test_api("POST", f"{BASE}/index/advert/injoin2",
                  data={"advert_id": "362548", "site_id": "12002"})

# 测试 report API（用 AJAX 方式）
print("\n[3] /index/offer/report_cpc - GET/POST (CPC报表)")
test_api("POST", f"{BASE}/index/offer/report_cpc",
         data={"start_date": "2026-03-01", "end_date": "2026-03-23", "site_id": "12002"})

print("\n[4] /index/offer/report_performance - POST")
test_api("POST", f"{BASE}/index/offer/report_performance",
         data={"start_date": "2026-03-01", "end_date": "2026-03-23", 
               "site_id": "12002", "dim": "CampaignId", "page": 1, "page_size": 20})

# 测试带 _/ 的 ThinkPHP 路由格式
print("\n[5] /index/offer/brands - GET (获取品牌列表)")
test_api("GET", f"{BASE}/index/offer/brands",
         params={"site_id": "12002", "page": 1, "page_size": 20})

# 用 AJAX header
print("\n[6] /index/advert/index - GET (商户列表)")
test_api("GET", f"{BASE}/index/advert/index",
         params={"site_id": "12002", "page": 1},
         extra_headers={"Accept": "application/json"})

# 测试可能的商品搜索 API
print("\n[7] /index/offer/product_list - POST (商品列表?)")
test_api("POST", f"{BASE}/index/offer/product_list",
         data={"advert_id": "362548", "site_id": "12002", "page": 1})

print("\n[8] /index/offer/brand_product - GET (品牌商品?)")
test_api("GET", f"{BASE}/index/offer/brand_product",
         params={"advert_id": "362548", "site_id": "12002"})

# ThinkPHP 常见的 API 格式
for action in ["get_products", "product", "products", "offer_list", "getproduct", "item_list"]:
    endpoint = f"{BASE}/index/offer/{action}"
    print(f"\n[auto] {endpoint}")
    r = test_api("GET", endpoint, params={"advert_id": "362548", "site_id": "12002"})
    if r:
        break  # 找到就停止

print("\n[9] /index/site/change - 站点切换 API")
test_api("POST", f"{BASE}/index/site/change",
         data={"site_id": "12002"})
