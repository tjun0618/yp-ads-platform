"""
在飞书 Offers 表添加「推广状态」字段 + 批量标注现有记录
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

    # ============ Step 1: 添加「推广状态」字段 ============
    print("[1] 添加「推广状态」字段...")

    # 先检查是否已存在
    resp = requests.get(
        f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields',
        headers=headers)
    existing_fields = [f['field_name'] for f in resp.json().get('data', {}).get('items', [])]

    if '推广状态' in existing_fields:
        print("  字段「推广状态」已存在，跳过创建")
    else:
        # 创建单选字段
        create_data = {
            "field_name": "推广状态",
            "type": 3,  # 单选
            "property": {
                "options": [
                    {"name": "可推广", "color": 0},     # 绿色
                    {"name": "待申请", "color": 1},     # 蓝色
                    {"name": "未匹配", "color": 2}      # 灰色
                ]
            }
        }
        resp = requests.post(
            f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/fields',
            headers=headers, json=create_data)
        result = resp.json()
        if result.get('code') == 0:
            print("  创建成功: 可推广 / 待申请 / 未匹配")
        else:
            print(f"  创建失败: {result}")
            return

    # ============ Step 2: 获取所有记录并分类 ============
    print("\n[2] 获取飞书记录并分类...")

    # 加载 asin_map
    with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
        asin_map = json.load(f)

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

    print(f"  共 {len(all_records)} 条记录")

    # 分类
    to_promote = []    # 可推广
    to_apply = []      # 待申请
    no_match = []      # 未匹配

    for rec in all_records:
        record_id = rec['record_id']
        fields = rec.get('fields', {})
        asin = (fields.get('ASIN') or [''])[0] if isinstance(fields.get('ASIN'), list) else (fields.get('ASIN') or '')
        tracking_url = (fields.get('Tracking URL') or [''])[0] if isinstance(fields.get('Tracking URL'), list) else (fields.get('Tracking URL') or '')

        asin = asin.strip() if asin else ''
        tracking_url = tracking_url.strip() if tracking_url else ''

        # 判断状态
        if tracking_url:
            # 已有投放链接
            to_promote.append(record_id)
        elif asin and asin in asin_map:
            # 在asin_map中但无链接
            to_apply.append(record_id)
        else:
            # 不在map中
            no_match.append(record_id)

    print(f"  可推广: {len(to_promote)}")
    print(f"  待申请: {len(to_apply)}")
    print(f"  未匹配: {len(no_match)}")

    # ============ Step 3: 批量更新状态 ============
    print("\n[3] 批量更新状态...")

    def update_status(record_ids, status):
        """批量更新，每次500条"""
        batch_size = 500
        success = 0
        fail = 0

        for i in range(0, len(record_ids), batch_size):
            batch = record_ids[i:i+batch_size]
            values = []
            for rid in batch:
                values.append({
                    "record_id": rid,
                    "fields": {
                        "推广状态": status
                    }
                })

            resp = requests.put(
                f'https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/batch_update',
                headers=headers,
                json={"records": values})

            result = resp.json()
            if result.get('code') == 0:
                success += len(batch)
            else:
                fail += len(batch)
                print(f"  更新失败: {result.get('msg', '')}")

            time.sleep(0.3)

        return success, fail

    # 更新三种状态
    s1, f1 = update_status(to_promote, "可推广")
    print(f"  可推广: {s1} 成功, {f1} 失败")

    s2, f2 = update_status(to_apply, "待申请")
    print(f"  待申请: {s2} 成功, {f2} 失败")

    s3, f3 = update_status(no_match, "未匹配")
    print(f"  未匹配: {s3} 成功, {f3} 失败")

    # ============ Step 4: 汇总待申请商户信息 ============
    print("\n[4] 汇总待申请商户信息...")

    # 找出待申请的商户列表（你去 YP 申请时需要用）
    apply_merchants = {}
    for rec in all_records:
        record_id = rec['record_id']
        if record_id in set(to_apply):
            fields = rec.get('fields', {})
            asin = (fields.get('ASIN') or [''])[0] if isinstance(fields.get('ASIN'), list) else (fields.get('ASIN') or '')
            asin = asin.strip() if asin else ''

            if asin and asin in asin_map:
                info = asin_map[asin]
                if info and isinstance(info, dict):
                    mid = info.get('merchant_id', '')
                    mname = info.get('merchant_name', '')
                    if mid:
                        if mid not in apply_merchants:
                            apply_merchants[mid] = {
                                'merchant_name': mname,
                                'asins': [],
                                'product_count': 0
                            }
                        apply_merchants[mid]['asins'].append(asin)
                        apply_merchants[mid]['product_count'] = len(apply_merchants[mid]['asins'])

    # 按商品数量排序
    sorted_merchants = sorted(apply_merchants.items(), key=lambda x: x[1]['product_count'], reverse=True)

    # 保存待申请商户列表
    apply_list = []
    for mid, info in sorted_merchants:
        apply_list.append({
            'merchant_id': mid,
            'merchant_name': info['merchant_name'],
            'apply_url': f'https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id=12002',
            'product_count': info['product_count'],
            'sample_asins': info['asins'][:5]
        })

    with open('output/pending_apply_merchants.json', 'w', encoding='utf-8') as f:
        json.dump(apply_list, f, ensure_ascii=False, indent=2)

    print(f"  共 {len(apply_list)} 个待申请商户")
    print(f"  涉及 {sum(m['product_count'] for m in apply_list)} 个商品")
    print()

    if apply_list:
        print("  【待申请商户 TOP 10】(按商品数量排序)")
        print(f"  {'商户名':<30} {'MID':>10} {'商品数':>6}  申请链接")
        print(f"  {'-'*30} {'-'*10} {'-'*6}  {'-'*50}")
        for m in apply_list[:10]:
            name = m['merchant_name'][:28]
            print(f"  {name:<30} {m['merchant_id']:>10} {m['product_count']:>6}  {m['apply_url'][:50]}")

    # 保存最终汇总
    summary = {
        'total_records': len(all_records),
        'can_promote': len(to_promote),
        'pending_apply': len(to_apply),
        'no_match': len(no_match),
        'pending_merchants_count': len(apply_list),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    with open('output/promotion_status_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print("全部完成!")
    print(f"  可推广商品: {len(to_promote)} 个 - 可直接投 Google Ads")
    print(f"  待申请商品: {len(to_apply)} 个 - {len(apply_list)} 个商户待申请")
    print(f"  未匹配商品: {len(no_match)} 个")
    print(f"  待申请商户列表: output/pending_apply_merchants.json")
    print("=" * 60)

if __name__ == '__main__':
    main()
