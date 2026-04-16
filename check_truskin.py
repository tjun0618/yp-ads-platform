from bs4 import BeautifulSoup
import re

# 读取有投放链接记录的 HTML
with open('output/truskin_brand_detail.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

asins = soup.select('div.asin-code')
tracking_links = soup.select('a[href*="openurlproduct"]')

print("ASIN 数量:", len(asins))
print("投放链接数量:", len(tracking_links))

if tracking_links:
    print("\n前 5 个投放链接:")
    for i, link_el in enumerate(tracking_links[:5]):
        href = link_el.get('href', '')
        print(f"  [{i+1}] {href[:140]}")

# 检查 ClipboardJS.copy() 中的链接（另一种存储方式）
clipboard_scripts = soup.find_all(text=lambda t: t and 'ClipboardJS.copy' in t)
print(f"\nClipboardJS.copy() 调用次数: {len(clipboard_scripts)}")

if clipboard_scripts:
    print("\n前 5 个 ClipboardJS.copy() 链接:")
    for i, script_text in enumerate(clipboard_scripts[:5]):
        # 提取 copy() 里的 URL
        match = re.search(r"ClipboardJS\.copy\('([^']+)'\)", script_text)
        if match:
            url = match.group(1)
            print(f"  [{i+1}] {url[:120]}...")
