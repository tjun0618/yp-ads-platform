#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP Offers 边采边匹配脚本

工作流程：
1. 通过 API 采集商品数据（每页100条）
2. 每采一批，立即拿 ASIN 去 asin_merchant_map.json 中匹配
3. 匹配到的自动补上：商户名、MID、tracking_url、track token
4. 匹配结果实时更新到飞书 Offers 表
5. 保存状态，支持断点续传

优势：不用等76万条全采完，边采边用
"""
import requests
import json
import time
import re
import sys
import io
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

# ============================================================
# 配置
# ============================================================
SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"

# 飞书配置
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
FEISHU_OFFERS_TABLE = "tblMCbaHhP88sgeS"

# 文件路径
OUTPUT_DIR = Path(__file__).parent / "output"
ASIN_MAP_FILE = OUTPUT_DIR / "asin_merchant_map.json"
STATE_FILE = OUTPUT_DIR / "offer_match_state.json"
MATCH_LOG_FILE = OUTPUT_DIR / "offer_match_results.json"

# API
OFFER_API_URL = "https://www.yeahpromos.com/index/apioffer/getoffer"
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


# ============================================================
# 数据加载
# ============================================================

def load_asin_map():
    """加载 ASIN -> 商户映射"""
    try:
        with open(ASIN_MAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        print("  [WARN] 未找到 asin_merchant_map.json")
        return {}

def load_state():
    """加载采集状态（断点续传）"""
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"page": 1, "total_collected": 0, "total_matched": 0,
                "total_with_url": 0, "last_update": ""}

def save_state(state):
    """保存采集状态"""
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_match_results():
    """加载已匹配的结果（避免重复）"""
    try:
        with open(MATCH_LOG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return {item["asin"]: item for item in data}
            return {}
    except:
        return {}

def save_match_results(results):
    """保存匹配结果"""
    with open(MATCH_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(results.values()), f, ensure_ascii=False, indent=2)


# ============================================================
# YP Offer API
# ============================================================

def get_offers_page(page=1, limit=100):
    """获取一页商品数据"""
    headers = {"token": TOKEN}
    params = {"site_id": SITE_ID, "page": page, "limit": limit}
    
    resp = requests.get(OFFER_API_URL, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"HTTP {resp.status_code}")
    
    data = resp.json()
    if isinstance(data, dict) and data.get("status") == "SUCCESS":
        if "data" in data and isinstance(data["data"], dict):
            offers = data["data"].get("data", [])
            total = data["data"].get("total", 0)
            page_total = data["data"].get("PageTotal", 1)
            return offers, total, page_total
    elif isinstance(data, dict) and data.get("code") == 100001:
        raise Exception("API限流，稍后重试")
    
    return [], 0, 0


# ============================================================
# 匹配逻辑
# ============================================================

def match_and_enrich(offers, asin_map, existing_results):
    """
    将商品数据与 asin_map 匹配，补全商户信息和投放链接
    
    Args:
        offers: API 返回的原始商品数据列表
        asin_map: ASIN -> 商户映射字典
        existing_results: 已有的匹配结果（避免重复处理）
    
    Returns:
        tuple: (新增匹配数, 新增有链接数, 匹配详情列表)
    """
    new_matches = []
    new_matched = 0
    new_with_url = 0
    
    for offer in offers:
        asin = str(offer.get("asin", "")).strip()
        if not asin:
            continue
        
        # 跳过已匹配的
        if asin in existing_results:
            continue
        
        # 在 asin_map 中查找
        map_data = asin_map.get(asin)
        if map_data:
            result = {
                "asin": asin,
                "product_name": str(offer.get("product_name", "")),
                "price": str(offer.get("price", "")),
                "payout": str(offer.get("payout", "")),
                "product_status": str(offer.get("product_status", "")),
                "category_name": str(offer.get("category_name", "")),
                # 从 asin_map 补全
                "merchant_id": map_data.get("merchant_id", ""),
                "merchant_name": map_data.get("merchant_name", ""),
                "tracking_url": map_data.get("tracking_url", ""),
                "track": map_data.get("track", ""),
                "pid": map_data.get("pid", ""),
                "matched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            existing_results[asin] = result
            new_matches.append(result)
            new_matched += 1
            
            if result["tracking_url"]:
                new_with_url += 1
    
    return new_matched, new_with_url, new_matches


# ============================================================
# 飞书更新
# ============================================================

def get_feishu_token():
    """获取飞书 token"""
    resp = requests.post(
        f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
        json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    )
    data = resp.json()
    if str(data.get("code", -1)) == "0":
        return data["tenant_access_token"]
    raise Exception(f"飞书认证失败: {data}")


def get_feishu_records_by_asin(token, asins):
    """根据 ASIN 列表从飞书获取对应记录"""
    # 逐个 ASIN 查询（飞书不支持批量 ASIN 过滤）
    headers = {"Authorization": f"Bearer {token}"}
    asin_records = {}
    
    for asin in asins:
        filter_str = json.dumps({
            "conjunction": "and",
            "conditions": [{"field_name": "ASIN", "operator": "is", "value": [asin]}]
        })
        params = {
            "page_size": 10,
            "filter": filter_str
        }
        
        try:
            resp = requests.get(
                f"{FEISHU_BASE_URL}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_OFFERS_TABLE}/records",
                headers=headers, params=params
            )
            data = resp.json()
            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])
                for item in items:
                    fields = item.get("fields", {})
                    record_asin = fields.get("ASIN", "")
                    if isinstance(record_asin, list):
                        record_asin = record_asin[0] if record_asin else ""
                    if str(record_asin).strip() == asin:
                        asin_records[asin] = item["record_id"]
        except Exception as e:
            print(f"    [WARN] 查询飞书 ASIN={asin} 失败: {e}")
        
        time.sleep(0.1)  # 飞书 API 限流
    
    return asin_records


def batch_update_feishu(token, match_details):
    """
    批量更新飞书表格中的商户信息和投放链接
    
    Args:
        token: 飞书 access token
        match_details: 匹配详情列表（含 asin, merchant_name, tracking_url 等）
    """
    if not match_details:
        return 0
    
    # 获取需要更新的 ASIN 对应的飞书 record_id
    asins = [m["asin"] for m in match_details]
    print(f"  查询飞书记录... ({len(asins)} 个 ASIN)")
    asin_to_record = get_feishu_records_by_asin(token, asins)
    
    if not asin_to_record:
        print(f"  飞书中未找到这些 ASIN 的记录")
        return 0
    
    print(f"  找到 {len(asin_to_record)} 条飞书记录")
    
    # 构建更新请求
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 先检查飞书表是否有需要的字段，如果没有则添加
    existing_fields = set()
    try:
        resp = requests.get(
            f"{FEISHU_BASE_URL}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_OFFERS_TABLE}/fields",
            headers=headers
        )
        fields_data = resp.json()
        for f in fields_data.get("data", {}).get("items", []):
            existing_fields.add(f["field_name"])
    except:
        pass
    
    # 确保必要字段存在
    required_fields = {
        "Merchant Name": 1,  # 文本
        "Merchant ID": 1,
        "Tracking URL": 1,
        "Track Token": 1,
    }
    for field_name, field_type in required_fields.items():
        if field_name not in existing_fields:
            try:
                requests.post(
                    f"{FEISHU_BASE_URL}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_OFFERS_TABLE}/fields",
                    headers=headers,
                    json={"field_name": field_name, "type": field_type}
                )
                print(f"    已添加字段: {field_name}")
                time.sleep(0.2)
            except:
                pass
    
    # 逐条更新（飞书 batch_update 有限制）
    updated = 0
    for detail in match_details:
        asin = detail["asin"]
        record_id = asin_to_record.get(asin)
        if not record_id:
            continue
        
        fields = {}
        if detail.get("merchant_name"):
            fields["Merchant Name"] = detail["merchant_name"]
        if detail.get("merchant_id"):
            fields["Merchant ID"] = detail["merchant_id"]
        if detail.get("tracking_url"):
            fields["Tracking URL"] = detail["tracking_url"]
        if detail.get("track"):
            fields["Track Token"] = detail["track"]
        
        if not fields:
            continue
        
        try:
            resp = requests.put(
                f"{FEISHU_BASE_URL}/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{FEISHU_OFFERS_TABLE}/records/{record_id}",
                headers=headers,
                json={"fields": fields}
            )
            if resp.json().get("code") == 0:
                updated += 1
            else:
                print(f"    [WARN] 更新失败 ASIN={asin}: {resp.json().get('msg','')}")
        except Exception as e:
            print(f"    [WARN] 更新异常 ASIN={asin}: {e}")
        
        time.sleep(0.15)
    
    return updated


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 70)
    print("  YP Offers 边采边匹配（采集 + 匹配 + 更新飞书）")
    print("=" * 70)
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 加载数据
    print("[1] 加载数据...")
    asin_map = load_asin_map()
    print(f"  ASIN映射: {len(asin_map):,} 个")
    
    state = load_state()
    existing_results = load_match_results()
    print(f"  已采集页: 第 {state['page']} 页")
    print(f"  已匹配商品: {len(existing_results)} 个")
    print(f"  累计采集: {state['total_collected']:,} 条")
    print()
    
    # 确定起始页
    start_page = state["page"]
    
    # 先获取第一页确认总数
    print("[2] 确认数据规模...")
    try:
        _, total_offers, page_total = get_offers_page(page=1)
        print(f"  商品总数: {total_offers:,} 条")
        # API 返回的 page_total 不可靠（总是 1），用总数估算
        estimated_pages = (total_offers + 99) // 100
        print(f"  估算总页数: {estimated_pages:,} 页")
        print(f"  从第 {start_page} 页开始采集")
    except Exception as e:
        print(f"  [ERROR] API 调用失败: {e}")
        return
    print()
    
    # 开始边采边匹配
    print("[3] 开始采集 + 匹配...")
    print("-" * 70)
    
    page = start_page
    consecutive_errors = 0
    max_consecutive_errors = 5
    pending_updates = []  # 待更新飞书的记录
    feishu_token = None
    feishu_update_interval = 50  # 每50条匹配更新一次飞书
    consecutive_empty = 0  # 连续空页数，用于判断是否到底
    max_empty_pages = 20  # 连续20页为空则认为采集完成
    
    while page <= estimated_pages:
        print(f"\n[第 {page}/{page_total} 页] 采集中...", end=" ")
        
        try:
            offers, _, _ = get_offers_page(page=page)
        except Exception as e:
            consecutive_errors += 1
            print(f"失败: {e} (连续错误 {consecutive_errors}/{max_consecutive_errors})")
            
            if consecutive_errors >= max_consecutive_errors:
                print(f"\n  连续 {max_consecutive_errors} 次错误，暂停 60 秒后重试...")
                time.sleep(60)
                consecutive_errors = 0
            else:
                time.sleep(6)  # 普通限流，等 6 秒
            
            continue
        
        consecutive_errors = 0
        
        if not offers:
            consecutive_empty += 1
            print(f"无数据 (连续空页 {consecutive_empty}/{max_empty_pages})")
            if consecutive_empty >= max_empty_pages:
                print("连续多页无数据，判定采集完成")
                break
            page += 1
            time.sleep(6)
            continue
        else:
            consecutive_empty = 0  # 有数据则重置计数
        
        # 匹配
        new_matched, new_with_url, new_details = match_and_enrich(
            offers, asin_map, existing_results
        )
        
        state["total_collected"] += len(offers)
        state["total_matched"] = len(existing_results)
        state["total_with_url"] = sum(1 for v in existing_results.values() if v.get("tracking_url"))
        
        # 收集待更新飞书的记录
        pending_updates.extend(new_details)
        
        # 进度输出
        pct = page / estimated_pages * 100
        match_pct = state["total_matched"] / max(state["total_collected"], 1) * 100
        print(f"{len(offers)} 条 | 累计 {state['total_collected']:,} | "
              f"匹配 {state['total_matched']} ({match_pct:.1f}%) | "
              f"有链接 {state['total_with_url']}")
        
        # 显示当前页匹配的商品
        if new_details:
            for d in new_details[:3]:
                name = d['product_name'][:40].encode('ascii', 'ignore').decode('ascii')
                merchant = d['merchant_name'][:20].encode('ascii', 'ignore').decode('ascii')
                url_status = "有链接" if d['tracking_url'] else "无链接"
                print(f"    [匹配] {name}... -> {merchant} ({url_status})")
            if len(new_details) > 3:
                print(f"    ... 还有 {len(new_details) - 3} 条")
        
        # 定期更新飞书
        if len(pending_updates) >= feishu_update_interval:
            try:
                if not feishu_token:
                    feishu_token = get_feishu_token()
                    print(f"\n  [飞书] 认证成功，开始更新 {len(pending_updates)} 条记录...")
                
                updated = batch_update_feishu(feishu_token, pending_updates)
                print(f"  [飞书] 更新完成: {updated}/{len(pending_updates)} 条")
                pending_updates = []
                
                # 飞书 token 有效期 2 小时，定期刷新
                feishu_token = get_feishu_token()
            except Exception as e:
                print(f"  [飞书] 更新失败: {e}，下次重试")
                feishu_token = None  # 强制下次重新认证
        
        # 保存状态（每10页）
        if page % 10 == 0:
            state["page"] = page + 1
            save_state(state)
            save_match_results(existing_results)
        
        page += 1
        time.sleep(6)  # API 限流：每分钟约 10 次
    
    # 最终处理：更新飞书中剩余的记录
    if pending_updates:
        print(f"\n[4] 更新飞书中剩余 {len(pending_updates)} 条记录...")
        try:
            if not feishu_token:
                feishu_token = get_feishu_token()
            updated = batch_update_feishu(feishu_token, pending_updates)
            print(f"  更新完成: {updated}/{len(pending_updates)} 条")
        except Exception as e:
            print(f"  [ERROR] {e}")
    
    # 最终保存
    state["page"] = page
    state["total_matched"] = len(existing_results)
    state["total_with_url"] = sum(1 for v in existing_results.values() if v.get("tracking_url"))
    save_state(state)
    save_match_results(existing_results)
    
    # 最终统计
    print()
    print("=" * 70)
    print("  最终统计")
    print("=" * 70)
    print(f"  采集商品总数: {state['total_collected']:,} 条")
    print(f"  匹配到商户: {state['total_matched']} 条 ({state['total_matched']/max(state['total_collected'],1)*100:.1f}%)")
    print(f"  有投放链接: {state['total_with_url']} 条")
    print(f"  采集页数: {min(page, estimated_pages)}/{estimated_pages}")
    print(f"  ASIN映射库: {len(asin_map):,} 个")
    print(f"  结果文件: {MATCH_LOG_FILE}")
    print(f"  状态文件: {STATE_FILE}")
    print()
    
    # 有投放链接的商品（最有价值的）
    with_url = [v for v in existing_results.values() if v.get("tracking_url")]
    if with_url:
        print(f"  前 10 个有投放链接的商品:")
        for item in with_url[:10]:
            name = item['product_name'][:50].encode('ascii', 'ignore').decode('ascii')
            merchant = item['merchant_name'][:20].encode('ascii', 'ignore').decode('ascii')
            payout = item['payout']
            print(f"    [{payout}%] {name}... -> {merchant}")
            print(f"           {item['tracking_url'][:80]}")
    
    print()
    print("  采集完成! 如需继续，重新运行脚本即可（自动断点续传）")
    print("=" * 70)


if __name__ == "__main__":
    main()
