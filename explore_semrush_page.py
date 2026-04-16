# -*- coding: utf-8 -*-
"""探查 SEMrush 页面结构"""
import re, sys, os
os.system('chcp 65001 >nul 2>&1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

html_file = 'temp/semrush_page_1775750009.html'
html = open(html_file, encoding='utf-8').read()

print(f"页面大小: {len(html)} 字符")
print()

# 1. 找含关键词的class
print("=" * 60)
print("含SEMrush关键词的CSS类名:")
print("=" * 60)
classes = re.findall(r'class=["\x27]([^"\x27]*(?:traffic|keyword|organic|paid|ad|compet|backlink|rank|search|overview|metric|chart|data|table|row|cell|card|panel|section|tab|nav|menu|sidebar|header|title|value|number|amount|score|percent)[^"\x27]*)["\x27]', html, re.I)
for c in sorted(set(classes))[:50]:
    print(f"  {c}")

# 2. 找所有table
print()
print("=" * 60)
print("页面中的table元素:")
print("=" * 60)
tables = re.findall(r'<table[^>]*class=["\x27]([^"\x27]*)["\x27][^>]*>', html, re.I)
for i, t in enumerate(tables[:10]):
    print(f"  table[{i}]: class='{t}'")

# 3. 找数据属性 data-*
print()
print("=" * 60)
print("data-* 属性:")
print("=" * 60)
data_attrs = re.findall(r'(data-[a-z][-a-z0-9]*)=', html, re.I)
for d in sorted(set(data_attrs))[:30]:
    print(f"  {d}")

# 4. 看看body文本前2000字
print()
print("=" * 60)
print("body文本前2000字:")
print("=" * 60)
body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.I | re.S)
if body_match:
    body = body_match.group(1)
    # 去标签
    text = re.sub(r'<[^>]+>', ' ', body)
    text = re.sub(r'\s+', ' ', text).strip()
    print(text[:2000])

# 5. 找Vue/React组件
print()
print("=" * 60)
print("前端框架标记:")
print("=" * 60)
vue = len(re.findall(r'data-v-[a-f0-9]+', html))
react = len(re.findall(r'data-react', html))
print(f"  Vue组件: {vue}")
print(f"  React标记: {react}")

# 6. 找API调用URL
print()
print("=" * 60)
print("页面中的API URL:")
print("=" * 60)
api_urls = re.findall(r'(https?://[^"\x27\s<>]*(?:api|analytics|data|query|search|keyword|traffic|overview)[^"\x27\s<>]*)', html, re.I)
for u in sorted(set(api_urls))[:20]:
    print(f"  {u}")
