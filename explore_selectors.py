# -*- coding: utf-8 -*-
"""
SEMrush 选择器探测 — 提取精确的 CSS 选择器
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
SEMRUSH_BASE = 'https://www.trends.fast.wmxpro.com'
OUTPUT_DIR = Path('output/semrush_selectors')
DOMAIN = 'amazon.com'


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]
        page = context.new_page()
        
        # ========== 1. Domain Overview ==========
        print("=" * 60)
        print("1️⃣ Domain Overview 选择器探测")
        print("=" * 60)
        
        page.goto(f'{SEMRUSH_BASE}/analytics/overview/?searchType=domain&q={DOMAIN}&db=us', 
                  wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        # 用 JS 提取所有含有数值的摘要卡片
        overview_data = page.evaluate('''() => {
            const results = {};
            
            // 查找所有带有 Organic Traffic, Organic Keywords 等标签的元素
            const allLabels = document.querySelectorAll('label, span, div, p');
            const targetLabels = [
                'Authority Score', 'Organic Traffic', 'Paid Traffic', 'Ref.Domains',
                'Organic Keywords', 'Paid Keywords', 'Backlinks', 'Traffic Share'
            ];
            
            targetLabels.forEach(label => {
                const elements = [...allLabels].filter(el => el.textContent.trim() === label);
                elements.forEach(el => {
                    // 向上查找包含数值的容器
                    let container = el.closest('[class*="widget"]') || el.parentElement?.parentElement;
                    if (container) {
                        const text = container.textContent.replace(/\\s+/g, ' ').trim().slice(0, 200);
                        // 查找所有数值元素
                        const valueEls = container.querySelectorAll('[class*="value"], [class*="num"], [class*="metric"], [class*="count"], span, p, div');
                        const values = [...valueEls]
                            .map(v => v.textContent.trim())
                            .filter(t => /^(\\d|\\$|%|[\d,.]+[KMB]?%?)/.test(t) && t.length < 30)
                            .slice(0, 3);
                        
                        if (!results[label]) results[label] = [];
                        results[label].push({
                            tag: el.tagName,
                            class: el.className.slice(0, 60),
                            containerClass: container?.className?.slice(0, 60) || '',
                            values: values
                        });
                    }
                });
            });
            
            return results;
        }''')
        
        print(json.dumps(overview_data, indent=2, ensure_ascii=False))
        (OUTPUT_DIR / '01_overview_selectors.json').write_text(
            json.dumps(overview_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # ========== 2. Organic Keywords ==========
        print("\n" + "=" * 60)
        print("2️⃣ Organic Keywords 选择器探测")
        print("=" * 60)
        
        page.goto(f'{SEMRUSH_BASE}/analytics/organic/positions/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        # 提取表格数据
        organic_data = page.evaluate('''() => {
            const results = { tables: [], exportBtn: null, columns: [] };
            
            // 查找 Export 按钮
            const exportBtns = document.querySelectorAll('button, a');
            exportBtns.forEach(btn => {
                if (btn.textContent.trim().includes('Export')) {
                    results.exportBtn = {
                        tag: btn.tagName,
                        text: btn.textContent.trim(),
                        class: btn.className.slice(0, 80)
                    };
                }
            });
            
            // 查找表格
            const tables = document.querySelectorAll('table, [class*="table"], [class*="grid"], [role="grid"]');
            tables.forEach((table, i) => {
                const rows = table.querySelectorAll('tr, [class*="row"], [role="row"]');
                const tableData = [];
                rows.forEach((row, ri) => {
                    if (ri < 6) {  // 只取前 6 行
                        const cells = row.querySelectorAll('td, th, [class*="cell"], [role="cell"], [role="columnheader"]');
                        const rowData = [];
                        cells.forEach(cell => {
                            rowData.push(cell.textContent.trim().slice(0, 50));
                        });
                        if (rowData.length > 0) tableData.push(rowData);
                    }
                });
                if (tableData.length > 0) {
                    results.tables.push({
                        index: i,
                        tag: table.tagName,
                        class: table.className.slice(0, 80),
                        rows: tableData
                    });
                }
            });
            
            // 查找分页信息
            const pagination = document.querySelector('[class*="pagin"], [class*="pager"], [class*="total"]');
            if (pagination) {
                results.pagination = pagination.textContent.trim().slice(0, 100);
            }
            
            return results;
        }''')
        
        print(json.dumps(organic_data, indent=2, ensure_ascii=False))
        (OUTPUT_DIR / '02_organic_selectors.json').write_text(
            json.dumps(organic_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # ========== 3. Paid Keywords ==========
        print("\n" + "=" * 60)
        print("3️⃣ Paid Keywords 选择器探测")
        print("=" * 60)
        
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        paid_data = page.evaluate('''() => {
            const results = { tables: [], exportBtn: null };
            
            // Export 按钮
            const exportBtns = document.querySelectorAll('button, a');
            exportBtns.forEach(btn => {
                if (btn.textContent.trim().includes('Export')) {
                    results.exportBtn = {
                        tag: btn.tagName,
                        text: btn.textContent.trim(),
                        class: btn.className.slice(0, 80)
                    };
                }
            });
            
            // 表格
            const tables = document.querySelectorAll('table, [class*="table"], [class*="grid"], [role="grid"]');
            tables.forEach((table, i) => {
                const rows = table.querySelectorAll('tr, [class*="row"], [role="row"]');
                const tableData = [];
                rows.forEach((row, ri) => {
                    if (ri < 6) {
                        const cells = row.querySelectorAll('td, th, [class*="cell"], [role="cell"], [role="columnheader"]');
                        const rowData = [];
                        cells.forEach(cell => {
                            rowData.push(cell.textContent.trim().slice(0, 50));
                        });
                        if (rowData.length > 0) tableData.push(rowData);
                    }
                });
                if (tableData.length > 0) {
                    results.tables.push({
                        index: i,
                        tag: table.tagName,
                        class: table.className.slice(0, 80),
                        rows: tableData
                    });
                }
            });
            
            return results;
        }''')
        
        print(json.dumps(paid_data, indent=2, ensure_ascii=False))
        (OUTPUT_DIR / '03_paid_selectors.json').write_text(
            json.dumps(paid_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # ========== 4. Ad Copies ==========
        print("\n" + "=" * 60)
        print("4️⃣ Ad Copies (Text Ads) 选择器探测")
        print("=" * 60)
        
        page.goto(f'{SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='networkidle', timeout=60000)
        time.sleep(5)
        
        ad_data = page.evaluate('''() => {
            const results = { tables: [], exportBtn: null, pageText: '' };
            
            // Export 按钮
            const exportBtns = document.querySelectorAll('button, a');
            exportBtns.forEach(btn => {
                if (btn.textContent.trim().includes('Export')) {
                    results.exportBtn = {
                        tag: btn.tagName,
                        text: btn.textContent.trim(),
                        class: btn.className.slice(0, 80)
                    };
                }
            });
            
            // 表格
            const tables = document.querySelectorAll('table, [class*="table"], [class*="grid"], [role="grid"]');
            tables.forEach((table, i) => {
                const rows = table.querySelectorAll('tr, [class*="row"], [role="row"]');
                const tableData = [];
                rows.forEach((row, ri) => {
                    if (ri < 6) {
                        const cells = row.querySelectorAll('td, th, [class*="cell"], [role="cell"], [role="columnheader"]');
                        const rowData = [];
                        cells.forEach(cell => {
                            rowData.push(cell.textContent.trim().slice(0, 80));
                        });
                        if (rowData.length > 0) tableData.push(rowData);
                    }
                });
                if (tableData.length > 0) {
                    results.tables.push({
                        index: i,
                        tag: table.tagName,
                        class: table.className.slice(0, 80),
                        rows: tableData
                    });
                }
            });
            
            // 页面文本
            results.pageText = document.body.innerText.slice(0, 3000);
            
            return results;
        }''')
        
        print(json.dumps(ad_data, indent=2, ensure_ascii=False)[:5000])
        (OUTPUT_DIR / '04_adcopies_selectors.json').write_text(
            json.dumps(ad_data, indent=2, ensure_ascii=False), encoding='utf-8')
        
        page.close()
        
        print("\n" + "=" * 60)
        print("✅ 选择器探测完成！")
        print(f"📁 结果保存在: {OUTPUT_DIR}")
        print("=" * 60)


if __name__ == '__main__':
    main()
