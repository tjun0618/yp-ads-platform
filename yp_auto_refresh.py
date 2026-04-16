#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP 商户状态定时刷新 + 增量采集系统
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
功能：
1. 定期调用 YP API 刷新商户状态（APPROVED / PENDING / UNAPPLIED）
2. 发现新通过的商户（PENDING → APPROVED）
3. 自动触发增量采集，获取新商户的商品和投放链接
4. 更新飞书多维表格

运行方式：
- 手动运行：python yp_auto_refresh.py
- 定时任务：Windows 计划任务 / Linux cron 每 X 小时运行一次
"""

import json
import time
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Tuple

# ─── 配置 ──────────────────────────────────────────────────────────────────────

OUTPUT_DIR = "output"
MERCHANTS_FILE = os.path.join(OUTPUT_DIR, "us_merchants_clean.json")
REFRESH_LOG_FILE = os.path.join(OUTPUT_DIR, "refresh_log.json")
NEW_MERCHANTS_FILE = os.path.join(OUTPUT_DIR, "new_approved_merchants.json")

YP_API_TOKEN = "7951dc7484fa9f9d"
YP_SITE_ID = "12002"
YP_API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"

# 飞书配置
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_CONFIG_FILE = os.path.join(OUTPUT_DIR, "feishu_table_config.json")

# ─── 日志 ──────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ─── 加载/保存 ─────────────────────────────────────────────────────────────────

def load_merchants() -> Dict:
    """加载当前商户数据"""
    if Path(MERCHANTS_FILE).exists():
        with open(MERCHANTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"approved_list": [], "unapplied_list": [], "approved": 0, "unapplied": 0, "total": 0}

def save_merchants(data: Dict):
    """保存商户数据"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(MERCHANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_refresh_log() -> List[Dict]:
    """加载刷新历史记录"""
    if Path(REFRESH_LOG_FILE).exists():
        with open(REFRESH_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_refresh_log(logs: List[Dict]):
    """保存刷新历史"""
    with open(REFRESH_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

# ─── API 调用 ─────────────────────────────────────────────────────────────────

def fetch_merchants_from_api() -> Tuple[List[Dict], List[Dict]]:
    """
    从 YP API 获取最新商户列表
    返回: (approved_list, unapplied_list)
    """
    import requests
    
    headers = {
        "token": YP_API_TOKEN,
        "siteid": YP_SITE_ID,
        "Content-Type": "application/json"
    }
    
    all_approved = []
    all_unapplied = []
    
    # 分页获取所有商户
    page = 1
    per_page = 100
    max_pages = 200  # 安全上限
    
    log("开始从 YP API 获取商户列表...")
    
    while page <= max_pages:
        try:
            resp = requests.get(
                YP_API_URL,
                headers=headers,
                params={"page": page, "limit": per_page},
                timeout=30
            )
            data = resp.json()
            
            if data.get("code") != 1:
                log(f"API 返回错误: {data.get('msg')}")
                break
            
            items = data.get("data", {}).get("Data", [])
            if not items:
                break
            
            for item in items:
                merchant = {
                    "mid": str(item.get("advert_id", "")),
                    "name": item.get("company_name", ""),
                    "status": item.get("status", ""),
                    "country": item.get("country", ""),
                    "commission": item.get("commission", ""),
                    "cookie_day": item.get("cookie_day", ""),
                }
                
                # 只保留 US 商户
                if "US" in merchant["country"] or "United States" in merchant["country"]:
                    if merchant["status"] == "APPROVED":
                        all_approved.append(merchant)
                    else:
                        all_unapplied.append(merchant)
            
            log(f"  第 {page} 页: {len(items)} 个商户")
            
            if len(items) < per_page:
                break
            
            page += 1
            time.sleep(0.5)  # 礼貌延迟
            
        except Exception as e:
            log(f"获取第 {page} 页出错: {e}")
            break
    
    log(f"API 获取完成: APPROVED={len(all_approved)}, UNAPPLIED={len(all_unapplied)}")
    return all_approved, all_unapplied

# ─── 状态对比 ─────────────────────────────────────────────────────────────────

def compare_merchants(old_approved: List[Dict], new_approved: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    对比新旧商户列表
    返回: (newly_approved, removed_approved)
    """
    old_mids = {m["mid"] for m in old_approved}
    new_mids = {m["mid"] for m in new_approved}
    
    # 新通过的商户（在 new 中但不在 old 中）
    newly_approved = [m for m in new_approved if m["mid"] not in old_mids]
    
    # 被取消的商户（在 old 中但不在 new 中）
    removed_approved = [m for m in old_approved if m["mid"] not in new_mids]
    
    return newly_approved, removed_approved

# ─── 增量采集 ─────────────────────────────────────────────────────────────────

def trigger_incremental_collection(new_merchants: List[Dict]):
    """
    触发增量采集脚本，只处理新通过的商户
    """
    if not new_merchants:
        return
    
    log(f"触发增量采集: {len(new_merchants)} 个新商户")
    
    # 保存新商户列表供采集脚本使用
    with open(NEW_MERCHANTS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"new_approved": new_merchants}, f, ensure_ascii=False, indent=2)
    
    # 启动增量采集脚本（后台运行）
    script_path = os.path.join(os.path.dirname(__file__), "incremental_collect.py")
    if Path(script_path).exists():
        log(f"启动增量采集脚本: {script_path}")
        try:
            # Windows 下使用 start 命令后台运行
            if sys.platform == "win32":
                subprocess.Popen(
                    ["python", "-X", "utf8", "incremental_collect.py"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                subprocess.Popen(
                    ["python3", "incremental_collect.py"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            log("增量采集脚本已启动（后台运行）")
        except Exception as e:
            log(f"启动增量采集脚本失败: {e}")
    else:
        log(f"警告: 增量采集脚本不存在: {script_path}")

# ─── 飞书更新 ─────────────────────────────────────────────────────────────────

def update_feishu_merchant_status(merchant_updates: List[Dict]):
    """
    更新飞书表格中的商户状态
    （可选：标记已取消的商户）
    """
    if not merchant_updates:
        return
    
    log(f"更新飞书表格: {len(merchant_updates)} 个商户状态变更")
    
    try:
        from lark_oapi.api.bitable import v1
        import lark_oapi as lark
        
        if not Path(FEISHU_CONFIG_FILE).exists():
            log("飞书配置文件不存在，跳过更新")
            return
        
        with open(FEISHU_CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        
        app_token = cfg.get("app_token")
        table_id = cfg.get("table_id")
        
        if not app_token or not table_id:
            log("飞书配置不完整，跳过更新")
            return
        
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.ERROR) \
            .build()
        
        # TODO: 根据 Merchant ID 更新飞书记录的状态字段
        # 需要实现查询现有记录 → 更新状态 的逻辑
        log("飞书表格更新功能待实现（需要添加状态字段）")
        
    except Exception as e:
        log(f"更新飞书表格失败: {e}")

# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("YP 商户状态定时刷新开始")
    log("=" * 60)
    
    # 1. 加载当前数据
    current_data = load_merchants()
    old_approved = current_data.get("approved_list", [])
    old_unapplied = current_data.get("unapplied_list", [])
    
    log(f"当前数据: APPROVED={len(old_approved)}, UNAPPLIED={len(old_unapplied)}")
    
    # 2. 从 API 获取最新数据
    new_approved, new_unapplied = fetch_merchants_from_api()
    
    # 3. 对比差异
    newly_approved, removed_approved = compare_merchants(old_approved, new_approved)
    
    log(f"状态对比:")
    log(f"  - 新通过商户: {len(newly_approved)} 个")
    log(f"  - 被取消商户: {len(removed_approved)} 个")
    
    if newly_approved:
        for m in newly_approved[:5]:  # 只显示前5个
            log(f"    + {m['name']} (mid={m['mid']})")
        if len(newly_approved) > 5:
            log(f"    ... 还有 {len(newly_approved) - 5} 个")
    
    # 4. 保存更新后的数据
    updated_data = {
        "total": len(new_approved) + len(new_unapplied),
        "approved": len(new_approved),
        "unapplied": len(new_unapplied),
        "approved_list": new_approved,
        "unapplied_list": new_unapplied,
        "last_updated": datetime.now().isoformat(),
    }
    save_merchants(updated_data)
    log("商户数据已更新保存")
    
    # 5. 记录刷新日志
    refresh_log = load_refresh_log()
    refresh_log.append({
        "timestamp": datetime.now().isoformat(),
        "approved_count": len(new_approved),
        "unapplied_count": len(new_unapplied),
        "newly_approved": len(newly_approved),
        "removed_approved": len(removed_approved),
        "new_merchants": [{"mid": m["mid"], "name": m["name"]} for m in newly_approved],
    })
    # 只保留最近 100 条日志
    refresh_log = refresh_log[-100:]
    save_refresh_log(refresh_log)
    
    # 6. 触发增量采集（如果有新商户）
    if newly_approved:
        log(f"发现 {len(newly_approved)} 个新通过商户，触发增量采集...")
        trigger_incremental_collection(newly_approved)
    else:
        log("没有新通过的商户，无需增量采集")
    
    # 7. 更新飞书状态（可选）
    if removed_approved:
        update_feishu_merchant_status(removed_approved)
    
    log("=" * 60)
    log("定时刷新完成")
    log("=" * 60)


if __name__ == "__main__":
    main()
