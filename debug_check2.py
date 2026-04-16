import urllib.request, sys, io, re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

r = urllib.request.urlopen('http://localhost:5055/merchant_products?merchant_id=362400')
html = r.read().decode('utf-8')

# renderPager 完整内容
rp = html.find('function renderPager')
print('=== renderPager ===')
print(html[rp:rp+2000])
print()

# 整个script块内容保存到文件
sc_start = html.find('<script>', 6000)
sc_end = html.find('</script>', sc_start) + 9
print(f'Script block: {sc_start} -> {sc_end}, len={sc_end-sc_start}')

# 保存整个script块到文件
with open('debug_script_block.js', 'w', encoding='utf-8') as f:
    f.write(html[sc_start:sc_end])
print('Script block saved to debug_script_block.js')

# 检查 {{ 双花括号
braces = [(m.start(), html[m.start():m.start()+60]) for m in re.finditer(r'\{\{', html[sc_start:sc_end])]
print(f'Double braces in script: {len(braces)}')
for pos, ctx in braces[:10]:
    print(f'  pos={pos}: {repr(ctx)}')
