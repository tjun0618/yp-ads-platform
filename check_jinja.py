import re

with open(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\ads_manager.py', 'r', encoding='utf-8') as f:
    src = f.read()

# 找所有 render_template_string 调用
for m in re.finditer(r'return render_template_string\((\w+)\)', src):
    varname = m.group(1)
    lineno = src[:m.start()].count('\n') + 1
    # 找该变量定义
    var_idx = src.rfind(varname + ' = ', 0, m.start())
    if var_idx < 0:
        print(f'Line {lineno}: render_template_string({varname}) - variable not found')
        continue
    snippet = src[var_idx:var_idx + 20000]
    bad = re.findall(r'\{\{[^}%\{][^}]*\}\}', snippet[:10000])
    if bad:
        print(f'Line {lineno}: render_template_string({varname}) - JINJA ISSUES: {bad[:3]}')
    else:
        print(f'Line {lineno}: render_template_string({varname}) - OK')
