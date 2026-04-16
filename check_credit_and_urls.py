# -*- coding: utf-8 -*-
"""
快速检查：
1. 外贸侠今日积分余额
2. 验证 Paid Keywords / Ad Copies 的正确 URL
"""
import time
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://localhost:9222'
SEMRUSH_BASE = 'https://zh.trends.fast.wmxpro.com'
TEST_DOMAIN = 'rei.com'  # 中等规模的户外品牌，数据丰富，便于测试

def main():
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CHROME_WS)
        context = browser.contexts[0]

        # 找到或创建 SEMrush Tab
        page = None
        for p in context.pages:
            if 'trends.fast' in p.url or 'wmxpro' in p.url:
                page = p
                print(f"✅ 复用已有 Tab: {p.url}")
                break
        if not page:
            page = context.new_page()
            print("🆕 创建新 Tab")

        # ─── 1. 检查积分 ───────────────────────────────────────────
        print("\n" + "="*50)
        print("【1】检查今日积分余额")
        print("="*50)
        page.goto(f'https://zh.trends.fast.wmxpro.com/wmx/credit/daily/limit',
                  wait_until='domcontentloaded', timeout=15000)
        time.sleep(4)
        credit_text = page.evaluate("() => document.body.innerText")
        print(credit_text[:500])

        # ─── 2. 测试 Paid Keywords URL 变体 ──────────────────────
        print("\n" + "="*50)
        print("【2】测试 Paid Keywords URL 变体")
        print("="*50)
        
        paid_urls = [
            f'{SEMRUSH_BASE}/analytics/advertising/positions/?searchType=domain&q={TEST_DOMAIN}&db=us',
            f'{SEMRUSH_BASE}/analytics/adwords/positions/?searchType=domain&q={TEST_DOMAIN}&db=us',
            f'{SEMRUSH_BASE}/analytics/paid/positions/?searchType=domain&q={TEST_DOMAIN}&db=us',
        ]
        
        for url in paid_urls:
            print(f"\n→ 测试: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(6)
            
            final_url = page.url
            title = page.title()
            
            # 检查是否有关键词表格
            rows = page.evaluate("""() => {
                const grid = document.querySelector('[role="grid"]');
                if (!grid) return 0;
                return grid.querySelectorAll('[role="row"]').length;
            }""")
            
            # 检查页面文字中是否包含付费关键词相关内容
            body_snippet = page.evaluate("() => document.body.innerText.slice(0, 300)")
            
            print(f"   最终URL: {final_url}")
            print(f"   标题: {title}")
            print(f"   Grid行数: {rows}")
            print(f"   页面内容: {body_snippet[:200]}")
            
            if rows > 1:
                print(f"   ✅ 找到数据！{rows} 行")
                # 提取第一行数据
                sample = page.evaluate("""() => {
                    const grid = document.querySelector('[role="grid"]');
                    const rows = grid.querySelectorAll('[role="row"]');
                    if (rows.length < 2) return null;
                    const cells = rows[1].querySelectorAll('[role="gridcell"], [role="cell"]');
                    return [...cells].map(c => c.textContent.trim()).slice(0, 8);
                }""")
                print(f"   第一行: {sample}")
                break

        # ─── 3. 测试 Ad Copies URL 变体 ───────────────────────────
        print("\n" + "="*50)
        print("【3】测试 Ad Copies URL 变体")
        print("="*50)
        
        ad_urls = [
            f'{SEMRUSH_BASE}/analytics/advertising/textads/?searchType=domain&q={TEST_DOMAIN}&db=us',
            f'{SEMRUSH_BASE}/analytics/adwords/textads/?searchType=domain&q={TEST_DOMAIN}&db=us',
            f'{SEMRUSH_BASE}/analytics/advertising/ads/?searchType=domain&q={TEST_DOMAIN}&db=us',
        ]
        
        for url in ad_urls:
            print(f"\n→ 测试: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=20000)
            time.sleep(6)
            
            final_url = page.url
            rows = page.evaluate("""() => {
                const grid = document.querySelector('[role="grid"]');
                if (!grid) return 0;
                return grid.querySelectorAll('[role="row"]').length;
            }""")
            
            body_snippet = page.evaluate("() => document.body.innerText.slice(0, 300)")
            print(f"   最终URL: {final_url}")
            print(f"   Grid行数: {rows}")
            print(f"   页面内容: {body_snippet[:200]}")
            
            if rows > 1:
                print(f"   ✅ 找到广告文案数据！{rows} 行")
                sample = page.evaluate("""() => {
                    const grid = document.querySelector('[role="grid"]');
                    const rows = grid.querySelectorAll('[role="row"]');
                    if (rows.length < 2) return null;
                    const cells = rows[1].querySelectorAll('[role="gridcell"], [role="cell"]');
                    return [...cells].map(c => c.textContent.trim()).slice(0, 6);
                }""")
                print(f"   第一行: {sample}")
                break

        print("\n" + "="*50)
        print("检查完毕")
        print("="*50)

if __name__ == '__main__':
    main()
