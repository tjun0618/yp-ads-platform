# -*- coding: utf-8 -*-
"""
SEMrush 数据采集 v9 — 单页 Tab 切换模式

核心改进（相比 v8）：
  - 不再跳转到 /organic/positions、/adwords/positions 等子页面
  - 只需在 Overview 页输入域名，然后切换左侧导航 Tab 采集各类数据
  - 每个商户理论上只消耗 1~2 次积分（视 Tab 切换是否消耗积分而定）
  - navigate_tab() 负责点击左侧导航 Tab 并等待数据加载

使用方法：
  python -X utf8 scrape_semrush.py --limit 20
  python -X utf8 scrape_semrush.py --domain rei.com
  python -X utf8 scrape_semrush.py --limit 50 --overview-only  # 只采集流量概览
"""

import json
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
import mysql.connector
import random
import re
from urllib.parse import urlparse

CHROME_WS = 'http://127.0.0.1:9222'
SEMRUSH_BASE = 'https://zh.trends.fast.wmxpro.com'
OUTPUT_DIR = Path('output/semrush_final')

MYSQL_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "admin", "database": "affiliate_marketing", "charset": "utf8mb4"
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS semrush_competitor_data (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id INT NOT NULL,
    merchant_name VARCHAR(255),
    domain VARCHAR(255) NOT NULL,
    monthly_visits VARCHAR(50),
    organic_traffic VARCHAR(50),
    paid_traffic VARCHAR(50),
    authority_score VARCHAR(20),
    organic_keywords_count VARCHAR(50),
    paid_keywords_count VARCHAR(50),
    backlinks VARCHAR(50),
    top_organic_keywords JSON,
    top_paid_keywords JSON,
    ad_copies JSON,
    scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50),
    UNIQUE KEY uk_merchant_domain (merchant_id, domain),
    INDEX idx_merchant (merchant_id),
    INDEX idx_domain (domain)
) ENGINE=InnoDB;
"""

# ─── 左侧/顶部导航 Tab 的可能文字（中文界面）────────────────────────
# 每个 tuple: (tab_keyword, 用途)
# 通过 text 内容匹配，不依赖 class
TAB_ORGANIC  = ['自然研究', '有机搜索', 'Organic Research', '自然关键词', 'Organic']
TAB_PAID     = ['广告研究', '付费搜索', 'Advertising Research', 'PPC', '付费关键词']
TAB_ADCOPY   = ['广告文案', 'Ad Copies', 'Text Ads', '搜索广告']


def extract_domain(url):
    if not url:
        return None
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain or None
    except:
        return None


def check_credit_ok(page):
    """检测是否积分不足"""
    try:
        body = page.evaluate("() => document.body.innerText.slice(0, 200)")
        return '积分已用完' not in body and 'credit/daily/limit' not in page.url
    except:
        return True


def enter_domain(page, domain, wait_sec=12):
    """
    在搜索框输入域名并提交，等待结果加载。
    返回 True = 成功，False = 积分不足
    """
    # 先找搜索框
    search_selectors = [
        'input[data-at="search-input"]',
        'input[placeholder*="example"]',
        'input[placeholder*="ebay"]',
        'input[placeholder*="示例"]',
        'input[type="search"]',
        'input[type="text"]',
    ]
    inp = None
    for sel in search_selectors:
        try:
            e = page.locator(sel).first
            if e.is_visible(timeout=2000):
                inp = e
                break
        except:
            continue

    if not inp:
        print(f"    ⚠️  未找到搜索框")
        return False

    # 清空并输入
    inp.triple_click()
    time.sleep(0.3)
    inp.fill('')
    inp.type(domain, delay=80)
    time.sleep(0.8)
    page.keyboard.press('Enter')
    time.sleep(wait_sec)

    # 检查积分
    if not check_credit_ok(page):
        print(f"    ⛔ 积分不足")
        return False

    # 验证 URL 更新
    if domain in page.url or 'q=' in page.url:
        print(f"    ✅ 搜索成功 → {page.url}")
        return True
    else:
        print(f"    ⚠️  URL 未更新: {page.url}")
        # 有时候 URL 不变但数据已加载，继续尝试
        return True


def navigate_tab(page, tab_keywords, wait_sec=8):
    """
    点击左侧/顶部导航中包含 tab_keywords 任一关键词的链接/Tab。
    返回 True = 成功点击，False = 未找到
    """
    for keyword in tab_keywords:
        try:
            # 尝试 text 匹配的链接或 Tab
            selectors = [
                f'a:has-text("{keyword}")',
                f'[role="tab"]:has-text("{keyword}")',
                f'li:has-text("{keyword}") a',
                f'nav a:has-text("{keyword}")',
            ]
            for sel in selectors:
                try:
                    elem = page.locator(sel).first
                    if elem.is_visible(timeout=2000):
                        href = elem.get_attribute('href') or ''
                        print(f"    → 点击 Tab: [{keyword}] {href}")
                        elem.click()
                        time.sleep(wait_sec)
                        if not check_credit_ok(page):
                            print(f"    ⛔ 积分不足（Tab 切换后）")
                            return False
                        return True
                except:
                    continue
        except:
            continue
    print(f"    ⚠️  未找到 Tab（关键词: {tab_keywords}）")
    return False


def extract_overview_data(page):
    """从当前页面提取概览统计数据（文本正则匹配）"""
    for label in ['有机流量', '自然流量', 'Organic Traffic', '权威评分']:
        try:
            page.wait_for_selector(f'text={label}', timeout=8000)
            break
        except:
            continue
    time.sleep(2)

    return page.evaluate(r'''() => {
        const bodyText = document.body.innerText;
        const data = {};
        const targets = [
            ['权威评分',    'authority_score'],
            ['有机流量',    'organic_traffic'],
            ['自然流量',    'organic_traffic'],
            ['付费流量',    'paid_traffic'],
            ['自然关键词',  'organic_keywords_count'],
            ['付费关键词',  'paid_keywords_count'],
            ['反向链接',    'backlinks'],
            ['引荐域名',    'ref_domains'],
        ];
        targets.forEach(([label, key]) => {
            if (data[key]) return;
            const esc = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const m = bodyText.match(new RegExp(esc + '\\s+([\\d,.]+[KMB]?)(?:\\s+([+-]?\\d+\\.?\\d*%)?)?'));
            if (m) data[key] = { value: m[1], change: m[2] || null };
        });
        return data;
    }''')


def extract_keyword_grid(page, max_rows=20):
    """从 [role="grid"] 提取关键词/广告数据，返回原始 rows（list of list）"""
    try:
        page.wait_for_selector('[role="grid"] [role="row"]', timeout=15000)
    except:
        return []
    time.sleep(3)

    return page.evaluate(f'''() => {{
        const results = [];
        const grid = document.querySelector('[role="grid"]');
        if (!grid) return results;
        const rows = grid.querySelectorAll('[role="row"]');
        rows.forEach((row, i) => {{
            if (i === 0) return;
            const cells = row.querySelectorAll('[role="gridcell"], [role="cell"]');
            const texts = [...cells].map(c => c.textContent.trim());
            if (texts.length >= 3 && (texts[1] || texts[2])) {{
                results.push(texts);
            }}
        }});
        return results.slice(0, {max_rows});
    }}''')


def parse_organic_kws(rows):
    return [{'keyword': r[1], 'intent': r[2], 'position': r[3],
             'traffic': r[5] if len(r)>5 else '', 'volume': r[7] if len(r)>7 else '',
             'url': r[10] if len(r)>10 else ''}
            for r in rows if len(r)>=4 and r[1]]


def parse_paid_kws(rows):
    return [{'keyword': r[1], 'position': r[3] if len(r)>3 else '',
             'cpc': r[4] if len(r)>4 else '', 'traffic': r[5] if len(r)>5 else '',
             'volume': r[6] if len(r)>6 else '', 'url': r[10] if len(r)>10 else ''}
            for r in rows if len(r)>=3 and r[1]]


def parse_ad_copies(rows):
    return [{'keyword': r[1] if len(r)>1 else '',
             'title': r[2] if len(r)>2 else '',
             'description': r[3] if len(r)>3 else '',
             'url': r[4] if len(r)>4 else ''}
            for r in rows if len(r)>=3 and (r[1] or r[2])]


def get_target_merchants(limit=10, skip_done=True):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)

    done_domains = set()
    if skip_done:
        cursor.execute("SELECT domain FROM semrush_competitor_data WHERE status='completed'")
        done_domains = {r['domain'] for r in cursor.fetchall()}
        if done_domains:
            print(f"  ↩️  已完成 {len(done_domains)} 个商户，跳过")

    cursor.execute("""
        SELECT DISTINCT m.mid as merchant_id, m.merchant_name, m.site_url, m.avg_payout
        FROM yp_merchants m
        WHERE m.country LIKE 'US%%' AND m.site_url IS NOT NULL
          AND m.site_url != '' AND m.merchant_status = 'onLine'
        ORDER BY m.avg_payout DESC
        LIMIT %s
    """, (limit * 4,))
    merchants = cursor.fetchall()
    cursor.close()
    conn.close()

    EXCLUDE = {'amazon.com','google.com','facebook.com','instagram.com',
               'twitter.com','youtube.com','pinterest.com','ebay.com'}
    valid, seen = [], set()
    for m in merchants:
        d = extract_domain(m['site_url'])
        if not d or d in EXCLUDE or d in done_domains or d in seen:
            continue
        seen.add(d)
        m['domain'] = d
        valid.append(m)
        if len(valid) >= limit:
            break
    return valid


def save_to_mysql(merchant, overview, organic_kws, paid_kws, ad_copies):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO semrush_competitor_data
            (merchant_id, merchant_name, domain, monthly_visits, organic_traffic,
             paid_traffic, authority_score, organic_keywords_count, paid_keywords_count,
             backlinks, top_organic_keywords, top_paid_keywords, ad_copies, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                merchant_name=VALUES(merchant_name), organic_traffic=VALUES(organic_traffic),
                paid_traffic=VALUES(paid_traffic), authority_score=VALUES(authority_score),
                organic_keywords_count=VALUES(organic_keywords_count),
                paid_keywords_count=VALUES(paid_keywords_count), backlinks=VALUES(backlinks),
                top_organic_keywords=VALUES(top_organic_keywords),
                top_paid_keywords=VALUES(top_paid_keywords), ad_copies=VALUES(ad_copies),
                scraped_at=NOW(), status=VALUES(status)
        """, (
            merchant['merchant_id'], merchant['merchant_name'], merchant['domain'],
            overview.get('organic_traffic', {}).get('value'),
            overview.get('organic_traffic', {}).get('value'),
            overview.get('paid_traffic', {}).get('value'),
            overview.get('authority_score', {}).get('value'),
            overview.get('organic_keywords_count', {}).get('value'),
            overview.get('paid_keywords_count', {}).get('value'),
            overview.get('backlinks', {}).get('value'),
            json.dumps(organic_kws, ensure_ascii=False) if organic_kws else None,
            json.dumps(paid_kws, ensure_ascii=False) if paid_kws else None,
            json.dumps(ad_copies, ensure_ascii=False) if ad_copies else None,
            'completed'
        ))
        conn.commit()
        print(f"    💾 MySQL 保存成功")
    except Exception as e:
        print(f"    ❌ MySQL 错误: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def scrape_one_merchant(page, merchant, overview_only=False):
    """采集单个商户 — 单页 Tab 切换模式"""
    mid    = merchant['merchant_id']
    name   = merchant['merchant_name']
    domain = merchant['domain']

    print(f"\n{'='*55}")
    print(f"🎯 [{mid}] {name} — {domain}")
    print(f"{'='*55}")

    result = {'overview': {}, 'organic': [], 'paid': [], 'ads': []}

    # ─── 访问 Overview 页并输入域名 ──────────────────────────
    print(f"  [1] 进入 Overview 页，搜索 {domain}...")
    overview_url = f'{SEMRUSH_BASE}/analytics/overview/?searchType=domain&q={domain}&db=us'
    page.goto(overview_url, wait_until='domcontentloaded', timeout=30000)
    time.sleep(10)

    if not check_credit_ok(page):
        print(f"  ⛔ 积分不足，停止")
        return None

    # 若 URL 中没有域名（被跳转到搜索页），在搜索框输入
    if domain not in page.url:
        print(f"  → URL 未含域名，尝试搜索框输入...")
        ok = enter_domain(page, domain, wait_sec=12)
        if not ok:
            return None

    # ─── 提取 Overview 数据 ──────────────────────────────────
    result['overview'] = extract_overview_data(page)
    ov = result['overview']
    print(f"  Overview: 有机流量={ov.get('organic_traffic',{}).get('value','-')} | "
          f"付费流量={ov.get('paid_traffic',{}).get('value','-')} | "
          f"权威评分={ov.get('authority_score',{}).get('value','-')}")

    if overview_only:
        save_to_mysql(merchant, result['overview'], [], [], [])
        return result

    # ─── 切换到自然关键词 Tab ─────────────────────────────────
    print(f"  [2] 切换到自然关键词 Tab...")
    found = navigate_tab(page, TAB_ORGANIC, wait_sec=10)
    if not found:
        # 备用：直接访问子页面 URL
        print(f"      备用：直接访问 organic/positions URL")
        page.goto(f'{SEMRUSH_BASE}/analytics/organic/positions/?searchType=domain&q={domain}&db=us',
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(10)
        if not check_credit_ok(page):
            return None

    raw = extract_keyword_grid(page)
    result['organic'] = parse_organic_kws(raw)
    print(f"  自然关键词: {len(result['organic'])} 条")
    if result['organic']:
        top = result['organic'][0]
        print(f"  Top: [{top['keyword']}] 位置={top['position']} 流量={top['traffic']}")

    # ─── 切换到付费关键词 Tab ─────────────────────────────────
    print(f"  [3] 切换到付费关键词 Tab...")
    found = navigate_tab(page, TAB_PAID, wait_sec=10)
    if not found:
        print(f"      备用：直接访问 adwords/positions URL")
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q={domain}&db=us',
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(10)
        if not check_credit_ok(page):
            return None

    raw = extract_keyword_grid(page)
    result['paid'] = parse_paid_kws(raw)
    print(f"  付费关键词: {len(result['paid'])} 条")
    if result['paid']:
        print(f"  Top: [{result['paid'][0]['keyword']}] CPC={result['paid'][0]['cpc']}")

    # ─── 切换到广告文案 Tab ───────────────────────────────────
    print(f"  [4] 切换到广告文案 Tab...")
    found = navigate_tab(page, TAB_ADCOPY, wait_sec=10)
    if not found:
        print(f"      备用：直接访问 adwords/textads URL")
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q={domain}&db=us',
                  wait_until='domcontentloaded', timeout=30000)
        time.sleep(10)
        if not check_credit_ok(page):
            return None

    raw = extract_keyword_grid(page)
    result['ads'] = parse_ad_copies(raw)
    print(f"  广告文案: {len(result['ads'])} 条")
    if result['ads']:
        print(f"  Top: {result['ads'][0].get('title','')[:50]}")

    # ─── 保存 ─────────────────────────────────────────────────
    save_to_mysql(merchant, result['overview'], result['organic'],
                  result['paid'], result['ads'])
    return result


def get_merchant_by_id(merchant_id, override_domain=None):
    """根据商户ID获取商户信息，包括website字段
    
    Args:
        merchant_id: 商户ID
        override_domain: 手动指定的域名，优先使用
    """
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT mid as merchant_id, merchant_name, site_url, website, avg_payout "
        "FROM yp_merchants WHERE mid = %s LIMIT 1",
        (merchant_id,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        return None
    # 优先使用手动传入的域名，其次使用 website 字段，最后使用 site_url
    domain = extract_domain(override_domain) if override_domain else None
    if not domain:
        domain = extract_domain(row.get('website') or row.get('site_url'))
    if not domain:
        return None
    return {
        'merchant_id': row['merchant_id'],
        'merchant_name': row['merchant_name'],
        'domain': domain,
        'avg_payout': row.get('avg_payout', 0)
    }


def main():
    parser = argparse.ArgumentParser(description='SEMrush 采集 v9 — 单页 Tab 模式')
    parser.add_argument('--limit', type=int, default=5,         help='采集商户数（默认5）')
    parser.add_argument('--domain', type=str,                    help='只采集指定域名（测试用）')
    parser.add_argument('--merchant-id', type=str,               help='指定商户ID采集（用于作战室触发）')
    parser.add_argument('--overview-only', action='store_true',  help='只采集 Overview（省积分）')
    parser.add_argument('--no-skip', action='store_true',        help='不跳过已采集商户')
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化 MySQL 表
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    conn.commit()
    cursor.close()
    conn.close()

    # 确定目标商户
    if args.merchant_id:
        # 如果同时指定了 --domain，优先使用手动传入的域名
        merchant = get_merchant_by_id(args.merchant_id, override_domain=args.domain)
        if not merchant:
            print(f"❌ 商户ID {args.merchant_id} 不存在或没有有效的 website/site_url")
            return
        merchants = [merchant]
    elif args.domain:
        merchants = [{'merchant_id': 0, 'merchant_name': args.domain,
                      'domain': args.domain, 'avg_payout': 0}]
    else:
        merchants = get_target_merchants(args.limit, skip_done=not args.no_skip)

    if not merchants:
        print("✅ 没有需要采集的商户（全部已完成）")
        return

    print(f"\n✅ 准备采集 {len(merchants)} 个商户：")
    for m in merchants:
        print(f"   [{m['merchant_id']}] {m['merchant_name']} ({m['domain']})")

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]

        page = None
        for p in context.pages:
            if 'trends.fast' in p.url or 'wmxpro' in p.url:
                page = p
                print(f"\n🔗 复用 Tab: {p.url}")
                break
        if not page:
            page = context.new_page()
            print("\n🆕 创建新 Tab")

        all_results = []
        aborted = False

        for i, merchant in enumerate(merchants, 1):
            print(f"\n📊 进度: {i}/{len(merchants)}")
            result = scrape_one_merchant(page, merchant,
                                          overview_only=args.overview_only)
            if result is None:
                print("\n⛔ 积分不足，已停止。明天积分重置后继续。")
                aborted = True
                break

            all_results.append({'domain': merchant['domain'], 'data': result})

            if i < len(merchants):
                delay = random.uniform(5, 10)
                print(f"  ⏱️  等待 {delay:.0f}s...")
                time.sleep(delay)

        # 保存汇总 JSON
        out_file = OUTPUT_DIR / 'all_results.json'
        out_file.write_text(
            json.dumps(all_results, indent=2, ensure_ascii=False), encoding='utf-8')

        print(f"\n{'='*60}")
        if aborted:
            print(f"⚠️  中断。已完成 {len(all_results)}/{len(merchants)} 个商户")
        else:
            print(f"✅ 完成！{len(all_results)} 个商户")
        print(f"📁 {out_file}")
        print(f"💾 semrush_competitor_data")
        print("=" * 60)


if __name__ == '__main__':
    main()
