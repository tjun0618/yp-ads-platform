"""
测试调试 Chrome 连接，并抓取一个有效 ASIN 的亚马逊商品详情
不做截图，直接测试 selector
用法: python test_chrome_connect.py
"""
import sys
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[ERROR] playwright 未安装")
    sys.exit(1)

TEST_ASIN = "B0BB81YX1V"
TEST_URL = "https://www.amazon.com/dp/B0BB81YX1V?maas=maas_adg_api_577128634505764562_static_12_113&ref_=aa_maas&tag=maas"

def main():
    print("=" * 60)
    print("Step 1: 连接调试 Chrome (localhost:9222)")
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            print("[OK] 成功连接 Chrome")
        except Exception as e:
            print(f"[FAIL] 无法连接: {e}")
            sys.exit(1)
        
        ctx = browser.contexts[0]
        page = ctx.new_page()
        print("[OK] 新标签页已创建")
        
        print(f"\nStep 2: 访问 tracking URL")
        try:
            page.goto(TEST_URL, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            landed_url = page.url
            print(f"[OK] 落地: {landed_url[:120]}")
        except Exception as e:
            print(f"[FAIL] goto 失败: {e}")
            page.close()
            sys.exit(1)
        
        if 'amazon.com' not in landed_url:
            print(f"[WARN] 未到达 Amazon: {landed_url}")
        else:
            print("[OK] 已在 Amazon 域名")
        
        # 添加英文参数
        if 'language=en_US' not in landed_url:
            en_url = (landed_url + '&language=en_US') if '?' in landed_url else (landed_url + '?language=en_US')
            try:
                page.goto(en_url, wait_until='domcontentloaded', timeout=30000)
                time.sleep(2)
                print(f"[OK] 英文页 URL: {page.url[:120]}")
            except Exception as e:
                print(f"[WARN] 英文页加载超时（尝试继续）: {e}")
        
        title = page.title()
        print(f"\n[PAGE TITLE] {title}")
        
        # 等待页面稳定
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except:
            pass
        
        print(f"\nStep 3: 测试 Selector")
        selectors = {
            "商品标题": "#productTitle",
            "品牌名": "#bylineInfo",
            "价格(旧)": "#priceblock_ourprice",
            "价格(新)": "#corePriceDisplay_desktop_feature_div .a-offscreen",
            "价格(通用)": ".a-price .a-offscreen",
            "Bullet points": "#feature-bullets ul li span.a-list-item",
            "评分": "#acrPopover",
            "评论数": "#acrCustomerReviewText",
            "库存": "#availability span",
            "描述": "#productDescription p",
            "Tech Specs": "#productDetails_techSpec_section_1 tr",
        }
        
        for name, sel in selectors.items():
            try:
                el = page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()[:100]
                    print(f"  [✓] {name}: {repr(text)}")
                else:
                    # 尝试所有匹配
                    els = page.query_selector_all(sel)
                    print(f"  [✗] {name}: NOT FOUND (query_all={len(els)})")
            except Exception as e:
                print(f"  [!] {name}: 出错 - {e}")
        
        # 输出页面 HTML 片段（帮助调试）
        print(f"\nStep 4: 检查页面 body 前200字符")
        try:
            body_text = page.inner_text("body")
            print(body_text[:300])
        except Exception as e:
            print(f"  [!] body 读取失败: {e}")
        
        page.close()
        print(f"\n[DONE]")

if __name__ == "__main__":
    main()
