import requests

s = requests.Session()

# 拉全量商户
r = s.get('http://127.0.0.1:5055/api/merchants?tab=approved&page=1&size=5000')
data = r.json()
all_items = data['items']

print(f'总商户数: {len(all_items)}')

# 检查含单引号/双引号/JS危险字符的商户名
danger = []
for m in all_items:
    name = m.get('merchant_name', '') or ''
    danger_chars = [c for c in ["'", '"', '<', '>', '`', '\\'] if c in name]
    if danger_chars:
        danger.append((m['merchant_id'], name, danger_chars))

print(f'含危险字符的商户: {len(danger)} 个')
for mid, name, chars in danger[:15]:
    print(f"  [{mid}] {repr(name)}  危险字符: {chars}")

# 同时检测 unapplied
r2 = s.get('http://127.0.0.1:5055/api/merchants?tab=unapplied&page=1&size=6000')
data2 = r2.json()
items2 = data2['items']
danger2 = []
for m in items2:
    name = m.get('merchant_name', '') or ''
    if any(c in name for c in ["'", '"', '<', '>', '`']):
        danger2.append((m['merchant_id'], name))

print(f'\nunapplied 总商户数: {len(items2)}')
print(f'含危险字符的商户: {len(danger2)} 个')
for mid, name in danger2[:5]:
    print(f"  [{mid}] {repr(name)}")
