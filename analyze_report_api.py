# -*- coding: utf-8 -*-
"""Deep analysis of report page to find API calls"""
import re
import json

with open('output/report_page_https_yeahpromos.com.html', 'r', encoding='utf-8') as f:
    html = f.read()

print("=" * 80)
print("报表页面 API 分析")
print("=" * 80)

# 1. Find all inline scripts
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
print(f"\n[1] Found {len(scripts)} script blocks")

# 2. Look for $.ajax, $.get, $.post calls
print("\n[2] AJAX calls found:")
for i, script in enumerate(scripts):
    # $.ajax({...})
    ajax_calls = re.findall(r'\$\.(?:ajax|get|post)\s*\(\s*({[^{}]*(?:{[^{}]*}[^{}]*)*})\s*\)', script, re.DOTALL)
    for call in ajax_calls:
        safe = call.replace('\n', ' ').replace('\t', ' ')[:300]
        if 'url' in safe or 'data' in safe:
            print(f"  Script {i}: {safe}")
    
    # url: "..."
    url_matches = re.findall(r'url\s*:\s*["\']([^"\']+)["\']', script)
    for url in url_matches:
        if '/index/' in url:
            print(f"  URL in script {i}: {url}")

# 3. Look for table/grid initialization
print("\n[3] Table initialization patterns:")
table_init = re.findall(r'(?:bootstrapTable|DataTable|initTable|loadData)\s*\([^)]*\)', html, re.IGNORECASE)
for t in table_init[:10]:
    safe = t.encode('ascii', 'replace').decode('ascii')[:200]
    print(f"  {safe}")

# 4. Look for data-url attributes (common in bootstrapTable)
print("\n[4] data-url attributes:")
data_urls = re.findall(r'data-url=["\']([^"\']+)["\']', html)
for u in data_urls:
    print(f"  {u}")

# 5. Look for report_performance or report_cpc calls
print("\n[5] report_performance/report_cpc references:")
report_refs = re.findall(r'report_(?:performance|cpc)[^"\'<>]*', html)
for r in set(report_refs):
    safe = r.encode('ascii', 'replace').decode('ascii')[:100]
    print(f"  {safe}")

# 6. Look for any API endpoint patterns
print("\n[6] All /index/ URLs in scripts:")
all_urls = set()
for script in scripts:
    urls = re.findall(r'["\'](/index/[^"\']+)["\']', script)
    all_urls.update(urls)

for u in sorted(all_urls):
    if any(k in u.lower() for k in ['api', 'report', 'data', 'query', 'get', 'post']):
        print(f"  {u}")

# 7. Look for function definitions that might call APIs
print("\n[7] Function definitions with 'report' or 'data':")
funcs = re.findall(r'function\s+(\w*[rR]eport\w*|\w*[dD]ata\w*|\w*[lL]oad\w*)\s*\([^)]*\)\s*\{', html)
for f in set(funcs):
    print(f"  {f}")

# 8. Search for specific patterns in the HTML
print("\n[8] Grid/table container attributes:")
grid_attrs = re.findall(r'<table[^>]*id=["\']([^"\']*)["\'][^>]*>', html)
for g in grid_attrs:
    print(f"  Table ID: {g}")

# Look for div with data attributes
div_data = re.findall(r'<div[^>]*data-[^>]*>', html)
for d in div_data[:10]:
    safe = d.encode('ascii', 'replace').decode('ascii')[:150]
    print(f"  Div: {safe}")

print("\n" + "=" * 80)
