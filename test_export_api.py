#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 export_advert_products 真实返回"""
import json, requests
from pathlib import Path

cookie_data = json.loads(Path(r'c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\output\yp_cookie.json').read_text('utf-8'))
phpsessid = cookie_data['PHPSESSID']

session = requests.Session()
session.cookies.set('PHPSESSID', phpsessid)
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'

for mid, name in [("363776", "Altec Lansing"), ("363722", "Aerotrunk"), ("363717", "Aensso")]:
    url = f'https://www.yeahpromos.com/index/advert/export_advert_products?advert_id={mid}&site_id=12002'
    session.headers['Referer'] = f'https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id=12002'
    r = session.get(url, timeout=20)
    ct = r.headers.get('Content-Type', '')
    content = r.content
    
    if content[:4] == b'PK\x03\x04':
        file_type = 'Excel/ZIP'
    elif content[:5] == b'<html' or content[:9] == b'<!DOCTYPE':
        file_type = 'HTML'
    elif len(content) == 0:
        file_type = 'EMPTY'
    else:
        file_type = f'UNKNOWN({content[:4]})'
    
    print(f'{name} ({mid}): status={r.status_code}, type={file_type}, size={len(content)}, ct={ct[:50]}')
    if file_type == 'HTML':
        print(f'  HTML head: {r.text[:300]}')
    elif file_type == 'Excel/ZIP':
        print(f'  ✅ 真实 Excel 文件！')
