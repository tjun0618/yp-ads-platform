#!/usr/bin/env python3
"""
反向匹配 v2：逐条更新飞书，稳定可靠
"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_ID = "tblMCbaHhP88sgeS"
FEISHU_BASE = "https://open.feishu.cn/open-apis"
ASIN_MAP_FILE = "output/asin_merchant_map.json"


def get_token():
    resp = requests.post(f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]


def main():
    print("=" * 70)
    print("  反向匹配 v2：逐条更新飞书")
    print("=" * 70)

    # 加载 asin_map
    with open(ASIN_MAP_FILE, 'r', encoding='utf-8') as f:
        asin_map = json.load(f)
    print(f"本地映射: {len(asin_map):,} 个")

    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 获取飞书所有记录
    print("获取飞书 Offers 表...")
    asin_to_record = {}
    page_token = None
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records",
            headers=headers, params=params
        )
        data = resp.json()
        if data.get("code") != 0:
            break
        for item in data["data"]["items"]:
            fields = item.get("fields", {})
            asin = fields.get("ASIN", "")
            if isinstance(asin, list):
                asin = asin[0] if asin else ""
            asin = str(asin).strip()
            if asin and asin not in asin_to_record:
                asin_to_record[asin] = item["record_id"]
        if not data["data"].get("has_more"):
            break
        page_token = data["data"].get("page_token")

    print(f"飞书 ASIN: {len(asin_to_record):,} 个")

    # 匹配
    matched = set(asin_to_record.keys()).intersection(set(asin_map.keys()))
    print(f"匹配: {len(matched)} 个")

    # 分类
    with_url_list = []
    without_url_list = []
    for asin in matched:
        map_data = asin_map[asin]
        record_id = asin_to_record[asin]
        entry = {"asin": asin, "record_id": record_id, "data": map_data}
        if map_data.get("tracking_url"):
            with_url_list.append(entry)
        else:
            without_url_list.append(entry)

    print(f"有投放链接: {len(with_url_list)} 个")
    print(f"无投放链接: {len(without_url_list)} 个")
    print()

    # 先更新有投放链接的（高优先级）
    all_updates = with_url_list + without_url_list
    updated = 0
    failed = 0
    token_refresh_counter = 0

    print(f"开始逐条更新 {len(all_updates)} 条记录...")

    for i, entry in enumerate(all_updates):
        rid = entry["record_id"]
        d = entry["data"]

        update_fields = {}
        if d.get("merchant_name"):
            update_fields["Merchant Name"] = d["merchant_name"]
        if d.get("merchant_id"):
            update_fields["Merchant ID"] = str(d["merchant_id"])
        if d.get("tracking_url"):
            update_fields["Tracking URL"] = d["tracking_url"]
        if d.get("track"):
            update_fields["Track Token"] = d["track"]

        if not update_fields:
            continue

        try:
            resp = requests.put(
                f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records/{rid}",
                headers=headers, json={"fields": update_fields}
            )
            result = resp.json()
            if result.get("code") == 0:
                updated += 1
            else:
                failed += 1
                if failed <= 5:
                    print(f"  [WARN] {entry['asin']} 更新失败: {result.get('msg', '')}")
        except Exception as e:
            failed += 1

        # 定期刷新 token 和进度输出
        token_refresh_counter += 1
        if token_refresh_counter % 200 == 0:
            token = get_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        if (i + 1) % 50 == 0 or i == len(all_updates) - 1:
            pct = (i + 1) / len(all_updates) * 100
            print(f"  进度: {i+1}/{len(all_updates)} ({pct:.0f}%) | 成功 {updated} | 失败 {failed}")

        time.sleep(0.15)

    print()
    print("=" * 70)
    print(f"更新完成: {updated} 成功, {failed} 失败")
    print(f"有投放链接已更新: {len(with_url_list)} 条")
    print("=" * 70)

    # 保存结果
    result = {
        "total_feishu": len(asin_to_record),
        "matched": len(matched),
        "with_url": len(with_url_list),
        "without_url": len(without_url_list),
        "updated": updated,
        "failed": failed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("output/reverse_match_result.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
