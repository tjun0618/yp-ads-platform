import requests

s = requests.Session()

# 分页扫全量 approved 商户（size=200，多页）
all_danger = []
page = 1
total_scanned = 0

while True:
    r = s.get(f'http://127.0.0.1:5055/api/merchants?tab=approved&page={page}&size=200')
    data = r.json()
    items = data['items']
    if not items:
        break
    total_scanned += len(items)
    for m in items:
        name = m.get('merchant_name', '') or ''
        danger_chars = [c for c in ["'", '"', '<', '>', '`', '\\'] if c in name]
        if danger_chars:
            all_danger.append((page, m['merchant_id'], name, danger_chars))
    pages = data.get('pages', 1)
    print(f'  第{page}/{pages}页 扫描 {len(items)} 条...')
    if page >= pages:
        break
    page += 1

print(f'\n全量 approved 扫描: {total_scanned} 条')
print(f'含危险字符: {len(all_danger)} 个')
for pg, mid, name, chars in all_danger:
    print(f"  [第{pg}页][{mid}] {repr(name)}  危险字符: {chars}")
