"""
逐条更新飞书 Offers 表的「推广状态」字段
"""
import requests, json, time

APP_ID = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID = 'tblMCbaHhP88sgeS'

def get_feishu_token():
    resp = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        json={'app_id': APP_ID, 'app_secret': APP_SECRET})
    return resp.json()['tenant_access_token']

def main():
    token = get_feishu_token()
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

    # 加载 asin_map
    print("[1] 加载 asin_map...")
    with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
        asin_map = json.load(f)
    print(f"  ASIN 映射: {len(asin_map):,} 个")

    # 获取所有记录
    print("\n[2] 获取飞书记录...")
    all_records = []
    page_token = None

    while True:
        params = {'page_size': 500}
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

    print(f"  共 {len(all_records):,} 条记录")

    # 分类
    print("\n[3] 分类记录...")
    to_promote = []
    to_apply = []
    no_match = []

    for rec in all_records:
        record_id = rec['record_id']
        fields = rec.get('fields', {})
        
        # ASIN 字段可能是字符串或数组
        asin_raw = fields.get('ASIN')
        if isinstance(asin_raw, list):
            asin = (asin_raw[0] if asin_raw else '') or ''
        else:
            asin = asin_raw or ''
        asin = asin.strip()

        # Tracking URL
        url_raw = fields.get('Tracking URL')
        if isinstance(url_raw, list):
            tracking_url = (url_raw[0] if url_raw else '') or ''
        else:
            tracking_url = url_raw or ''
        tracking_url = tracking_url.strip()

        # 检查当前状态，跳过已更新的
        status_raw = fields.get('推广状态')
        if isinstance(status_raw, list):
            current_status = (status_raw[0] if status_raw else '') or ''
        else:
            current_status = status_raw or ''
        current_status = (current_status or '').strip()

        if current_status:
            # 已有状态，跳过
            continue

        if tracking_url:
            to_promote.append(record_id)
        elif asin and asin in asin_map:
            to_apply.append(record_id)
        else:
            no_match.append(record_id)

    print(f"  可推广: {len(to_promote)}")
    print(f"  待申请: {len(to_apply)}")
    print(f"  未匹配: {len(no_match)}")
    print(f"  已有状态跳过: {len(all_records) - len(to_promote) - len(to_apply) - len(no_match)}")

    # 逐条更新
    total = len(to_promote) + len(to_apply) + len(no_match)
    print(f"\n[4] 逐条更新 ({total} 条, 预计 {total * 0.15 / 60:.1f} 分钟)...")

    success = 0
    fail = 0
    count = 0
    start_time = time.time()
    token_refresh_time = time.time()

    # 合并所有待更新记录
    update_queue = [
        (to_promote, "可推广"),
        (to_apply, "待申请"),
        (no_match, "未匹配")
    ]

    for records, status in update_queue:
        if not records:
            continue
        
        for record_id in records:
            # 每 1800 秒刷新一次 token（飞书 token 有效期 2 小时）
            if time.time() - token_refresh_time > 1800:
                print("  刷新飞书 token...")
                token = get_feishu_token()
                headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
                token_refresh_time = time.time()
            
            try:
                body = {
                    "fields": {
                        "推广状态": status
                    }
                }
                resp = requests.put(
                    f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}',
                    headers=headers, json=body, timeout=10)
                
                result = resp.json()
                if result.get('code') == 0:
                    success += 1
                else:
                    fail += 1
                    # 如果是 token 过期，立即刷新
                    if result.get('code') == 99991668 or result.get('code') == 99991663:
                        token = get_feishu_token()
                        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
                        token_refresh_time = time.time()

            except Exception as e:
                fail += 1

            count += 1
            if count % 100 == 0:
                elapsed = time.time() - start_time
                pct = count / total * 100
                remaining = (total - count) * 0.15 / 60
                print(f"  进度: {count}/{total} ({pct:.1f}%) | 成功:{success} 失败:{fail} | 预计剩余: {remaining:.1f} 分钟")

            time.sleep(0.15)

    elapsed = time.time() - start_time
    print(f"\n  完成! 耗时 {elapsed:.0f} 秒")
    print(f"  成功: {success}, 失败: {fail}")

    # 保存汇总
    summary = {
        'total_updated': count,
        'success': success,
        'fail': fail,
        'can_promote': len(to_promote),
        'pending_apply': len(to_apply),
        'no_match': len(no_match),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    with open('output/promotion_status_update_result.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存: output/promotion_status_update_result.json")

if __name__ == '__main__':
    main()
