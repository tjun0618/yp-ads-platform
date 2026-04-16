# -*- coding: utf-8 -*-
"""
SEMrush DOM 深度分析 — 找到表格行的真实 DOM 结构
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
DOMAIN = 'amazon.com'


def main():
    OUTPUT_DIR = Path('output/semrush_dom_analysis')
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
        
        # ===== Organic Keywords 页面 =====
        print("=" * 60)
        print("分析 Organic Keywords DOM 结构")
        print("=" * 60)
        
        page.goto(f'https://zh.trends.fast.wmxpro.com/analytics/organic/positions/?searchType=domain&q={DOMAIN}&db=us',
                  wait_until='networkidle', timeout=60000)
        time.sleep(10)  # 长等待
        
        # 深度 DOM 分析
        dom_info = page.evaluate('''() => {
            const info = {};
            
            // 1. 找所有包含 "amazon" 文字的行级元素
            const allElements = document.querySelectorAll('div, span, tr, td, li, p');
            const keywordRows = [];
            
            for (const el of allElements) {
                const text = el.textContent.trim();
                // 查找包含关键词排名特征的元素
                if (/^\\d+$/.test(text) && parseInt(text) > 0 && parseInt(text) < 1000000) {
                    const parent = el.parentElement;
                    const grandparent = parent?.parentElement;
                    const siblings = parent ? [...parent.children].map(c => c.textContent.trim().slice(0, 30)) : [];
                    
                    if (siblings.length >= 3) {
                        keywordRows.push({
                            tag: el.tagName,
                            class: el.className.slice(0, 50),
                            text: text,
                            parentTag: parent?.tagName,
                            parentClass: parent?.className.slice(0, 50),
                            siblingCount: siblings.length,
                            siblings: siblings.slice(0, 8)
                        });
                    }
                }
            }
            
            info.keywordRows = keywordRows.slice(0, 10);
            
            // 2. 查找所有可能的数据行容器
            const rowContainers = document.querySelectorAll('[class*="row"], [class*="Row"], [class*="item"], [class*="Item"]');
            info.rowContainerCount = rowContainers.length;
            info.rowContainerClasses = [...new Set([...rowContainers].map(el => el.className.slice(0, 60)))].slice(0, 15);
            
            // 3. 查找所有带有 data- 属性的元素（可能包含数据）
            const dataElements = document.querySelectorAll('[data-keyword], [data-position], [data-volume], [data-url], [data-row]');
            info.dataElements = [...dataElements].map(el => ({
                tag: el.tagName,
                attrs: [...el.attributes].map(a => `${a.name}=${a.value.slice(0,30)}`),
                text: el.textContent.trim().slice(0, 50)
            })).slice(0, 10);
            
            // 4. 查找所有 SVG/Canvas 图表附近的数据
            const tables = document.querySelectorAll('table');
            info.tableCount = tables.length;
            info.tableInfo = [...tables].map((t, i) => ({
                index: i,
                rows: t.querySelectorAll('tr').length,
                text: t.textContent.trim().slice(0, 200)
            })).slice(0, 5);
            
            // 5. 查找所有 role 属性
            const roleElements = document.querySelectorAll('[role]');
            const roleSet = new Set([...roleElements].map(el => el.getAttribute('role')));
            info.roles = [...roleSet].sort();
            
            // 6. 尝试查找特定内容："amazon" 关键词
            // 在 body 全文本中搜索关键词模式
            const bodyText = document.body.innerText;
            const kwMatch = bodyText.match(/amazon[^\\n]{0,100}/gi);
            info.amazonMentions = kwMatch ? kwMatch.slice(0, 10) : [];
            
            // 7. 检查是否有虚拟化列表（React/Redux 组件）
            const virtualLists = document.querySelectorAll('[class*="virtual"], [class*="Virtual"], [class*="scroll"]');
            info.virtualListCount = virtualLists.length;
            
            return info;
        }''')
        
        print(json.dumps(dom_info, indent=2, ensure_ascii=False))
        (OUTPUT_DIR / 'organic_dom.json').write_text(
            json.dumps(dom_info, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # ===== 截图检查 =====
        page.screenshot(path=str(OUTPUT_DIR / 'organic_screenshot.png'), full_page=True)
        
        # ===== 查看 HTML 源码（缩小范围） =====
        html_source = page.content()
        
        # 查找包含数据模式的 HTML 片段
        print("\n\n--- HTML 数据模式搜索 ---")
        import re
        
        # 查找可能的表格行
        # SEMrush 使用 React，可能以 JSON 形式嵌入数据
        json_patterns = re.findall(r'"keyword"\s*:\s*"([^"]{5,50})"', html_source)
        print(f"JSON keyword 模式: {len(json_patterns)} 个")
        for p in json_patterns[:10]:
            print(f"  {p}")
        
        # 查找 HTML 中的排名数字
        rank_patterns = re.findall(r'class="[^"]*">\s*(\d{1,3})\s*</(?:span|div|td)>', html_source)
        print(f"\n排名数字模式: {len(rank_patterns)} 个")
        for p in rank_patterns[:10]:
            print(f"  {p}")
        
        # 查找 __NEXT_DATA__ 或类似的全局数据
        next_data = re.findall(r'<script[^>]*>window\.__[A-Z_]+\s*=\s*(\{.{0,500})', html_source)
        if next_data:
            print(f"\n全局数据脚本: {len(next_data)} 个")
            for nd in next_data[:3]:
                print(f"  {nd[:200]}")
        
        # 保存截取的 HTML 片段（包含关键词表格区域）
        table_start = html_source.find('关键词')
        if table_start > 0:
            table_section = html_source[max(0, table_start-500):table_start+3000]
            (OUTPUT_DIR / 'organic_table_html.txt').write_text(table_section, encoding='utf-8')
            print(f"\n关键词区域 HTML 已保存")
        
        print(f"\n✅ DOM 分析完成: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
