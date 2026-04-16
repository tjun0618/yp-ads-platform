"""
模拟浏览器执行商户商品页面
直接调用API，用Python重现renderBody逻辑，检查是否有数据渲染问题
"""
import urllib.request, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 1. 获取API数据
merchant_id = '362400'
url = f'http://localhost:5055/api/merchant_products?merchant_id={merchant_id}&page=1&size=20'
r = urllib.request.urlopen(url)
data = json.loads(r.read().decode('utf-8'))

print('=== API Response ===')
print(f'total: {data.get("total")}')
print(f'pages: {data.get("pages")}')
print(f'items count: {len(data.get("items", []))}')
print(f'error: {data.get("error")}')
merchant = data.get('merchant', {})
print(f'merchant: {merchant}')
print()

# 2. 检查第一件商品的字段
items = data.get('items', [])
if items:
    print('=== First item ===')
    for k, v in items[0].items():
        print(f'  {k}: {repr(v)[:80]}')

# 3. 获取完整页面HTML，检查有无JS错误点
r2 = urllib.request.urlopen(f'http://localhost:5055/merchant_products?merchant_id={merchant_id}')
html = r2.read().decode('utf-8')

# 检查 renderBody 函数内是否有异常字符
rb_start = html.find('function renderBody')
rb_end = html.find('\nfunction ', rb_start + 20)
rb_code = html[rb_start:rb_end]
print(f'\n=== renderBody length: {len(rb_code)} ===')

# 找innerHTML中可能导致异常的地方
import re
# 找 data-* 属性和 onclick 中的拼接
onclick_matches = list(re.finditer(r'onclick=', rb_code))
print(f'onclick count: {len(onclick_matches)}')
for m in onclick_matches:
    ctx = rb_code[m.start():m.start()+100]
    print(f'  {repr(ctx)}')

# 检查 + 号拼接中是否有明显问题
# 比如 downloadPlan('' + p.asin + '') -> 正确应该是 downloadPlan(' + p.asin + ')
dp_idx = rb_code.find('downloadPlan')
if dp_idx >= 0:
    print(f'\ndownloadPlan call: {repr(rb_code[dp_idx:dp_idx+80])}')

# 检查 generateAd
ga_idx = rb_code.find('generateAd')
if ga_idx >= 0:
    print(f'generateAd call: {repr(rb_code[ga_idx:ga_idx+80])}')
