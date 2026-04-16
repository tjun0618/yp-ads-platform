import ast
with open('ads_manager.py', 'r', encoding='utf-8-sig') as f:
    src = f.read()
try:
    ast.parse(src)
    print('syntax OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    print(f'  text: {e.text}')
