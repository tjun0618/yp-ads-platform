# -*- coding: utf-8 -*-
"""
外贸侠 SEMrush 界面探查脚本 v2
使用 Playwright CDP 连接已登录的 Chrome，复用已有 context
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME_WS = 'http://127.0.0.1:9222'
WAIMAOXIA_URL = 'https://www.waimaoxia.net'
OUTPUT_DIR = Path('output/waimaoxia_explore')


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🔍 外贸侠 SEMrush 界面探查 v2")
    print("=" * 60)
    
    try:
        with sync_playwright() as pw:
            # 连接调试 Chrome
            browser = pw.chromium.connect_over_cdp(CHROME_WS)
            
            # 获取已有的 context（关键：复用已登录的 session）
            if not browser.contexts:
                print("❌ 没有 browser context，请确认 Chrome 已打开并有页面")
                return
            context = browser.contexts[0]
            
            # 列出当前所有页面
            pages = context.pages
            print(f"\n📋 当前有 {len(pages)} 个页面:")
            for i, p in enumerate(pages):
                print(f"  [{i}] {p.url[:80]}")
            
            # 找到或创建一个页面
            target_page = None
            for p in pages:
                if 'waimaoxia' in p.url or 'semrush' in p.url:
                    target_page = p
                    print(f"\n✅ 复用已有页面: {p.url[:80]}")
                    break
            
            if not target_page:
                # 在已有 context 中创建新 page（共享 cookies）
                target_page = context.new_page()
                print(f"\n✅ 在已有 context 中创建新 page（共享登录状态）")
            
            page = target_page
            
            # 1. 访问外贸侠首页
            print(f"\n1️⃣ 访问首页: {WAIMAOXIA_URL}")
            page.goto(WAIMAOXIA_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(4)
            
            # 保存截图
            page.screenshot(path=str(OUTPUT_DIR / 'v2_home.png'), full_page=True)
            (OUTPUT_DIR / 'v2_home.html').write_text(page.content(), encoding='utf-8')
            
            current_url = page.url
            print(f"   当前 URL: {current_url}")
            
            # 检查登录状态
            page_text = page.inner_text('body') if page.locator('body').count() > 0 else ''
            if '立即登录' in page_text and '个人中心' not in page_text:
                print("   ❌ 未检测到登录状态，页面仍显示'立即登录'")
                print("   可能需要先在浏览器中手动登录")
                # 保存页面文本
                (OUTPUT_DIR / 'v2_home_text.txt').write_text(page_text[:3000], encoding='utf-8')
                return
            else:
                print("   ✅ 已检测到登录状态")
            
            # 2. 收集页面信息
            print(f"\n2️⃣ 分析页面结构...")
            
            # 检查是否有 iframe
            iframes_info = page.eval_on_selector_all('iframe', 
                'els => els.map(f => ({src: f.src, id: f.id, class: f.className}))')
            print(f"   iframe 数量: {len(iframes_info)}")
            for iframe in iframes_info[:5]:
                print(f"     - src: {iframe['src'][:100]}")
            (OUTPUT_DIR / 'v2_iframes.json').write_text(json.dumps(iframes_info, indent=2), encoding='utf-8')
            
            # 收集所有链接
            links = page.eval_on_selector_all('a[href]', 
                'els=>els.map(e=>({text:e.textContent.trim().slice(0,60),href:e.href}))')
            print(f"   链接数量: {len(links)}")
            (OUTPUT_DIR / 'v2_links.json').write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding='utf-8')
            
            # 显示前 20 个链接
            for link in links[:20]:
                print(f"     - {link['text'][:40]} -> {link['href'][:80]}")
            
            # 3. 检测搜索框
            print(f"\n3️⃣ 检测搜索框...")
            search_info = page.eval_on_selector_all('input', 
                'els=>els.map(e=>({type:e.type,placeholder:e.placeholder,name:e.name,id:e.id,class:e.className}))')
            print(f"   input 数量: {len(search_info)}")
            for inp in search_info[:10]:
                print(f"     - type={inp['type']}, placeholder='{inp['placeholder']}', name='{inp['name']}', id='{inp['id']}'")
            (OUTPUT_DIR / 'v2_inputs.json').write_text(json.dumps(search_info, indent=2), encoding='utf-8')
            
            # 4. 点击"个人中心"或找到 SEMrush 入口
            print(f"\n4️⃣ 查找 SEMrush 功能入口...")
            
            # 尝试找到功能菜单
            menu_items = []
            for selector in ['.nav-font a', '.menu a', 'nav a', '[class*="menu"] a', '[class*="nav"] a']:
                try:
                    items = page.locator(selector).all()
                    for item in items:
                        text = item.text_content().strip()
                        href = item.get_attribute('href') or ''
                        if text and len(text) > 1 and len(text) < 30:
                            menu_items.append({'text': text, 'href': href, 'selector': selector})
                except:
                    pass
            
            # 去重
            seen = set()
            unique_items = []
            for item in menu_items:
                key = f"{item['text']}|{item['href']}"
                if key not in seen:
                    seen.add(key)
                    unique_items.append(item)
            
            print(f"   找到 {len(unique_items)} 个菜单项:")
            for item in unique_items[:30]:
                marker = ' ⭐' if 'semrush' in item['text'].lower() or 'semrush' in item['href'].lower() or '分析' in item['text'] or '流量' in item['text'] or 'analytics' in item['href'].lower() else ''
                print(f"     - {item['text'][:40]} -> {item['href'][:80]}{marker}")
            
            # 5. 如果有 SEMrush 链接，尝试访问
            print(f"\n5️⃣ 测试 SEMrush 功能页面...")
            
            semrush_links = [item for item in unique_items if 'semrush' in item['href'].lower() or 'analytics' in item['href'].lower()]
            
            if semrush_links:
                test_url = semrush_links[0]['href']
                if not test_url.startswith('http'):
                    test_url = WAIMAOXIA_URL + test_url
                print(f"   找到 SEMrush 链接: {test_url}")
                page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(4)
                page.screenshot(path=str(OUTPUT_DIR / 'v2_semrush_page.png'), full_page=True)
                (OUTPUT_DIR / 'v2_semrush_page.html').write_text(page.content(), encoding='utf-8')
                print(f"   已保存: v2_semrush_page.png")
                
                # 检查页面文本
                semrush_text = page.inner_text('body')[:1000] if page.locator('body').count() > 0 else ''
                (OUTPUT_DIR / 'v2_semrush_text.txt').write_text(semrush_text, encoding='utf-8')
                print(f"   页面文本前200字: {semrush_text[:200]}")
            else:
                # 尝试直接访问可能的 SEMrush URL
                test_urls = [
                    f'{WAIMAOXIA_URL}/semrush',
                    f'{WAIMAOXIA_URL}/tool/semrush',
                    f'{WAIMAOXIA_URL}/#/semrush',
                    f'{WAIMAOXIA_URL}/analytics/overview/?q=amazon.com&db=us',
                ]
                
                for url in test_urls:
                    try:
                        print(f"   尝试: {url}")
                        page.goto(url, wait_until='domcontentloaded', timeout=15000)
                        time.sleep(3)
                        page.screenshot(path=str(OUTPUT_DIR / f'v2_test_{url.split("/")[-1][:20]}.png'))
                        
                        test_text = page.inner_text('body')[:200] if page.locator('body').count() > 0 else ''
                        print(f"   页面文本: {test_text[:150]}")
                        print(f"   当前 URL: {page.url}")
                    except Exception as e:
                        print(f"   ❌ 失败: {e}")
            
            # 6. 查看页面完整文本
            print(f"\n6️⃣ 保存页面文本...")
            page.goto(WAIMAOXIA_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            full_text = page.inner_text('body') if page.locator('body').count() > 0 else ''
            (OUTPUT_DIR / 'v2_full_text.txt').write_text(full_text, encoding='utf-8')
            print(f"   页面文本长度: {len(full_text)} 字符")
            
            print("\n" + "=" * 60)
            print("✅ 探查完成")
            print(f"📁 结果保存在: {OUTPUT_DIR}")
            print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ 错误: {e}")


if __name__ == '__main__':
    main()
