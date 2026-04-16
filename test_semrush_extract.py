# -*- coding: utf-8 -*-
"""
SEMrush 完整数据提取 v6 — 修复域名输入 + 等待表格数据
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
OUTPUT_DIR = Path('output/semrush_v6')
DOMAIN = 'amazon.com'


def navigate_to_page(page, domain, path):
    """直接用 URL 导航（最可靠的方式），确保完整域名"""
    # 构建完整 URL（使用中文域名也无妨，SEMrush 能处理）
    url = f'https://zh.trends.fast.wmxpro.com{path}?searchType=domain&q={domain}&db=us'
    print(f"  导航: {url[:80]}...")
    page.goto(url, wait_until='networkidle', timeout=60000)
    
    # 等待 URL 稳定
    time.sleep(2)
    
    # 如果页面有搜索框，检查并补全域名
    try:
        for sel in ['input[class*="SBox"]', 'input[type="text"]']:
            inp = page.locator(sel).first
            if inp.is_visible(timeout=2000):
                val = inp.input_value()
                if val and domain not in val:
                    print(f"  搜索框值不完整: '{val}'，修正为: '{domain}'")
                    inp.fill(domain)
                    time.sleep(0.5)
                    page.keyboard.press('Enter')
                    time.sleep(6)
                break
    except:
        pass
    
    print(f"  最终 URL: {page.url[:100]}")
    time.sleep(5)
    return page.url


def extract_overview(page):
    """提取概览数据（中英文双适配）"""
    # 等待数据出现
    for label in ['Organic Traffic', '自然流量', '有机流量']:
        try:
            page.wait_for_selector(f'text={label}', timeout=8000)
            break
        except:
            continue
    
    return page.evaluate(r'''() => {
        const bodyText = document.body.innerText;
        const data = {};
        
        // 所有标签（中英文）
        const allTargets = [
            ['权威评分', 'Authority Score'],
            ['有机流量', 'Organic Traffic'],
            ['自然流量', 'Organic Traffic'],
            ['付费流量', 'Paid Traffic'],
            ['自然关键词', 'Organic Keywords'],
            ['付费关键词', 'Paid Keywords'],
            ['反向链接', 'Backlinks'],
            ['引荐域名', 'Ref.Domains'],
            ['流量份额', 'Traffic Share'],
        ];
        
        allTargets.forEach(([label, key]) => {
            const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escaped + '\\s+([\\d,.]+[KMB]?)(?:\\s+([+-]?\\d+\\.?\\d*%)?)?');
            const match = bodyText.match(regex);
            if (match) {
                data[key] = { value: match[1], change: match[2] || null };
            }
        });
        
        return data;
    }''')


def wait_and_extract_table(page, label_patterns, timeout=30):
    """等待表格数据加载并提取"""
    start = time.time()
    
    while time.time() - start < timeout:
        result = page.evaluate('''() => {
            const results = { headers: [], rows: [] };
            
            // role=grid
            document.querySelectorAll('[role="grid"]').forEach(grid => {
                const rows = grid.querySelectorAll('[role="row"]');
                rows.forEach((row, i) => {
                    const cells = [...row.querySelectorAll('[role="cell"], [role="columnheader"]')]
                        .map(c => c.textContent.trim());
                    if (i === 0 && cells.length > 2) results.headers = cells;
                    else if (cells.length > 3 && i > 0) results.rows.push(cells);
                });
            });
            
            // table
            if (results.rows.length === 0) {
                document.querySelectorAll('table').forEach(table => {
                    const trs = table.querySelectorAll('tr');
                    trs.forEach((tr, i) => {
                        const cells = [...tr.querySelectorAll('td, th')].map(c => c.textContent.trim());
                        if (i === 0 && cells.length > 2) results.headers = cells;
                        else if (cells.length > 3 && i > 0) results.rows.push(cells);
                    });
                });
            }
            
            return results;
        }''')
        
        if result['rows']:
            return result
        
        print(f"    等待数据加载... ({int(time.time()-start)}s)")
        time.sleep(3)
    
    return result


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]
        
        page = None
        for p in context.pages:
            if 'trends.fast' in p.url:
                page = p
                break
        if not page:
            page = context.new_page()
        
        results = {}
        
        # ========== 1. Domain Overview ==========
        print("=" * 60)
        print(f"1. Domain Overview: {DOMAIN}")
        print("=" * 60)
        
        navigate_to_page(page, DOMAIN, '/analytics/overview/')
        page.screenshot(path=str(OUTPUT_DIR / '01_overview.png'), full_page=True)
        
        results['overview'] = extract_overview(page)
        print(f"  概览数据:")
        for k, v in results['overview'].items():
            print(f"    {k}: {v['value']} {v.get('change','')}")
        
        # ========== 2. Organic Keywords ==========
        print(f"\n{'='*60}")
        print(f"2. Organic Keywords: {DOMAIN}")
        print("=" * 60)
        
        navigate_to_page(page, DOMAIN, '/analytics/organic/positions/')
        
        # 关键：等待关键词表格加载
        organic = wait_and_extract_table(page, ['Keyword', '关键词'], timeout=20)
        page.screenshot(path=str(OUTPUT_DIR / '02_organic.png'), full_page=True)
        
        print(f"  列: {organic['headers']}")
        print(f"  行数: {len(organic['rows'])}")
        for row in organic['rows'][:5]:
            print(f"    {row[:6]}")
        
        results['organic'] = {
            'headers': organic['headers'],
            'count': len(organic['rows']),
            'sample': organic['rows'][:10]
        }
        
        # ========== 3. Paid Keywords ==========
        print(f"\n{'='*60}")
        print(f"3. Paid Keywords: {DOMAIN}")
        print("=" * 60)
        
        navigate_to_page(page, DOMAIN, '/analytics/adwords/positions/')
        
        paid = wait_and_extract_table(page, ['Keyword', '关键词'], timeout=20)
        page.screenshot(path=str(OUTPUT_DIR / '03_paid.png'), full_page=True)
        
        print(f"  列: {paid['headers']}")
        print(f"  行数: {len(paid['rows'])}")
        for row in paid['rows'][:5]:
            print(f"    {row[:6]}")
        
        results['paid'] = {
            'headers': paid['headers'],
            'count': len(paid['rows']),
            'sample': paid['rows'][:10]
        }
        
        # ========== 4. Ad Copies ==========
        print(f"\n{'='*60}")
        print(f"4. Ad Copies: {DOMAIN}")
        print("=" * 60)
        
        navigate_to_page(page, DOMAIN, '/analytics/adwords/textads/')
        
        ads = wait_and_extract_table(page, ['Title', '标题', 'Headline'], timeout=20)
        page.screenshot(path=str(OUTPUT_DIR / '04_ads.png'), full_page=True)
        
        print(f"  列: {ads['headers']}")
        print(f"  行数: {len(ads['rows'])}")
        for row in ads['rows'][:5]:
            print(f"    {row[:6]}")
        
        results['ads'] = {
            'headers': ads['headers'],
            'count': len(ads['rows']),
            'sample': ads['rows'][:10]
        }
        
        # 保存
        (OUTPUT_DIR / 'full_result.json').write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f"\n{'='*60}")
        print(f"✅ 全部完成！{OUTPUT_DIR}/full_result.json")
        print("=" * 60)


if __name__ == '__main__':
    main()
