"""
从飞书多维表格下载商户数据（merchant_id 列表）
用于后续网页端抓取商品投放链接
"""
import requests
import json
import time
from datetime import datetime

# 飞书配置
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
MERCHANTS_TABLE_ID = "tblR2JhVsdTugueo"

OUTPUT_FILE = "output/merchants_from_feishu.json"


def get_feishu_token():
    """获取飞书访问令牌"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = {"app_id": APP_ID, "app_secret": APP_SECRET}
    resp = requests.post(url, json=data, timeout=30)
    result = resp.json()
    if result.get("code") == 0:
        return result.get("tenant_access_token")
    else:
        raise Exception(f"获取Token失败: {result}")


def fetch_feishu_merchants(token):
    """从飞书获取所有商户数据"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP_TOKEN}/tables/{MERCHANTS_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    all_records = []
    page_token = None
    page_num = 0
    
    while True:
        page_num += 1
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        result = resp.json()
        
        if result.get("code") != 0:
            print(f"  Error: {result.get('msg')}")
            break
        
        data = result.get("data", {})
        records = data.get("items", [])
        
        if not records:
            break
        
        all_records.extend(records)
        print(f"  Page {page_num}: {len(records)} records (total: {len(all_records)})")
        
        has_more = data.get("has_more", False)
        if not has_more:
            break
        
        page_token = data.get("page_token")
        time.sleep(0.3)
    
    return all_records


def main():
    print("=" * 60)
    print("从飞书下载商户数据")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    print("获取飞书Token...")
    token = get_feishu_token()
    print(f"Token 获取成功: {token[:20]}...")
    
    print(f"\n从飞书表格 {MERCHANTS_TABLE_ID} 下载商户数据...")
    records = fetch_feishu_merchants(token)
    
    print(f"\n总计获取: {len(records)} 条记录")
    
    # 解析商户数据
    merchants = []
    for rec in records:
        fields = rec.get("fields", {})
        
        # 提取所有字段
        merchant = {
            "record_id": rec.get("record_id", ""),
            "merchant_id": fields.get("merchant_id", fields.get("ID", fields.get("商户ID", ""))),
            "merchant_name": fields.get("merchant_name", fields.get("Name", fields.get("商户名称", ""))),
            "avg_payout": fields.get("avg_payout", fields.get("佣金率", 0)),
            "website": fields.get("website", fields.get("网站", "")),
            "country": fields.get("country", fields.get("国家", "")),
            "status": fields.get("status", fields.get("状态", "")),
        }
        
        # merchant_id 可能是数字
        mid = merchant.get("merchant_id")
        if isinstance(mid, list):
            mid = mid[0] if mid else None
        
        merchant["merchant_id"] = mid
        merchants.append(merchant)
    
    # 统计
    with_mid = [m for m in merchants if m.get("merchant_id")]
    print(f"有 merchant_id 的记录: {len(with_mid)}")
    
    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    
    print(f"\n已保存到: {OUTPUT_FILE}")
    
    # 打印字段示例
    if records:
        sample = records[0].get("fields", {})
        print(f"\n字段列表: {list(sample.keys())[:10]}")
        print(f"Sample: {json.dumps(sample, ensure_ascii=False)[:300]}")
    
    return merchants


if __name__ == "__main__":
    main()
