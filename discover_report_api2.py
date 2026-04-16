# -*- coding: utf-8 -*-
"""Verify cookie and fetch report page, then discover API endpoints"""
import requests
import re
import json

COOKIE = {'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc'}
BASE = 'https://www.yeahpromos.com'
REPORT_URL = f'{BASE}/index/offer/report_performance?start_date=2026-03-01&end_date=2026-03-23&site_id=12002&dim=CampaignId'

# 1. Get report page
print("[1] Fetching report page...")
resp = requests.get(REPORT_URL, cookies=COOKIE, timeout=15, allow_redirects=False)
print(f"  Status: {resp.status_code}")

if resp.status_code == 302:
    loc = resp.headers.get('Location', '')
    print(f"  Redirected to: {loc}")
    print("  Cookie is EXPIRED!")
    exit(1)

if resp.status_code == 200:
    html = resp.text
    print(f"  HTML length: {len(html)}")
    
    # Save HTML
    with open('output/report_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("  Saved to output/report_page.html")
    
    # 2. Find all script tags (inline JS)
    print("\n[2] Searching for API endpoints in inline JS...")
    inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"  Found {len(inline_scripts)} inline script blocks")
    
    api_candidates = set()
    ajax_calls = set()
    
    for i, script in enumerate(inline_scripts):
        # Look for URL patterns
        urls = re.findall(r'["\'](/index/[^"\']+)["\']', script)
        for u in urls:
            api_candidates.add(u)
        
        # Look for $.ajax, $.get, $.post
        ajax_matches = re.findall(r'\$\.(?:ajax|get|post)\s*\(\s*({[^}]+})', script)
        for m in ajax_matches:
            ajax_calls.add(m[:200])
        
        # Look for fetch()
        fetch_matches = re.findall(r'fetch\s*\(\s*["\']([^"\']+)["\']', script)
        for m in fetch_matches:
            api_candidates.add(m)
        
        # Look for url: patterns
        url_matches = re.findall(r'url\s*:\s*["\']([^"\']+)["\']', script)
        for m in url_matches:
            api_candidates.add(m)
        
        # Look for data-url attributes
        data_urls = re.findall(r'data-[^=]*=["\']([^"\']+)["\']', script)
        for m in data_urls:
            if '/index/' in m or 'api' in m.lower() or 'report' in m.lower():
                api_candidates.add(m)
    
    # Also search in HTML (not just scripts)
    html_urls = re.findall(r'data-url=["\']([^"\']+)["\']', html)
    for u in html_urls:
        api_candidates.add(u)
    
    print(f"\n  All /index/ URLs found ({len(api_candidates)}):")
    for u in sorted(api_candidates):
        print(f"    {u}")
    
    if ajax_calls:
        print(f"\n  AJAX calls found ({len(ajax_calls)}):")
        for a in sorted(ajax_calls):
            safe = a.encode('ascii', 'replace').decode('ascii')
            print(f"    {safe}")
    
    # 3. Look for external script files
    print("\n[3] External script files:")
    ext_scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
    for s in ext_scripts:
        print(f"    {s}")
    
    # 4. Search for table/grid initialization patterns
    print("\n[4] Table/Grid initialization patterns:")
    table_patterns = re.findall(r'(?:DataTable|bootstrapTable|grid|table)\s*[\(]', html, re.IGNORECASE)
    print(f"  Found {len(table_patterns)} table init patterns")
    
    # 5. Search for any API endpoint patterns
    print("\n[5] All URL-like patterns containing 'report' or 'data':")
    report_urls = re.findall(r'["\']([^"\']*(?:report|performance|getData|loadData|query)[^"\']*)["\']', html, re.IGNORECASE)
    for u in report_urls:
        safe = u.encode('ascii', 'replace').decode('ascii')
        print(f"    {safe}")
