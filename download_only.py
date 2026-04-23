#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP 纯下载脚本 v5 — 直接写 MySQL（去掉 Excel 中转层）
改动说明（对比 v4）：
  - 去掉 append_to_excel()，改为 bulk_upsert_mysql()
  - 断点续传仍由 state.json 维护（只存 completed_mids / failed_mids）
  - 日志中"Excel 现有商品"改为查 MySQL COUNT 行数显示
  - ON DUPLICATE KEY UPDATE 天然防重复，幂等安全
  - v5.1: 支持 --single <mid> 参数，只采集指定商户（不修改 state.json）
"""

import sys
import json
import time
import os
import re
import traceback
from datetime import datetime
from pathlib import Path

import mysql.connector

# ─── 配置 ──────────────────────────────────────────────────────────────────
SITE_ID = "12002"
SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = str(SCRIPT_DIR / "output")
STATE_FILE = os.path.join(OUTPUT_DIR, "download_state.json")
DOWNLOAD_DIR = os.path.join(OUTPUT_DIR, "downloads")
LOG_FILE = os.path.join(OUTPUT_DIR, "download_log.txt")

BASE_URL = "https://www.yeahpromos.com"

# MySQL 连接配置
DB_CONFIG = dict(
    host="localhost",
    port=3306,
    user="root",
    password="admin",
    database="affiliate_marketing",
    charset="utf8mb4",
    autocommit=False,
)

COL_KEYS = [
    "merchant_name",
    "merchant_id",
    "asin",
    "product_name",
    "category",
    "price",
    "commission",
    "tracking_link",
    "scraped_at",
]

# ─── 日志 ──────────────────────────────────────────────────────────────────
_log_fh = None


def _get_log_fh():
    global _log_fh
    if _log_fh is None:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        _log_fh = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    return _log_fh


def log(tag, msg):
    ts = datetime.now().strftime("%H:%M:%S")
    # 过滤掉 emoji/特殊 Unicode，避免 Windows 控制台编码问题
    safe_msg = (
        msg.encode("ascii", "ignore").decode("ascii")
        if isinstance(msg, str)
        else str(msg)
    )
    line = f"[{ts}][{tag}] {safe_msg}"
    print(line, flush=True)
    try:
        _get_log_fh().write(line + "\n")
    except Exception:
        pass


# ─── MySQL 工具 ────────────────────────────────────────────────────────────
def _clean_price(raw) -> str | None:
    """把 '$12.99' / 'USD 155' / '12.99' / '' 等清洗为纯数字字符串，或 None（decimal 列友好）"""
    if raw is None:
        return None
    s = str(raw).strip()
    # 处理 "USD 155" 格式
    if s.upper().startswith("USD "):
        s = s[4:].strip()
    # 处理 "$155" 格式
    s = s.lstrip("$").strip()
    # 去掉千分位逗号
    s = s.replace(",", "")
    # 只保留数字和小数点
    m = re.match(r"[\d]+(?:\.\d+)?", s)
    return m.group(0) if m else None


UPSERT_SQL = """
INSERT INTO yp_products
    (merchant_name, merchant_id, asin, product_name, category,
     price, commission, tracking_url, scraped_at)
VALUES
    (%(merchant_name)s, %(merchant_id)s, %(asin)s, %(product_name)s, %(category)s,
     %(price)s, %(commission)s, %(tracking_link)s, %(scraped_at)s)
ON DUPLICATE KEY UPDATE
    merchant_name  = VALUES(merchant_name),
    product_name   = VALUES(product_name),
    category       = VALUES(category),
    price          = VALUES(price),
    commission     = VALUES(commission),
    tracking_url   = VALUES(tracking_url),
    scraped_at     = VALUES(scraped_at)
"""

UPSERT_MERCHANT_SQL = """
INSERT INTO yp_merchants (merchant_id, merchant_name, country, status)
VALUES (%s, %s, 'US - United States(US)', 'APPROVED')
ON DUPLICATE KEY UPDATE merchant_name = VALUES(merchant_name), status = VALUES(status)
"""


def ensure_merchant(conn, merchant_id: str, merchant_name: str):
    """确保商户记录存在"""
    try:
        cur = conn.cursor()
        cur.execute(UPSERT_MERCHANT_SQL, (merchant_id, merchant_name))
        conn.commit()
        cur.close()
    except Exception as e:
        log("MAIN", f"创建商户记录失败: {e}")


def bulk_upsert_mysql(conn, products: list, batch_size: int = 500):
    """批量 UPSERT 到 yp_products，每 batch_size 条提交一次"""
    if not products:
        return 0
    cur = conn.cursor()
    inserted = 0
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        cur.executemany(UPSERT_SQL, batch)
        conn.commit()
        inserted += len(batch)
    cur.close()
    return inserted


def get_db_product_count(conn):
    """查询 yp_products 当前总行数，供日志显示"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM yp_products")
        row = cur.fetchone()
        cur.close()
        return row[0] if row else 0
    except Exception:
        return -1


# ─── 状态（只存 mid 列表，轻量，永不膨胀）──────────────────────────────────
def load_state():
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return {
            "completed_mids": d.get("completed_mids", []),
            "failed_mids": d.get("failed_mids", []),
        }
    return {"completed_mids": [], "failed_mids": []}


def save_state(completed_mids: set, failed_mids: set):
    """只保存商户 ID 集合，state 文件永远只有几 KB（原子写）"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    data = {
        "completed_mids": sorted(completed_mids),
        "failed_mids": sorted(failed_mids),
        "last_updated": datetime.now().isoformat(),
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, STATE_FILE)


# ─── Excel 解析（保留：仍用于解析 YP 下载的 xlsx，只是不再写 Excel 了）──────
def parse_excel_file(filepath, merchant_id, merchant_name):
    try:
        fsize = os.path.getsize(filepath)
        if fsize < 100:
            log("EXCEL", f"文件过小({fsize}B)，跳过")
            return None
        with open(filepath, "rb") as fh:
            magic = fh.read(2)
        if magic != b"PK":
            log("EXCEL", f"非 xlsx 格式(头={magic.hex()})，跳过")
            return None

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
            products.append(
                {
                    "asin": asin,
                    "product_name": str(row[1])[:200] if row[1] else "",
                    "category": str(row[2]) if row[2] else "",
                    "commission": str(row[3]) if row[3] else "",
                    "price": str(row[4]) if row[4] else "",
                    "tracking_link": str(row[5]) if row[5] else "",
                    "merchant_id": merchant_id,
                    "merchant_name": merchant_name,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        wb.close()
        return products
    except Exception as e:
        log("EXCEL", f"解析失败: {e}")
        return None


def parse_html_fallback(page, mid, merchant_name):
    """HTML 解析兜底：遍历所有分页，提取 ASIN、产品名、价格、佣金、链接"""
    import requests as req_lib

    products = []
    cookies = page.context.cookies()
    sess_cookie = next((c for c in cookies if c["name"] == "PHPSESSID"), None)

    def _extract_product_info(html):
        """从 HTML 中提取商品信息"""
        # 提取 ASIN
        asin_list = re.findall(r'<div class="asin-code">([A-Z0-9]{10})</div>', html)
        # 提取链接
        link_list = [
            l.replace("&amp;", "&")
            for l in re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
        ]
        # 提取产品名称（尝试多种模式）
        name_list = re.findall(
            r'<div class="product-name[^"]*"[^>]*>([^<]+)</div>', html
        )
        if not name_list:
            name_list = re.findall(
                r'<td[^>]*class="[^"]*name[^"]*"[^>]*>([^<]+)</td>', html
            )
        # 提取价格（尝试多种模式）
        price_list = re.findall(
            r'<div class="price[^"]*"[^>]*>\$?([0-9,.]+)</div>', html
        )
        if not price_list:
            price_list = re.findall(r"\$([0-9,.]+)", html)
        # 提取佣金
        comm_list = re.findall(r"(\d+%)", html)

        return asin_list, link_list, name_list, price_list, comm_list

    if not sess_cookie:
        html = page.content()
        asin_list, link_list, name_list, price_list, comm_list = _extract_product_info(
            html
        )
        for i, asin in enumerate(asin_list):
            products.append(
                {
                    "asin": asin,
                    "product_name": name_list[i] if i < len(name_list) else "",
                    "category": "",
                    "commission": comm_list[i] if i < len(comm_list) else "",
                    "price": price_list[i] if i < len(price_list) else "",
                    "tracking_link": link_list[i] if i < len(link_list) else "",
                    "merchant_id": mid,
                    "merchant_name": merchant_name,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        return products

    session = req_lib.Session()
    session.cookies.set("PHPSESSID", sess_cookie["value"])
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
    page_num = 1
    while True:
        try:
            url = (
                f"{BASE_URL}/index/offer/brand_detail"
                f"?is_delete=0&advert_id={mid}&site_id={SITE_ID}&page={page_num}"
            )
            r = session.get(url, timeout=20)
            html = r.text
            asin_list, link_list, name_list, price_list, comm_list = (
                _extract_product_info(html)
            )
            if not asin_list:
                break
            for i, asin in enumerate(asin_list):
                products.append(
                    {
                        "asin": asin,
                        "product_name": name_list[i] if i < len(name_list) else "",
                        "category": "",
                        "commission": comm_list[i] if i < len(comm_list) else "",
                        "price": price_list[i] if i < len(price_list) else "",
                        "tracking_link": link_list[i] if i < len(link_list) else "",
                        "merchant_id": mid,
                        "merchant_name": merchant_name,
                        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            if len(asin_list) < 30:
                break
            page_num += 1
            time.sleep(0.3)
        except Exception as e:
            log("HTML", f"页面{page_num}解析失败: {e}")
            break
    return products


# ─── 主下载逻辑 ────────────────────────────────────────────────────────────
def main():
    log("MAIN", "=" * 60)
    log("MAIN", "YP 下载脚本 v5.1 — 直接写 MySQL（无 Excel 中转）")
    log("MAIN", "=" * 60)

    # ── --single <mid> 参数：单商户手动采集模式 ──────────────────────────────
    single_mid = None
    if "--single" in sys.argv:
        idx = sys.argv.index("--single")
        if idx + 1 < len(sys.argv):
            single_mid = str(sys.argv[idx + 1]).strip()
            log("MAIN", f"单商户模式：merchant_id = {single_mid}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("MAIN", "未安装 playwright")
        return

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # 连接 MySQL
    try:
        db_conn = mysql.connector.connect(**DB_CONFIG)
        log("MAIN", "MySQL 连接成功")
    except Exception as e:
        log("MAIN", f"MySQL 连接失败: {e}，请确认数据库已启动")
        return

    # ── 构建待处理商户列表 ────────────────────────────────────────────────
    if single_mid:
        # 单商户模式：从 yp_merchants 查名称，构造最小列表
        try:
            cur = db_conn.cursor(dictionary=True)
            cur.execute(
                "SELECT merchant_name FROM yp_merchants WHERE merchant_id=%s LIMIT 1",
                (single_mid,),
            )
            row = cur.fetchone()
            cur.close()
            single_name = (row or {}).get("merchant_name") or single_mid
        except Exception:
            single_name = single_mid
        pending = [{"mid": single_mid, "name": single_name}]
        completed_mids = set()
        failed_mids = set()
        log("MAIN", f"单商户: {single_name} (mid={single_mid})")
    else:
        # 正常全量模式：从 us_merchants_clean.json 加载
        merchants_file = str(SCRIPT_DIR / "output" / "us_merchants_clean.json")
        with open(merchants_file, "r", encoding="utf-8") as f:
            us_data = json.load(f)
        all_merchants = us_data["approved_list"]

        state = load_state()
        completed_mids = set(state.get("completed_mids", []))
        failed_mids = set(state.get("failed_mids", []))

        # 查当前 MySQL 中的商品数（仅用于日志显示）
        db_count = get_db_product_count(db_conn)

        pending = [
            m
            for m in all_merchants
            if m["mid"] not in completed_mids and m["mid"] not in failed_mids
        ]
        log(
            "MAIN",
            f"总商户: {len(all_merchants)} | 已完成: {len(completed_mids)} | 失败: {len(failed_mids)} | 待处理: {len(pending)}",
        )
        log("MAIN", f"MySQL yp_products 现有商品: {db_count:,} 条")

    if not pending:
        log("MAIN", "✅ 所有商户已处理完毕！")
        db_conn.close()
        return

    with sync_playwright() as p:
        # 尝试连接调试 Chrome，失败则自动拉起
        def _try_connect_chrome(pw):
            try:
                return pw.chromium.connect_over_cdp("http://localhost:9222")
            except Exception:
                return None

        browser = _try_connect_chrome(p)
        if browser is None:
            log("MAIN", "Chrome 调试模式未启动，尝试自动启动...")
            # 找 Chrome 可执行文件
            import glob as _glob, socket as _socket

            candidates = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Users\wuhj\AppData\Local\Google\Chrome\Application\chrome.exe",
            ]
            candidates += _glob.glob(
                r"C:\Users\wuhj\AppData\Local\**\chrome.exe", recursive=True
            )[:3]
            chrome_exe = next((c for c in candidates if os.path.isfile(c)), None)
            if not chrome_exe:
                log(
                    "MAIN",
                    '❌ 未找到 Chrome，请手动运行: chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\\Users\\wuhj\\Chrome_Debug"',
                )
                db_conn.close()
                return
            import subprocess as _sp

            _sp.Popen(
                [
                    chrome_exe,
                    "--remote-debugging-port=9222",
                    "--user-data-dir=C:\\Users\\wuhj\\Chrome_Debug",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
                creationflags=_sp.CREATE_NEW_CONSOLE,
            )
            log("MAIN", "Chrome 已拉起，等待 CDP 就绪（最多10秒）...")
            for _ in range(20):
                time.sleep(0.5)
                try:
                    s = _socket.create_connection(("127.0.0.1", 9222), timeout=1)
                    s.close()
                    break
                except Exception:
                    pass
            browser = _try_connect_chrome(p)
            if browser is None:
                log(
                    "MAIN",
                    "❌ Chrome 调试模式启动后仍无法连接，请确认已登录 YP 平台后重试",
                )
                db_conn.close()
                return
        log("MAIN", "成功连接到调试 Chrome！")

        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        start_time = time.time()
        total_added = 0  # 本次运行新增商品数

        for idx, merchant in enumerate(pending):
            mid = merchant["mid"]
            name = merchant["name"]

            elapsed = int(time.time() - start_time)
            log(
                "MAIN",
                f"[{idx + 1}/{len(pending)}] {name} (mid={mid}) | "
                f"{elapsed // 60}m{elapsed % 60}s | 本次新增: {total_added:,}",
            )

            products_this = []

            try:
                # 打开商户页面
                url = (
                    f"{BASE_URL}/index/offer/brand_detail"
                    f"?is_delete=0&advert_id={mid}&site_id={SITE_ID}"
                )
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(1.5)

                # 检查登录状态
                html = page.content()
                if "Login name cannot be empty" in html or (
                    "login" in page.url.lower() and "yeahpromos" in page.url.lower()
                ):
                    log("MAIN", "检测到未登录，等待 60 秒请在 Chrome 中重新登录...")
                    time.sleep(60)
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    html = page.content()
                    if "Login name cannot be empty" in html:
                        log("MAIN", f"仍未登录，跳过 {name}")
                        failed_mids.add(mid)
                        save_state(completed_mids, failed_mids)
                        continue

                # ── 检查下载按钮并触发 ───────────────────────────────────
                try:
                    has_btn = page.evaluate("""
                        () => {
                            const links = Array.from(document.querySelectorAll('a'));
                            return links.some(a => a.href && a.href.includes('export_advert_products'));
                        }
                    """)

                    if not has_btn:
                        log("MAIN", "  无下载按钮，跳过")
                        completed_mids.add(mid)
                        save_state(completed_mids, failed_mids)
                        time.sleep(0.3)
                        continue

                    with page.expect_download(timeout=20000) as dl_info:
                        page.evaluate("""
                            () => {
                                const links = Array.from(document.querySelectorAll('a'));
                                const dl = links.find(a => a.href && a.href.includes('export_advert_products'));
                                if (dl) dl.click();
                            }
                        """)
                    dl = dl_info.value
                    save_path = os.path.join(DOWNLOAD_DIR, f"offer_{mid}.xlsx")
                    dl.save_as(save_path)
                    products_this = parse_excel_file(save_path, mid, name)
                    try:
                        os.remove(save_path)  # 解析完立即删除临时文件
                    except Exception:
                        pass

                    if products_this is None:
                        log("MAIN", "  Excel 无效，HTML 兜底...")
                        products_this = parse_html_fallback(page, mid, name) or []
                        if products_this:
                            log("MAIN", f"  HTML兜底: {len(products_this)} 条")
                        else:
                            log("MAIN", "  兜底也无商品")
                    elif products_this:
                        log("MAIN", f"  ✅ Excel 解析: {len(products_this)} 条")
                    else:
                        log("MAIN", "  Excel 为空（商户确实无商品）")

                except Exception as e_dl:
                    log("MAIN", f"  下载异常: {type(e_dl).__name__}: {str(e_dl)[:100]}")
                    products_this = parse_html_fallback(page, mid, name) or []
                    if products_this:
                        log("MAIN", f"  HTML兜底: {len(products_this)} 条")

                # ── 立即写 MySQL，不在内存中累积 ─────────────────────────
                if products_this:
                    # 清洗 price 字段（decimal 列不接受 $ 前缀）
                    for p in products_this:
                        p["price"] = _clean_price(p.get("price"))

                    # 检查是否有重复 ASIN
                    all_asins = [p["asin"] for p in products_this]
                    unique_asins = set(all_asins)
                    if len(all_asins) != len(unique_asins):
                        log(
                            "MAIN",
                            f"  注意: Excel 有 {len(all_asins)} 行，但只有 {len(unique_asins)} 个唯一 ASIN",
                        )
                        # 去重：只保留每个 ASIN 的第一条记录
                        seen = set()
                        products_dedup = []
                        for p in products_this:
                            if p["asin"] not in seen:
                                seen.add(p["asin"])
                                products_dedup.append(p)
                        products_this = products_dedup
                        log("MAIN", f"  去重后: {len(products_this)} 条")

                    # MySQL 连接断线自动重连
                    try:
                        db_conn.ping(reconnect=True, attempts=3, delay=2)
                    except Exception:
                        db_conn = mysql.connector.connect(**DB_CONFIG)

                    # 确保商户记录存在
                    ensure_merchant(db_conn, mid, name)

                    # 增量同步：先删除不在新列表中的商品
                    new_asins = set(p["asin"] for p in products_this)
                    cur = db_conn.cursor(dictionary=True)
                    cur.execute(
                        "SELECT asin FROM yp_products WHERE merchant_id = %s",
                        (mid,),
                    )
                    existing_asins = set(r["asin"] for r in cur.fetchall())

                    # 找出需要删除的 ASIN（数据库有但新采集没有）
                    asins_to_delete = existing_asins - new_asins
                    if asins_to_delete:
                        delete_count = len(asins_to_delete)
                        cur.execute(
                            f"DELETE FROM yp_products WHERE merchant_id = %s AND asin IN ({','.join(['%s'] * delete_count)})",
                            [mid] + list(asins_to_delete),
                        )
                        db_conn.commit()
                        log("MAIN", f"  删除 {delete_count} 个已下架商品")

                    cur.close()

                    n = bulk_upsert_mysql(db_conn, products_this)
                    total_added += n
                    log("MAIN", f"  → MySQL 写入 {n} 条（本次合计: {total_added:,}）")

                    # 显示同步结果
                    log(
                        "MAIN",
                        f"  同步完成: 新增/更新 {n} 条, 删除 {len(asins_to_delete)} 条, 当前 {len(new_asins)} 条",
                    )

                completed_mids.add(mid)
                if not single_mid:
                    save_state(completed_mids, failed_mids)
                time.sleep(0.5)

            except Exception as e:
                log("MAIN", f"  处理 {name} 出错: {e}")
                failed_mids.add(mid)
                if not single_mid:
                    save_state(completed_mids, failed_mids)

    elapsed_total = int(time.time() - start_time)
    log("MAIN", "=" * 60)
    log("MAIN", f"完成！成功: {len(completed_mids)} | 失败: {len(failed_mids)}")
    log("MAIN", f"本次新增商品: {total_added:,} 条")
    log(
        "MAIN",
        f"耗时: {elapsed_total // 3600}h{elapsed_total % 3600 // 60}m{elapsed_total % 60}s",
    )

    # 显示最终 MySQL 总数
    final_count = get_db_product_count(db_conn)
    log("MAIN", f"MySQL yp_products 最终总数: {final_count:,} 条")

    # 自动增量同步缓存表（无论新增还是删除都需要同步）
    try:
        log("MAIN", "正在同步 yp_us_products 缓存表...")
        from build_us_cache import incremental_refresh

        incremental_refresh()
    except Exception as e:
        log("MAIN", f"缓存表同步失败（不影响采集结果）: {e}")

    db_conn.close()


if __name__ == "__main__":
    main()
