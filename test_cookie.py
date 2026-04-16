# -*- coding: utf-8 -*-
import requests

# Cookie from browser - domain is yeahpromos.com (not www)
COOKIE = {
    'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc',
    'user_id': '2864',
    'user_name': 'Tong%20Jun',
    'think_lang': 'zh-cn',
}

# Try both domain variants
DOMAINS = [
    'https://yeahpromos.com',
    'https://www.yeahpromos.com',
]

REPORT_PATH = '/index/offer/report_performance?start_date=2026-03-01&end_date=2026-03-23&site_id=12002&dim=CampaignId'

for domain in DOMAINS:
    url = domain + REPORT_PATH
    print(f"\n=== Testing {domain} ===")
    
    resp = requests.get(url, cookies=COOKIE, timeout=15, allow_redirects=False)
    print(f"  Status: {resp.status_code}")
    
    if resp.status_code == 302:
        loc = resp.headers.get('Location', '')
        print(f"  Redirect: {loc}")
    elif resp.status_code == 200:
        print(f"  Success! HTML length: {len(resp.text)}")
        # Save
        with open(f'output/report_page_{domain.replace("://", "_")}.html', 'w', encoding='utf-8') as f:
            f.write(resp.text)
        print(f"  Saved HTML")
        
        # Look for API patterns
        import re
        api_urls = re.findall(r'["\'](/index/[^"\']*(?:api|report|data|query)[^"\']*)["\']', resp.text, re.IGNORECASE)
        if api_urls:
            print(f"\n  API URLs found ({len(set(api_urls))}):")
            for u in sorted(set(api_urls))[:20]:
                print(f"    {u}")
