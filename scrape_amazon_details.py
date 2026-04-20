# -*- coding: utf-8 -*-
"""
scrape_amazon_details.py
========================
从 yp_products 表中读取 amazon_url，通过 Playwright 连接已登录的 Chrome 调试实例，
抓取亚马逊商品详情（标题、价格、bullet points、描述、规格参数、评论等），
写入 amazon_product_details 表。

用法:
  python -X utf8 scrape_amazon_details.py              # 增量（只处理未抓取的 ASIN）
  python -X utf8 scrape_amazon_details.py --limit 50   # 只处理 50 条测试
  python -X utf8 scrape_amazon_details.py --asin B0CPW78492  # 单个 ASIN 测试
  python -X utf8 scrape_amazon_details.py --refetch     # 重新抓取所有（覆盖更新）
  python -X utf8 scrape_amazon_details.py --no-setup    # 跳过配送地址和语言设置，直接访问原始链接

前提条件:
  - 已启动调试模式 Chrome: chrome.exe --remote-debugging-port=9222
  - Chrome 中已打开过亚马逊页面
  - 默认会切换配送地址到中国并设置语言为英语（--no-setup 可跳过）
"""

import argparse
import json
import os
import re
import time
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ─── 配置 ───────────────────────────────────────────────────────────────────
DB_CONFIG = dict(
    host="localhost",
    user="root",
    password="admin",
    database="affiliate_marketing",
    charset="utf8mb4",
)
CHROME_WS = "http://127.0.0.1:9222"  # Chrome 调试端口（使用 127.0.0.1 避免 IPv6 问题）
CHROME_DEBUG_PORT = 9222
CHROME_USER_DATA = "C:\\Chrome_Debug"
PAGE_TIMEOUT = 25000  # ms，页面加载超时
NAV_DELAY = 2.5  # 秒，导航后等待
RETRY_LIMIT = 2  # 失败重试次数
BATCH_SIZE = 50  # 进度日志间隔
CN_ZIPCODE = "100000"  # 北京邮编，用于切换配送地址到中国

# ─── 控制文件路径 ──────────────────────────────────────────────────────────────
# 用 os.path.abspath 确保即使 __file__ 是相对路径也能得到正确绝对路径
_BASE_DIR = Path(os.path.abspath(__file__)).parent
STOP_FILE = _BASE_DIR / ".scrape_stop"  # 存在 → 优雅停止
PROGRESS_FILE = _BASE_DIR / ".scrape_progress"  # 实时写入进度（供 UI 读取）


def _start_chrome_debug():
    """启动 Chrome 调试模式"""
    import subprocess
    import time

    # Chrome 路径
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome_exe = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_exe = p
            break

    if not chrome_exe:
        print("[ERROR] 未找到 Chrome 浏览器")
        return False

    print(f"[INFO] 启动 Chrome 调试模式: {chrome_exe}")

    # 启动 Chrome
    subprocess.Popen(
        [
            chrome_exe,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            f"--user-data-dir={CHROME_USER_DATA}",
            "--no-first-run",
            "about:blank",
        ],
        shell=False,
    )

    # 等待 Chrome 启动
    print("[INFO] 等待 Chrome 启动...")
    for i in range(10):
        time.sleep(1)
        try:
            import urllib.request

            urllib.request.urlopen(
                f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=2
            )
            print(f"[OK] Chrome 调试模式已启动 (等待 {i + 1} 秒)")
            return True
        except:
            pass

    print("[ERROR] Chrome 调试模式启动超时")
    return False


def _check_chrome_debug() -> bool:
    """检查 Chrome 调试模式是否运行"""
    try:
        import urllib.request

        urllib.request.urlopen(
            f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=2
        )
        return True
    except:
        return False


def _should_stop() -> bool:
    """检查停止信号文件是否存在"""
    return STOP_FILE.exists()


def _write_progress(
    idx: int,
    total: int,
    success: int,
    fail: int,
    current_asin: str = "",
    status: str = "running",
):
    """把实时进度写入进度文件（JSON），供控制台 UI 读取"""
    try:
        data = {
            "idx": idx,
            "total": total,
            "success": success,
            "fail": fail,
            "current_asin": current_asin,
            "status": status,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        tmp = str(PROGRESS_FILE) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, str(PROGRESS_FILE))
    except Exception:
        pass


# ─── 一次性初始化：设置语言为英语 ──────────────────────
def setup_language_and_address(page):
    """
    启动时执行一次：检测语言，如果不是英语则设置为 en_US
    之后每个商品页面无需追加 ?language=en_US 参数。
    """

    # ── 检测并设置语言为英语 ────────────────────────────────────
    print("[setup] 检测语言设置...")
    PREF_URL = (
        "https://www.amazon.com/customer-preferences/edit"
        "?ie=UTF8&preferencesReturnUrl=%2F&ref_=topnav_lang_ais"
    )
    try:
        page.goto(PREF_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
        time.sleep(2)

        # 找 en_US 单选按钮，检查是否已选中
        en_radio_checked = page.evaluate("""
            () => {
                for (const radio of document.querySelectorAll('input[type="radio"]')) {
                    if (radio.value === 'en_US') return radio.checked;
                }
                return null;
            }
        """)

        if en_radio_checked is None:
            print("[setup] 未找到 en_US 单选按钮，跳过语言设置")
            return
        elif en_radio_checked:
            print("[setup] 语言已是英语（en_US），无需设置")
            return
        else:
            # 选中英语
            print("[setup] 语言不是英语，正在设置为 en_US...")
            page.evaluate("""
                () => {
                    for (const radio of document.querySelectorAll('input[type="radio"]')) {
                        if (radio.value === 'en_US') { radio.click(); break; }
                    }
                }
            """)
            time.sleep(1)
            print("[setup] 已选中英语（en_US）")

        # 点击 Save Changes
        for save_sel in [
            "#icp-save-button input",
            "#icp-save-button",
            "#icp-btn-save input",
            '.a-button-primary input[type="submit"]',
        ]:
            try:
                page.locator(save_sel).first.click(timeout=3000)
                time.sleep(3)
                print(f"[setup] Save Changes 成功")
                break
            except Exception:
                pass

    except Exception as e:
        print(f"[setup] 语言设置失败（继续）: {e}")

    print("[setup] 初始化完成，开始采集商品...\n")


# ─── 数据抓取逻辑 ─────────────────────────────────────────────────────────────
def scrape_product(page, amazon_url: str, asin: str) -> dict:
    """
    访问商品页面（可能是 YP tracking_url，会重定向到 Amazon），抓取所有详情。
    返回 dict，可直接 INSERT 到 amazon_product_details。
    """
    # Step 1: 访问页面（可能是 YP tracking_url，会自动重定向到 Amazon）
    print(f"  访问: {amazon_url[:60]}...")
    page.goto(amazon_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT)
    time.sleep(3)

    # Step 2: 检查是否在 YP 平台页面，尝试触发跳转
    landed_url = page.url
    if "yeahpromos.com" in landed_url or "yp" in landed_url.lower():
        print(f"  在 YP 平台页面，等待自动跳转...")
        # 先等待页面可能的服务端重定向或 meta refresh
        time.sleep(5)
        landed_url = page.url
        if "amazon.com" not in landed_url:
            # 尝试查找并点击所有可能的跳转元素
            selectors_to_try = [
                'a[href*="amazon"]',
                'a[href*="amzn"]',
                "button.amazon-link",
                ".product-link a",
                "a.btn-primary",
                "#redirect-btn",
                'a[target="_blank"]',
                "a.visit-product",
                "a.go-to-store",
            ]
            for sel in selectors_to_try:
                try:
                    btn = page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        href = btn.get_attribute("href") or ""
                        print(f"  找到跳转元素: {sel} href={href[:60]}")
                        # 如果 href 包含 amazon，直接导航过去
                        if "amazon.com" in href or "amzn.to" in href:
                            page.goto(
                                href,
                                wait_until="domcontentloaded",
                                timeout=PAGE_TIMEOUT,
                            )
                            time.sleep(3)
                            break
                        else:
                            btn.click(timeout=3000)
                            time.sleep(5)
                            break
                except:
                    pass

            # 检查是否有新标签页被打开（有些跳转会开新窗口）
            landed_url = page.url
            if "amazon.com" not in landed_url:
                try:
                    context = page.context
                    pages = context.pages
                    for p in pages:
                        p_url = p.url
                        if "amazon.com" in p_url:
                            print(f"  检测到新标签页: {p_url[:60]}")
                            page = p
                            break
                except:
                    pass

        # 如果仍然在 YP 页面，尝试从页面 HTML 提取 Amazon 链接
        landed_url = page.url
        if "amazon.com" not in landed_url:
            print(f"  未自动跳转，尝试从页面提取 Amazon 链接...")
            try:
                page_content = page.content()
                # 查找包含 /dp/ 或 /gp/product/ 的 Amazon 链接
                amazon_links = re.findall(
                    r'https?://[^\s"\'<>]*amazon\.[^\s"\'<>]*/(?:dp|gp/product|product)/[A-Z0-9]{10}',
                    page_content,
                )
                if amazon_links:
                    direct_url = amazon_links[0]
                    print(f"  提取到 Amazon 链接: {direct_url[:80]}")
                    page.goto(
                        direct_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT
                    )
                    time.sleep(3)
                else:
                    # 用 ASIN 拼接 Amazon 链接
                    print(f"  页面未找到 Amazon 链接，用 ASIN 构造: {asin}")
                    page.goto(
                        f"https://www.amazon.com/dp/{asin}",
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT,
                    )
                    time.sleep(3)
            except Exception as e:
                print(f"  提取链接失败，回退到 ASIN 直连: {e}")
                page.goto(
                    f"https://www.amazon.com/dp/{asin}",
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )
                time.sleep(3)

        # 最后一次等待跳转完成
        for i in range(15):
            landed_url = page.url
            if "amazon.com" in landed_url:
                print(f"  已到达 Amazon: {landed_url[:80]}")
                break
            print(f"  等待就绪... ({i + 1}/15) 当前: {landed_url[:50]}")
            time.sleep(3)

    # Step 3: 确认已在亚马逊域名
    landed_url = page.url
    if "amazon.com" not in landed_url:
        raise Exception(f"跳转后不在亚马逊域名: {landed_url[:80]}")

    # Step 3b: 检查验证码/登录 — 如果是登录页，尝试提取 return_to 中的实际商品链接
    if "signin" in landed_url.lower():
        # 从 URL 中提取 openid.return_to 参数
        return_match = re.search(r"openid\.return_to=([^&]+)", landed_url)
        if return_match:
            return_url = return_match.group(1)
            # URL decode
            from urllib.parse import unquote

            return_url = unquote(return_url)
            print(f"  登录页 return_to: {return_url[:100]}")
            # 如果 return_to 指向商品页，直接导航过去
            if "/dp/" in return_url or "/gp/product/" in return_url:
                print(f"  从登录页提取到商品链接，直接导航...")
                page.goto(
                    return_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT
                )
                time.sleep(3)
                landed_url = page.url
            else:
                # return_to 不是商品页，用 ASIN 直连
                print(f"  return_to 非商品页，用 ASIN 直连: {asin}")
                page.goto(
                    f"https://www.amazon.com/dp/{asin}",
                    wait_until="domcontentloaded",
                    timeout=PAGE_TIMEOUT,
                )
                time.sleep(3)
                landed_url = page.url
        else:
            # 登录页没有 return_to，用 ASIN 直连
            print(f"  登录页无 return_to，用 ASIN 直连: {asin}")
            page.goto(
                f"https://www.amazon.com/dp/{asin}",
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT,
            )
            time.sleep(3)
            landed_url = page.url

    # Step 3c: 检查验证码
    if "captcha" in page.url.lower():
        raise Exception(f"页面跳转到验证码页: {page.url[:80]}")

    # Step 4: 检查页面是否是 404 / Page Not Found（商品已下架）
    try:
        page_title = page.title()
        if "page not found" in page_title.lower() or "sorry" in page_title.lower():
            raise Exception(f"商品页面404/已下架: title='{page_title}'")
    except Exception as e:
        if "商品页面404" in str(e):
            raise
        pass  # title() 本身失败则忽略

    data = {"asin": asin, "amazon_url": amazon_url}

    # ── 标题 ──────────────────────────────────────────────────────────
    for sel in [
        "#productTitle",
        "h1.a-size-large",
        "h1#title",
        ".product-title-word-break",
    ]:
        try:
            title = page.locator(sel).first.text_content(timeout=3000)
            if title and title.strip():
                data["title"] = title.strip()
                break
        except Exception:
            pass

    # ── 品牌 ──────────────────────────────────────────────────────────
    for sel in ["#bylineInfo", "a#bylineInfo", "tr.po-brand td.a-span9 span"]:
        try:
            brand_raw = page.locator(sel).first.text_content(timeout=3000)
            if brand_raw:
                brand = re.sub(
                    r"^(Brand:|Visit the|Store|\s)+", "", brand_raw, flags=re.I
                ).strip()
                brand = re.sub(r"\s+Store$", "", brand, flags=re.I).strip()
                data["brand"] = brand
                break
        except Exception:
            pass

    # ── 价格 ──────────────────────────────────────────────────────────
    # 优先取 apex-price-to-pay-value（当前实付价），其次 .a-offscreen
    for sel in [
        ".a-price.apex-price-to-pay-value .a-offscreen",
        ".a-price.aok-align-center .a-offscreen",
        "#corePrice_feature_div .a-offscreen",
        "#corePriceDisplay_desktop_feature_div .a-offscreen",
        "#apex_desktop .a-price:first-child .a-offscreen",
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
    ]:
        try:
            price_els = page.locator(sel).all()
            for el in price_els:
                p = el.text_content(timeout=2000)
                if p and "$" in p and len(p.strip()) < 20:
                    data["price"] = p.strip()
                    break
            if data.get("price"):
                break
        except Exception:
            pass

    # 原价（划线价）
    for sel in [
        ".a-text-price .a-offscreen",
        "#priceblock_saleprice",
        ".a-price.a-text-price .a-offscreen",
    ]:
        try:
            orig = page.locator(sel).first.text_content(timeout=2000)
            if orig and "$" in orig and orig.strip() != data.get("price"):
                data["original_price"] = orig.strip()
                break
        except Exception:
            pass

    # ── 评分 ──────────────────────────────────────────────────────────
    for sel in [
        "#acrPopover .a-icon-alt",
        "#averageCustomerReviews .a-icon-alt",
        ".a-icon-star .a-icon-alt",
        ".a-icon-alt",  # 取第一个含 star 的
    ]:
        try:
            els = page.locator(sel).all()
            for el in els:
                r = el.text_content(timeout=2000)
                if r and "star" in r.lower():
                    data["rating"] = r.strip()
                    break
            if data.get("rating"):
                break
        except Exception:
            pass

    # ── 评论数 ──────────────────────────────────────────────────────
    for sel in [
        "#acrCustomerReviewText",
        "#ratings-count",
        '[data-hook="total-review-count"]',
    ]:
        try:
            rc = page.locator(sel).first.text_content(timeout=3000)
            if rc and rc.strip():
                data["review_count"] = rc.strip()
                break
        except Exception:
            pass

    # ── 库存状态 ──────────────────────────────────────────────────────
    for sel in [
        "#availability span",
        "#deliveryMessageMirror span",
        "#outOfStockBuyBox_feature_div .a-section span",
    ]:
        try:
            avail = page.locator(sel).first.text_content(timeout=3000)
            if avail and avail.strip():
                data["availability"] = avail.strip()[:255]
                break
        except Exception:
            pass

    # ── Bullet Points ─────────────────────────────────────────────────
    bullets = []
    for sel in [
        "#feature-bullets li:not(.aok-hidden) span.a-list-item",
        "#feature-bullets .a-list-item",
        "#productFactsDesktopExpander li span.a-list-item",
    ]:
        try:
            bullet_els = page.locator(sel).all()
            for el in bullet_els:
                txt = el.text_content(timeout=2000)
                if txt and txt.strip() and len(txt.strip()) > 3:
                    bullets.append(txt.strip())
            if bullets:
                break
        except Exception:
            pass
    if bullets:
        data["bullet_points"] = json.dumps(bullets, ensure_ascii=False)

    # ── 商品描述 ─────────────────────────────────────────────────────
    desc_parts = []
    for sel in [
        "#productDescription p",
        "#productDescription span",
        "#aplus p",
        "#dpx-aplus-product-description_feature_div p",
    ]:
        try:
            desc_els = page.locator(sel).all()
            for el in desc_els[:20]:
                txt = el.text_content(timeout=2000)
                if txt and len(txt.strip()) > 20:
                    desc_parts.append(txt.strip())
        except Exception:
            pass
        if desc_parts:
            break
    if desc_parts:
        data["description"] = "\n\n".join(desc_parts)[:50000]

    # ── 商品规格参数 ──────────────────────────────────────────────────
    details = {}
    # JS 代码特征关键词，用于过滤脏数据
    JS_PATTERNS = re.compile(
        r"P\.when\(|\.execute\(|function\(|onclick=|addEventListener|<script",
        re.IGNORECASE,
    )
    # 需要跳过的字段名（含 JS 动态内容）
    SKIP_KEYS = {"customer reviews", "asin"}

    def _is_clean(k: str, v: str) -> bool:
        """判断规格条目是否干净（无 JS 代码、不是黑名单字段）"""
        if k.lower() in SKIP_KEYS:
            return False
        if JS_PATTERNS.search(v):
            return False
        return True

    # 方法1: 表格形式
    for tbl_sel in [
        "#productDetails_techSpec_section_1 tr",
        "#productDetails_detailBullets_sections1 tr",
        "#productDetails_expanderTables_depthLeftSections tr",
        "#productDetails_expanderTables_depthRightSections tr",
    ]:
        try:
            rows = page.locator(tbl_sel).all()
            for row in rows:
                cells = row.locator("td, th").all()
                if len(cells) >= 2:
                    key = cells[0].text_content(timeout=2000)
                    val = cells[1].text_content(timeout=2000)
                    if key and val:
                        k = re.sub(r"\s+", " ", key.strip())
                        v = re.sub(r"\s+", " ", val.strip())
                        if k and v and _is_clean(k, v):
                            details[k] = v
        except Exception:
            pass
    # 方法2: bullet 形式
    if not details:
        try:
            items = page.locator("#detailBullets_feature_div li .a-list-item").all()
            for item in items:
                txt = item.text_content(timeout=2000)
                if txt and ":" in txt:
                    parts = txt.split(":", 1)
                    if len(parts) == 2 and parts[0].strip():
                        k = parts[0].strip()
                        v = parts[1].strip()
                        if _is_clean(k, v):
                            details[k] = v
        except Exception:
            pass
    if details:
        data["product_details"] = json.dumps(details, ensure_ascii=False)

    # ── 分类路径 ──────────────────────────────────────────────────────
    try:
        breadcrumbs = page.locator("#wayfinding-breadcrumbs_feature_div a").all()
        cats = [el.text_content(timeout=2000) for el in breadcrumbs]
        cats = [re.sub(r"\s+", " ", c.strip()) for c in cats if c and c.strip()]
        if cats:
            data["category_path"] = " > ".join(cats)
    except Exception:
        pass

    # ── 主图 URL ──────────────────────────────────────────────────────
    for img_sel in [
        "#landingImage",
        "#imgTagWrapperId img",
        "#main-image-container img",
    ]:
        try:
            img_el = page.locator(img_sel).first
            img_src = img_el.get_attribute("src", timeout=3000)
            if not img_src or img_src.startswith("data:"):
                img_src = img_el.get_attribute("data-old-hires", timeout=2000)
            if img_src and not img_src.startswith("data:"):
                data["main_image_url"] = img_src
                break
        except Exception:
            pass

    # ── 所有图片（从 JS 变量提取）────────────────────────────────────
    try:
        img_json_str = page.evaluate("""
            () => {
                try {
                    const match = document.body.innerHTML.match(/'colorImages':\\s*\\{[^}]*'initial':\\s*(\\[.*?\\])/s);
                    return match ? match[1] : null;
                } catch(e) { return null; }
            }
        """)
        if img_json_str:
            imgs_raw = json.loads(img_json_str)
            img_urls = []
            for img in imgs_raw[:10]:
                url = img.get("hiRes") or img.get("large") or img.get("main")
                if url:
                    img_urls.append(url)
            if img_urls:
                data["image_urls"] = json.dumps(img_urls, ensure_ascii=False)
    except Exception:
        pass

    # ── 评论（前5条）─────────────────────────────────────────────────
    reviews = []
    try:
        review_items = page.locator('[data-hook="review"]').all()[:5]
        for rev in review_items:
            try:
                star = rev.locator(
                    '[data-hook="review-star-rating"] .a-icon-alt, [data-hook="cmps-review-star-rating"] .a-icon-alt'
                ).first.text_content(timeout=2000)
                rtitle = rev.locator(
                    '[data-hook="review-title"] span:not(.a-icon-alt)'
                ).first.text_content(timeout=2000)
                rbody = rev.locator(
                    '[data-hook="review-body"] span'
                ).first.text_content(timeout=2000)
                if rbody:
                    reviews.append(
                        {
                            "rating": star.strip() if star else "",
                            "title": rtitle.strip() if rtitle else "",
                            "body": rbody.strip()[:500],
                        }
                    )
            except Exception:
                pass
    except Exception:
        pass
    if reviews:
        data["top_reviews"] = json.dumps(reviews, ensure_ascii=False)

    # ── 关键词提取 ────────────────────────────────────────────────────
    kw_source = data.get("title", "")
    if bullets:
        kw_source += " " + " ".join(bullets[:3])
    if kw_source:
        stop = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "for",
            "with",
            "in",
            "on",
            "of",
            "to",
            "is",
            "are",
            "this",
            "that",
            "it",
            "from",
            "by",
            "as",
            "at",
            "be",
            "has",
            "have",
            "can",
            "will",
            "your",
            "our",
            "its",
            "their",
            "not",
            "but",
            "set",
            "get",
            "use",
            "used",
            "pack",
        }
        words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9\-]{2,}\b", kw_source)
        kw_list = list(
            dict.fromkeys(w.lower() for w in words if w.lower() not in stop)
        )[:30]
        if kw_list:
            data["keywords"] = json.dumps(kw_list, ensure_ascii=False)

    data["page_language"] = "en-US"
    data["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


# ─── MySQL 写入 ───────────────────────────────────────────────────────────────
UPSERT_SQL = """
INSERT INTO amazon_product_details
    (asin, title, brand, price, original_price, rating, review_count,
     availability, bullet_points, description, product_details, category_path,
     main_image_url, image_urls, top_reviews, keywords, amazon_url,
     page_language, scraped_at)
VALUES
    (%(asin)s, %(title)s, %(brand)s, %(price)s, %(original_price)s, %(rating)s,
     %(review_count)s, %(availability)s, %(bullet_points)s, %(description)s,
     %(product_details)s, %(category_path)s, %(main_image_url)s, %(image_urls)s,
     %(top_reviews)s, %(keywords)s, %(amazon_url)s, %(page_language)s, %(scraped_at)s)
ON DUPLICATE KEY UPDATE
    title           = VALUES(title),
    brand           = VALUES(brand),
    price           = VALUES(price),
    original_price  = VALUES(original_price),
    rating          = VALUES(rating),
    review_count    = VALUES(review_count),
    availability    = VALUES(availability),
    bullet_points   = VALUES(bullet_points),
    description     = VALUES(description),
    product_details = VALUES(product_details),
    category_path   = VALUES(category_path),
    main_image_url  = VALUES(main_image_url),
    image_urls      = VALUES(image_urls),
    top_reviews     = VALUES(top_reviews),
    keywords        = VALUES(keywords),
    amazon_url      = VALUES(amazon_url),
    page_language   = VALUES(page_language),
    scraped_at      = VALUES(scraped_at)
"""

ALL_FIELDS = [
    "asin",
    "title",
    "brand",
    "price",
    "original_price",
    "rating",
    "review_count",
    "availability",
    "bullet_points",
    "description",
    "product_details",
    "category_path",
    "main_image_url",
    "image_urls",
    "top_reviews",
    "keywords",
    "amazon_url",
    "page_language",
    "scraped_at",
]


def ensure_field(d: dict, fields: list):
    for f in fields:
        d.setdefault(f, None)
    return d


# ─── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Scrape Amazon product details")
    parser.add_argument("--limit", type=int, default=0, help="Max records (0=all)")
    parser.add_argument("--asin", type=str, default="", help="Single ASIN test")
    parser.add_argument(
        "--url", type=str, default="", help="Tracking URL to visit (YP platform link)"
    )
    parser.add_argument(
        "--refetch", action="store_true", help="Re-scrape existing records"
    )
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="Skip address/language setup, use original link",
    )
    args = parser.parse_args()

    # ── 从 MySQL 获取待处理列表 ──────────────────────────────────────
    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)

    if args.asin:
        # 单个 ASIN 模式
        if args.url:
            # 优先使用传入的 URL
            amazon_url = args.url
            print(f"[INFO] 使用传入的 URL: {amazon_url[:80]}...")
        else:
            # 从数据库查询 tracking_url
            cur.execute(
                "SELECT tracking_url FROM yp_us_products WHERE asin = %s LIMIT 1",
                (args.asin,),
            )
            row = cur.fetchone()
            if row and row.get("tracking_url"):
                amazon_url = row["tracking_url"]
                print(f"[INFO] 使用 tracking_url: {amazon_url[:80]}...")
            else:
                # 最后才构造默认 URL
                amazon_url = f"https://www.amazon.com/dp/{args.asin}"
                print(f"[WARN] 未找到 tracking_url，使用默认 URL: {amazon_url}")
        todo = [{"asin": args.asin, "amazon_url": amazon_url}]
        total = 1
    else:
        if args.refetch:
            sql = """
                SELECT p.asin, p.tracking_url AS amazon_url
                FROM yp_us_products p
                WHERE p.tracking_url IS NOT NULL AND p.tracking_url != ''
                GROUP BY p.asin
                ORDER BY MIN(p.id)
            """
        else:
            # 增量：跳过已采集（含 __404__ 标记）的 ASIN
            sql = """
                SELECT p.asin, p.tracking_url AS amazon_url
                FROM yp_us_products p
                LEFT JOIN amazon_product_details d ON p.asin = d.asin
                WHERE d.asin IS NULL
                  AND p.tracking_url IS NOT NULL AND p.tracking_url != ''
                GROUP BY p.asin
                ORDER BY MIN(p.id)
            """
        if args.limit:
            sql += f" LIMIT {args.limit}"
        cur.execute(sql)
        todo = cur.fetchall()
        total = len(todo)

    print(f"[INFO] Pending ASINs: {total:,}")
    if total == 0:
        print("[OK] Nothing to process, exiting.")
        db.close()
        return

    # ── 连接 Chrome ──────────────────────────────────────────────────
    # 先检查 Chrome 调试模式是否运行，没有则自动启动
    if not _check_chrome_debug():
        print("[INFO] Chrome 调试模式未运行，正在自动启动...")
        if not _start_chrome_debug():
            print("[ERROR] 无法启动 Chrome 调试模式")
            db.close()
            return

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(CHROME_WS)
        except Exception as e:
            print(f"[ERROR] Cannot connect to Chrome debug port {CHROME_WS}: {e}")
            print("  Please start debug Chrome manually")
            db.close()
            return

        contexts = browser.contexts
        ctx = contexts[0] if contexts else browser.new_context()
        page = ctx.new_page()
        print("[OK] New tab created for Amazon scraping")

        # ── 一次性初始化：切换地址到中国 + 设置语言为英语（--no-setup 可跳过）───────────────
        if not args.no_setup:
            setup_language_and_address(page)
        else:
            print("[INFO] 跳过配送地址和语言设置，直接访问原始链接")

        print(f"[OK] Connected to Chrome, starting scrape...\n")

        success_count = 0
        fail_count = 0
        fail_log = []

        # 启动时清理旧的停止信号（上次可能残留）
        if STOP_FILE.exists():
            STOP_FILE.unlink()
            print("[INFO] 已清除上次残留的停止信号文件")

        def get_fresh_page():
            """尝试获取一个有效的新 Tab，如果当前 page 失效则重建"""
            try:
                contexts_ = browser.contexts
                ctx_ = contexts_[0] if contexts_ else browser.new_context()
                p = ctx_.new_page()
                return p
            except Exception as e:
                print(f"[WARN] 无法创建新 Tab: {e}")
                return None

        for idx, row in enumerate(todo, 1):
            # ── 检查停止信号 ───────────────────────────────────────────
            if _should_stop():
                print(
                    f"\n[STOP] 检测到停止信号，已安全退出（已处理 {idx - 1}/{total}）"
                )
                _write_progress(
                    idx - 1, total, success_count, fail_count, "", status="stopped"
                )
                break

            asin = row["asin"]
            amazon_url = row["amazon_url"]

            print(f"[{idx:>5}/{total}] {asin}", end="  ")
            sys.stdout.flush()

            retried = 0
            while retried <= RETRY_LIMIT:
                try:
                    detail = scrape_product(page, amazon_url, asin)
                    detail = ensure_field(detail, ALL_FIELDS)

                    cur.execute(UPSERT_SQL, detail)
                    db.commit()

                    title_short = (detail.get("title") or "")[:40]
                    price = detail.get("price") or "N/A"
                    rating = detail.get("rating") or "N/A"
                    bullets_n = (
                        len(json.loads(detail["bullet_points"]))
                        if detail.get("bullet_points")
                        else 0
                    )
                    print(
                        f'OK  {price}  {rating}  bullets={bullets_n}  "{title_short}"'
                    )
                    success_count += 1
                    _write_progress(idx, total, success_count, fail_count, asin)
                    break

                except PlaywrightTimeout:
                    retried += 1
                    if retried > RETRY_LIMIT:
                        print(f"FAIL timeout (gave up after {RETRY_LIMIT} retries)")
                        fail_count += 1
                        fail_log.append({"asin": asin, "reason": "timeout"})
                    else:
                        print(f"  retry {retried}/{RETRY_LIMIT}...", end="")
                        # retry 等待期间也检查停止信号
                        for _ in range(3):
                            if _should_stop():
                                break
                            time.sleep(1)

                except Exception as e:
                    err_str = str(e)[:200]
                    # Tab 被关闭时自动重建
                    if "has been closed" in err_str or "Target closed" in err_str:
                        print(f"  [Tab closed, recreating...]", end="")
                        new_page = get_fresh_page()
                        if new_page:
                            page = new_page
                            print(f" [OK] retry {retried + 1}/{RETRY_LIMIT}...", end="")
                            retried += 1
                            time.sleep(2)
                            continue
                    # 404 / 已下架商品：写入标记记录，避免重复采集
                    if (
                        "404" in err_str
                        or "已下架" in err_str
                        or "Page Not Found" in err_str.lower()
                    ):
                        print(f"SKIP 商品已下架/404")
                        mark = ensure_field(
                            {
                                "asin": asin,
                                "amazon_url": amazon_url,
                                "title": "__404__",
                                "availability": "PAGE_NOT_FOUND",
                                "page_language": "en-US",
                                "scraped_at": datetime.now().strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                            },
                            ALL_FIELDS,
                        )
                        try:
                            cur.execute(UPSERT_SQL, mark)
                            db.commit()
                        except Exception:
                            pass
                        fail_count += 1
                        fail_log.append({"asin": asin, "reason": "404/已下架"})
                        break
                    print(f"FAIL {err_str[:120]}")
                    fail_count += 1
                    fail_log.append({"asin": asin, "reason": err_str[:200]})
                    break

            if idx % BATCH_SIZE == 0:
                print(
                    f"\n  -- Progress: {idx}/{total} | OK={success_count} FAIL={fail_count} --\n"
                )

            time.sleep(0.5)

        # ── 结束 ─────────────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print(f"DONE! Total={total} | Success={success_count} | Fail={fail_count}")
        # 写最终进度状态
        _write_progress(total, total, success_count, fail_count, "", status="finished")

        if fail_log:
            import os

            os.makedirs("output", exist_ok=True)
            fail_path = "output/amazon_scrape_failures.json"
            with open(fail_path, "w", encoding="utf-8") as f:
                json.dump(fail_log, f, ensure_ascii=False, indent=2)
            print(f"  Failure log: {fail_path}")

        page.close()
        db.close()


if __name__ == "__main__":
    main()
