# -*- coding: utf-8 -*-
"""
尝试找出 YP 报表页面调用的 API 端点
策略：
1. 直接用 requests 获取报表页面 HTML，找里面的 JS API 调用
2. 尝试常见的 YP API 端点格式
3. 分析 YP 平台已有的 API 模式来猜测报表 API
"""

import requests
import re
import json

# 两个 cookie 都试一下
COOKIES_LIST = [
    {'PHPSESSID': '5tg1c06l5m15bd4d7rbu6gqbn2'},
    {'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc'},
]

BASE = 'https://www.yeahpromos.com'
REPORT_URL = f'{BASE}/index/offer/report_performance?start_date=2026-03-01&end_date=2026-03-23&site_id=12002&dim=CampaignId'

# 尝试猜测的 API 端点
CANDIDATE_APIS = [
    # 报表相关
    '/index/offer/report_performance',
    '/index/offer/get_report',
    '/index/offer/getPerformance',
    '/index/offer/report',
    '/index/report/performance',
    '/index/report/getData',
    '/index/apioffer/report',
    '/index/apioffer/getreport',
    '/index/apioffer/performance',
    '/index/apioffer/getperformance',
    # 商品-商户关系相关
    '/index/offer/get_products',
    '/index/offer/getproduct',
    '/index/apioffer/getproducts',
    '/index/apioffer/get_products',
    '/index/getadvert/getproducts',
    '/index/offer/brand_products',
    '/index/offer/getBrandProducts',
]

for cookie in COOKIES_LIST:
    print(f"\n=== Testing cookie: {cookie['PHPSESSID'][:10]}... ===")
    
    # 1. 先获取报表页面 HTML
    print("\n[1] Fetching report page HTML...")
    try:
        resp = requests.get(REPORT_URL, cookies=cookie, timeout=15, allow_redirects=False)
        print(f"  Status: {resp.status_code}")
        if resp.status_code == 200:
            html = resp.text
            print(f"  HTML length: {len(html)}")
            
            # 搜索 API 相关的 JS 代码
            api_patterns = [
                r'(?:url|href|action|src)\s*[=:]\s*["\']([^"\']*(?:api|report|performance|data|ajax)[^"\']*)["\']',
                r'\.(?:get|post|ajax|fetch)\s*\(\s*["\']([^"\']+)["\']',
                r'loadData|loadReport|getReport|fetchData|getData',
            ]
            
            found_apis = set()
            for pattern in api_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for m in matches:
                    found_apis.add(str(m)[:120])
            
            if found_apis:
                print(f"  Found API references:")
                for api in found_apis:
                    print(f"    {api}")
            
            # 搜索 script src
            scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if scripts:
                print(f"\n  Script sources ({len(scripts)}):")
                for s in scripts:
                    print(f"    {s}")
        elif resp.status_code == 302:
            print(f"  Redirected to: {resp.headers.get('Location', 'unknown')}")
        else:
            print(f"  Unexpected status")
    except Exception as e:
        print(f"  Error: {e}")
    
    # 2. 尝试常见 API 端点
    print("\n[2] Testing candidate API endpoints...")
    for endpoint in CANDIDATE_APIS:
        url = f'{BASE}{endpoint}'
        # GET with params
        params = {
            'start_date': '2026-03-01',
            'end_date': '2026-03-23',
            'site_id': '12002',
            'dim': 'CampaignId',
            'page': 1,
            'limit': 5,
        }
        try:
            resp = requests.get(url, cookies=cookie, params=params, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data.get('status') == 'SUCCESS' or data.get('code') == 0 or 'data' in data:
                        print(f"  HIT! {endpoint}")
                        print(f"    Response keys: {list(data.keys())[:10]}")
                        # Print sample
                        sample = json.dumps(data, ensure_ascii=False)[:500]
                        print(f"    Sample: {sample}")
                    else:
                        # Still interesting
                        print(f"  OK but empty: {endpoint} -> {json.dumps(data, ensure_ascii=False)[:100]}")
                except:
                    pass
            elif resp.status_code == 302:
                pass  # Still login redirect
        except:
            pass
    
    # 3. 也试试 POST
    print("\n[3] Testing POST endpoints...")
    for endpoint in CANDIDATE_APIS[:5]:
        url = f'{BASE}{endpoint}'
        payload = {
            'start_date': '2026-03-01',
            'end_date': '2026-03-23',
            'site_id': '12002',
            'dim': 'CampaignId',
            'page': 1,
            'limit': 5,
        }
        try:
            resp = requests.post(url, cookies=cookie, json=payload, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if 'data' in data:
                        print(f"  POST HIT! {endpoint}")
                        print(f"    Keys: {list(data.keys())[:10]}")
                        sample = json.dumps(data, ensure_ascii=False)[:300]
                        print(f"    Sample: {sample}")
                except:
                    pass
        except:
            pass

print("\n=== Done ===")
