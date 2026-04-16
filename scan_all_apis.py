# -*- coding: utf-8 -*-
"""
系统扫描 YP 平台所有可能的 API 端点
基于常见的 URL 模式和已知的端点进行猜测
"""
import requests
import json
from urllib.parse import urljoin

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
HEADERS = {'token': TOKEN}
COOKIE = {'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc'}

BASE = 'https://www.yeahpromos.com'

# 基于发现的模式构建候选 API 列表
API_PREFIXES = [
    '/index/api',
    '/index/apioffer',
    '/index/apiadvert',
    '/index/apireport',
    '/index/apicategory',
    '/index/apimerchant',
    '/index/apiproduct',
    '/index/apiuser',
    '/index/apiorder',
    '/index/apitrack',
    '/index/apicommission',
    '/index/apistats',
    '/index/apidata',
]

API_ACTIONS = [
    'get', 'list', 'query', 'search', 'find',
    'getlist', 'getdata', 'getinfo', 'getdetail',
    'getoffer', 'getoffers', 'getproduct', 'getproducts',
    'getmerchant', 'getmerchants', 'getadvert', 'getadverts',
    'getcategory', 'getcategories',
    'getreport', 'getperformance', 'getstats',
    'getuser', 'getorder', 'gettracking',
    'getcommission', 'getpayout',
    'getbrand', 'getbrands',
    'getall', 'gettop', 'getnew', 'gethot',
    'export', 'download', 'upload',
    'create', 'update', 'delete', 'save',
    'apply', 'join', 'injoin', 'enroll',
    'check', 'verify', 'validate',
    'sync', 'refresh', 'reload',
]

# 已知的有效端点（用于验证）
KNOWN_WORKING = [
    '/index/apioffer/getoffer',
    '/index/getadvert/getadvert',
    '/index/apioffer/getcategory',
]

# 从之前探索中发现的端点
DISCOVERED = [
    '/index/advert/export_top_merchants',
    '/index/advert/injoin2',
]

print("=" * 80)
print("YP 平台 API 端点扫描")
print("=" * 80)

working_apis = []

# 测试已知的有效端点（验证 token 是否工作）
print("\n[1] 验证已知端点（确认 token 有效）")
print("-" * 60)
for endpoint in KNOWN_WORKING:
    url = urljoin(BASE, endpoint)
    params = {'site_id': SITE_ID, 'page': 1, 'limit': 5}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 200:
            try:
                data = resp.json()
                status = data.get('status', data.get('Status', 'unknown'))
                if status in ['SUCCESS', 'success', 0, 200]:
                    print(f"  [OK] {endpoint} - WORKING")
                    working_apis.append({
                        'endpoint': endpoint,
                        'status': 'verified',
                        'sample_keys': list(data.keys())[:5]
                    })
                else:
                    print(f"  [FAIL] {endpoint} - Status: {status}")
            except:
                print(f"  [?] {endpoint} - Not JSON")
        else:
            print(f"  [FAIL] {endpoint} - HTTP {resp.status_code}")
    except Exception as e:
        print(f"  [FAIL] {endpoint} - Error: {e}")

# 测试已发现的端点
print("\n[2] 测试已发现的端点")
print("-" * 60)
for endpoint in DISCOVERED:
    url = urljoin(BASE, endpoint)
    
    try:
        resp = requests.get(url, headers=HEADERS, cookies=COOKIE, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '')
            if 'json' in content_type:
                try:
                    data = resp.json()
                    print(f"  [OK] {endpoint} - JSON")
                    working_apis.append({
                        'endpoint': endpoint,
                        'status': 'discovered',
                        'type': 'json',
                        'keys': list(data.keys())
                    })
                except:
                    pass
            elif 'spreadsheet' in content_type or 'excel' in content_type:
                print(f"  [OK] {endpoint} - EXCEL")
                working_apis.append({
                    'endpoint': endpoint,
                    'status': 'discovered',
                    'type': 'excel'
                })
            else:
                print(f"  [?] {endpoint} - {content_type[:30]}")
    except Exception as e:
        print(f"  [FAIL] {endpoint} - {e}")

# 系统扫描候选 API
print("\n[3] 系统扫描候选 API 端点")
print("-" * 60)
print("  扫描中... (这可能需要几分钟)")

candidates_tested = 0
for prefix in API_PREFIXES:
    for action in API_ACTIONS:
        endpoint = f"{prefix}/{action}"
        url = urljoin(BASE, endpoint)
        params = {'site_id': SITE_ID, 'page': 1, 'limit': 5}
        
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=5)
            candidates_tested += 1
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    status = data.get('status', data.get('Status', 'unknown'))
                    if status in ['SUCCESS', 'success', 0, 200] or 'data' in data:
                        print(f"  [FOUND] {endpoint}")
                        working_apis.append({
                            'endpoint': endpoint,
                            'status': 'found',
                            'keys': list(data.keys())[:10]
                        })
                        
                        # Save sample
                        safe_name = endpoint.replace('/', '_')
                        with open(f'output/api_scan_{safe_name}.json', 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                except:
                    pass
        except:
            pass
        
        if candidates_tested % 100 == 0:
            print(f"    ... tested {candidates_tested} endpoints")

print(f"\n  Total candidates tested: {candidates_tested}")

# 汇总结果
print("\n" + "=" * 80)
print(f"发现 {len(working_apis)} 个可用 API 端点")
print("=" * 80)

for api in working_apis:
    print(f"\n{api['endpoint']}")
    print(f"  Status: {api['status']}")
    if 'type' in api:
        print(f"  Type: {api['type']}")
    if 'keys' in api:
        print(f"  Response Keys: {api['keys']}")
    if 'sample_keys' in api:
        print(f"  Sample Keys: {api['sample_keys']}")

# 保存完整列表
with open('output/all_discovered_apis.json', 'w', encoding='utf-8') as f:
    json.dump(working_apis, f, ensure_ascii=False, indent=2)

print(f"\n完整列表已保存到: output/all_discovered_apis.json")
print("=" * 80)
