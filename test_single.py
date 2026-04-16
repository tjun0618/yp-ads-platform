# -*- coding: utf-8 -*-
"""
SEMrush 单域名完整提取 — 直接复用已有 Tab
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
SEMRUSH_BASE = 'https://zh.trends.fast.wmxpro.com'
DOMAIN = 'amazon.com'


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]
        
        # 找到已有的 SEMrush Tab（关键！）
        page = None
        for p in context.pages:
            if 'trends.fast' in p.url:
                page = p
                print(f"✅ 复用 Tab: {p.url[:80]}")
                break
        
        if not page:
            print("❌ 未找到 SEMrush Tab，请先在浏览器中打开 SEMrush 页面")
            return
        
        results = {}
        
        # ===== 1. Overview =====
        print(f"\n[1/4] Overview: {DOMAIN}")
        page.goto(f'{SEMRUSH_BASE}/analytics/overview/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='commit', timeout=30000)
        time.sleep(10)
        
        # 修正搜索框
        try:
            for sel in ['input[class*="SBox"]', 'input[type="text"]']:
                inp = page.locator(sel).first
                if inp.is_visible(timeout=2000):
                    if DOMAIN not in (inp.input_value() or ''):
                        inp.fill(DOMAIN)
                        page.keyboard.press('Enter')
                        time.sleep(10)
                    break
        except:
            pass
        
        results['overview'] = page.evaluate(r'''() => {
            const t = document.body.innerText;
            const d = {};
            [['权威评分','authority_score'],['有机流量','organic_traffic'],['自然流量','organic_traffic'],['付费流量','paid_traffic'],['自然关键词','organic_keywords_count'],['付费关键词','paid_keywords_count'],['反向链接','backlinks'],['引荐域名','ref_domains'],['Authority Score','authority_score_en'],['Organic Traffic','organic_traffic_en'],['Paid Traffic','paid_traffic_en'],['Organic Keywords','organic_keywords_count_en'],['Paid Keywords','paid_keywords_count_en'],['Backlinks','backlinks_en']].forEach(([l,k])=>{
                const e=l.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
                const m=t.match(new RegExp(e+'\\s+([\\d,.]+[KMB]?)(?:\\s+([+-]?\\d+\\.?\\d*%)?)?'));
                if(m) d[k]={value:m[1],change:m[2]||null};
            });
            return d;
        }''')
        
        ov = results['overview']
        print(f"  Organic Traffic: {ov.get('organic_traffic',ov.get('organic_traffic_en',{})).get('value','-')}")
        print(f"  Paid Traffic: {ov.get('paid_traffic',ov.get('paid_traffic_en',{})).get('value','-')}")
        print(f"  Authority: {ov.get('authority_score',ov.get('authority_score_en',{})).get('value','-')}")
        
        # ===== 2. Organic Keywords =====
        print(f"\n[2/4] Organic Keywords: {DOMAIN}")
        page.goto(f'{SEMRUSH_BASE}/analytics/organic/positions/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='commit', timeout=30000)
        time.sleep(10)
        
        results['organic'] = page.evaluate('''() => {
            const kws = [];
            const grid = document.querySelector('[role="grid"]');
            if (!grid) return {count: 0, keywords: []};
            
            grid.querySelectorAll('[role="row"]').forEach((row, i) => {
                if (i === 0) return;
                const cells = [...row.querySelectorAll('[role="gridcell"]')].map(c=>c.textContent.trim());
                if (cells.length >= 7 && cells[1]) {
                    kws.push({keyword:cells[1], intent:cells[2], position:cells[3], traffic:cells[5], volume:cells[7]});
                }
            });
            return {count: kws.length, keywords: kws.slice(0, 20)};
        }''')
        
        print(f"  获取: {results['organic']['count']} 条")
        if results['organic']['keywords']:
            k = results['organic']['keywords'][0]
            print(f"  Top: {k['keyword']} (排名:{k['position']}, 流量:{k['traffic']})")
        
        # ===== 3. Paid Keywords =====
        print(f"\n[3/4] Paid Keywords: {DOMAIN}")
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='commit', timeout=30000)
        time.sleep(10)
        
        # 检查是否跳转到了 overview
        if 'overview' in page.url.lower() and 'adwords' not in page.url.lower():
            print("  ⚠️ 被重定向到 overview，尝试直接广告研究入口...")
            page.goto(f'{SEMRUSH_BASE}/advertising/research/positions.html?searchType=domain&q={DOMAIN}&db=us',
                      wait_until='commit', timeout=30000)
            time.sleep(10)
        
        # 如果还是搜索页面，点击分析
        page_text = page.inner_text('body')[:500]
        if '获取完整分析' in page_text or '分析竞争对手' in page_text:
            print("  需要点击分析按钮...")
            try:
                btn = page.locator('button:has-text("获取完整分析"), button:has-text("分析")').first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    time.sleep(10)
            except:
                pass
        
        results['paid'] = page.evaluate('''() => {
            const kws = [];
            const grid = document.querySelector('[role="grid"]');
            if (!grid) return {count: 0, keywords: []};
            
            grid.querySelectorAll('[role="row"]').forEach((row, i) => {
                if (i === 0) return;
                const cells = [...row.querySelectorAll('[role="gridcell"]')].map(c=>c.textContent.trim());
                if (cells.length >= 5 && cells[1]) {
                    kws.push({keyword:cells[1], position:cells[3], cpc:cells[4], traffic:cells[5]});
                }
            });
            return {count: kws.length, keywords: kws.slice(0, 20)};
        }''')
        
        print(f"  获取: {results['paid']['count']} 条")
        if results['paid']['keywords']:
            print(f"  Top: {results['paid']['keywords'][0]}")
        else:
            print(f"  当前 URL: {page.url[:80]}")
            print(f"  页面文本: {page.inner_text('body')[:200]}")
        
        # ===== 4. Ad Copies =====
        print(f"\n[4/4] Ad Copies: {DOMAIN}")
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='commit', timeout=30000)
        time.sleep(10)
        
        # 如果需要搜索
        page_text = page.inner_text('body')[:500]
        if '获取完整分析' in page_text or '广告研究' in page_text:
            try:
                btn = page.locator('button:has-text("获取完整分析"), button:has-text("分析")').first
                if btn.is_visible(timeout=3000):
                    btn.click()
                    time.sleep(10)
            except:
                pass
        
        results['ads'] = page.evaluate('''() => {
            const ads = [];
            const grid = document.querySelector('[role="grid"]');
            if (!grid) return {count: 0, ads: []};
            
            grid.querySelectorAll('[role="row"]').forEach((row, i) => {
                if (i === 0) return;
                const cells = [...row.querySelectorAll('[role="gridcell"]')].map(c=>c.textContent.trim());
                if (cells.length >= 3) {
                    ads.push({keyword:cells[1], title:cells[2], description:cells[3], url:cells[4]});
                }
            });
            return {count: ads.length, ads: ads.slice(0, 20)};
        }''')
        
        print(f"  获取: {results['ads']['count']} 条")
        if results['ads']['ads']:
            print(f"  Top: {results['ads']['ads'][0]}")
        else:
            print(f"  当前 URL: {page.url[:80]}")
        
        # 保存
        out = Path('output/semrush_single')
        out.mkdir(parents=True, exist_ok=True)
        (out / 'result.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
        
        print(f"\n{'='*60}")
        print(f"✅ 完成! {out}/result.json")
        print("=" * 60)


if __name__ == '__main__':
    main()
