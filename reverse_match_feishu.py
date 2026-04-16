#!/usr/bin/env python3
"""
反向匹配：用 asin_merchant_map 直接查飞书 Offers 表，补全投放链接
几分钟搞定，不需要等76万条全采完。
"""
import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# 配置
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
OFFERS_TABLE_ID = "tblMCbaHhP88sgeS"
FEISHU_BASE = "https://open.feishu.cn/open-apis"
ASIN_MAP_FILE = "output/asin_merchant_map.json"


def get_feishu_token():
    resp = requests.post(f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return resp.json()["tenant_access_token"]


def get_all_feishu_asins(token):
    """获取飞书 Offers 表中所有记录的 ASIN 和 record_id"""
    headers = {"Authorization": f"Bearer {token}"}
    asin_to_record = {}  # asin -> record_id
    page_token = None
    total_pages = 0

    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(
            f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{OFFERS_TABLE_ID}/records",
            headers=headers, params=params
        )
        data = resp.json()

        if data.get("code") != 0:
            print(f"  Error: {data}")
            break

        items = data["data"]["items"]
        total_pages += 1

        for item in items:
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

        if total_pages % 3 == 0:
            print(f"  已读取 {total_pages} 页，ASIN 数: {len(asin_to_record)}")

    return asin_to_record


def ensure_fields_exist(token):
    """确保飞书表有需要的字段"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 获取现有字段
    resp = requests.get(
        f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{OFFERS_TABLE_ID}/fields",
        headers=headers
    )
    existing = set()
    for f in resp.json().get("data", {}).get("items", []):
        existing.add(f["field_name"])

    # 需要添加的字段
    needed = {
        "Merchant Name": 1,   # 文本
        "Merchant ID": 1,     # 文本
        "Tracking URL": 1,    # 文本
        "Track Token": 1,     # 文本
    }

    added = 0
    for name, ftype in needed.items():
        if name not in existing:
            resp = requests.post(
                f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{OFFERS_TABLE_ID}/fields",
                headers=headers,
                json={"field_name": name, "type": ftype}
            )
            if resp.json().get("code") == 0:
                print(f"  已添加字段: {name}")
                added += 1
            time.sleep(0.2)

    return added


def batch_update_feishu(token, updates):
    """
    批量更新飞书记录
    updates: list of {record_id, fields: {...}}
    飞书 batch_update 每次最多 500 条
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    url = f"{FEISHU_BASE}/bitable/v1/apps/{APP_TOKEN}/tables/{OFFERS_TABLE_ID}/records/batch_update"
    batch_size = 500
    updated = 0
    failed = 0

    for i in range(0, len(updates), batch_size):
        batch = updates[i:i + batch_size]
        records = []
        for u in batch:
            records.append({
                "record_id": u["record_id"],
                "fields": u["fields"]
            })

        resp = requests.put(url, headers=headers, json={"records": records})
        data = resp.json()

        if data.get("code") == 0:
            updated += len(batch)
            print(f"  更新进度: {updated}/{len(updates)}")
        else:
            failed += len(batch)
            print(f"  更新失败: {data.get('msg', '')}")

        time.sleep(0.5)

    return updated, failed


def main():
    print("=" * 70)
    print("  反向匹配：asin_map -> 飞书 Offers 表，补全投放链接")
    print("=" * 70)
    print()

    # 1. 加载 asin_map
    print("[1] 加载 ASIN 映射...")
    with open(ASIN_MAP_FILE, 'r', encoding='utf-8') as f:
        asin_map = json.load(f)
    print(f"  本地映射: {len(asin_map):,} 个 ASIN")
    print()

    # 2. 获取飞书所有 ASIN
    print("[2] 获取飞书 Offers 表所有 ASIN...")
    token = get_feishu_token()
    asin_to_record = get_all_feishu_asins(token)
    print(f"  飞书 ASIN: {len(asin_to_record):,} 个")
    print()

    # 3. 交叉匹配
    print("[3] 交叉匹配...")
    matched_asins = set(asin_to_record.keys()).intersection(set(asin_map.keys()))
    unmatched_asins = set(asin_to_record.keys()) - set(asin_map.keys())
    print(f"  匹配成功: {len(matched_asins)} 个")
    print(f"  未匹配: {len(unmatched_asins)} 个")
    print()

    if not matched_asins:
        print("  没有匹配到的 ASIN，退出")
        return

    # 4. 分类统计
    with_url = 0
    without_url = 0
    for asin in matched_asins:
        if asin_map[asin].get("tracking_url"):
            with_url += 1
        else:
            without_url += 1

    print(f"  有投放链接: {with_url} 个")
    print(f"  无投放链接: {without_url} 个")
    print()

    # 5. 确保字段存在
    print("[4] 检查飞书字段...")
    ensure_fields_exist(token)
    print()

    # 6. 构建更新请求
    print("[5] 构建更新请求...")
    updates = []
    for asin in matched_asins:
        record_id = asin_to_record[asin]
        map_data = asin_map[asin]

        fields = {}
        if map_data.get("merchant_name"):
            fields["Merchant Name"] = map_data["merchant_name"]
        if map_data.get("merchant_id"):
            fields["Merchant ID"] = str(map_data["merchant_id"])
        if map_data.get("tracking_url"):
            fields["Tracking URL"] = map_data["tracking_url"]
        if map_data.get("track"):
            fields["Track Token"] = map_data["track"]

        if fields:
            updates.append({"record_id": record_id, "fields": fields})

    print(f"  需要更新: {len(updates)} 条记录")
    print()

    # 7. 执行更新
    print("[6] 更新飞书表格...")
    updated, failed = batch_update_feishu(token, updates)
    print()

    # 8. 输出有投放链接的商品（最有价值的）
    print("=" * 70)
    print("  有投放链接的商品（可直接用于 Google Ads）")
    print("=" * 70)
    count = 0
    for asin in matched_asins:
        map_data = asin_map[asin]
        if map_data.get("tracking_url"):
            name = map_data.get("product_name", "")[:50].encode('ascii', 'ignore').decode('ascii')
            merchant = map_data.get("merchant_name", "")[:20].encode('ascii', 'ignore').decode('ascii')
            url = map_data["tracking_url"][:80]
            print(f"  {asin} | {merchant} | {name}")
            print(f"    -> {url}")
            count += 1

    print()
    print("=" * 70)
    print("  最终统计")
    print("=" * 70)
    print(f"  飞书 Offers 总数: {len(asin_to_record):,}")
    print(f"  匹配成功: {len(matched_asins)} ({len(matched_asins)/len(asin_to_record)*100:.1f}%)")
    print(f"  有投放链接: {with_url} ({with_url/len(asin_to_record)*100:.1f}%)")
    print(f"  飞书更新: {updated} 条成功, {failed} 条失败")
    print()

    # 保存结果
    result = {
        "total_feishu": len(asin_to_record),
        "matched": len(matched_asins),
        "with_url": with_url,
        "without_url": without_url,
        "updated": updated,
        "failed": failed,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("output/reverse_match_result.json", 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: output/reverse_match_result.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
