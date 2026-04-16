#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP 商户商品多线程流水线
━━━━━━━━━━━━━━━━━━━━━━
- 下载线程：连接调试 Chrome，逐个商户下载 Excel 并解析商品数据
- 上传线程：监控队列，每积累 UPLOAD_BATCH_SIZE 条就批量写入飞书多维表格

运行前请确保：
  Chrome 已以 --remote-debugging-port=9222 模式启动且已登录 YP
  命令：
    & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
      --remote-debugging-port=9222 --user-data-dir="C:\\Users\\wuhj\\Chrome_Debug"
"""

import json
import time
import os
import re
import sys
import threading
import queue
import traceback
from datetime import datetime
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────────────────────────────────

SITE_ID    = "12002"
OUTPUT_DIR = "output"
STATE_FILE = os.path.join(OUTPUT_DIR, "download_state.json")
DOWNLOAD_DIR = os.path.join(OUTPUT_DIR, "downloads")

# 飞书配置
FEISHU_APP_ID     = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
# 留空 → 自动创建新表格；或填入已有表格的 Token 和 Table ID
FEISHU_APP_TOKEN  = ""
FEISHU_TABLE_ID   = ""
FEISHU_TABLE_NAME = "YP商户商品(Excel下载)"
FEISHU_CONFIG_FILE = os.path.join(OUTPUT_DIR, "feishu_table_config.json")

# 积累多少条商品触发一次上传（飞书单次最大 500）
UPLOAD_BATCH_SIZE = 200
# 上传线程轮询间隔（秒）
UPLOAD_POLL_INTERVAL = 15

# ─── 日志 ──────────────────────────────────────────────────────────────────────

_log_lock = threading.Lock()

def log(tag: str, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    with _log_lock:
        print(f"[{ts}][{tag}] {msg}", flush=True)

# ─── 状态持久化 ────────────────────────────────────────────────────────────────

_state_lock = threading.Lock()

def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "completed_mids": [],
        "failed_mids": [],
        "products": [],
        "uploaded_count": 0,
    }

def save_state(state: dict):
    state["last_updated"] = datetime.now().isoformat()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tmp_file = STATE_FILE + ".tmp"
    with _state_lock:
        # 原子写入：先写临时文件，再 replace，避免并发读到半截 JSON
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, STATE_FILE)


def get_uploaded_count() -> int:
    """从独立计数文件读取已上传条数（不触碰 download_state.json）"""
    counter_file = os.path.join(OUTPUT_DIR, "upload_counter.json")
    if Path(counter_file).exists():
        try:
            return json.load(open(counter_file, encoding='utf-8')).get("uploaded_count", 0)
        except Exception:
            return 0
    return 0

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
                "asin":          asin,
                "product_name":  str(row[1])[:200] if row[1] else "",
                "category":      str(row[2]) if row[2] else "",
                "commission":    str(row[3]) if row[3] else "",
                "price":         str(row[4]) if row[4] else "",
                "tracking_link": str(row[5]) if row[5] else "",
                "merchant_id":   merchant_id,
                "merchant_name": merchant_name,
                "scraped_at":    datetime.now().isoformat(),
            })
        wb.close()
        return products
    except Exception as e:
        log("EXCEL", f"读取失败: {e}")
        return []

# ─── 飞书 ─────────────────────────────────────────────────────────────────────

def get_or_create_feishu_table() -> tuple:
    """获取或创建飞书多维表格，返回 (app_token, table_id)"""
    from lark_oapi.api.bitable import v1
    import lark_oapi as lark

    # 先看本地缓存
    if Path(FEISHU_CONFIG_FILE).exists():
        with open(FEISHU_CONFIG_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        log("UPLOAD", f"读取缓存: app_token={cfg['app_token'][:12]}…, table_id={cfg['table_id']}")
        return cfg["app_token"], cfg["table_id"]

    # 脚本里手动填了
    if FEISHU_APP_TOKEN and FEISHU_TABLE_ID:
        return FEISHU_APP_TOKEN, FEISHU_TABLE_ID

    client = lark.Client.builder() \
        .app_id(FEISHU_APP_ID) \
        .app_secret(FEISHU_APP_SECRET) \
        .log_level(lark.LogLevel.ERROR) \
        .build()

    # 创建多维表格
    log("UPLOAD", f"创建新飞书多维表格: {FEISHU_TABLE_NAME}")
    resp = client.bitable.v1.app.create(
        v1.CreateAppRequest.builder()
            .request_body(v1.App.builder().name(FEISHU_TABLE_NAME).build())
            .build()
    )
    if not resp.success():
        raise RuntimeError(f"创建飞书表格失败: {resp.code} {resp.msg}")
    app_token = resp.data.app.app_token
    log("UPLOAD", f"✅ 表格已创建: app_token={app_token}")

    # 获取默认 table_id
    list_resp = client.bitable.v1.app_table.list(
        v1.ListAppTableRequest.builder().app_token(app_token).build()
    )
    if list_resp.success() and list_resp.data.items:
        table_id = list_resp.data.items[0].table_id
    else:
        raise RuntimeError("无法获取 table_id")
    log("UPLOAD", f"✅ table_id={table_id}")

    # 创建字段（第一个字段默认已存在，其余追加）
    fields_def = [
        ("ASIN",         1),
        ("Product Name", 1),
        ("Category",     1),
        ("Commission",   1),
        ("Price",        1),
        ("Tracking URL", 1),
        ("Merchant ID",  1),
        ("Merchant Name",1),
        ("Collected At", 1),
    ]
    for fname, ftype in fields_def:
        try:
            client.bitable.v1.app_table_field.create(
                v1.CreateAppTableFieldRequest.builder()
                    .app_token(app_token)
                    .table_id(table_id)
                    .request_body(
                        v1.AppTableField.builder()
                            .field_name(fname)
                            .type(ftype)
                            .build()
                    )
                    .build()
            )
        except Exception:
            pass
    log("UPLOAD", "✅ 表格字段已就绪")

    # 保存缓存
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(FEISHU_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"app_token": app_token, "table_id": table_id}, f)

    return app_token, table_id


def feishu_upload_batch(records: list) -> bool:
    """批量写入飞书多维表格（每批 ≤ 500），返回是否全部成功"""
    try:
        from lark_oapi.api.bitable import v1
        import lark_oapi as lark

        app_token, table_id = get_or_create_feishu_table()
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .log_level(lark.LogLevel.ERROR) \
            .build()

        CHUNK = 500
        total = 0
        for i in range(0, len(records), CHUNK):
            chunk = records[i:i + CHUNK]
            feishu_records = []
            for item in chunk:
                fields = {
                    "ASIN":          item.get("asin", ""),
                    "Product Name":  item.get("product_name", ""),
                    "Category":      item.get("category", ""),
                    "Commission":    item.get("commission", ""),
                    "Price":         item.get("price", ""),
                    "Tracking URL":  item.get("tracking_link", ""),
                    "Merchant ID":   str(item.get("merchant_id", "")),
                    "Merchant Name": item.get("merchant_name", ""),
                    "Collected At":  item.get("scraped_at", ""),
                }
                feishu_records.append(
                    v1.AppTableRecord.builder().fields(fields).build()
                )
            req = v1.BatchCreateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    v1.BatchCreateAppTableRecordRequestBody.builder()
                        .records(feishu_records)
                        .build()
                ) \
                .build()
            resp = client.bitable.v1.app_table_record.batch_create(req)
            if resp.success():
                total += len(chunk)
                log("UPLOAD", f"  ✅ 批次 +{len(chunk)} 条（本次已上传 {total}）")
            else:
                log("UPLOAD", f"  ❌ 批次失败: {resp.code} - {resp.msg}")
                return False
        return True

    except Exception as e:
        log("UPLOAD", f"❌ 上传异常: {e}")
        traceback.print_exc()
        return False

# ─── 上传线程 ─────────────────────────────────────────────────────────────────

def upload_worker(upload_queue: queue.Queue, stop_event: threading.Event):
    """
    持续从 upload_queue 取商品记录，
    积累到 UPLOAD_BATCH_SIZE 就上传一次；
    stop_event 被置位后，处理完所有剩余记录再退出。
    """
    log("UPLOAD", "上传线程已启动，等待数据...")
    pending = []

    while not stop_event.is_set() or not upload_queue.empty():
        try:
            item = upload_queue.get(timeout=UPLOAD_POLL_INTERVAL)
            pending.append(item)
            upload_queue.task_done()
        except queue.Empty:
            pass

        should_upload = (
            len(pending) >= UPLOAD_BATCH_SIZE
            or (stop_event.is_set() and upload_queue.empty() and len(pending) > 0)
        )

        if should_upload and pending:
            log("UPLOAD", f"开始上传 {len(pending)} 条到飞书...")
            ok = feishu_upload_batch(pending)
            if ok:
                # 用独立的轻量计数文件，不碰 download_state.json（避免并发损坏）
                counter_file = os.path.join(OUTPUT_DIR, "upload_counter.json")
                try:
                    cnt = json.load(open(counter_file, encoding='utf-8')).get("uploaded_count", 0) if Path(counter_file).exists() else 0
                except Exception:
                    cnt = 0
                cnt += len(pending)
                with open(counter_file, 'w', encoding='utf-8') as cf:
                    json.dump({"uploaded_count": cnt, "last_updated": datetime.now().isoformat()}, cf)
                log("UPLOAD", f"✅ 飞书上传完成，累计已上传: {cnt} 条")
                pending = []
            else:
                log("UPLOAD", f"⚠️ 上传失败，{len(pending)} 条将重试")
                for item in pending:
                    upload_queue.put(item)
                pending = []
                time.sleep(30)  # 等 30 秒再重试

    # 处理线程退出时可能遗留的 pending
    if pending:
        log("UPLOAD", f"最终上传剩余 {len(pending)} 条...")
        feishu_upload_batch(pending)
        pending = []

    log("UPLOAD", "上传线程退出。")

# ─── 下载线程 ─────────────────────────────────────────────────────────────────

def download_worker(upload_queue: queue.Queue, stop_event: threading.Event):
    """
    连接调试 Chrome，逐个商户下载 Excel，解析后推入 upload_queue。
    全部完成后置 stop_event 通知上传线程收尾。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("DOWNLOAD", "❌ 未安装 playwright，请运行: pip install playwright && playwright install chromium")
        stop_event.set()
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # 加载商户列表
    merchants_file = os.path.join(OUTPUT_DIR, "us_merchants_clean.json")
    with open(merchants_file, 'r', encoding='utf-8') as f:
        us_data = json.load(f)
    all_merchants = us_data['approved_list']

    state        = load_state()
    completed_mids = set(state.get('completed_mids', []))
    failed_mids    = set(state.get('failed_mids', []))
    all_products   = list(state.get('products', []))

    pending = [m for m in all_merchants if m['mid'] not in completed_mids]
    log("DOWNLOAD", f"总商户: {len(all_merchants)} | 已完成: {len(completed_mids)} | 待处理: {len(pending)}")

    # 断点续传：把历史中未上传的推入队列（用独立计数文件，不依赖 download_state.json）
    already_uploaded = get_uploaded_count()
    unsent = all_products[already_uploaded:]
    if unsent:
        log("DOWNLOAD", f"发现 {len(unsent)} 条历史数据未上传（已上传 {already_uploaded} 条），推入队列...")
        for p in unsent:
            upload_queue.put(p)

    with sync_playwright() as p:
        # 连接已启动的调试 Chrome
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            log("DOWNLOAD", "✅ 成功连接到调试 Chrome！")
        except Exception as e:
            log("DOWNLOAD", f"❌ 连接 Chrome 失败: {e}")
            log("DOWNLOAD", "请先启动调试模式 Chrome：")
            log("DOWNLOAD", '  & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\\Users\\wuhj\\Chrome_Debug"')
            stop_event.set()
            return

        contexts = browser.contexts
        context  = contexts[0] if contexts else browser.new_context(accept_downloads=True)
        pages    = context.pages
        page     = pages[0] if pages else context.new_page()

        start_time = time.time()

        for idx, merchant in enumerate(pending):
            mid  = merchant['mid']
            name = merchant['name']

            elapsed = int(time.time() - start_time)
            log("DOWNLOAD",
                f"[{idx+1}/{len(pending)}] {name} (mid={mid}) | "
                f"{elapsed//60}m{elapsed%60}s | 队列积压: {upload_queue.qsize()}")

            products_this = []

            try:
                url = (f"https://www.yeahpromos.com/index/offer/brand_detail"
                       f"?is_delete=0&advert_id={mid}&site_id={SITE_ID}")
                page.goto(url, timeout=30000)
                page.wait_for_load_state('networkidle')
                html = page.content()

                # 登录检测
                if ('Login name cannot be empty' in html
                        or ('login' in page.url.lower() and 'yeahpromos' in page.url.lower())):
                    log("DOWNLOAD", "⚠️ 检测到未登录，等待 60 秒请在 Chrome 中重新登录...")
                    time.sleep(60)
                    page.goto(url, timeout=30000)
                    page.wait_for_load_state('networkidle')
                    html = page.content()
                    if 'Login name cannot be empty' in html:
                        log("DOWNLOAD", f"❌ 仍未登录，跳过 {name}")
                        failed_mids.add(mid)
                        save_state({
                            "completed_mids": list(completed_mids),
                            "failed_mids":    list(failed_mids),
                            "products":       all_products,
                            "uploaded_count": state.get("uploaded_count", 0),
                        })
                        continue

                # ── 尝试点击 Download Products ────────────────────────────────
                download_btn = page.query_selector(
                    'a:has-text("Download"), button:has-text("Download"), '
                    'a:has-text("Export"), button:has-text("Export"), '
                    'a[href*="export"], a[href*="download"]'
                )

                if download_btn:
                    log("DOWNLOAD", "  📥 找到下载按钮，点击...")
                    try:
                        with page.expect_download(timeout=60000) as dl_info:
                            download_btn.click()
                        dl = dl_info.value
                        save_path = os.path.join(DOWNLOAD_DIR, f"offer_{mid}.xlsx")
                        dl.save_as(save_path)
                        products_this = read_excel(save_path, mid, name)
                        try:
                            os.remove(save_path)
                        except Exception:
                            pass
                        log("DOWNLOAD", f"  📊 Excel 解析: {len(products_this)} 条")
                    except Exception as e_dl:
                        log("DOWNLOAD", f"  ⚠️ 下载失败，切页面解析: {e_dl}")

                # ── 无下载按钮 / 下载失败 → 解析页面 ──────────────────────────
                if not products_this:
                    asin_list = re.findall(
                        r'<div class="asin-code">([A-Z0-9]{10})</div>', html
                    )
                    link_list = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
                    link_list = [l.replace("&amp;", "&") for l in link_list]
                    for i, asin in enumerate(asin_list):
                        link = link_list[i] if i < len(link_list) else ""
                        products_this.append({
                            "asin":          asin,
                            "product_name":  "",
                            "category":      "",
                            "commission":    "",
                            "price":         "",
                            "tracking_link": link,
                            "merchant_id":   mid,
                            "merchant_name": name,
                            "scraped_at":    datetime.now().isoformat(),
                        })
                    if asin_list:
                        log("DOWNLOAD", f"  📊 页面解析: {len(asin_list)} 条")
                    else:
                        log("DOWNLOAD", f"  ⚠️ 无商品（商户可能为空）")

                # ── 推入队列 & 更新本地 state ──────────────────────────────────
                for prod in products_this:
                    upload_queue.put(prod)
                all_products.extend(products_this)
                completed_mids.add(mid)

                save_state({
                    "completed_mids": list(completed_mids),
                    "failed_mids":    list(failed_mids),
                    "products":       all_products,
                    "uploaded_count": state.get("uploaded_count", 0),
                })

                time.sleep(1)  # 礼貌延迟

            except Exception as e:
                log("DOWNLOAD", f"❌ 处理 {name}(mid={mid}) 出错: {e}")
                failed_mids.add(mid)
                save_state({
                    "completed_mids": list(completed_mids),
                    "failed_mids":    list(failed_mids),
                    "products":       all_products,
                    "uploaded_count": state.get("uploaded_count", 0),
                })

        log("DOWNLOAD", "=" * 50)
        log("DOWNLOAD", "🎉 下载线程全部完成！")
        log("DOWNLOAD", f"成功: {len(completed_mids)} | 失败: {len(failed_mids)} | 商品: {len(all_products)}")
        log("DOWNLOAD", "=" * 50)

    # 通知上传线程可以收尾
    stop_event.set()

# ─── 主程序 ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  YP 商户商品  多线程流水线")
    print("  下载线程 ──→ Queue ──→ 飞书上传线程")
    print("=" * 70)

    # 检查依赖
    try:
        import lark_oapi
    except ImportError:
        print("❌ 未安装飞书 SDK，请运行: pip install lark-oapi")
        sys.exit(1)

    upload_q   = queue.Queue()
    stop_event = threading.Event()

    t_upload   = threading.Thread(
        target=upload_worker,   args=(upload_q, stop_event),
        daemon=False, name="UploadThread"
    )
    t_download = threading.Thread(
        target=download_worker, args=(upload_q, stop_event),
        daemon=False, name="DownloadThread"
    )

    t_upload.start()
    t_download.start()

    try:
        t_download.join()
        log("MAIN", "下载线程结束，等待上传线程消化剩余数据...")
        upload_q.join()
        t_upload.join()
    except KeyboardInterrupt:
        log("MAIN", "⚠️ 用户中断，等待当前上传批次完成后退出...")
        stop_event.set()
        upload_q.join()
        t_upload.join()

    st = load_state()
    log("MAIN", "=" * 50)
    log("MAIN", "✅ 全部完成！")
    log("MAIN", f"已下载商户: {len(st.get('completed_mids', []))}")
    log("MAIN", f"总商品数:   {len(st.get('products', []))}")
    log("MAIN", f"已上传飞书: {get_uploaded_count()}")
    if Path(FEISHU_CONFIG_FILE).exists():
        cfg = json.load(open(FEISHU_CONFIG_FILE, encoding='utf-8'))
        log("MAIN", f"飞书表格链接: https://feishu.cn/base/{cfg['app_token']}")
    log("MAIN", "=" * 50)


if __name__ == "__main__":
    main()
