import sys
sys.path.insert(0, r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu')

# 直接导入 ads_manager，捕获渲染错误
import traceback

# 模拟 render_template_string 调用
try:
    from flask import Flask
    from jinja2 import Environment
    
    # 读取 ads_manager.py，找到 MERCHANT_PRODUCTS_UNIFIED_HTML 的值
    import re
    with open(r'C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\ads_manager.py', 'r', encoding='utf-8') as f:
        src = f.read()
    
    # 找 MERCHANT_PRODUCTS_UNIFIED_HTML 的定义
    idx = src.find('MERCHANT_PRODUCTS_UNIFIED_HTML')
    print(f'MERCHANT_PRODUCTS_UNIFIED_HTML found at line ~{src[:idx].count(chr(10))+1}')
    print(src[idx:idx+300])
    
except Exception as e:
    traceback.print_exc()
