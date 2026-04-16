"""
批量获取 tracking_url 对应的 Amazon URL，写入 yp_products.amazon_url
原理：GET tracking_url（不跟跳转），读响应头 refresh: 0;url=https://www.amazon.com/...
"""

import mysql.connector
import requests
import re
import time
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── 配置 ─────────────────────────────────────────────────
BATCH_SIZE      = 1000      # 每批从 DB 取多少条
CONCURRENCY     = 30        # 并发线程数
RETRY_TIMES     = 2         # 失败重试次数
REQUEST_TIMEOUT = 12        # 请求超时秒
LOG_FILE        = os.path.join(os.path.dirname(__file__), "output", "fetch_amazon_urls.log")

DB_CONFIG = dict(
    host='localhost', port=3306,
    user='root', password='admin',
    database='affiliate_marketing',
    charset='utf8mb4'
)
# ──────────────────────────────────────────────────────────

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger(__name__)


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    })
    return s


def parse_refresh_url(headers: dict) -> str | None:
    """从响应头 refresh 字段提取 URL"""
    refresh = headers.get("refresh", "") or headers.get("Refresh", "")
    if not refresh:
        return None
    m = re.search(r'url=(.+)', refresh, re.IGNORECASE)
    return m.group(1).strip() if m else None


def fetch_one(session, row_id: int, tracking_url: str) -> tuple:
    """返回 (id, amazon_url_or_None, error_or_None)"""
    for attempt in range(RETRY_TIMES + 1):
        try:
            resp = session.get(tracking_url, allow_redirects=False, timeout=REQUEST_TIMEOUT)
            url = parse_refresh_url(resp.headers)
            if url:
                return (row_id, url, None)
            return (row_id, None, f"no_refresh_status_{resp.status_code}")
        except requests.exceptions.Timeout:
            if attempt < RETRY_TIMES:
                time.sleep(1)
                continue
            return (row_id, None, "timeout")
        except Exception as e:
            if attempt < RETRY_TIMES:
                time.sleep(0.5)
                continue
            return (row_id, None, str(e)[:80])
    return (row_id, None, "max_retry")


def db_connect():
    return mysql.connector.connect(**DB_CONFIG)


def get_pending_batch(conn, batch_size: int) -> list:
    """取一批 amazon_url 为空且有 tracking_url 的记录"""
    cur = conn.cursor()
    cur.execute(
        """SELECT id, tracking_url FROM yp_products
           WHERE (amazon_url IS NULL OR amazon_url = '')
             AND tracking_url IS NOT NULL AND tracking_url != ''
           ORDER BY id
           LIMIT %s""",
        (batch_size,)
    )
    rows = cur.fetchall()
    cur.close()
    return rows


def batch_update(conn, results: list):
    """批量 UPDATE amazon_url，results = [(id, url), ...]"""
    if not results:
        return
    cur = conn.cursor()
    cur.executemany(
        "UPDATE yp_products SET amazon_url = %s WHERE id = %s",
        [(url, rid) for rid, url in results]
    )
    conn.commit()
    cur.close()


def main():
    conn = db_connect()

    # 统计
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM yp_products WHERE amazon_url IS NOT NULL AND amazon_url != ''")
    done_init = cur.fetchone()[0]
    cur.close()

    log.info(f"总任务量: {total:,} 条")
    log.info(f"已完成: {done_init:,} 条  待处理: {total - done_init:,} 条")

    session = make_session()
    total_processed = 0
    total_success = 0
    total_fail = 0
    start_time = time.time()

    while True:
        rows = get_pending_batch(conn, BATCH_SIZE)
        if not rows:
            log.info("所有记录已处理完毕！")
            break

        log.info(f"取到 {len(rows)} 条 | id {rows[0][0]}~{rows[-1][0]}")

        # 并发抓取
        results_ok = []   # [(id, amazon_url)]
        results_fail = [] # [(id, 'FAILED')]

        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {
                executor.submit(fetch_one, session, row_id, url): row_id
                for row_id, url in rows
            }
            for future in as_completed(futures):
                row_id, amazon_url, err = future.result()
                total_processed += 1
                if amazon_url:
                    total_success += 1
                    results_ok.append((row_id, amazon_url))
                else:
                    total_fail += 1
                    results_fail.append((row_id, "FAILED"))
                    if err not in ("no_refresh_status_200",):
                        log.debug(f"  id={row_id} err={err}")

        # 批量写入 — 先写成功的，再写失败的（FAILED 占位，避免重复查询）
        batch_update(conn, results_ok)
        batch_update(conn, results_fail)

        elapsed = time.time() - start_time
        speed = total_processed / elapsed if elapsed > 0 else 0
        remaining = (total - done_init - total_processed) / speed if speed > 0 else 0
        log.info(
            f"本批完成 | 累计: {total_processed:,} 条 | 成功: {total_success:,} | 失败: {total_fail} "
            f"| 速度: {speed:.0f}条/s | 预计剩余: {remaining/60:.1f}分钟"
        )

    elapsed = time.time() - start_time
    log.info(f"=== 全部完成 === 处理 {total_processed:,} | 成功 {total_success:,} | 失败 {total_fail} | 耗时 {elapsed/60:.1f}分钟")
    conn.close()


if __name__ == "__main__":
    main()
