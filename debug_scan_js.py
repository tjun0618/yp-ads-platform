import urllib.request, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 直接从Flask获取原始字节
r = urllib.request.urlopen('http://localhost:5055/merchant_products?merchant_id=362400')
raw = r.read()  # 保留原始字节

print('Response len:', len(raw))
print('Content-Type:', r.headers.get('Content-Type'))

# 用字节来找 &#8249; 
idx = raw.find(b'8249')
print('8249 at byte:', idx)
if idx >= 0:
    snip = raw[idx-30:idx+100]
    print('bytes around 8249:', repr(snip))
    for i, b in enumerate(snip):
        if b in (0x0a, 0x0d):
            print(f'  NEWLINE 0x{b:02x} at snippet offset {i}, ctx: {repr(snip[max(0,i-10):i+10])}')

# 找script内部的JS字符串换行问题
# 策略：找所有 单引号字符串内部的换行
# JS里：单引号字符串不能跨行，找 ' 之后在遇到 ' 之前出现了 \n

print('\n=== Scanning for newlines inside JS strings ===')
html = raw.decode('utf-8', errors='replace')
sc = html.find('<script>', 6000)
se = html.rfind('</script>')
js_code = html[sc+8:se]

in_single = False
in_double = False
in_template = False
escape = False
errors = []

for i, ch in enumerate(js_code):
    if escape:
        escape = False
        continue
    if ch == '\\':
        escape = True
        continue
    if ch in ('\n', '\r') and in_single:
        # 找出行号
        line_num = js_code[:i].count('\n') + 1
        ctx_start = max(0, i-60)
        ctx_end = min(len(js_code), i+60)
        errors.append(f'Line {line_num}, byte {i}: newline inside single-quote string')
        errors.append(f'  Context: {repr(js_code[ctx_start:ctx_end])}')
    if ch == "'" and not in_double and not in_template:
        in_single = not in_single
    elif ch == '"' and not in_single and not in_template:
        in_double = not in_double

if errors:
    print(f'Found {len(errors)//2} violation(s):')
    for e in errors[:20]:
        print(' ', e)
else:
    print('No newlines inside single-quote strings found')
