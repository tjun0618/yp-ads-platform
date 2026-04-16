from bs4 import BeautifulSoup
import re

# 读取 truskin_brand_detail.html
with open('output/truskin_brand_detail.html', 'r', encoding='utf-8') as f:
    html = f.read()

print("=== 解析 truskin_brand_detail.html ===")
print(f"HTML 大小: {len(html):,} bytes")

# 提取所有 ClipboardJS.copy() 调用
clipboard_pattern = r"ClipboardJS\.copy\('([^']+)'\)"
matches = re.findall(clipboard_pattern, html)
print(f"\nClipboardJS.copy() 调用次数: {len(matches)}")

if matches:
    print("\n前 10 个投放链接:")
    for i, url in enumerate(matches[:10]):
        url = url.replace("&amp;", "&")
        print(f"  [{i+1}] {url[:130]}")

        # 提取 track 和 pid
        if 'track=' in url and 'pid=' in url:
            track_match = re.search(r'track=([^&]+)', url)
            pid_match = re.search(r'pid=(\d+)', url)
            if track_match and pid_match:
                print(f"       track={track_match.group(1)}, pid={pid_match.group(1)}")

# 提取 ASIN
asins = re.findall(r'<div class="asin-code">([^<]+)</div>', html)
print(f"\nASIN 数量（正则提取）: {len(asins)}")
if asins:
    print(f"前 5 个 ASIN: {asins[:5]}")

# 检查是否一一对应
print(f"\nASIN 与投放链接对应关系:")
print(f"  ASIN: {len(asins)}")
print(f"  链接: {len(matches)}")
print(f"  匹配: {'✅ 是' if len(asins) == len(matches) else '⚠️ 否'}")

# 提取商品名
product_names = re.findall(r'<div class="product-name">([^<]+)</div>', html)
print(f"\n商品名数量: {len(product_names)}")
if product_names:
    print(f"第一个商品名: {product_names[0][:80]}...")
