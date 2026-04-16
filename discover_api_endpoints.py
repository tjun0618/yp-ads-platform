# -*- coding: utf-8 -*-
"""
尝试发现 YP 平台的 API 端点
基于已知的 API 模式来猜测
"""
import requests
import json

COOKIE = {
    'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc',
    'user_id': '2864',
}

BASE = 'https://yeahpromos.com'

# 基于 YP 平台 URL 模式猜测的 API 端点
# 已知: /index/apioffer/getoffer, /index/getadvert/getadvert
CANDIDATE_APIS = [
    # 商品相关
    '/index/apioffer/getoffer',
    '/index/apioffer/getproducts',
    '/index/apioffer/getproduct',
    '/index/apioffer/getofferbymerchant',
    '/index/apioffer/getoffers',
    '/index/apioffer/getproductlist',
    '/index/apioffer/getproductsbymerchant',
    '/index/apioffer/getmerchantproducts',
    
    # 商户相关  
    '/index/getadvert/getadvert',
    '/index/getadvert/getmerchants',
    '/index/getadvert/getmerchant',
    '/index/getadvert/getmerchantdetail',
    '/index/getadvert/getmerchantproducts',
    
    # 报表相关
    '/index/apireport/performance',
    '/index/apireport/report',
    '/index/apireport/getreport',
    '/index/apireport/getdata',
    '/index/apireport/getperformance',
    '/index/api/report',
    '/index/api/getreport',
    
    # 其他可能的 API
    '/index/api/getproducts',
    '/index/api/getoffers',
    '/index/api/getmerchant',
    '/index/offer/api',
    '/index/offer/api_get',
    '/index/offer/getdata',
]

print("=" * 80)
print("发现 YP 平台 API 端点")
print("=" * 80)

found_apis = []

for endpoint in CANDIDATE_APIS:
    url = f"{BASE}{endpoint}"
    
    # 准备参数
    params = {
        'site_id': '12002',
        'page': 1,
        'limit': 5,
    }
    
    # 某些端点可能需要不同参数
    if 'merchant' in endpoint.lower():
        params['advert_id'] = '362548'  # NORTIV 8
    if 'report' in endpoint.lower():
        params.update({
            'start_date': '2026-03-01',
            'end_date': '2026-03-23',
            'dim': 'CampaignId'
        })
    
    try:
        resp = requests.get(url, cookies=COOKIE, params=params, timeout=10)
        
        if resp.status_code == 200:
            content_type = resp.headers.get('Content-Type', '')
            
            # 检查是否是 JSON
            if 'json' in content_type.lower() or resp.text.strip().startswith('{'):
                try:
                    data = resp.json()
                    status = data.get('status', data.get('code', 'unknown'))
                    
                    # 成功的 API
                    if status in ['SUCCESS', 0, 200, 'success'] or 'data' in data:
                        print(f"\n✓ HIT: {endpoint}")
                        print(f"  Status in response: {status}")
                        print(f"  Response keys: {list(data.keys())[:10]}")
                        
                        # 检查数据结构
                        if 'data' in data:
                            d = data['data']
                            if isinstance(d, list):
                                print(f"  Data: list[{len(d)}]")
                                if d and isinstance(d[0], dict):
                                    print(f"  First item keys: {list(d[0].keys())[:10]}")
                            elif isinstance(d, dict):
                                print(f"  Data keys: {list(d.keys())[:10]}")
                        
                        found_apis.append({
                            'endpoint': endpoint,
                            'status': status,
                            'keys': list(data.keys())
                        })
                        
                        # 保存样本
                        safe_name = endpoint.replace('/', '_').replace('.', '_')
                        with open(f'output/api_{safe_name}.json', 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                except:
                    pass
            
    except Exception as e:
        pass

print("\n" + "=" * 80)
print(f"发现 {len(found_apis)} 个可用 API:")
print("=" * 80)
for api in found_apis:
    print(f"  {api['endpoint']}")
    print(f"    Status: {api['status']}")
    print(f"    Keys: {api['keys']}")
