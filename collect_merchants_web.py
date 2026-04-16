"""
通过网页端（Cookie）采集所有商户数据
由于 API 被限流，改用网页登录方式抓取
"""
import requests
import json
import re
import time
from datetime import datetime

# Cookie 配置
COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.yeahpromos.com/"
}

SITE_ID = "12002"
OUTPUT_FILE = "output/merchants_web.json"
STATE_FILE = "output/merchants_web_state.json"


def load_state():
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"page": 1, "total": 0}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def load_existing_merchants():
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def fetch_merchants_page(page, limit=100):
    """通过网页API端点采集商户数据"""
    url = "https://www.yeahpromos.com/index.php/index/getadvert/getadvert"
    
    # 尝试通过 Cookie 方式访问 API
    data = {
        "page": page,
        "limit": limit,
        "site_id": SITE_ID
    }
    
    headers = dict(HEADERS)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["X-Requested-With"] = "XMLHttpRequest"
    
    try:
        resp = requests.post(url, headers=headers, data=data, cookies=COOKIES, timeout=30)
        result = resp.json()
        
        if result.get('code') == 200:
            d = result.get('data', {})
            if isinstance(d, dict):
                records = d.get('Data', d.get('data', []))
            else:
                records = d if isinstance(d, list) else []
            return records, None
        else:
            return [], result.get('msg', 'Unknown error')
    except Exception as e:
        return [], str(e)


def fetch_merchants_page_v2(page):
    """尝试通过网页列表页面抓取"""
    url = f"https://www.yeahpromos.com/index/offer/offerList?site_id={SITE_ID}&page={page}"
    
    try:
        resp = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=30)
        
        # 检查是否需要登录
        if '/index/login' in resp.url or 'login' in resp.text[:500].lower():
            return [], "需要登录"
        
        # 尝试解析 JSON（如果是 AJAX 响应）
        if resp.headers.get('content-type', '').startswith('application/json'):
            result = resp.json()
            d = result.get('data', {})
            if isinstance(d, dict):
                records = d.get('Data', d.get('data', []))
            else:
                records = d
            return records, None
        
        return [], "非JSON响应"
    except Exception as e:
        return [], str(e)


def main():
    print("=" * 60)
    print("网页端商户数据采集")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    state = load_state()
    merchants = load_existing_merchants()
    
    # 建立已有商户ID集合
    existing_ids = set(str(m.get('merchant_id', '')) for m in merchants)
    
    print(f"当前商户数: {len(merchants)}")
    print(f"从第 {state['page']} 页继续...")
    
    page = state['page']
    max_empty = 3
    empty_count = 0
    new_count = 0
    
    while True:
        print(f"\n抓取第 {page} 页...", end=" ", flush=True)
        
        records, error = fetch_merchants_page(page)
        
        if error:
            print(f"错误: {error}")
            empty_count += 1
            if empty_count >= max_empty:
                print(f"\n连续 {max_empty} 次失败，停止")
                break
            time.sleep(5)
            page += 1
            continue
        
        if not records:
            print("空页面")
            empty_count += 1
            if empty_count >= max_empty:
                print(f"\n连续 {max_empty} 次空页面，采集完成")
                break
            page += 1
            continue
        
        empty_count = 0
        page_new = 0
        
        for r in records:
            mid = str(r.get('merchant_id', r.get('id', '')))
            if mid and mid not in existing_ids:
                merchants.append({
                    'merchant_id': r.get('merchant_id', r.get('id')),
                    'merchant_name': r.get('merchant_name', r.get('name', '')),
                    'avg_payout': r.get('avg_payout', r.get('payout', 0)),
                    'cookie_days': r.get('cookie_days', 0),
                    'website': r.get('website', ''),
                    'country': r.get('country', ''),
                    'status': r.get('status', ''),
                    'collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                existing_ids.add(mid)
                page_new += 1
                new_count += 1
        
        print(f"获取 {len(records)} 条，新增 {page_new} 条，累计 {len(merchants)} 条")
        
        # 每10页保存一次
        if page % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(merchants, f, ensure_ascii=False, indent=2)
            state['page'] = page + 1
            state['total'] = len(merchants)
            save_state(state)
            print(f"  已保存 {len(merchants)} 条商户数据")
        
        page += 1
        time.sleep(0.5)
    
    # 最终保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    
    # 同时更新主文件
    with open('output/merchants_data.json', 'w', encoding='utf-8') as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    
    state['page'] = page
    state['total'] = len(merchants)
    save_state(state)
    
    print(f"\n{'=' * 60}")
    print(f"采集完成!")
    print(f"总商户数: {len(merchants)}")
    print(f"本次新增: {new_count}")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
