"""
基于已保存的 HTML 文件，验证解析逻辑是否可靠
解析 NORTIV 8 的 brand_detail 页面
"""
from bs4 import BeautifulSoup

print("=" * 60)
print("基于已保存 HTML 解析验证")
print("=" * 60)

# 读取 NORTIV 8 的 brand_detail HTML
with open('output/page_brand_detail_nortiv8.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

# ① 提取 ASIN
asins = soup.select('div.asin-code')
print(f"\nASIN 数量: {len(asins)}")

if asins:
    print(f"前 5 个 ASIN:")
    for i, asin_el in enumerate(asins[:5]):
        asin_text = asin_el.get_text(strip=True)
        print(f"  [{i+1}] {asin_text}")

# ② 提取商品名
product_names = soup.select('div.product-name')
print(f"\n商品名数量: {len(product_names)}")
if product_names:
    print(f"前 5 个商品名:")
    for i, name_el in enumerate(product_names[:5]):
        name_text = name_el.get_text(strip=True)
        print(f"  [{i+1}] {name_text}")

# ③ 提取投放链接
tracking_links = soup.select('a[href*="openurlproduct"]')
print(f"\n投放链接数量: {len(tracking_links)}")

if tracking_links:
    print(f"前 5 个链接:")
    for i, link_el in enumerate(tracking_links[:5]):
        href = link_el.get('href', '')
        print(f"  [{i+1}] {href[:100]}...")
        
        # 从链接中提取 track 和 pid
        if 'track=' in href and 'pid=' in href:
            import re
            track_match = re.search(r'track=([^&]+)', href)
            pid_match = re.search(r'pid=([^&]+)', href)
            if track_match and pid_match:
                print(f"       track={track_match.group(1)}")
                print(f"       pid={pid_match.group(1)}")

# ④ 检查 ASIN 与投放链接的对应关系
print(f"\n--- ASIN 与投放链接数量对比 ---")
print(f"ASIN: {len(asins)}, 投放链接: {len(tracking_links)}")
print(f"是否匹配: {'✅ 匹配' if len(asins) == len(tracking_links) else '⚠️ 不匹配'}")

# ⑤ 提取分页信息
last_page = soup.select_one('.layui-laypage-last')
if last_page:
    total_pages = last_page.get_text(strip=True)
    print(f"\n总页数: {total_pages}")
    print(f"预计商品总数: {int(total_pages) * 30}")

# ⑥ 验证商品卡片的结构
print(f"\n--- 商品卡片结构验证 ---")
product_cards = soup.select('.layui-col-md4')
print(f"商品卡片 (layui-col-md4) 数量: {len(product_cards)}")

if product_cards:
    first_card = product_cards[0]
    # 提取卡片内的关键信息
    card_asin = first_card.select_one('div.asin-code')
    card_name = first_card.select_one('div.product-name')
    card_link = first_card.select_one('a[href*="openurlproduct"]')
    
    print(f"第一个卡片内:")
    print(f"  ASIN: {card_asin.get_text(strip=True) if card_asin else '未找到'}")
    print(f"  名称: {card_name.get_text(strip=True) if card_name else '未找到'}")
    print(f"  链接: {card_link.get('href','')[:100] if card_link else '未找到'}")

print("\n✅ 解析逻辑验证完成")
