import urllib.request, sys, io, re

r = urllib.request.urlopen('http://localhost:5055/merchant_products?merchant_id=362400')
raw = r.read()
html = raw.decode('utf-8')

# 提取最后一个 <script> 块（不带标签）
sc_start = html.rfind('<script>')
sc_end = html.rfind('</script>')
js = html[sc_start+8:sc_end]

# 保存为纯JS文件（LF换行）
js_lf = js.replace('\r\n', '\n').replace('\r', '\n')
with open('extracted.js', 'w', encoding='utf-8', newline='\n') as f:
    f.write(js_lf)

print(f'Extracted {len(js_lf)} chars to extracted.js')
print(f'Lines: {js_lf.count(chr(10))}')

# 同时保存原始HTML
with open('merchant_page.html', 'wb') as f:
    f.write(raw)
print(f'Saved {len(raw)} bytes to merchant_page.html')
