"""
快速测试多个 ASIN，诊断是真 404 还是访问/语言问题
"""
import time
from playwright.sync_api import sync_playwright

# 待测试的 ASIN 列表（从之前的空数据中取）
TEST_ASINS = [
    "B087TJZ4SS",
    "B0CWLFRP8C",
    "B0CRHYTMQM",
    "B0D16RKN1Q",
    "B09G1Z83GM",   # 已知正常的
]

CDPUrl = "http://localhost:9222"

def test_asin(page, asin):
    url = f"https://www.amazon.com/dp/{asin}"
    print(f"\n--- ASIN: {asin} ---")
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(3)

        real_url = page.url
        title = page.title()
        print(f"  URL    : {real_url[:100]}")
        print(f"  Title  : {title[:80]}")

        # 检查各种状态
        if 'captcha' in real_url.lower():
            print(f"  状态   : ⚠️ 验证码页面")
            return "CAPTCHA"
        if 'signin' in real_url.lower():
            print(f"  状态   : ⚠️ 登录页面")
            return "SIGNIN"
        if 'page not found' in title.lower():
            print(f"  状态   : ❌ 真的 404/下架")
            return "404"

        # 检查是否有价格/标题
        h1 = None
        for sel in ['#productTitle', 'h1', '.product-title']:
            try:
                h1 = page.locator(sel).first.text_content(timeout=2000)
                if h1 and h1.strip():
                    h1 = h1.strip()[:80]
                    break
            except:
                pass

        price = None
        for sel in ['.a-price .a-offscreen', '#priceblock_ourprice', '.a-price-whole']:
            try:
                price = page.locator(sel).first.text_content(timeout=2000)
                if price and price.strip():
                    price = price.strip()[:20]
                    break
            except:
                pass

        # 检查页面语言
        lang = page.evaluate("() => document.documentElement.lang || 'unknown'")

        print(f"  语言   : {lang}")
        print(f"  标题   : {h1 or '(空)'}")
        print(f"  价格   : {price or '(空)'}")

        if h1:
            print(f"  状态   : ✅ 正常商品页")
            return "OK"
        else:
            # 截图看看
            page.screenshot(path=f"test_{asin}.png")
            print(f"  状态   : ⚠️ 页面加载但无标题，已截图 test_{asin}.png")
            return "EMPTY"

    except Exception as e:
        print(f"  状态   : ❌ 异常: {e}")
        return "ERROR"


with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(CDPUrl)
    ctx = browser.contexts[0]
    page = ctx.new_page()

    results = {}
    for asin in TEST_ASINS:
        r = test_asin(page, asin)
        results[asin] = r
        time.sleep(2)

    page.close()
    browser.close()

print("\n\n========== 汇总 ==========")
for asin, r in results.items():
    icon = {"OK": "✅", "404": "❌", "CAPTCHA": "⚠️", "SIGNIN": "⚠️", "EMPTY": "🔸", "ERROR": "💥"}.get(r, "?")
    print(f"  {icon} {asin}: {r}")
