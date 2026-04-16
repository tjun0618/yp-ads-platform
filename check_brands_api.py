# -*- coding: utf-8 -*-
"""
检查 brands 和 advert/index 页面的 API 接口
"""
import requests
import re
import json

COOKIE = {
    'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc',
    'user_id': '2864',
    'user_name': 'Tong%20Jun',
}

BASE = 'https://yeahpromos.com'

PAGES = [
    '/index/offer/brands',
    '/index/advert/index',
]

print("=" * 80)
print("检查页面 API 接口")
print("=" * 80)

for page in PAGES:
    url = f"{BASE}{page}"
    print(f"\n{'='*60}")
    print(f"页面: {page}")
    print('='*60)
    
    # 获取页面 HTML
    resp = requests.get(url, cookies=COOKIE, timeout=15)
    print(f"Status: {resp.status_code}")
    
    if resp.status_code == 200:
        html = resp.text
        print(f"HTML length: {len(html)}")
        
        # 保存 HTML
        safe_name = page.replace('/', '_')
        with open(f'output/page_{safe_name}.html', 'w', encoding='utf-8') as f:
            f.write(html)
        
        # 查找 API 相关的内容
        print("\n[1] 查找 data-url 属性:")
        data_urls = re.findall(r'data-url=["\']([^"\']+)["\']', html)
        for u in set(data_urls):
            print(f"  {u}")
        
        print("\n[2] 查找 ajax/api 相关的 URL:")
        api_patterns = re.findall(r'["\'](/index/[^"\']*(?:api|ajax|data|load|get)[^"\']*)["\']', html, re.IGNORECASE)
        for u in set(api_patterns):
            print(f"  {u}")
        
        print("\n[3] 查找 script 中的 URL 模式:")
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
        all_urls = set()
        for script in scripts:
            urls = re.findall(r'["\'](/index/[^"\']+)["\']', script)
            all_urls.update(urls)
        
        for u in sorted(all_urls):
            if any(k in u.lower() for k in ['api', 'ajax', 'data', 'get', 'load', 'query']):
                print(f"  {u}")
        
        # 查找特定的 brands/advert 相关 API
        print("\n[4] 查找 brands/advert 相关端点:")
        brand_patterns = re.findall(r'["\'](/index/[^"\']*(?:brand|advert|merchant)[^"\']*)["\']', html, re.IGNORECASE)
        for u in set(brand_patterns):
            print(f"  {u}")

print("\n" + "=" * 80)
print("测试发现的 API 端点")
print("=" * 80)

# 测试可能的 API 端点
TEST_ENDPOINTS = [
    '/index/offer/getbrands',
    '/index/offer/getadvert',
    '/index/advert/getadvert',
    '/index/advert/getlist',
    '/index/apioffer/getbrands',
    '/index/apiadvert/getlist',
    '/index/offer/brandsdata',
    '/index/advert/indexdata',
]

TOKEN = '7951dc7484fa9f9d'
HEADERS = {'token': TOKEN}

for endpoint in TEST_ENDPOINTS:
    url = f"{BASE}{endpoint}"
    params = {'site_id': '12002', 'page': 1, 'limit': 10}
    
    try:
        resp = requests.get(url, headers=HEADERS, cookies=COOKIE, params=params, timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                status = data.get('status', data.get('code', 'unknown'))
                if status in ['SUCCESS', 0, 200] or 'data' in data:
                    print(f"\n✓ HIT: {endpoint}")
                    print(f"  Status: {status}")
                    print(f"  Keys: {list(data.keys())[:10]}")
                    if 'data' in data:
                        d = data['data']
                        if isinstance(d, list):
                            print(f"  Data: list[{len(d)}]")
                        elif isinstance(d, dict):
                            print(f"  Data keys: {list(d.keys())[:10]}")
            except:
                pass
    except:
        pass

print("\n" + "=" * 80)
