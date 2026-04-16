"""
刷新待申请商户的投放链接
用法: python refresh_pending_merchants.py
功能:
1. 找出飞书表中状态为「待申请」的记录
2. 提取这些记录对应的商户 MID
3. 重新抓取这些商户的网页页面，检查是否已有 track token
4. 如果有，更新 asin_map + 更新飞书记录（状态改为「可推广」+ 补全链接）
"""
import requests, json, time, re, os
from urllib.parse import urlencode

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'
SITE_ID = '12002'
COOKIES = {
    'PHPSESSID': os.environ.get('YP_PHPSESSID', '5tg1c06l5m15bd4d7rbu6gqbn2')
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASIN_MAP_FILE = os.path.join(BASE_DIR, 'output', 'asin_merchant_map.json')

def get_feishu_token():
    resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        json={'app_id': APP_ID, 'app_secret': APP_SECRET})
    return resp.json()['tenant_access_token']

def get_pending_records(token):
    """获取飞书表中状态为「待申请」的记录"""
    headers = {'Authorization': 'Bearer ' + token}
    all_records = []
    page_token = None

    while True:
        params = {'page_size': 500, 'filter': json.dumps([{"conjunction": "and", "conditions": [{"field_name": "推广状态", "operator": "is", "value": ["待申请"]}]}])}
        if page_token:
            params['page_token'] = page_token

        resp = requests.get(
            f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records',
            headers=headers, params=params)
        data = resp.json()

        items = data.get('data', {}).get('items', [])
        all_records.extend(items)

        page_token = data.get('data', {}).get('page_token')
        if not page_token or not items:
            break

    return all_records

def scrape_merchant_page(mid):
    """抓取单个商户页面，检查是否有 track token"""
    url = f'https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id={SITE_ID}'
    
    try:
        resp = requests.get(url, cookies=COOKIES, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if resp.status_code != 200:
            return None, f"HTTP {resp.status_code}"
        
        html = resp.text
        
        # 提取所有 ClipboardJS.copy('...') 中的投放链接
        pattern = r"ClipboardJS\.copy\('(https://yeahpromos\.com/index/index/openurlproduct\?[^']+)'\)"
        links = re.findall(pattern, html)
        
        if not links:
            return None, "无投放链接（未申请或未通过）"
        
        # 解析链接中的 track 和 pid
        results = []
        for link in links:
            track_match = re.search(r'track=([^&]+)', link)
            pid_match = re.search(r'pid=(\d+)', link)
            
            results.append({
                'tracking_url': link,
                'track_token': track_match.group(1) if track_match else '',
                'pid': pid_match.group(1) if pid_match else ''
            })
        
        return results, f"找到 {len(results)} 个投放链接"
        
    except requests.exceptions.Timeout:
        return None, "请求超时"
    except Exception as e:
        return None, str(e)

def extract_merchant_info(html, mid):
    """从商户页面提取商户名"""
    # 尝试从页面标题或内容中提取商户名
    name_match = re.search(r'<h[23][^>]*>([^<]+)</h[23]>', html)
    if name_match:
        return name_match.group(1).strip()
    return ''

def main():
    print("=" * 60)
    print("刷新待申请商户 - 检查投放链接是否已生成")
    print("=" * 60)

    # Step 1: 获取待申请记录
    print("\n[1] 获取飞书「待申请」记录...")
    token = get_feishu_token()
    pending_records = get_pending_records(token)
    print(f"  找到 {len(pending_records)} 条待申请记录")

    if not pending_records:
        print("  没有待申请记录，无需刷新")
        return

    # Step 2: 提取商户 MID 列表（去重）
    print("\n[2] 提取涉及的商户...")
    
    # 加载 asin_map
    with open(ASIN_MAP_FILE, 'r', encoding='utf-8') as f:
        asin_map = json.load(f)

    # 按 MID 分组记录
    merchant_records = {}  # mid -> [record_ids]
    for rec in pending_records:
        record_id = rec['record_id']
        fields = rec.get('fields', {})
        
        asin_raw = fields.get('ASIN')
        if isinstance(asin_raw, list):
            asin = (asin_raw[0] if asin_raw else '') or ''
        else:
            asin = asin_raw or ''
        asin = asin.strip()

        # 优先用飞书记录中的 Merchant ID
        mid_raw = fields.get('Merchant ID')
        if isinstance(mid_raw, list):
            mid = (mid_raw[0] if mid_raw else '') or ''
        else:
            mid = mid_raw or ''
        mid = str(mid).strip()

        # 如果飞书没存 mid，从 asin_map 查
        if not mid and asin and asin in asin_map:
            info = asin_map[asin]
            if info and isinstance(info, dict):
                mid = str(info.get('merchant_id', '')).strip()

        if mid:
            if mid not in merchant_records:
                merchant_records[mid] = []
            merchant_records[mid].append({
                'record_id': record_id,
                'asin': asin
            })

    print(f"  涉及 {len(merchant_records)} 个商户")

    # Step 3: 逐个商户刷新
    print(f"\n[3] 开始刷新商户页面...")
    print("-" * 60)

    newly_approved = []  # 新批准的商户
    still_pending = []   # 仍然待申请
    errors = []          # 出错的

    total_merchants = len(merchant_records)
    for i, (mid, records) in enumerate(merchant_records.items()):
        asin_count = len(records)
        links, msg = scrape_merchant_page(mid)

        if links:
            newly_approved.append({
                'mid': mid,
                'link_count': len(links),
                'record_count': asin_count,
                'links': links,
                'records': records
            })
            status_icon = "OK"
        elif "HTTP" in msg or "超时" in msg or str(msg).startswith("Error"):
            errors.append({'mid': mid, 'msg': msg, 'record_count': asin_count})
            status_icon = "ERR"
        else:
            still_pending.append({'mid': mid, 'msg': msg, 'record_count': asin_count})
            status_icon = ".."

        print(f"  [{status_icon}] {i+1}/{total_merchants} MID={mid} ({asin_count}条) - {msg}")
        time.sleep(0.5)

    # Step 4: 处理新批准的商户
    print(f"\n[4] 处理结果...")
    print(f"  新批准商户: {len(newly_approved)}")
    print(f"  仍然待申请: {len(still_pending)}")
    print(f"  抓取出错:   {len(errors)}")

    if not newly_approved:
        print("\n  没有新批准的商户，无需更新")
        return

    # 更新 asin_map 和飞书
    print(f"\n[5] 更新数据...")
    updated_count = 0
    feishu_headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

    for approved in newly_approved:
        mid = approved['mid']
        links = approved['links']
        records = approved['records']
        
        # 建立 pid -> tracking_url 映射
        pid_to_link = {}
        for link_info in links:
            pid = link_info.get('pid', '')
            if pid:
                pid_to_link[pid] = link_info

        for rec in records:
            record_id = rec['record_id']
            asin = rec['asin']

            # 更新 asin_map
            if asin and asin in asin_map:
                for link_info in links:
                    if asin_map[asin].get('pid') == link_info.get('pid'):
                        asin_map[asin]['tracking_url'] = link_info['tracking_url']
                        asin_map[asin]['track_token'] = link_info['track_token']
                        break
                else:
                    # pid 不匹配，用第一个链接
                    asin_map[asin]['tracking_url'] = links[0]['tracking_url']
                    asin_map[asin]['track_token'] = links[0]['track_token']

            # 更新飞书记录
            update_fields = {"推广状态": "可推广"}
            
            # 补全 Tracking URL 和 Track Token
            if links:
                update_fields['Tracking URL'] = links[0]['tracking_url']
                update_fields['Track Token'] = links[0]['track_token']

            try:
                resp = requests.put(
                    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}',
                    headers=feishu_headers,
                    json={"fields": update_fields},
                    timeout=10)
                
                if resp.json().get('code') == 0:
                    updated_count += 1
                else:
                    print(f"    飞书更新失败: record={record_id}, msg={resp.json().get('msg')}")
            except Exception as e:
                print(f"    飞书更新异常: {record_id}, {e}")

            time.sleep(0.15)

    # 保存更新后的 asin_map
    with open(ASIN_MAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(asin_map, f, ensure_ascii=False, indent=2)
    
    print(f"\n  asin_map 已更新: {ASIN_MAP_FILE}")
    print(f"  飞书记录已更新: {updated_count} 条")

    # 保存刷新报告
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_pending': len(pending_records),
        'total_merchants': total_merchants,
        'newly_approved_merchants': len(newly_approved),
        'still_pending_merchants': len(still_pending),
        'errors': len(errors),
        'updated_records': updated_count,
        'approved_mids': [a['mid'] for a in newly_approved],
        'still_pending_mids': [s['mid'] for s in still_pending],
        'error_mids': [e['mid'] for e in errors]
    }

    report_file = os.path.join(BASE_DIR, 'output', 'refresh_report.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"刷新完成! {updated_count} 条记录从「待申请」变为「可推广」")
    print(f"详细报告: {report_file}")
    print(f"{'=' * 60}")

if __name__ == '__main__':
    main()
