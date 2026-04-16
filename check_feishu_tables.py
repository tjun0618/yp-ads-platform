#!/usr/bin/env python3
"""检查飞书表格列表和Offers表中的ASIN数量"""
import json
import requests

APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"

def get_token():
    resp = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET}
    )
    return resp.json()["tenant_access_token"]

def main():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 获取所有表格
    resp = requests.get(
        f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables",
        headers=headers
    )
    data = resp.json()
    print("飞书表格列表:")
    tables = {}
    for t in data.get("data", {}).get("items", []):
        print(f"  {t['name']}: {t['table_id']}")
        tables[t['name']] = t['table_id']
    
    # 找Offers表
    offers_table_id = None
    for name, tid in tables.items():
        if "offer" in name.lower() or "商品" in name or "product" in name.lower():
            offers_table_id = tid
            print(f"\n找到Offers相关表: {name} -> {tid}")
            break
    
    if not offers_table_id:
        print("\n未找到Offers表，检查第一个表的字段...")
        if tables:
            first_tid = list(tables.values())[0]
            resp2 = requests.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{first_tid}/fields",
                headers=headers
            )
            fields = resp2.json()
            for f in fields.get("data", {}).get("items", []):
                print(f"  字段: {f['field_name']}")
        return
    
    # 获取Offers表中ASIN
    asins = set()
    page_token = None
    page = 0
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        resp3 = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{offers_table_id}/records",
            headers=headers,
            params=params
        )
        result = resp3.json()
        if result.get("code") != 0:
            print(f"Error: {result}")
            break
        items = result["data"]["items"]
        page += 1
        for item in items:
            fields = item.get("fields", {})
            asin = fields.get("ASIN") or fields.get("asin") or fields.get("product_asin", "")
            if isinstance(asin, list):
                asin = asin[0] if asin else ""
            if asin:
                asins.add(str(asin).strip())
        if not result["data"].get("has_more"):
            break
        page_token = result["data"].get("page_token")
        print(f"  已获取 {page} 页，当前ASIN数: {len(asins)}")
    
    print(f"\n飞书Offers表中唯一ASIN总数: {len(asins)}")
    
    # 与asin_merchant_map对比
    with open("output/asin_merchant_map.json", "r", encoding="utf-8") as f:
        asin_map = json.load(f)
    
    print(f"本地ASIN映射总数: {len(asin_map)}")
    matched = asins.intersection(set(asin_map.keys()))
    print(f"飞书ASIN在本地映射中找到的: {len(matched)}")
    print(f"未找到的: {len(asins) - len(matched)}")
    
    unmatched = asins - set(asin_map.keys())
    print(f"\n未匹配的ASIN前20个:")
    for a in list(unmatched)[:20]:
        print(f"  {a}")
    
    # 保存所有飞书ASIN到文件
    with open("output/feishu_offers_asins.json", "w", encoding="utf-8") as f:
        json.dump(list(asins), f, ensure_ascii=False, indent=2)
    print(f"\n飞书ASIN列表已保存: output/feishu_offers_asins.json")

if __name__ == "__main__":
    main()
