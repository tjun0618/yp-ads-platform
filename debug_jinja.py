import sys, os, traceback
os.chdir(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu')

# 用 Flask test client 直接发请求，获取真实异常
try:
    # 先设置环境避免 Flask 启动服务器
    os.environ['FLASK_ENV'] = 'testing'
    
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ads_manager",
        r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\ads_manager.py'
    )
    mod = importlib.util.load_from_spec = None  # not using this approach
    
    # 直接用 requests 打开 debug=True 的端点
    # 实际上 Flask 的 500 在 production 模式下不暴露 traceback
    # 改用：直接读取 MERCHANT_PRODUCTS_UNIFIED_HTML 并测试 Jinja2 渲染
    
    from flask import Flask
    from jinja2 import Environment, BaseLoader, TemplateSyntaxError
    
    # 读取 ads_manager.py 内容
    with open(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\ads_manager.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到 MERCHANT_PRODUCTS_UNIFIED_HTML = ... 的结束位置
    # 它是一个长字符串拼接 (...)
    # 先找 _PAGER_JS_DARK, _BASE_STYLE_DARK, _SCRAPE_TOPNAV 的内容，看有没有 {{ }} 问题
    
    patterns_to_check = ['_PAGER_JS_DARK', '_BASE_STYLE_DARK', '_SCRAPE_TOPNAV', '_NAV_HTML']
    for pat in patterns_to_check:
        idx = content.find(f'{pat} = ')
        if idx < 0:
            idx = content.find(f'{pat}=')
        if idx >= 0:
            snippet = content[idx:idx+200]
            has_jinja = '{{' in snippet[50:] or '{%' in snippet[50:]
            print(f'{pat} at line ~{content[:idx].count(chr(10))+1}: jinja={{ {has_jinja} }} | first 120: {repr(snippet[:120])}')
        else:
            print(f'{pat}: NOT FOUND')
    
    print('\n--- Checking for {{ in MERCHANT_PRODUCTS_UNIFIED_HTML content ---')
    # 找 MERCHANT_PRODUCTS_UNIFIED_HTML 的实际字符串内容（在 page_merchant_products 之后）
    start = content.find('# 商户商品页 HTML')
    end_marker = content.find('\n\n\n', start + 100)
    if end_marker < 0:
        end_marker = start + 5000
    html_def = content[start:end_marker]
    
    # 检查模板变量
    jinja_vars = set()
    import re
    for m in re.finditer(r'\{\{[^}]+\}\}', html_def):
        jinja_vars.add(m.group())
    print('Jinja2 {{ }} found in MERCHANT_PRODUCTS_UNIFIED_HTML:', jinja_vars if jinja_vars else 'NONE')
    
    jinja_blocks = set()
    for m in re.finditer(r'\{%[^%]+%\}', html_def):
        jinja_blocks.add(m.group())
    print('Jinja2 {% %} found:', jinja_blocks if jinja_blocks else 'NONE')

except Exception as e:
    traceback.print_exc()
