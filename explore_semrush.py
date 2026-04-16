# -*- coding: utf-8 -*-
"""
SEMrush 真实界面探查 — 通过外贸侠代理的实际域名
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
SEMRUSH_BASE = 'https://www.trends.fast.wmxpro.com'
OUTPUT_DIR = Path('output/semrush_explore')


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🔍 SEMrush 真实界面探查")
    print(f"   域名: {SEMRUSH_BASE}")
    print("=" * 60)
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        
        # 在已有 context 中创建新 page
        page = context.new_page()
        
        # 1. 访问域名概览页面
        test_domain = 'amazon.com'
        overview_url = f'{SEMRUSH_BASE}/analytics/overview/?searchType=domain&q={test_domain}&db=us'
        print(f"\n1️⃣ 访问域名概览: {overview_url}")
        
        page.goto(overview_url, wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        # 截图
        page.screenshot(path=str(OUTPUT_DIR / '01_overview.png'), full_page=True)
        (OUTPUT_DIR / '01_overview.html').write_text(page.content(), encoding='utf-8')
        print(f"   当前 URL: {page.url}")
        
        # 获取页面文本
        page_text = page.inner_text('body')[:3000] if page.locator('body').count() > 0 else ''
        (OUTPUT_DIR / '01_overview_text.txt').write_text(page_text, encoding='utf-8')
        print(f"   页面文本前300字:\n   {page_text[:300]}")
        
        # 2. 分析页面结构
        print(f"\n2️⃣ 分析页面结构...")
        
        # 查找所有数据区域
        data_regions = page.eval_on_selector_all('[class*="data"], [class*="summary"], [class*="stat"], [class*="traffic"], [class*="visit"]',
            'els=>els.map(e=>({tag:e.tagName, class:e.className, text:e.textContent.trim().slice(0,80)}))')
        print(f"   数据区域数量: {len(data_regions)}")
        for d in data_regions[:20]:
            print(f"     - [{d['tag']}] .{d['class'][:50]} = {d['text'][:60]}")
        (OUTPUT_DIR / '02_data_regions.json').write_text(json.dumps(data_regions, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # 查找所有链接
        links = page.eval_on_selector_all('a[href]',
            'els=>els.map(e=>({text:e.textContent.trim().slice(0,60),href:e.href}))')
        print(f"\n   链接数量: {len(links)}")
        for link in links[:30]:
            print(f"     - {link['text'][:40]} -> {link['href'][:80]}")
        (OUTPUT_DIR / '02_links.json').write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # 查找 table
        tables = page.eval_on_selector_all('table',
            'els=>els.map((t,i)=>({index:i, rows:t.rows.length, text:t.textContent.trim().slice(0,200)}))')
        print(f"\n   表格数量: {len(tables)}")
        for t in tables[:5]:
            print(f"     - 表格 {t['index']}: {t['rows']} 行")
        
        # 3. 访问自然关键词页面
        print(f"\n3️⃣ 访问自然关键词页面...")
        organic_url = f'{SEMRUSH_BASE}/analytics/organic/positions/?searchType=domain&q={test_domain}&db=us'
        page.goto(organic_url, wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        page.screenshot(path=str(OUTPUT_DIR / '03_organic_keywords.png'), full_page=True)
        (OUTPUT_DIR / '03_organic_keywords.html').write_text(page.content(), encoding='utf-8')
        
        organic_text = page.inner_text('body')[:2000] if page.locator('body').count() > 0 else ''
        (OUTPUT_DIR / '03_organic_keywords_text.txt').write_text(organic_text, encoding='utf-8')
        print(f"   当前 URL: {page.url}")
        print(f"   页面文本前200字:\n   {organic_text[:200]}")
        
        # 查找 Export 按钮
        export_selectors = ['button:has-text("Export")', 'button:has-text("导出")', '[class*="export"]', 'a:has-text("Export")']
        for sel in export_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2000):
                    print(f"   ✅ 找到 Export 按钮: {sel}")
                    break
            except:
                pass
        
        # 4. 访问付费关键词页面
        print(f"\n4️⃣ 访问付费关键词页面...")
        paid_url = f'{SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q={test_domain}&db=us'
        page.goto(paid_url, wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        page.screenshot(path=str(OUTPUT_DIR / '04_paid_keywords.png'), full_page=True)
        (OUTPUT_DIR / '04_paid_keywords.html').write_text(page.content(), encoding='utf-8')
        
        paid_text = page.inner_text('body')[:2000] if page.locator('body').count() > 0 else ''
        (OUTPUT_DIR / '04_paid_keywords_text.txt').write_text(paid_text, encoding='utf-8')
        print(f"   当前 URL: {page.url}")
        print(f"   页面文本前200字:\n   {paid_text[:200]}")
        
        # 5. 访问广告文案页面
        print(f"\n5️⃣ 访问广告文案页面...")
        ad_url = f'{SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q={test_domain}&db=us'
        page.goto(ad_url, wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        page.screenshot(path=str(OUTPUT_DIR / '05_ad_copies.png'), full_page=True)
        (OUTPUT_DIR / '05_ad_copies.html').write_text(page.content(), encoding='utf-8')
        
        ad_text = page.inner_text('body')[:2000] if page.locator('body').count() > 0 else ''
        (OUTPUT_DIR / '05_ad_copies_text.txt').write_text(ad_text, encoding='utf-8')
        print(f"   当前 URL: {page.url}")
        print(f"   页面文本前200字:\n   {ad_text[:200]}")
        
        page.close()
        
        print("\n" + "=" * 60)
        print("✅ SEMrush 界面探查完成！")
        print(f"📁 结果保存在: {OUTPUT_DIR}")
        print("=" * 60)
        print(f"""
关键发现:
- SEMrush 实际域名: {SEMRUSH_BASE}
- URL 格式: {SEMRUSH_BASE}/analytics/overview/?searchType=domain&q=DOMAIN&db=us
- 自然关键词: {SEMRUSH_BASE}/analytics/organic/positions/?searchType=domain&q=DOMAIN&db=us
- 付费关键词: {SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q=DOMAIN&db=us
- 广告文案: {SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q=DOMAIN&db=us
""")


if __name__ == '__main__':
    main()
