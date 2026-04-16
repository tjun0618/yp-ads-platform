# -*- coding: utf-8 -*-
"""
探查：Overview 页面上有哪些 Tab，每个 Tab 能获取哪些数据
目标：确认是否可以在 Overview 单页取到 organic/paid keywords + ad copies
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
SEMRUSH_BASE = 'https://zh.trends.fast.wmxpro.com'

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]

        page = None
        for p in context.pages:
            if 'trends.fast' in p.url or 'wmxpro' in p.url:
                page = p
                break
        if not page:
            page = context.new_page()

        # ─── 先检查积分 ───────────────────────────
        page.goto(f'{SEMRUSH_BASE}/wmx/credit/daily/limit',
                  wait_until='domcontentloaded', timeout=15000)
        time.sleep(3)
        credit = page.evaluate("() => document.body.innerText.slice(0, 200)")
        print("【积分状态】")
        print(credit[:200])
        if '积分已用完' in credit:
            print("\n⚠️ 积分已用完，无法测试。请明天积分重置后再运行。")
            return

        # ─── 访问 Overview 搜索页（不带 q 参数）───
        print("\n" + "="*60)
        print("【步骤1】访问 Overview 主页（不带域名）")
        url = f'{SEMRUSH_BASE}/analytics/overview/'
        page.goto(url, wait_until='domcontentloaded', timeout=20000)
        time.sleep(5)

        # 截图
        page.screenshot(path='output/explore_overview_1_before_search.png')

        # 找到搜索框
        search_selectors = [
            'input[data-at="search-input"]',
            'input[placeholder*="example"]',
            'input[placeholder*="ebay"]',
            'input[placeholder*="示例"]',
            'input[type="text"]',
        ]
        inp = None
        for sel in search_selectors:
            try:
                e = page.locator(sel).first
                if e.is_visible(timeout=2000):
                    inp = e
                    print(f"  ✅ 找到搜索框: selector={sel}")
                    break
            except:
                continue

        if not inp:
            print("  ❌ 未找到搜索框，截图查看")
            return

        # ─── 输入测试域名 ─────────────────────────
        TEST_DOMAIN = 'rei.com'
        print(f"\n【步骤2】在搜索框输入: {TEST_DOMAIN}")
        inp.triple_click()
        time.sleep(0.3)
        inp.type(TEST_DOMAIN, delay=100)
        time.sleep(1.5)

        # 截图（输入后、提交前）
        page.screenshot(path='output/explore_overview_2_typed.png')

        # 看看有没有下拉建议
        suggestions = page.evaluate("""() => {
            const items = document.querySelectorAll('[role="option"], [role="listbox"] li, [class*="suggest"] li');
            return [...items].slice(0, 5).map(el => el.textContent.trim());
        }""")
        if suggestions:
            print(f"  下拉建议: {suggestions}")

        page.keyboard.press('Enter')
        time.sleep(12)  # 等待数据加载

        # 截图（搜索后）
        page.screenshot(path='output/explore_overview_3_after_search.png')
        print(f"  当前 URL: {page.url}")

        # ─── 提取页面上所有 Tab 名称 ──────────────
        print("\n【步骤3】提取页面 Tab 列表")
        tabs = page.evaluate("""() => {
            const tabs = document.querySelectorAll('[role="tab"], nav a, [class*="Tab"], [class*="tab"]');
            return [...tabs].slice(0, 20).map(el => ({
                text: el.textContent.trim(),
                href: el.getAttribute('href') || '',
                role: el.getAttribute('role') || '',
            })).filter(t => t.text.length > 0 && t.text.length < 50);
        }""")
        print(f"  找到 {len(tabs)} 个 Tab/导航项:")
        for t in tabs:
            print(f"    [{t['role']}] {t['text']} → {t['href']}")

        # ─── 提取页面上所有可见的数字/统计数据 ──
        print("\n【步骤4】提取 Overview 页面统计数据")
        body_text = page.evaluate("() => document.body.innerText")
        print("  页面文本（前 1000 字）:")
        print(body_text[:1000])

        # ─── 检查页面上是否有关键词 Table/Grid ───
        print("\n【步骤5】检查页面是否直接包含关键词数据")
        grids = page.evaluate("""() => {
            const grids = document.querySelectorAll('[role="grid"], table');
            return [...grids].map(g => ({
                rows: g.querySelectorAll('[role="row"], tr').length,
                html_preview: g.outerHTML.slice(0, 200),
            }));
        }""")
        print(f"  找到 {len(grids)} 个 grid/table:")
        for i, g in enumerate(grids):
            print(f"    [{i}] {g['rows']} 行 | {g['html_preview'][:100]}")

        # ─── 保存完整页面 HTML ─────────────────────
        html = page.content()
        with open('output/explore_overview_full.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\n  📄 完整 HTML 已保存到 output/explore_overview_full.html")

        # ─── 检查左侧/顶部导航中是否有关键词入口 ──
        print("\n【步骤6】提取所有链接（含 keyword/paid/organic 相关）")
        links = page.evaluate("""() => {
            const links = document.querySelectorAll('a[href]');
            return [...links]
                .map(a => ({ text: a.textContent.trim(), href: a.href }))
                .filter(l => l.href && (
                    l.href.includes('keyword') || l.href.includes('organic') ||
                    l.href.includes('paid') || l.href.includes('adword') ||
                    l.href.includes('advertising') || l.text.includes('关键') ||
                    l.text.includes('付费') || l.text.includes('广告')
                ))
                .slice(0, 30);
        }""")
        print(f"  相关链接 ({len(links)} 条):")
        for l in links:
            print(f"    {l['text'][:30]:30s} → {l['href']}")

        print("\n" + "="*60)
        print("探查完毕！请查看截图：")
        print("  output/explore_overview_1_before_search.png")
        print("  output/explore_overview_2_typed.png")
        print("  output/explore_overview_3_after_search.png")

if __name__ == '__main__':
    main()
