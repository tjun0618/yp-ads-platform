#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google 浏览器关键词采集脚本（Playwright 版）
=============================================
仅采集美国商户（yp_merchants.country LIKE 'US%'），约 7,457 个。

通过 Playwright 控制 Chrome，对每个商户名：
  1. 在 Google 搜索框输入商户名 → 读取自动补全下拉（Autocomplete）
  2. 提交搜索 → 读取页面底部"People also search for"及相关搜索

优点：完全模拟真实用户操作，无超时/限速问题

用法:
    python -X utf8 scrape_google_suggest_browser.py --limit 10
    python -X utf8 scrape_google_suggest_browser.py --merchant "Nike"
    python -X utf8 scrape_google_suggest_browser.py --no-skip
"""

import argparse
import json
import time
import re
import os
from datetime import datetime
import mysql.connector
from playwright.sync_api import sync_playwright

# ─── 配置 ────────────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4",
}

GOOGLE_URL = "https://www.google.com/?hl=en&gl=us"
DELAY_BETWEEN_MERCHANTS = 2.5  # 商户间隔（秒），避免触发人机验证

# ─── MySQL ────────────────────────────────────────────────────────────────────


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_table(conn):
    cur = conn.cursor()
    # 原始采集数据表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS google_suggest_keywords (
            id            INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id   VARCHAR(50),
            merchant_name VARCHAR(255),
            brand_query   VARCHAR(255),
            autocomplete  JSON COMMENT '搜索框下拉建议',
            related       JSON COMMENT '搜索结果页相关搜索',
            all_keywords  JSON COMMENT '全部关键词去重合并',
            keyword_count INT DEFAULT 0,
            status        VARCHAR(20) DEFAULT 'completed',
            scraped_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_mid (merchant_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # Google Ads 投放：品牌关键词表（US商户）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_merchant_keywords (
            id             INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            merchant_id    VARCHAR(50)  NOT NULL,
            merchant_name  VARCHAR(255),
            website        TEXT,
            avg_payout     DECIMAL(12,2) COMMENT '商户平均佣金金额($)',
            cookie_days    SMALLINT      COMMENT 'Cookie有效天数',
            keyword        VARCHAR(255) NOT NULL,
            keyword_source VARCHAR(20)  COMMENT 'autocomplete / related',
            synced_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_merchant_id (merchant_id),
            INDEX idx_keyword     (keyword),
            UNIQUE KEY uq_mid_kw  (merchant_id, keyword(200))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
          COMMENT='Google Ads 投放：品牌关键词表（US商户，来自 Google Suggest）'
    """)
    conn.commit()
    cur.close()


def get_target_merchants(conn, limit=None, merchant_name=None, merchant_id=None):
    """从 yp_us_products 获取商户信息（优先），回退到 yp_merchants"""
    cur = conn.cursor(dictionary=True)

    if merchant_id:
        # 优先从 yp_us_products 查找（这是商品列表的数据源）
        cur.execute(
            """
            SELECT DISTINCT yp_merchant_id AS merchant_id, merchant_name
            FROM yp_us_products
            WHERE yp_merchant_id = %s AND merchant_name IS NOT NULL AND merchant_name != ''
            LIMIT 1
        """,
            (int(merchant_id),),
        )
        row = cur.fetchone()
        if row:
            cur.close()
            return [row]
        # 回退到 yp_merchants
        cur.execute(
            """
            SELECT merchant_id, merchant_name
            FROM yp_merchants
            WHERE merchant_id = %s AND merchant_name IS NOT NULL AND merchant_name != ''
            LIMIT 1
        """,
            (str(merchant_id),),
        )
        row = cur.fetchone()
        cur.close()
        return [row] if row else []

    us_filter = (
        "country LIKE 'US%' AND merchant_name IS NOT NULL AND merchant_name != ''"
    )

    if merchant_name:
        cur.execute(
            f"""
            SELECT merchant_id, merchant_name
            FROM yp_merchants
            WHERE {us_filter} AND merchant_name LIKE %s
            ORDER BY merchant_id
        """,
            (f"%{merchant_name}%",),
        )
    elif limit:
        cur.execute(
            f"""
            SELECT merchant_id, merchant_name
            FROM yp_merchants
            WHERE {us_filter}
            ORDER BY merchant_id LIMIT %s
        """,
            (limit,),
        )
    else:
        cur.execute(f"""
            SELECT merchant_id, merchant_name
            FROM yp_merchants
            WHERE {us_filter}
            ORDER BY merchant_id
        """)
    rows = cur.fetchall()
    cur.close()
    return rows


def get_completed_ids(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT merchant_id FROM google_suggest_keywords WHERE status='completed'"
    )
    ids = {row[0] for row in cur.fetchall()}
    cur.close()
    return ids


def save_to_mysql(conn, merchant_id, merchant_name, brand_query, autocomplete, related):
    """保存原始采集数据到 google_suggest_keywords，同时同步到 ads_merchant_keywords"""

    # 品牌名匹配逻辑：支持模糊匹配
    # 1. 完整匹配（忽略大小写）
    # 2. 去除特殊符号后匹配（如 "Nectar & Nest" -> "nectar nest"）
    # 3. 检查品牌名的主要单词是否出现
    import re as _re

    brand_lower = brand_query.lower().strip()
    # 去除特殊符号，只保留字母数字空格
    brand_clean = _re.sub(r"[^a-z0-9\s]", "", brand_lower).strip()
    # 提取主要单词（忽略常见词）
    brand_words = [
        w
        for w in brand_clean.split()
        if w
        and len(w) > 2
        and w not in ("the", "and", "for", "inc", "llc", "ltd", "co", "com")
    ]

    def is_brand_related(kw):
        kw_lower = kw.lower()
        # 完整匹配
        if brand_lower in kw_lower:
            return True
        # 去除特殊符号后匹配
        if brand_clean and brand_clean in kw_lower:
            return True
        # 检查品牌名的主要单词是否都出现（适用于 "Brand Name" 这种情况）
        if len(brand_words) >= 2:
            # 至少包含品牌名中的一半单词
            match_count = sum(1 for w in brand_words if w in kw_lower)
            if match_count >= max(1, len(brand_words) // 2):
                return True
        return False

    filtered_autocomplete = [kw for kw in autocomplete if is_brand_related(kw)]
    filtered_related = [kw for kw in related if is_brand_related(kw)]
    all_kws = sorted(set(filtered_autocomplete + filtered_related))

    cur = conn.cursor()

    # ① 写原始数据表（保存筛选后的关键词）
    cur.execute(
        """
        INSERT INTO google_suggest_keywords
            (merchant_id, merchant_name, brand_query, autocomplete, related, all_keywords, keyword_count, status, scraped_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,'completed',NOW())
        ON DUPLICATE KEY UPDATE
            brand_query   = VALUES(brand_query),
            autocomplete  = VALUES(autocomplete),
            related       = VALUES(related),
            all_keywords  = VALUES(all_keywords),
            keyword_count = VALUES(keyword_count),
            scraped_at    = NOW()
    """,
        (
            str(merchant_id),
            merchant_name,
            brand_query,
            json.dumps(autocomplete, ensure_ascii=False),
            json.dumps(related, ensure_ascii=False),
            json.dumps(all_kws, ensure_ascii=False),
            len(all_kws),
        ),
    )

    # ② 同步到 ads_merchant_keywords（先查商户补充信息）
    cur.execute(
        """
        SELECT website, avg_payout, cookie_days
        FROM yp_merchants
        WHERE CONVERT(merchant_id USING utf8mb4) = CONVERT(%s USING utf8mb4)
        LIMIT 1
    """,
        (str(merchant_id),),
    )
    m_info = cur.fetchone()
    website = m_info[0] if m_info else None
    avg_payout = m_info[1] if m_info else None
    cookie_days = m_info[2] if m_info else None

    # 关键词去重，保留来源，并筛选出与品牌相关的词（使用上面的匹配函数）
    seen = {}
    for kw in autocomplete:
        k = kw.strip()
        if k and k.lower() not in seen and is_brand_related(k):
            seen[k.lower()] = (k, "autocomplete")
    for kw in related:
        k = kw.strip()
        if k and k.lower() not in seen and is_brand_related(k):
            seen[k.lower()] = (k, "related")

    for _, (kw_orig, src) in seen.items():
        cur.execute(
            """
            INSERT INTO ads_merchant_keywords
                (merchant_id, merchant_name, website, avg_payout, cookie_days,
                 keyword, keyword_source)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                merchant_name  = VALUES(merchant_name),
                website        = VALUES(website),
                avg_payout     = VALUES(avg_payout),
                cookie_days    = VALUES(cookie_days),
                keyword_source = VALUES(keyword_source),
                synced_at      = NOW()
        """,
            (
                str(merchant_id),
                merchant_name,
                website,
                avg_payout,
                cookie_days,
                kw_orig,
                src,
            ),
        )

    conn.commit()
    cur.close()
    return all_kws


# ─── 品牌名清洗 ───────────────────────────────────────────────────────────────


def clean_brand(name):
    # 去掉末尾的地区/类型标记，可能有多个，循环处理
    pattern = r"\s+(US|UK|EU|AU|CA|PL|DE|FR|IT|ES|NL|COM|INC|LLC|LTD|CO\.|CORP\.?|CPS|CPA|CPL|CPM|B2B|B2C)$"
    for _ in range(4):
        new = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()
        if new == name:
            break
        name = new
    # 去掉国家域名后缀（如 .de .fr .co.uk）
    name = re.sub(
        r"\.(com|net|org|io|co|de|fr|uk|it|es|nl|pl|ru|jp|cn)(\.\w{2})?$",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    return re.sub(r"\s+", " ", name).strip()


# ─── 浏览器采集核心 ────────────────────────────────────────────────────────────


def scrape_one(page, brand):
    """对单个品牌名采集自动补全 + 相关搜索，返回 (autocomplete[], related[])"""
    autocomplete = []
    related = []

    # ── Step 1: 打开 Google 首页，输入品牌名，读自动补全 ──
    page.goto(GOOGLE_URL, wait_until="domcontentloaded", timeout=20000)
    time.sleep(1)

    # 定位搜索框（textarea 或 input，Google 两种都有）
    search_box = page.locator("textarea[name='q'], input[name='q']").first
    search_box.click()
    time.sleep(0.5)
    search_box.fill("")
    search_box.type(brand, delay=60)  # 模拟人工输入，每字符 60ms
    time.sleep(1.5)  # 等自动补全下拉弹出

    # 读取自动补全下拉 —— Google 用 li[role='option'] 或 li.sbct 等
    suggestions = page.evaluate("""() => {
        const results = [];
        // 方法1: role=option
        document.querySelectorAll('[role="option"]').forEach(el => {
            const t = el.innerText.trim().split('\\n')[0].trim();
            if (t) results.push(t);
        });
        // 方法2: 备用 selector
        if (results.length === 0) {
            document.querySelectorAll('li.sbct, .erkvQe li, ul[role=listbox] li').forEach(el => {
                const t = el.innerText.trim().split('\\n')[0].trim();
                if (t) results.push(t);
            });
        }
        return [...new Set(results)];
    }""")
    autocomplete = [s for s in suggestions if s and len(s) > 1]
    print(f"    自动补全: {len(autocomplete)} 条 → {autocomplete[:4]}")

    # ── Step 2: 提交搜索，读结果页"相关搜索" ──
    # 使用 Promise 等待导航完成，避免 context destroyed 错误
    try:
        nav_promise = page.wait_for_event("framenavigated", timeout=15000)
        page.keyboard.press("Enter")
        nav_promise  # 等待导航完成
    except Exception:
        pass

    # 等待搜索结果页面稳定
    try:
        page.wait_for_selector("#search, #rso, [data-sokoban-container]", timeout=10000)
    except Exception:
        pass
    time.sleep(1.5)

    related_raw = page.evaluate("""() => {
        const results = [];

        // 最佳选择器：基于 URL 参数提取相关搜索链接
        // Google 相关搜索链接格式: /search?q=关键词&sa=X&ved=...
        document.querySelectorAll('a[href*="/search?q="][href*="sa=X"]').forEach(el => {
            const href = el.getAttribute('href') || '';
            // 从 URL 提取 q 参数
            const match = href.match(/[?&]q=([^&]+)/);
            if (match) {
                const t = decodeURIComponent(match[1].replace(/\\+/g, ' '));
                // 过滤导航类链接
                if (t && !t.includes('site:') && el.innerText.trim()) {
                    results.push(t);
                }
            }
        });

        // 备用选择器1: data-q 属性
        if (results.length === 0) {
            document.querySelectorAll('[data-q]').forEach(el => {
                const t = el.getAttribute('data-q') || el.innerText.trim();
                if (t) results.push(t);
            });
        }

        // 备用选择器2: People Also Ask 区域
        if (results.length === 0) {
            document.querySelectorAll('.related-question-pair, .kp-blk [role="button"]').forEach(el => {
                const t = el.innerText.trim();
                if (t && t.length > 2) results.push(t);
            });
        }

        return [...new Set(results)];
    }""")
    related = [s for s in related_raw if s and 2 < len(s) < 100]
    print(f"    相关搜索: {len(related)} 条 → {related[:4]}")

    return autocomplete, related


# ─── 主程序 ───────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--merchant", type=str, help="按商户名称模糊匹配")
    parser.add_argument(
        "--merchant-id",
        type=str,
        dest="merchant_id",
        help="按商户ID精确采集（按需模式）",
    )
    parser.add_argument("--no-skip", action="store_true")
    args = parser.parse_args()

    conn = get_db()
    ensure_table(conn)

    merchants = get_target_merchants(
        conn,
        limit=args.limit,
        merchant_name=args.merchant,
        merchant_id=args.merchant_id,
    )
    print(f"目标商户数（仅美国 US）: {len(merchants)}")

    if not args.no_skip:
        done = get_completed_ids(conn)
        merchants = [m for m in merchants if str(m["merchant_id"]) not in done]
        print(f"  待采集: {len(merchants)}")

    if not merchants:
        print("全部已完成，退出。")
        return

    os.makedirs("output", exist_ok=True)
    backup = f"output/google_suggest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"

    ok = err = 0

    with sync_playwright() as pw:
        # 连接到已开启调试端口的 Chrome（继承已登录的 Google 账户，减少验证码）
        # 如果没有调试 Chrome，则自动启动新浏览器
        try:
            browser = pw.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
            page = ctx.new_page()
            print("已连接到调试 Chrome")
        except Exception:
            browser = pw.chromium.launch(headless=False, args=["--lang=en-US"])
            ctx = browser.new_context(locale="en-US")
            page = ctx.new_page()
            print("已启动新 Chrome（无头模式关闭，可见窗口）")

        for idx, m in enumerate(merchants, 1):
            mid = m["merchant_id"]
            mname = m["merchant_name"]
            brand = clean_brand(mname)
            print(f"\n[{idx}/{len(merchants)}] {mname}  →  搜索词: '{brand}'")

            try:
                ac, rel = scrape_one(page, brand)
                all_kws = save_to_mysql(conn, mid, mname, brand, ac, rel)

                # 本地备份
                with open(backup, "a", encoding="utf-8") as f:
                    f.write(
                        json.dumps(
                            {
                                "merchant_id": str(mid),
                                "merchant_name": mname,
                                "brand_query": brand,
                                "autocomplete": ac,
                                "related": rel,
                                "keyword_count": len(all_kws),
                                "scraped_at": datetime.now().isoformat(),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )

                print(f"  ✓ 共 {len(all_kws)} 个关键词入库")
                ok += 1

            except Exception as e:
                print(f"  ✗ {e}")
                err += 1

            if idx < len(merchants):
                time.sleep(DELAY_BETWEEN_MERCHANTS)

        page.close()

    # 汇总
    print(f"\n{'=' * 55}")
    print(f"完成！成功 {ok} | 失败 {err}")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(keyword_count) FROM google_suggest_keywords")
    row = cur.fetchone()
    print(f"数据库累计: {row[0]} 商户 / {row[1] or 0} 关键词")
    cur.close()
    print(f"备份文件: {backup}")
    conn.close()


if __name__ == "__main__":
    main()
