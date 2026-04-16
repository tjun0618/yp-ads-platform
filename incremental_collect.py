#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP 增量采集脚本
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
功能：
- 读取 yp_auto_refresh.py 生成的新商户列表
- 只采集这些新通过商户的商品数据
- 自动上传到飞书多维表格

运行方式：
- 由 yp_auto_refresh.py 自动调用
- 或手动运行：python incremental_collect.py
"""

import json
import time
import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────────────────────────────────

SITE_ID = "12002"
OUTPUT_DIR = "output"
NEW_MERCHANTS_FILE = os.path.join(OUTPUT_DIR, "new_approved_merchants.json")
INCREMENTAL_STATE_FILE = os.path.join(OUTPUT_DIR, "incremental_state.json")
DOWNLOAD_DIR = os.path.join(OUTPUT_DIR, "downloads")

# 飞书配置
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_CONFIG_FILE = os.path.join(OUTPUT_DIR, "feishu_table_config.json")

# ─── 日志 ──────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ─── 状态 ──────────────────────────────────────────────────────────────────────

def load_incremental_state() -> Dict:
    """加载增量采集状态"""
    if Path(INCREMENTAL_STATE_FILE).exists():
        with open(INCREMENTAL_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed_mids": [], "products": [], "last_run": None}

def save_incremental_state(state: dict):
    """保存增量采集状态"""
    state["last_run"] = datetime.now().isoformat()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(INCREMENTAL_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# ─── Excel 解析 ───────────────────────────────────────────────────────────────

def read_excel(filepath: str, merchant_id, merchant_name: str) -> list:
    """读取下载的 Excel，返回商品列表"""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        ws = wb.active
        products = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            asin = str(row[0]).strip()
            if not asin or len(asin) != 10:
                continue
            products.append({
                "asin": asin,
                "product_name": str(row[1])[:200] if row[1] else "",
                "category": str(row[2]) if row[2] else "",
                "commission": str(row[3]) if row[3] else "",
                "price": str(row[4]) if row[4] else "",
                "tracking_link": str(row[5]) if row[5] else "",
                "merchant_id": merchant_id,
                "merchant_name": merchant_name,
                "scraped_at": datetime.now().isoformat(),
                "source": "incremental",
            })
        wb.close()
        return products
    except Exception as e:
        log(f"读取 Excel 失败: {e}")
        return []

# ─── 飞书上传 ─────────────────────────────────────────────────────────────────

def get_feishu_table() -> tuple:
    """获取飞书表格配置"""
    if not Path(FEISHU_CONFIG_FILE).exists():
        raise FileNotFoundError("飞书配置文件不存在，请先运行主采集脚本")
    
    with open(FEISHU_CONFIG_FILE, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg["app_token"], cfg["table_id"]

def upload_to_feishu(products: list) -> bool:
    """批量上传到飞书"""
    try:
        from lark_oapi.api.bitable import v1
        import lark_oapi as lark
        
        app_token, table_id = get_feishu_table()
        
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.ERROR) \
            .build()
        
        CHUNK = 500
        total = 0
        
        for i in range(0, len(products), CHUNK):
            chunk = products[i:i + CHUNK]
            records = []
            for item in chunk:
                fields = {
                    "ASIN": item.get("asin", ""),
                    "Product Name": item.get("product_name", ""),
                    "Category": item.get("category", ""),
                    "Commission": item.get("commission", ""),
                    "Price": item.get("price", ""),
                    "Tracking URL": item.get("tracking_link", ""),
                    "Merchant ID": str(item.get("merchant_id", "")),
                    "Merchant Name": item.get("merchant_name", ""),
                    "Collected At": item.get("scraped_at", ""),
                }
                records.append(v1.AppTableRecord.builder().fields(fields).build())
            
            req = v1.BatchCreateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    v1.BatchCreateAppTableRecordRequestBody.builder().records(records).build()
                ) \
                .build()
            
            resp = client.bitable.v1.app_table_record.batch_create(req)
            if resp.success():
                total += len(chunk)
                log(f"  ✅ 上传 +{len(chunk)} 条（累计 {total}）")
            else:
                log(f"  ❌ 上传失败: {resp.code} - {resp.msg}")
                return False
            
            time.sleep(0.5)
        
        return True
        
    except Exception as e:
        log(f"上传飞书异常: {e}")
        traceback.print_exc()
        return False

# ─── 采集单个商户 ─────────────────────────────────────────────────────────────

def collect_merchant(page, merchant: dict) -> list:
    """采集单个商户的商品"""
    mid = merchant["mid"]
    name = merchant["name"]
    products = []
    
    try:
        url = f"https://www.yeahpromos.com/index/offer/brand_detail?is_delete=0&advert_id={mid}&site_id={SITE_ID}"
        page.goto(url, timeout=30000)
        page.wait_for_load_state('networkidle')
        html = page.content()
        
        # 检查登录状态
        if 'Login name cannot be empty' in html:
            log(f"  ⚠️ {name}: 未登录，跳过")
            return []
        
        # 尝试点击 Download Products
        download_btn = page.query_selector(
            'a:has-text("Download"), button:has-text("Download"), '
            'a:has-text("Export"), button:has-text("Export"), '
            'a[href*="export"], a[href*="download"]'
        )
        
        if download_btn:
            try:
                with page.expect_download(timeout=60000) as dl_info:
                    download_btn.click()
                dl = dl_info.value
                save_path = os.path.join(DOWNLOAD_DIR, f"offer_{mid}.xlsx")
                dl.save_as(save_path)
                products = read_excel(save_path, mid, name)
                try:
                    os.remove(save_path)
                except:
                    pass
                log(f"  📊 {name}: Excel 解析 {len(products)} 条")
            except Exception as e:
                log(f"  ⚠️ {name}: 下载失败 {e}")
        
        # 如果下载失败或无按钮，解析页面
        if not products:
            asin_list = re.findall(r'<div class="asin-code">([A-Z0-9]{10})</div>', html)
            link_list = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
            link_list = [l.replace("&amp;", "&") for l in link_list]
            
            for i, asin in enumerate(asin_list):
                link = link_list[i] if i < len(link_list) else ""
                products.append({
                    "asin": asin,
                    "product_name": "",
                    "category": "",
                    "commission": "",
                    "price": "",
                    "tracking_link": link,
                    "merchant_id": mid,
                    "merchant_name": name,
                    "scraped_at": datetime.now().isoformat(),
                    "source": "incremental_page",
                })
            
            if asin_list:
                log(f"  📊 {name}: 页面解析 {len(asin_list)} 条")
        
        return products
        
    except Exception as e:
        log(f"  ❌ {name}: 采集失败 {e}")
        return []

# ─── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    log("=" * 60)
    log("YP 增量采集开始")
    log("=" * 60)
    
    # 1. 检查新商户列表
    if not Path(NEW_MERCHANTS_FILE).exists():
        log(f"新商户文件不存在: {NEW_MERCHANTS_FILE}")
        log("请先运行 yp_auto_refresh.py 发现新商户")
        return
    
    with open(NEW_MERCHANTS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    new_merchants = data.get("new_approved", [])
    if not new_merchants:
        log("没有新商户需要采集")
        return
    
    log(f"待采集新商户: {len(new_merchants)} 个")
    
    # 2. 加载状态
    state = load_incremental_state()
    completed_mids = set(state.get("completed_mids", []))
    all_products = list(state.get("products", []))
    
    # 过滤已完成的
    pending = [m for m in new_merchants if m["mid"] not in completed_mids]
    log(f"其中未采集: {len(pending)} 个")
    
    if not pending:
        log("所有新商户已采集完成")
        return
    
    # 3. 连接 Chrome
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("未安装 playwright")
        return
    
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            log("✅ 已连接到调试 Chrome")
        except Exception as e:
            log(f"❌ 连接 Chrome 失败: {e}")
            log("请先启动调试模式 Chrome")
            return
        
        contexts = browser.contexts
        context = contexts[0] if contexts else browser.new_context(accept_downloads=True)
        pages = context.pages
        page = pages[0] if pages else context.new_page()
        
        # 4. 逐个采集
        for idx, merchant in enumerate(pending):
            log(f"[{idx+1}/{len(pending)}] 采集: {merchant['name']}")
            
            products = collect_merchant(page, merchant)
            if products:
                all_products.extend(products)
                log(f"  累计商品: {len(all_products)}")
            
            completed_mids.add(merchant["mid"])
            
            # 保存状态
            save_incremental_state({
                "completed_mids": list(completed_mids),
                "products": all_products,
            })
            
            time.sleep(1)
        
        browser.close()
    
    # 5. 上传到飞书
    if all_products:
        log(f"开始上传 {len(all_products)} 条商品到飞书...")
        if upload_to_feishu(all_products):
            log("✅ 上传完成")
            # 清空已上传的商品（保留 completed_mids）
            save_incremental_state({
                "completed_mids": list(completed_mids),
                "products": [],
            })
        else:
            log("⚠️ 上传失败，商品保留在状态中下次重试")
    
    log("=" * 60)
    log(f"增量采集完成: 成功 {len(completed_mids)} 个商户")
    log("=" * 60)


if __name__ == "__main__":
    main()
