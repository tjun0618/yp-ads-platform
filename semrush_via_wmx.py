# -*- coding: utf-8 -*-
"""
外贸侠 SEMrush 自动化采集脚本 v2.0
流程：自动检测/启动Chrome -> 打开登录页 -> 等待用户登录 -> SEO工具包 -> Semrush高级版 -> 输入域名采集
"""

import json
import time
import sys
import os
import argparse
import subprocess
import shutil

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ============ 配置 ============
CHROME_WS = "http://127.0.0.1:9222"
CHROME_DEBUG_PORT = 9222
CHROME_USER_DATA_DIR = r"C:\Chrome_Debug"
WAIMAOXIA_LOGIN_URL = "https://www.waimaoxia.net/login"
WMXPRO_URL = "https://zh.trends.fast.wmxpro.com/analytics/overview/?searchType=domain"
OUTPUT_DIR = Path("temp")

# Chrome 路径候选（按优先级）
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# 选择器配置
SELECTORS = {
    "username_input": "input[placeholder='请输入账号']",
    "password_input": "input[placeholder='请输入密码']",
    "login_button": "button[type='button'].el-button--primary",
    "cookie_accept": ".cookie-consent .cookie-accept, .accept-cookies",
    "seo_tool_menu": "text=SEO工具包",
    "semrush_advanced": "text=Semrush 高级版",
    # SEMrush 页面（wmxpro.com 域名）
    "domain_input": "input[placeholder*='域名'], input[placeholder*='domain'], input[placeholder*='Domain'], "
    "input[placeholder*='网址'], input[placeholder*='URL'], input[placeholder*='网站'], "
    "input.search-input, input.domain-input, input[type='text']",
    "search_button": "button:has-text('查询'), button:has-text('搜索'), button:has-text('分析'), "
    "button:has-text('Search'), button:has-text('Analyze'), "
    "button[type='submit'], button.search, .search-btn, .search-button",
    "traffic_section": ".traffic-overview, .organic-search, [class*='traffic']",
    "keywords_section": ".keywords-section, [class*='keyword']",
    "ads_section": ".ads-section, .advertising-section, [class*='ad']",
}


# ============ Chrome 管理工具 ============


def find_chrome():
    """查找本地 Chrome 可执行文件"""
    for path in CHROME_PATHS:
        if os.path.isfile(path):
            return path
    # 尝试 PATH 里找
    chrome = shutil.which("chrome") or shutil.which("chrome.exe")
    if chrome:
        return chrome
    return None


def is_chrome_debug_running():
    """检测 Chrome 调试端口是否可用"""
    try:
        resp = urlopen(f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=3)
        data = json.loads(resp.read())
        print(f"✅ Chrome 调试端口已就绪 ({data.get('Browser', 'unknown')})")
        return True
    except (URLError, OSError, json.JSONDecodeError):
        return False


def start_chrome_debug():
    """启动 Chrome 调试模式"""
    chrome_path = find_chrome()
    if not chrome_path:
        print("❌ 未找到 Chrome 浏览器，请手动安装或指定路径")
        print("   支持的浏览器：Chrome、Brave、Edge")
        return False

    # 确保用户数据目录存在
    os.makedirs(CHROME_USER_DATA_DIR, exist_ok=True)

    print(f"🚀 启动 Chrome 调试模式...")
    print(f"   路径: {chrome_path}")
    print(f"   端口: {CHROME_DEBUG_PORT}")
    print(f"   数据目录: {CHROME_USER_DATA_DIR}")

    try:
        subprocess.Popen(
            [
                chrome_path,
                f"--remote-debugging-port={CHROME_DEBUG_PORT}",
                f"--user-data-dir={CHROME_USER_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    except Exception as e:
        print(f"❌ 启动 Chrome 失败: {e}")
        return False

    # 等待端口就绪（最多30秒）
    print("   等待 Chrome 启动...")
    for i in range(15):
        time.sleep(2)
        if is_chrome_debug_running():
            return True
        if (i + 1) % 5 == 0:
            print(f"   等待中... ({(i + 1) * 2}秒)")

    print("❌ Chrome 启动超时，请检查是否有冲突的 Chrome 实例")
    print("   提示：如果已有 Chrome 在运行，需要先关闭所有 Chrome 窗口再试")
    return False


def ensure_chrome_ready():
    """确保 Chrome 调试模式可用，不可用则自动启动"""
    if is_chrome_debug_running():
        return True

    print("⚠️ Chrome 调试端口未就绪，尝试自动启动...")
    if start_chrome_debug():
        return True

    # 自动启动失败，提示用户手动处理
    print("\n💡 自动启动失败，请手动操作：")
    print("   1. 关闭所有 Chrome 窗口")
    print("   2. 运行以下命令启动 Chrome 调试模式：")
    chrome_path = find_chrome()
    if chrome_path:
        print(
            f'      "{chrome_path}" --remote-debugging-port={CHROME_DEBUG_PORT} --user-data-dir="{CHROME_USER_DATA_DIR}"'
        )
    print("   3. Chrome 打开后重新运行本脚本")
    return False


class WaimaoxiaSemrushCollector:
    """外贸侠 SEMrush 数据采集器"""

    def __init__(self, chrome_ws=CHROME_WS):
        self.chrome_ws = chrome_ws
        self.browser = None
        self.context = None
        self.page = None
        self.output_file = None
        self._playwright = None
        # 网络拦截：存储 SEMrush 内部 API 返回的 JSON 数据
        self._api_responses = {
            "overview": None,  # 域名概览数据
            "organic_keywords": None,  # 自然搜索关键词
            "paid_keywords": None,  # 付费搜索关键词
            "ad_copies": None,  # 广告文案
            "competitors_organic": None,  # 自然竞品
            "competitors_paid": None,  # 付费竞品
            "referring_sources": None,  # 引用来源（RPC: result.sources）
            "raw_api_urls": [],  # 所有拦截到的 API URL（调试用）
        }

    def connect(self):
        """连接到 Chrome DevTools（自动检测并启动Chrome）"""
        # 先确保 Chrome 调试模式可用
        if not ensure_chrome_ready():
            return False

        print(f"🔌 连接到 Chrome: {self.chrome_ws}")

        self._playwright = sync_playwright().start()
        try:
            self.browser = self._playwright.chromium.connect_over_cdp(self.chrome_ws)
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False

        # 获取已有 context
        if not self.browser.contexts:
            print("❌ 没有 browser context")
            return False

        self.context = self.browser.contexts[0]
        print(f"✅ 已连接到 Chrome，当前有 {len(self.context.pages)} 个页面")
        return True

    def create_page(self):
        """创建或复用页面"""
        # 优先复用已有的 SEMrush 概览页
        for ctx in self.browser.contexts:
            for p in ctx.pages:
                url = p.url
                if "wmxpro" in url and "overview" in url and "q=" in url:
                    self.context = ctx
                    self.page = p
                    self._setup_api_interceptor()
                    print(f"✅ 复用已有 SEMrush 页面: {url[:80]}...")
                    return self.page

        # 没有可复用的页面，创建新页面
        self.page = self.context.new_page()
        # 设置网络响应拦截器，捕获 SEMrush 内部 API 数据
        self._setup_api_interceptor()
        print("✅ 创建新页面（已启用API拦截器）")
        return self.page

    def _setup_api_interceptor(self):
        """设置网络响应拦截器，捕获 SEMrush 内部 API 返回的 JSON 数据

        SEMrush (wmxpro) 的数据请求架构：
        - 统一数据端点：/dpa/rpc（POST请求，数据类型由请求体参数决定）
        - 关键词端点：/mini-kwogw/v2/webapi
        - 其他辅助端点：/notes/api/、/recommendation/api/、/search-bar/api/

        由于 /dpa/rpc 是统一端点，无法按URL路径分类，
        必须从响应JSON的字段结构自动判断数据类型。
        """
        self._rpc_dump_count = 0  # 限制RPC响应样本保存数量

        def _classify_rpc_response(body, url):
            """从 /dpa/rpc 响应的JSON结构自动分类数据类型

            SEMrush的RPC响应可能包含多种数据，通过检查字段名来判断类型。
            支持下划线式和驼峰式字段名（如 authority_score / authorityScore）。
            返回: (category, data) 或 (None, None)
            """
            if not isinstance(body, dict):
                return None, None

            # 将响应体转为字符串进行特征检测（前3000字符，兼顾深度嵌套）
            body_str = json.dumps(body, ensure_ascii=False)[:3000].lower()

            # 提取 result 层（JSON-RPC格式：{jsonrpc, id, result: {...}}）
            inner_data = body.get("result", body.get("data", body.get("response", {})))
            inner_str = ""
            if isinstance(inner_data, dict):
                inner_str = json.dumps(inner_data, ensure_ascii=False)[:3000].lower()
            combined = body_str + " " + inner_str

            # ─── 分类优先级：从最具体到最通用 ───

            # 1. 广告文案 — 包含 ad_copies, creative 等字段
            if any(
                k in combined
                for k in [
                    "ad_copies",
                    "ad_copy",
                    "creative_title",
                    "creative_snippet",
                    "ads_text",
                    "ads_text_ad",
                    "adcreative",
                    "text_ad",
                ]
            ):
                return "ad_copies", body

            # 2. 付费关键词 — 包含 adwords + position/keyword 字段
            #    注意：SEMrush 的广告关键词数据可能使用不同的字段名
            if any(
                k in combined
                for k in [
                    "adwords_keyword",
                    "paid_keyword",
                    "adwords_position",
                    "paid_position",
                    "paid_traffic",
                    "adwords_traffic",
                    "ad_cost",
                    "ad_position",
                    "ads_keywords",
                ]
            ):
                return "paid_keywords", body

            # 2b. 检查 URL 路径是否包含 adwords/positions（广告关键词页面）
            #     这类响应通常包含关键词数据，但字段名可能与自然关键词相同
            if (
                "/adwords/positions" in url.lower()
                or "/adwords/keywords" in url.lower()
            ):
                # 如果响应包含关键词字段，归类为付费关键词
                if any(k in combined for k in ["keyword", "volume", "cpc", "position"]):
                    return "paid_keywords", body

            # 3. 自然关键词 — 包含 top_keywords（RPC特有）或 organic 关键词字段
            #    RPC格式的关键词数据：result.topics[].pages[].top_keywords[]
            if "top_keywords" in combined:
                if "paid" in combined or "adwords" in combined:
                    return "paid_keywords", body
                return "organic_keywords", body

            if any(
                k in combined
                for k in [
                    "organic_position",
                    "organic_keyword",
                    "position_organic",
                    "organic_traffic",
                    "organic_search",
                ]
            ):
                return "organic_keywords", body

            # 4. 引用来源 — result.sources 包含 domain + mentions_count
            if any(
                k in combined
                for k in ["mentions_count", "referring_sources", "sources"]
            ):
                # 排除纯日期列表（id=2的result只有daily/monthly日期数组）
                if isinstance(inner_data, dict) and "sources" in inner_data:
                    return "referring_sources", body

            # 5. 自然竞品 — organic competitor
            if any(
                k in combined
                for k in ["organic_competitor", "competitor_organic", "se_domain"]
            ):
                return "competitors_organic", body

            # 6. 付费竞品 — paid/adwords competitor
            if any(
                k in combined
                for k in ["adwords_competitor", "paid_competitor", "competitor_paid"]
            ):
                return "competitors_paid", body

            # 7. 概览数据 — authorityScore(驼峰) 或 authority_score 或 反向链接数据
            #    RPC格式：{authorityScore, backlinks, referringDomains, ...}
            if any(
                k in combined
                for k in [
                    "authorityscore",
                    "authority_score",
                    "domain_overview",
                    "domain_rank",
                    "ascore",
                    "linkpower",
                    "referringdomains",
                ]
            ):
                return "overview", body

            # 8. 概览数据 — result.target 包含域名级流量概览
            #    RPC格式：{target: {keywords, traffic, keywords_branded, ...}}
            if isinstance(inner_data, dict) and "target" in inner_data:
                target = inner_data["target"]
                if isinstance(target, dict) and any(
                    k in target for k in ["keywords", "traffic", "domain"]
                ):
                    return "overview", body

            # 9. 宽松匹配：典型SEMrush数据字段
            if any(
                k in combined
                for k in [
                    "search_volume",
                    "keyword_difficulty",
                    "cpc",
                    "position_change",
                    "serp_feature",
                    "url_min_position",
                ]
            ):
                if "paid" in combined or "adwords" in combined:
                    return "paid_keywords", body
                return "organic_keywords", body

            # 10. 关键词/位置分布图数据 — keyword/position dict with number keys
            #     不做分类，这些是图表数据不是原始关键词

            return None, None

        def _on_response(response):
            try:
                url = response.url
                # 只处理 wmxpro 域名的请求
                if "wmxpro.com" not in url:
                    return

                # 记录所有 wmxpro URL（调试用）
                self._api_responses["raw_api_urls"].append(url)
                if len(self._api_responses["raw_api_urls"]) > 300:
                    self._api_responses["raw_api_urls"] = self._api_responses[
                        "raw_api_urls"
                    ][-200:]

                # ─── 拦截 /dpa/rpc 统一数据端点 ───
                if "/dpa/rpc" in url:
                    try:
                        body = response.json()
                    except:
                        # RPC可能用非标准content-type，尝试text解析
                        try:
                            text = response.text()
                            body = json.loads(text)
                        except:
                            return

                    if not isinstance(body, dict):
                        return

                    # 自动分类RPC响应
                    category, rpc_data = _classify_rpc_response(body, url)

                    if category:
                        # 存储到对应分类
                        existing = self._api_responses.get(category)
                        if not existing:
                            self._api_responses[category] = rpc_data
                            print(f"   [API拦截/RPC] {category}: {url[:80]}")
                        else:
                            # 对于overview类型，合并多个RPC响应（可能来自不同ID的请求）
                            if (
                                category == "overview"
                                and isinstance(rpc_data, dict)
                                and isinstance(existing, dict)
                            ):
                                # 深度合并：将新的result字段合并到已有的result中
                                existing_result = existing.get("result", existing)
                                new_result = rpc_data.get("result", rpc_data)
                                if isinstance(existing_result, dict) and isinstance(
                                    new_result, dict
                                ):
                                    merged = dict(existing_result)
                                    for k, v in new_result.items():
                                        if k not in merged:
                                            merged[k] = v
                                    existing["result"] = merged
                                    print(
                                        f"   [API拦截/RPC] {category}(合并): {url[:80]}"
                                    )
                                else:
                                    # 无法合并，保留更大的
                                    if len(
                                        json.dumps(rpc_data, ensure_ascii=False)
                                    ) > len(json.dumps(existing, ensure_ascii=False)):
                                        self._api_responses[category] = rpc_data
                                        print(
                                            f"   [API拦截/RPC] {category}(更新): {url[:80]}"
                                        )
                            else:
                                # 非overview类型，保留更完整的数据
                                if isinstance(rpc_data, dict) and isinstance(
                                    existing, dict
                                ):
                                    if len(
                                        json.dumps(rpc_data, ensure_ascii=False)
                                    ) > len(json.dumps(existing, ensure_ascii=False)):
                                        self._api_responses[category] = rpc_data
                                        print(
                                            f"   [API拦截/RPC] {category}(更新): {url[:80]}"
                                        )
                    else:
                        # 未分类的RPC响应 — 保存样本供调试分析
                        if self._rpc_dump_count < 10:
                            try:
                                api_dump_dir = OUTPUT_DIR / "api_dumps"
                                api_dump_dir.mkdir(exist_ok=True)
                                dump_file = (
                                    api_dump_dir
                                    / f"rpc_unclassified_{self._rpc_dump_count}_{int(time.time())}.json"
                                )
                                dump_file.write_text(
                                    json.dumps(body, ensure_ascii=False, indent=2)[
                                        :50000
                                    ],
                                    encoding="utf-8",
                                )
                                self._rpc_dump_count += 1
                                print(
                                    f"   [API拦截/RPC] 未分类响应已保存: {dump_file.name}"
                                )
                            except:
                                pass

                    return  # /dpa/rpc 处理完毕

                # ─── 拦截 /mini-kwogw/v2/webapi 关键词端点 ───
                if "/mini-kwogw" in url:
                    try:
                        body = response.json()
                    except:
                        try:
                            body = json.loads(response.text())
                        except:
                            return

                    if isinstance(body, dict):
                        if not self._api_responses.get("organic_keywords"):
                            self._api_responses["organic_keywords"] = body
                            print(f"   [API拦截/KWOGW] 自然关键词: {url[:80]}")
                        # 保存样本
                        try:
                            api_dump_dir = OUTPUT_DIR / "api_dumps"
                            api_dump_dir.mkdir(exist_ok=True)
                            dump_file = api_dump_dir / f"kwogw_{int(time.time())}.json"
                            dump_file.write_text(
                                json.dumps(body, ensure_ascii=False, indent=2)[:50000],
                                encoding="utf-8",
                            )
                        except:
                            pass
                    return

                # ─── 拦截其他已知数据端点 ───
                # 只对非静态资源的JSON响应做进一步处理
                content_type = response.headers.get("content-type", "")
                is_data_endpoint = any(
                    ep in url
                    for ep in [
                        "/notes/api/",
                        "/recommendation/api/",
                        "/search-bar/api/",
                        "/analytics/",
                        "/semrush/",
                    ]
                )
                is_static = any(
                    ext in url
                    for ext in [".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico"]
                )

                if is_static:
                    return

                if (
                    "json" not in content_type
                    and "javascript" not in content_type
                    and not is_data_endpoint
                ):
                    return

                try:
                    body = response.json()
                except:
                    return

                if not isinstance(body, dict):
                    return

                # 按 URL 路径分类（兼容旧版API格式）
                url_lower = url.lower()
                category = None

                if "/analytics/overview" in url_lower:
                    category = "overview"
                elif any(
                    k in url_lower
                    for k in ["/organic/positions", "/organic/keywords", "/organic_key"]
                ):
                    category = "organic_keywords"
                elif any(
                    k in url_lower
                    for k in ["/adwords/positions", "/adwords_key", "/paid_key"]
                ):
                    category = "paid_keywords"
                elif any(
                    k in url_lower
                    for k in [
                        "/adwords/ad-copies",
                        "/ad-copies",
                        "/adcopies",
                        "/ads_copies",
                        "/adcopy",
                    ]
                ):
                    category = "ad_copies"
                elif any(
                    k in url_lower for k in ["/organic/competitors", "/organic_comp"]
                ):
                    category = "competitors_organic"
                elif any(
                    k in url_lower for k in ["/adwords/competitors", "/paid_comp"]
                ):
                    category = "competitors_paid"

                if category and not self._api_responses.get(category):
                    self._api_responses[category] = body
                    print(f"   [API拦截] {category}: {url[:120]}")

            except Exception:
                pass  # 拦截器不能抛异常，静默忽略

        # 保存引用以便后续移除监听器
        self._api_listener = _on_response
        self.page.on("response", _on_response)

    def _parse_api_overview(self, api_data, data):
        """从 API 响应中解析概览数据

        支持多种格式：
        - 旧格式: {data: {organic: {traffic: ...}, authority_score: ...}}
        - RPC格式: {jsonrpc, id, result: {target: {keywords, traffic, keywords_branded, ...}}}
        - RPC概览格式: {jsonrpc, id, result: {authorityScore, backlinks, referringDomains, ...}}
        """
        if not api_data:
            return
        try:
            # SEMrush API 响应结构可能多种多样，需要探测性解析
            def _deep_get(obj, *keys, default=None):
                """多层嵌套取值"""
                for key in keys:
                    if isinstance(obj, dict):
                        obj = obj.get(key, default)
                    elif (
                        isinstance(obj, list)
                        and isinstance(key, int)
                        and key < len(obj)
                    ):
                        obj = obj[key]
                    else:
                        return default
                    if obj is None:
                        return default
                return obj

            # ═══ 处理RPC格式：提取 result 层 ═══
            result_obj = api_data.get("result", api_data)
            if not isinstance(result_obj, dict):
                result_obj = api_data

            # ─── RPC概览格式: {authorityScore, backlinks, referringDomains, ...} ───
            # 这是单独的authority/backlinks RPC响应
            if "authorityScore" in result_obj or "backlinks" in result_obj:
                auth = result_obj.get("authorityScore")
                if auth and not data["traffic"].get("authority_score"):
                    data["traffic"]["authority_score"] = (
                        int(auth) if isinstance(auth, (int, float)) else auth
                    )
                bl = result_obj.get("backlinks")
                if bl:
                    data["traffic"]["backlinks"] = bl
                rd = result_obj.get("referringDomains")
                if rd:
                    data["traffic"]["referring_domains"] = rd

            # ─── RPC target格式: result.target = {keywords, traffic, keywords_branded, ...} ───
            target = result_obj.get("target", {})
            if isinstance(target, dict) and (
                target.get("traffic") or target.get("keywords")
            ):
                # 流量
                if target.get("traffic") and not data["traffic"].get("organic"):
                    data["traffic"]["organic"] = str(target["traffic"])
                if target.get("keywords"):
                    data["organic_keywords"]["total"] = str(target["keywords"])
                if target.get("keywords_branded") is not None:
                    data["traffic"]["branded_keywords"] = target["keywords_branded"]
                if target.get("keywords_non_branded") is not None:
                    data["traffic"]["non_branded_keywords"] = target[
                        "keywords_non_branded"
                    ]
                if target.get("traffic_branded") is not None:
                    data["traffic"]["branded"] = str(target["traffic_branded"])
                if target.get("traffic_non_branded") is not None:
                    data["traffic"]["non_branded"] = str(target["traffic_non_branded"])
                # 日期
                if target.get("date"):
                    data["traffic"]["data_date"] = target["date"]
                if target.get("database"):
                    data["traffic"]["database"] = target["database"]

            # ─── 旧格式兼容 ───
            # 解析流量数据
            if not data["traffic"].get("organic"):
                organic = _deep_get(
                    api_data, "data", "organic", "traffic"
                ) or _deep_get(api_data, "organic", "traffic")
                if organic:
                    data["traffic"]["organic"] = str(organic)

            if not data["traffic"].get("paid"):
                paid = _deep_get(api_data, "data", "paid", "traffic") or _deep_get(
                    api_data, "paid", "traffic"
                )
                if paid:
                    data["traffic"]["paid"] = str(paid)

            if not data["traffic"].get("authority_score"):
                auth = _deep_get(api_data, "data", "authority_score") or _deep_get(
                    api_data, "authority_score"
                )
                if auth:
                    data["traffic"]["authority_score"] = (
                        int(auth) if str(auth).isdigit() else auth
                    )

            # 解析关键词总数
            if (
                not data["organic_keywords"].get("total")
                or data["organic_keywords"]["total"] == 0
            ):
                organic_kw = _deep_get(
                    api_data, "data", "organic", "keywords"
                ) or _deep_get(api_data, "organic", "keywords_count")
                if organic_kw:
                    data["organic_keywords"]["total"] = str(organic_kw)

            if (
                not data["paid_keywords"].get("total")
                or data["paid_keywords"]["total"] == 0
            ):
                paid_kw = _deep_get(api_data, "data", "paid", "keywords") or _deep_get(
                    api_data, "paid", "keywords_count"
                )
                if paid_kw:
                    data["paid_keywords"]["total"] = str(paid_kw)

            print(f"   [API解析] 概览数据已提取")
        except Exception as e:
            print(f"   [API解析] 概览解析失败: {e}")

    def _parse_api_keywords(self, api_data, data, keyword_type="organic"):
        """从 API 响应中解析关键词数据

        支持多种响应格式：
        - 直接列表: [{keyword, position, volume, ...}, ...]
        - 嵌套数据: {data: [{...}], result: [{...}]}
        - RPC格式: {result: {target: {...}, topics: [{pages: [{top_keywords: [...]}]}]}}
        - 旧RPC格式: {data: {records: [{...}]}} 或 {result: {data: [{...}]}}
        """
        if not api_data:
            return
        try:
            keywords = []
            kw_list = None

            if isinstance(api_data, dict):
                # ═══ 优先处理RPC topics格式（SEMrush最常见的关键词返回格式） ═══
                # 格式: {jsonrpc, id, result: {target: {...}, topics: [{pages: [{top_keywords: [...]}]}]}}
                result_obj = api_data.get("result", api_data)
                if isinstance(result_obj, dict) and "topics" in result_obj:
                    rpc_keywords = []
                    for topic in result_obj.get("topics", []):
                        if not isinstance(topic, dict):
                            continue
                        for page in topic.get("pages", []):
                            if not isinstance(page, dict):
                                continue
                            for kw_item in page.get("top_keywords", []):
                                if isinstance(kw_item, dict) and kw_item.get("keyword"):
                                    rpc_keywords.append(kw_item)
                    if rpc_keywords:
                        kw_list = rpc_keywords
                        # 同时从 result.target 提取关键词总数
                        target = result_obj.get("target", {})
                        if isinstance(target, dict):
                            target_key = (
                                "organic_keywords"
                                if keyword_type == "organic"
                                else "paid_keywords"
                            )
                            if target.get("keywords"):
                                data[target_key]["total"] = str(target["keywords"])

                # ═══ 通用路径搜索（非topics格式） ═══
                if kw_list is None:
                    search_paths = [
                        "data",
                        "keywords",
                        "results",
                        "data.data",
                        "data.records",
                        "data.result",
                        "result",
                        "result.data",
                        "result.records",
                        "response",
                        "response.data",
                        "response.records",
                    ]
                    for path in search_paths:
                        parts = path.split(".")
                        obj = api_data
                        for part in parts:
                            if isinstance(obj, dict):
                                obj = obj.get(part)
                            else:
                                obj = None
                                break
                        if isinstance(obj, list) and len(obj) > 0:
                            kw_list = obj
                            break

                    # 深度搜索：遍历所有顶层键
                    if kw_list is None:
                        for key, val in api_data.items():
                            if (
                                isinstance(val, list)
                                and len(val) > 0
                                and isinstance(val[0], dict)
                            ):
                                kw_list = val
                                break
                            if isinstance(val, dict):
                                for k2, v2 in val.items():
                                    if (
                                        isinstance(v2, list)
                                        and len(v2) > 0
                                        and isinstance(v2[0], dict)
                                    ):
                                        kw_list = v2
                                        break
                            if kw_list:
                                break

                if kw_list is None and isinstance(api_data, list):
                    kw_list = api_data

            if kw_list:
                for item in kw_list[:50]:
                    if not isinstance(item, dict):
                        continue
                    # RPC topics格式：keyword, cpc, kd, volume, traffic, url, url_min_position, intents
                    kw = {
                        "keyword": item.get("keyword")
                        or item.get("phrase")
                        or item.get("term")
                        or item.get("query", ""),
                        "position": item.get("url_min_position")
                        or item.get("position")
                        or item.get("rank", 0),
                        "volume": item.get("volume") or item.get("search_volume", ""),
                        "cpc": item.get("cpc", ""),
                        "kd": item.get("kd", ""),
                        "traffic": item.get("traffic", ""),
                        "intent": self._decode_intent(item.get("intents", []))
                        or item.get("intent")
                        or item.get("search_intent", ""),
                        "url": item.get("url") or item.get("landing_page", ""),
                    }
                    if kw["keyword"]:
                        keywords.append(kw)

            if keywords:
                target_key = (
                    "organic_keywords" if keyword_type == "organic" else "paid_keywords"
                )
                # 如果API返回了关键词总数，也更新
                if isinstance(api_data, dict):
                    total = api_data.get("total") or api_data.get("total_count")
                    # 也从result.target提取
                    if not total:
                        result_obj = api_data.get("result", {})
                        if isinstance(result_obj, dict):
                            target = result_obj.get("target", {})
                            if isinstance(target, dict) and target.get("keywords"):
                                total = target["keywords"]
                    if total:
                        data[target_key]["total"] = str(total)
                data[target_key]["top_keywords"] = keywords
                print(f"   [API解析] {keyword_type}关键词: {len(keywords)} 条")
            else:
                # 如果解析不到结构化关键词，保存原始数据供调试
                debug_file = (
                    OUTPUT_DIR
                    / f"semrush_api_{keyword_type}_raw_{int(time.time())}.json"
                )
                debug_file.write_text(
                    json.dumps(api_data, ensure_ascii=False, indent=2)[:50000],
                    encoding="utf-8",
                )
                print(
                    f"   [API解析] {keyword_type}关键词格式未知，原始数据已保存: {debug_file}"
                )
        except Exception as e:
            print(f"   [API解析] {keyword_type}关键词解析失败: {e}")

    @staticmethod
    def _decode_intent(intents):
        """将SEMrush RPC的intent数字代码转为文字

        intents: [0] = informational, [1] = navigational, [2] = transactional, [3] = commercial
        """
        if not isinstance(intents, list) or not intents:
            return ""
        intent_map = {
            0: "informational",
            1: "navigational",
            2: "transactional",
            3: "commercial",
        }
        return ", ".join(intent_map.get(i, str(i)) for i in intents)

    def _parse_api_ad_copies(self, api_data, data):
        """从 API 响应中解析广告文案

        支持多种响应格式：
        - 直接列表: [{headline, description, url}, ...]
        - 嵌套数据: {data: [{...}], result: [{...}]}
        - RPC格式: {data: {records: [{...}]}} 或 {result: {data: [{...}]}}
        """
        if not api_data:
            return
        try:
            ads = []
            ad_list = None

            if isinstance(api_data, dict):
                # 深度搜索列表数据
                search_paths = [
                    "data",
                    "ad_copies",
                    "ads",
                    "results",
                    "data.data",
                    "data.records",
                    "data.result",
                    "result",
                    "result.data",
                    "result.records",
                    "response",
                    "response.data",
                    "response.records",
                ]
                for path in search_paths:
                    parts = path.split(".")
                    obj = api_data
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    if isinstance(obj, list) and len(obj) > 0:
                        ad_list = obj
                        break

                # 深度搜索：遍历所有顶层键，找到第一个非空列表
                if ad_list is None:
                    for key, val in api_data.items():
                        if (
                            isinstance(val, list)
                            and len(val) > 0
                            and isinstance(val[0], dict)
                        ):
                            ad_list = val
                            break
                        # 二层嵌套
                        if isinstance(val, dict):
                            for k2, v2 in val.items():
                                if (
                                    isinstance(v2, list)
                                    and len(v2) > 0
                                    and isinstance(v2[0], dict)
                                ):
                                    ad_list = v2
                                    break
                        if ad_list:
                            break

                if ad_list is None and isinstance(api_data, list):
                    ad_list = api_data

            if ad_list:
                for item in ad_list[:20]:
                    if not isinstance(item, dict):
                        continue
                    ad = {
                        "headline": item.get("headline")
                        or item.get("title")
                        or item.get("headlines", ""),
                        "descriptions": item.get("descriptions")
                        or item.get("description")
                        or [],
                        "url": item.get("url")
                        or item.get("display_url")
                        or item.get("landing_page", ""),
                        "raw": item.get("text") or item.get("copy") or "",
                    }
                    # 如果 headline 是列表（Google Ads 有多个标题行）
                    if isinstance(ad["headline"], list):
                        ad["headline"] = " | ".join(str(h) for h in ad["headline"] if h)
                    # 如果 descriptions 是字符串，转为列表
                    if isinstance(ad["descriptions"], str):
                        ad["descriptions"] = [ad["descriptions"]]
                    # 也尝试从创意字段提取（SEMrush特有字段名）
                    if not ad["headline"]:
                        ad["headline"] = (
                            item.get("creative_title")
                            or item.get("ad_title")
                            or item.get("visible_url", "")
                        )
                    if not ad["descriptions"] or ad["descriptions"] == [""]:
                        desc = (
                            item.get("creative_snippet")
                            or item.get("text_description")
                            or item.get("snippet", "")
                        )
                        if desc:
                            ad["descriptions"] = (
                                [desc] if isinstance(desc, str) else desc
                            )
                    if ad["headline"] or ad["raw"]:
                        ads.append(ad)

            if ads:
                # 过滤无效广告
                valid_ads = self._filter_valid_ads(ads, data.get("domain", ""))
                data["ad_copies"] = valid_ads
                print(f"   [API解析] 广告文案: {len(valid_ads)} 条（原始{len(ads)}条）")
            else:
                debug_file = OUTPUT_DIR / f"semrush_api_ads_raw_{int(time.time())}.json"
                debug_file.write_text(
                    json.dumps(api_data, ensure_ascii=False, indent=2)[:50000],
                    encoding="utf-8",
                )
                print(f"   [API解析] 广告文案格式未知，原始数据已保存: {debug_file}")
        except Exception as e:
            print(f"   [API解析] 广告文案解析失败: {e}")

    def check_login_status(self):
        """检查是否已登录（多重检测）"""
        try:
            current_url = self.page.url

            # 检测1：URL已离开登录页 → 大概率已登录
            if (
                "/login" not in current_url
                and "login" not in current_url.lower().split("/")[-1]
            ):
                login_form = self.page.locator(
                    "input[placeholder='请输入账号'], input[placeholder*='密码'], input[type='password']"
                ).count()
                if login_form == 0:
                    print(f"   [检测] URL已离开登录页: {current_url}")
                    return True

            # 检测2：Cookie中存在登录态
            try:
                cookies = self.context.cookies()
                for cookie in cookies:
                    name_lower = cookie.get("name", "").lower()
                    if any(
                        k in name_lower for k in ["token", "session", "auth", "sid"]
                    ):
                        if "waimaoxia" in cookie.get(
                            "domain", ""
                        ) or "waimaoxia" in cookie.get("path", ""):
                            print(f"   [检测] 找到登录Cookie: {cookie.get('name')}")
                            return True
            except:
                pass

            # 检测3：页面上有已登录标志元素
            logged_in_selectors = [
                ".user-info",
                ".user-name",
                ".avatar",
                ".user-avatar",
                ".header-user",
                ".nav-user",
                '[class*="user"]',
                '[class*="avatar"]',
                ".el-dropdown",
            ]
            for sel in logged_in_selectors:
                if self.page.locator(sel).count() > 0:
                    print(f"   [检测] 找到已登录元素: {sel}")
                    return True

            # 检测4：页面文本检测
            try:
                page_text = self.page.inner_text("body", timeout=3000)
                logged_in_keywords = [
                    "退出",
                    "个人中心",
                    "会员中心",
                    "我的账户",
                    "欢迎回来",
                    "注销",
                    "工具包",
                    "SEO工具",
                    "VIP",
                    "到期时间",
                    "dashboard",
                    "logout",
                ]
                for kw in logged_in_keywords:
                    if kw in page_text:
                        print(f"   [检测] 页面含已登录关键词: {kw}")
                        return True

                # 登录页特征消失
                login_keywords = [
                    "立即登录",
                    "请输入账号",
                    "请输入密码",
                    "记住密码",
                    "忘记密码",
                ]
                has_login_keyword = any(kw in page_text for kw in login_keywords)
                if not has_login_keyword and "/login" not in current_url:
                    print(f"   [检测] 登录页关键词消失且URL已变，判定已登录")
                    return True
            except:
                pass

            return False
        except:
            return None

    def open_login_page(self):
        """打开外贸侠登录页"""
        # 如果已经在 SEMrush 概览页且有查询参数，跳过登录检查
        current_url = self.page.url
        if (
            "wmxpro" in current_url
            and "overview" in current_url
            and "q=" in current_url
        ):
            print("✅ 已在 SEMrush 概览页，跳过登录检查")
            return True

        print(f"\n🌐 打开登录页: {WAIMAOXIA_LOGIN_URL}")
        self.page.goto(
            WAIMAOXIA_LOGIN_URL, wait_until="domcontentloaded", timeout=30000
        )
        time.sleep(3)

        # 检查是否已登录
        status = self.check_login_status()
        if status is True:
            print("✅ 检测到已登录状态")
            return True

        print("⏳ 等待用户手动登录...")
        print("   请在浏览器中完成登录操作")

        # 等待登录完成
        max_wait = 300
        for i in range(max_wait):
            time.sleep(1)
            status = self.check_login_status()
            if status is True:
                print(f"✅ 检测到登录成功！({i + 1}秒)")
                return True
            if (i + 1) % 10 == 0:
                current_url = self.page.url
                print(f"   已等待 {i + 1} 秒... 当前URL: {current_url}")
                # URL已离开登录页，直接继续
                if "/login" not in current_url:
                    print(f"   ⚠️ URL已离开登录页，尝试直接继续...")
                    return True

        print("❌ 等待登录超时")
        return False

    def navigate_to_semrush(self):
        """导航到 SEMrush 高级版（会新开窗口）"""
        # 如果已经在 SEMrush 概览页，跳过导航
        current_url = self.page.url
        if "wmxpro" in current_url and "overview" in current_url:
            print("✅ 已在 SEMrush 概览页，跳过导航")
            return True

        print("\n📍 导航到 SEMrush 高级版...")

        # 记录当前页面数量，用于检测新窗口
        pages_before = [p.url for p in self.context.pages]
        print(f"   当前页面数: {len(self.context.pages)}")
        for i, url in enumerate(pages_before):
            print(f"     [{i}] {url}")

        # 方法1：点击 "Semrush 高级版" 菜单（会新开窗口）
        clicked = False
        try:
            print("   尝试点击 'Semrush 高级版'...")
            semrush_btn = self.page.locator("text=Semrush 高级版").first
            if semrush_btn.is_visible(timeout=5000):
                semrush_btn.click()
                clicked = True
                print("   已点击 'Semrush 高级版'")
        except Exception as e:
            print(f"   点击失败: {e}")

        if not clicked:
            # 尝试先展开 SEO工具包
            try:
                print("   尝试先点击 'SEO工具包'...")
                self.page.locator("text=SEO工具包").first.click(timeout=5000)
                time.sleep(2)
                semrush_btn = self.page.locator("text=Semrush 高级版").first
                if semrush_btn.is_visible(timeout=5000):
                    semrush_btn.click()
                    clicked = True
                    print("   已点击 'Semrush 高级版'")
            except Exception as e:
                print(f"   SEO工具包方式失败: {e}")

        # 等待新窗口打开
        if clicked:
            print("   等待新窗口打开...")

            # 使用轮询方式检测新页面
            for i in range(45):  # 增加等待时间到45秒
                time.sleep(1)

                # 重新获取 contexts（关键！新页面可能在新的 context 中）
                try:
                    all_contexts = self.browser.contexts
                except:
                    all_contexts = [self.context]

                # 遍历所有 context 的所有页面
                for ctx in all_contexts:
                    try:
                        current_pages = ctx.pages
                    except:
                        continue

                    for p in current_pages:
                        try:
                            url = p.url
                        except:
                            continue

                        # 检查是否是 wmxpro 页面
                        if "wmxpro" in url or ("analytics" in url and "domain" in url):
                            print(f"   ✅ 检测到 SEMrush 页面: {url}")
                            # 更新 context 和 page
                            self.context = ctx
                            self.page = p
                            # 重新设置 API 拦截器
                            try:
                                self._setup_api_interceptor()
                            except:
                                pass
                            # 等待页面加载
                            try:
                                p.wait_for_load_state("domcontentloaded", timeout=10000)
                            except:
                                pass
                            time.sleep(2)
                            print(f"✅ 已切换到 SEMrush 页面")
                            return True

                # 打印调试信息
                if (i + 1) % 5 == 0:
                    total_pages = sum(
                        len(ctx.pages) for ctx in all_contexts if hasattr(ctx, "pages")
                    )
                    print(f"   等待中... ({i + 1}秒), 总页面数: {total_pages}")

        # 方法2：直接在当前页面打开 SEMrush URL
        print("   尝试直接打开 SEMrush URL...")
        try:
            self.page.goto(
                WMXPRO_URL,
                wait_until="domcontentloaded",
                timeout=20000,
            )
            time.sleep(3)
            if "wmxpro" in self.page.url:
                print(f"✅ 成功加载 SEMrush 页面: {self.page.url}")
                return True
        except Exception as e:
            print(f"   直接打开失败: {e}")

        # 方法3：遍历所有 context 的所有页面找 SEMrush
        print("   遍历所有 context 查找 SEMrush...")
        try:
            for ctx in self.browser.contexts:
                for p in ctx.pages:
                    try:
                        url = p.url
                        print(f"   页面: {url}")
                        if "wmxpro" in url or ("analytics" in url and "domain" in url):
                            self.context = ctx
                            self.page = p
                            try:
                                self._setup_api_interceptor()
                            except:
                                pass
                            print(f"✅ 找到 SEMrush 页面: {url}")
                            time.sleep(3)
                            return True
                    except:
                        continue
        except Exception as e:
            print(f"   遍历页面失败: {e}")

        # 方法4：在当前页面强制导航
        print("   尝试在当前页面强制导航...")
        try:
            # 检查当前页面是否已经是 SEMrush
            if "wmxpro" in self.page.url:
                print(f"✅ 当前页面已经是 SEMrush: {self.page.url}")
                return True

            # 强制导航
            self.page.goto(
                WMXPRO_URL,
                wait_until="networkidle",
                timeout=30000,
            )
            time.sleep(3)
            if "wmxpro" in self.page.url:
                print(f"✅ 强制导航成功: {self.page.url}")
                return True
        except Exception as e:
            print(f"   强制导航失败: {e}")

        print("❌ 无法导航到 SEMrush 页面")
        return False

    def _explore_page_inputs(self):
        """探查页面上的输入框和按钮（用于调试选择器）"""
        print("\n📋 探查页面元素...")

        # 保存完整HTML用于调试
        debug_file = OUTPUT_DIR / f"semrush_explore_{int(time.time())}.html"
        try:
            debug_file.write_text(self.page.content(), encoding="utf-8")
            print(f"   页面HTML已保存: {debug_file}")
        except:
            pass

        # 列出所有 input 元素
        try:
            inputs = self.page.eval_on_selector_all(
                "input",
                """
                els => els.map((e, i) => ({
                    index: i,
                    type: e.type || '',
                    placeholder: e.placeholder || '',
                    name: e.name || '',
                    id: e.id || '',
                    className: e.className || '',
                    visible: e.offsetParent !== null,
                    value: e.value || '',
                }))
            """,
            )
            print(f"\n   找到 {len(inputs)} 个 input 元素:")
            for inp in inputs:
                vis = "✅可见" if inp.get("visible") else "❌隐藏"
                print(
                    f"   [{inp['index']}] {vis} type={inp['type']} placeholder='{inp['placeholder']}' "
                    f"name='{inp['name']}' id='{inp['id']}' class='{inp['className'][:60]}'"
                )
        except Exception as e:
            print(f"   探查input失败: {e}")

        # 列出所有 button 元素
        try:
            buttons = self.page.eval_on_selector_all(
                "button",
                """
                els => els.map((e, i) => ({
                    index: i,
                    text: e.textContent.trim().substring(0, 40),
                    type: e.type || '',
                    className: (e.className || '').substring(0, 60),
                    visible: e.offsetParent !== null,
                }))
            """,
            )
            print(f"\n   找到 {len(buttons)} 个 button 元素:")
            for btn in buttons:
                vis = "✅可见" if btn.get("visible") else "❌隐藏"
                print(
                    f"   [{btn['index']}] {vis} text='{btn['text']}' type={btn['type']} class='{btn['className'][:60]}'"
                )
        except Exception as e:
            print(f"   探查button失败: {e}")

        # 列出所有可点击的 a/span/div（含搜索/查询/分析文字）
        try:
            clickable = self.page.eval_on_selector_all(
                "a, span, div",
                """
                els => els.filter(e => {
                    const t = (e.textContent || '').trim();
                    return t.length > 0 && t.length < 30 && 
                           /查询|搜索|分析|search|analyze|query/i.test(t);
                }).map((e, i) => ({
                    index: i,
                    tag: e.tagName,
                    text: e.textContent.trim().substring(0, 40),
                    className: (e.className || '').substring(0, 60),
                }))
            """,
            )
            if clickable:
                print(f"\n   找到 {len(clickable)} 个搜索/查询相关元素:")
                for el in clickable:
                    print(
                        f"   [{el['index']}] <{el['tag']}> text='{el['text']}' class='{el['className'][:60]}'"
                    )
        except:
            pass

        # 当前URL
        print(f"\n   当前URL: {self.page.url}")
        # 页面标题
        try:
            print(f"   页面标题: {self.page.title()}")
        except:
            pass

        return inputs if "inputs" in dir() else []

    def input_domain(self, domain):
        """输入域名并搜索"""
        print(f"\n🔍 输入域名: {domain}")

        domain = domain.strip().lower()
        domain = domain.replace("https://", "").replace("http://", "")
        domain = domain.replace("www.", "")
        domain = domain.split("/")[0]
        print(f"   清理后: {domain}")

        # 先等待页面加载完成
        time.sleep(3)

        # 尝试多种选择器
        domain_input_selectors = [
            "input[placeholder*='域名']",
            "input[placeholder*='domain']",
            "input[placeholder*='Domain']",
            "input[placeholder*='网址']",
            "input[placeholder*='URL']",
            "input[placeholder*='网站']",
            "input.domain-input",
            "input.search-input",
            "input[type='text']:visible",
            "input:not([type='hidden']):not([type='password']):not([type='checkbox'])",
        ]

        input_el = None
        for sel in domain_input_selectors:
            try:
                count = self.page.locator(sel).count()
                if count > 0:
                    # 检查是否可见
                    first = self.page.locator(sel).first
                    if first.is_visible(timeout=2000):
                        input_el = first
                        print(f"   找到输入框: {sel}")
                        break
            except:
                continue

        if not input_el:
            # 探查页面结构
            print("   ⚠️ 预设选择器均未匹配，开始探查页面...")
            inputs_info = self._explore_page_inputs()

            # 根据探查结果智能选择
            for inp in inputs_info or []:
                if not inp.get("visible"):
                    continue
                inp_type = inp.get("type", "")
                inp_ph = inp.get("placeholder", "")
                # 跳过明显不是域名的输入框
                if inp_type in (
                    "password",
                    "checkbox",
                    "radio",
                    "hidden",
                    "submit",
                    "file",
                ):
                    continue
                # 优先选有提示文字的
                if any(
                    kw in inp_ph.lower()
                    for kw in [
                        "domain",
                        "域名",
                        "url",
                        "网址",
                        "网站",
                        "keyword",
                        "关键词",
                    ]
                ):
                    try:
                        sel = f"input:nth-of-type({inp['index'] + 1})"
                        input_el = self.page.locator(sel).first
                        print(
                            f"   智能匹配输入框: placeholder='{inp_ph}' type={inp_type}"
                        )
                        break
                    except:
                        continue

            # 最后兜底：取页面上第一个可见的text输入框
            if not input_el:
                try:
                    first_visible = self.page.locator("input[type='text']").first
                    if first_visible.is_visible(timeout=2000):
                        input_el = first_visible
                        print("   兜底：使用页面上第一个可见text输入框")
                except:
                    pass

        if not input_el:
            print("❌ 页面上未找到任何可用的输入框")
            self._explore_page_inputs()  # 再探查一次方便排查
            return False

        try:
            input_el.fill("")
            input_el.fill(domain)
            time.sleep(1)

            # 尝试点击搜索按钮
            search_selectors = [
                "button:has-text('查询')",
                "button:has-text('搜索')",
                "button:has-text('分析')",
                "button:has-text('Search')",
                "button:has-text('Analyze')",
                "button[type='submit']",
                "button.search",
                ".search-btn",
                ".search-button",
            ]
            clicked = False
            for sel in search_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        print(f"   已点击搜索按钮: {sel}")
                        clicked = True
                        break
                except:
                    continue

            if not clicked:
                # 回车提交
                print("   未找到搜索按钮，尝试回车提交")
                input_el.press("Enter")

            time.sleep(5)
            try:
                self.page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass
            print("✅ 搜索结果已加载")
            return True

        except Exception as e:
            print(f"❌ 输入域名失败: {e}")
            return False

    def extract_data(self):
        """提取 SEMrush 数据（优先使用API拦截数据，文本解析作为fallback）"""
        print("\n📊 提取数据...")

        data = {
            "domain": "",
            "traffic": {},
            "organic_keywords": {"total": 0, "trend": [], "top_keywords": []},
            "paid_keywords": {"total": 0, "trend": [], "top_keywords": []},
            "competitors": [],
            "referring_sources": [],
            "serp_distribution": {},
            "branded_traffic": {},
            "country_traffic": [],  # 按国家/地区划分的流量数据
            "ad_copies": [],
            "raw_text_snippet": "",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        try:
            # 0. 滚动页面确保所有内容加载
            print("   滚动页面加载所有内容...")
            for i in range(15):
                self.page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.3)
            time.sleep(2)

            # 保存页面用于调试
            debug_file = OUTPUT_DIR / f"semrush_page_{int(time.time())}.html"
            debug_file.write_text(self.page.content(), encoding="utf-8")
            print(f"   页面已保存: {debug_file}")

            # 1. 提取页面全部文本
            page_text = ""
            try:
                page_text = self.page.inner_text("body", timeout=10000)
                data["raw_text_snippet"] = page_text[:5000]
            except:
                pass

            # 2. 提取域名（从搜索框或页面文本）
            try:
                search_input = self.page.locator(
                    "input[placeholder*='域名'], input[placeholder*='domain'], input[placeholder*='Domain']"
                ).first
                if search_input.is_visible(timeout=2000):
                    data["domain"] = search_input.input_value().strip()
            except:
                pass
            if not data["domain"]:
                import re

                dm = re.search(
                    r"([a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2})?)", page_text[:500]
                )
                if dm:
                    data["domain"] = dm.group(1)

            # ═══════════════════════════════════════════════
            # 3. 【优先】从API拦截数据中提取
            # ═══════════════════════════════════════════════
            api_intercepted = sum(
                1
                for v in self._api_responses.values()
                if v is not None and not isinstance(v, list)
            )
            raw_api_count = len(self._api_responses.get("raw_api_urls", []))
            print(
                f"   [API拦截] 已捕获 {raw_api_count} 个API请求，{api_intercepted} 类数据"
            )

            # 3a. 解析概览API数据
            if self._api_responses.get("overview"):
                self._parse_api_overview(self._api_responses["overview"], data)

            # 3b. 解析自然关键词API数据
            if self._api_responses.get("organic_keywords"):
                self._parse_api_keywords(
                    self._api_responses["organic_keywords"], data, "organic"
                )

            # 3c. 解析付费关键词API数据
            if self._api_responses.get("paid_keywords"):
                self._parse_api_keywords(
                    self._api_responses["paid_keywords"], data, "paid"
                )

            # 3d. 解析广告文案API数据
            if self._api_responses.get("ad_copies"):
                self._parse_api_ad_copies(self._api_responses["ad_copies"], data)

            # 3e. 解析竞品API数据
            if self._api_responses.get("competitors_organic"):
                self._parse_api_competitors(
                    self._api_responses["competitors_organic"], data, "organic"
                )
            if self._api_responses.get("competitors_paid"):
                self._parse_api_competitors(
                    self._api_responses["competitors_paid"], data, "paid"
                )

            # 3f. 解析引用来源API数据（RPC格式：result.sources）
            if self._api_responses.get("referring_sources"):
                self._parse_api_referring_sources(
                    self._api_responses["referring_sources"], data
                )

            # ═══════════════════════════════════════════════
            # 3b. 【JS数据提取】从页面React/DOM中提取结构化数据
            # ═══════════════════════════════════════════════
            self._extract_data_via_js(data, page_text)

            # ═══════════════════════════════════════════════
            # 4. 【Fallback】文本解析补充缺失数据
            # ═══════════════════════════════════════════════
            # 流量数据 — 如果API没覆盖，用文本解析补充
            if not data["traffic"].get("organic") or not data["traffic"].get("paid"):
                self._extract_traffic_from_text(page_text, data)

            # 竞品数据 — 如果API没覆盖
            if not data["competitors"] and not data["referring_sources"]:
                self._extract_competitors_from_text(page_text, data)

            # 广告文案 — 如果API没捕获到，用DOM/文本解析兜底
            if not data["ad_copies"]:
                self._extract_ads_data(data)

            # 关键词 — 如果API没捕获到，用DOM/文本解析兜底
            if not data["organic_keywords"].get("top_keywords") and not data[
                "paid_keywords"
            ].get("top_keywords"):
                self._extract_keywords_data(data)

            # SERP分布（只有文本解析）
            if not data["serp_distribution"]:
                self._extract_serp_distribution(page_text, data)

            # 按国家/地区划分的流量数据
            self._extract_country_traffic(page_text, data)

            # 最终摘要
            print(f"   域名: {data['domain']}")
            print(f"   流量数据: {list(data['traffic'].keys())}")
            organic_comp = [
                c for c in data["competitors"] if c.get("type") == "organic"
            ]
            paid_comp = [c for c in data["competitors"] if c.get("type") == "paid"]
            print(
                f"   SEO竞品: {len(organic_comp)}, 付费竞品: {len(paid_comp)}, 引用来源: {len(data.get('referring_sources', []))}"
            )
            print(
                f"   自然关键词: {data['organic_keywords'].get('total', 'N/A')} (详细{len(data['organic_keywords'].get('top_keywords', []))}条)"
            )
            print(
                f"   付费关键词: {data['paid_keywords'].get('total', 'N/A')} (详细{len(data['paid_keywords'].get('top_keywords', []))}条)"
            )
            print(f"   广告文案: {len(data['ad_copies'])} 条")
            print(f"   SERP分布: {data['serp_distribution']}")
            print(f"   国家/地区: {len(data.get('country_traffic', []))} 个")

            # 保存API拦截的原始URL列表供调试
            if self._api_responses.get("raw_api_urls"):
                api_log_file = OUTPUT_DIR / f"semrush_api_urls_{int(time.time())}.txt"
                api_log_file.write_text(
                    "\n".join(self._api_responses["raw_api_urls"]), encoding="utf-8"
                )
                print(f"   API URL列表已保存: {api_log_file}")

            return data

        except Exception as e:
            print(f"❌ 提取数据失败: {e}")
            import traceback

            traceback.print_exc()
            return data

    def _navigate_subpages_for_api(self, data):
        """主动导航到关键词/广告子页面，触发API请求以获取数据

        SEMrush 的数据是按需加载的（懒加载）：
        - 概览页只加载摘要数据
        - 点击到子页面才会请求详细数据
        - 我们利用API拦截器，在导航时捕获响应

        导航策略：优先使用侧边栏点击导航（比直接URL跳转更稳定），
        因为直接跳转有时会被wmxpro重定向回概览页。
        """
        import re

        domain = data.get("domain", "")
        if not domain:
            return

        base_url = "/".join(self.page.url.split("/")[:3])

        # 提取当前URL中的db参数
        db_param = "us"
        db_match = re.search(r"[?&]db=(\w+)", self.page.url)
        if db_match:
            db_param = db_match.group(1)

        # 1. 导航到自然搜索关键词页面（如果还没拿到关键词数据）
        if not data["organic_keywords"].get("top_keywords"):
            try:
                # 优先使用侧边栏导航
                sidebar_navigated = False
                for sel in [
                    "text=自然搜索研究",
                    "text=Organic Research",
                    "text=自然搜索",
                    '[data-at*="organic"] a',
                    'a[href*="organic/overview"]',
                ]:
                    try:
                        link = self.page.locator(sel).first
                        if link.is_visible(timeout=3000):
                            link.click()
                            time.sleep(3)
                            sidebar_navigated = True
                            print(f"   [导航] 侧边栏点击: {sel}")
                            break
                    except:
                        continue

                if not sidebar_navigated:
                    organic_url = f"{base_url}/analytics/organic/overview?db={db_param}&q={domain}&searchType=domain"
                    print(f"   [导航] 自然搜索关键词: {organic_url}")
                    self.page.goto(
                        organic_url, wait_until="domcontentloaded", timeout=20000
                    )
                    time.sleep(5)

                try:
                    self.page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass

                # 等待RPC请求完成
                time.sleep(3)

                # 尝试点击关键词标签加载更多
                for tab_sel in [
                    "text=关键词",
                    "text=Keywords",
                    "text=排名",
                    "text=Positions",
                ]:
                    try:
                        tab = self.page.locator(tab_sel).first
                        if tab.is_visible(timeout=3000):
                            tab.click()
                            time.sleep(3)
                            break
                    except:
                        continue

                # 检查API是否拦截到了数据
                if self._api_responses.get("organic_keywords"):
                    self._parse_api_keywords(
                        self._api_responses["organic_keywords"], data, "organic"
                    )
                    if data["organic_keywords"].get("top_keywords"):
                        print(
                            f"   [导航成功] 自然关键词: {len(data['organic_keywords']['top_keywords'])} 条"
                        )

                # 如果API没拿到，尝试JS DOM提取
                if not data["organic_keywords"].get("top_keywords"):
                    self._extract_data_via_js(data)

            except Exception as e:
                print(f"   [导航失败] 自然关键词: {e}")

        # 2. 导航到广告研究页面（获取付费关键词和广告文案）
        #    先检查是否需要获取付费关键词或广告文案
        need_paid_keywords = not data["paid_keywords"].get("top_keywords")
        need_ad_copies = not data["ad_copies"]

        if need_paid_keywords or need_ad_copies:
            try:
                # 优先使用侧边栏导航
                sidebar_navigated = False
                for sel in [
                    "text=广告研究",
                    "text=Advertising Research",
                    "text=Ad Research",
                    '[data-at*="adwords"] a',
                    'a[href*="adwords"]',
                ]:
                    try:
                        link = self.page.locator(sel).first
                        if link.is_visible(timeout=3000):
                            link.click()
                            time.sleep(3)
                            sidebar_navigated = True
                            print(f"   [导航] 侧边栏点击: {sel}")
                            break
                    except:
                        continue

                if not sidebar_navigated:
                    ad_url = f"{base_url}/analytics/adwords/positions?db={db_param}&q={domain}&searchType=domain"
                    print(f"   [导航] 广告研究: {ad_url}")
                    self.page.goto(ad_url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(5)

                try:
                    self.page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass

                # 等待RPC请求完成
                time.sleep(3)

                # 2a. 先尝试获取付费关键词（点击"关键词"标签）
                if need_paid_keywords:
                    print("   [导航] 尝试获取付费关键词...")
                    # 尝试点击"关键词"标签
                    for tab_sel in [
                        "text=关键词",
                        "text=Keywords",
                        "text=排名",
                        "text=Positions",
                        'a[href*="positions"]',
                        '[data-at*="positions"]',
                    ]:
                        try:
                            tab = self.page.locator(tab_sel).first
                            if tab.is_visible(timeout=3000):
                                tab.click()
                                time.sleep(3)
                                print(f"   [导航] 点击关键词标签: {tab_sel}")
                                break
                        except:
                            continue

                    # 等待数据加载
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass
                    time.sleep(2)

                    # 检查API是否拦截到了付费关键词数据
                    if self._api_responses.get("paid_keywords"):
                        self._parse_api_keywords(
                            self._api_responses["paid_keywords"], data, "paid"
                        )
                        if data["paid_keywords"].get("top_keywords"):
                            print(
                                f"   [导航成功] 付费关键词: {len(data['paid_keywords']['top_keywords'])} 条"
                            )

                    # 如果API没拿到，尝试从页面提取
                    if not data["paid_keywords"].get("top_keywords"):
                        self._extract_paid_keywords(data)

                # 2b. 然后尝试获取广告文案（点击"广告副本"标签）
                if need_ad_copies:
                    print("   [导航] 尝试获取广告文案...")
                    # 尝试点击"广告副本"标签
                    for tab_sel in [
                        "text=广告副本",
                        "text=文字广告",
                        "text=Ad Copies",
                        "text=Text Ads",
                        'a[href*="ads"]',
                        '[data-at*="ads"]',
                    ]:
                        try:
                            tab = self.page.locator(tab_sel).first
                            if tab.is_visible(timeout=3000):
                                tab.click()
                                time.sleep(3)
                                print(f"   [导航] 点击广告副本标签: {tab_sel}")
                                break
                        except:
                            continue

                    # 等待数据加载
                    try:
                        self.page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass
                    time.sleep(2)

                    # 检查API是否拦截到了广告文案数据
                    if self._api_responses.get("ad_copies"):
                        self._parse_api_ad_copies(
                            self._api_responses["ad_copies"], data
                        )
                        if data["ad_copies"]:
                            print(
                                f"   [导航成功] 广告文案: {len(data['ad_copies'])} 条"
                            )

                    # 如果API还是没拿到，尝试从页面文本提取
                    if not data["ad_copies"]:
                        page_text = ""
                        try:
                            page_text = self.page.inner_text("body", timeout=10000)
                        except:
                            pass
                        if page_text:
                            ad_copies = self._parse_ad_samples_from_text(
                                page_text, domain
                            )
                            if ad_copies:
                                # 质量过滤
                                valid_ads = self._filter_valid_ads(ad_copies, domain)
                                if valid_ads:
                                    data["ad_copies"] = valid_ads
                                    print(
                                        f"   [页面提取] 广告文案: {len(valid_ads)} 条"
                                    )

                    # 如果文本也没拿到，尝试JS DOM提取
                    if not data["ad_copies"]:
                        self._extract_data_via_js(data)

            except Exception as e:
                print(f"   [导航失败] 广告研究: {e}")

        # 4. 最终备选方案：截图+OCR提取
        #    如果前面的方法都没有获取到数据，使用OCR作为最终备选
        if not data["paid_keywords"].get("top_keywords") or not data["ad_copies"]:
            print("\n   📸 尝试截图+OCR备选方案...")

            # 4a. 付费关键词OCR提取
            if not data["paid_keywords"].get("top_keywords"):
                try:
                    self._extract_paid_keywords_by_ocr(data)
                except Exception as e:
                    print(f"   OCR提取付费关键词失败: {e}")

            # 4b. 广告文案OCR提取
            if not data["ad_copies"]:
                try:
                    self._extract_ad_copies_by_ocr(data)
                except Exception as e:
                    print(f"   OCR提取广告文案失败: {e}")

        # 5. 导航回概览页
        try:
            overview_url = (
                f"{base_url}/analytics/overview/?searchType=domain&q={domain}"
            )
            self.page.goto(overview_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)
        except:
            pass

    def _filter_valid_ads(self, ad_copies, domain):
        """过滤有效的广告文案，去除SEMrush UI文本等误识别

        SEMrush页面上有很多平台自身的推广文本，容易被误识别为广告文案。
        真正的Google Ads广告文案特征：
        - 标题≤30字符，描述≤90字符
        - 包含产品/服务关键词
        - 通常有明确的URL
        - 多为英文（美国市场广告）
        """
        if not ad_copies:
            return []

        # SEMrush平台UI描述文本特征（中文推广/说明文本）
        semrush_ui_markers = [
            "全面了解域名",
            "分析域名随时间",
            "查看域名占据主导",
            "发现为域名吸引",
            "比较不同国家",
            "将报告轻松导出",
            "请勿出售我的个人信息",
            "开始使用 Semrush",
            "查看套餐和价格",
            "请求专属演示",
            "获取免费一对一",
            "我们的专员将从头指导",
            "获取完整分析",
            "评估域名在特定时期",
            "节省用于摘要分析",
            "揭示和分析特定国家",
            "通过一站式获取",
            "Cookie 设置",
            "使用条款",
            "隐私政策",
            # 更多SEMrush UI特征
            "Semrush 平台",
            "semrush平台",
            "充分利用 Semrush",
            "从头指导您逐步了解",
            "专员将从头指导",
            "比较多达五个竞争对手",
            "反向链接数量",
            "自然搜索流量、付费搜索流量",
            "自然流量、付费流量和反向链接",
            "摘要分析的时间",
            "一份报告中比较",
            "特定国家或全球的关键指标",
            "特定时期",
            "获取免费",
            "专属演示",
            "一对一",
            # 2026-04-10 新增：从beautybyearth采集中发现的遗漏
            "Semrush. 版权所有",
            "© 2008",
            "联系我们",
            "发送反馈",
            "用户手册",
            "导出成 PDF",
            "按国家/地区进行比较",
            "增长审核",
            "跳到内容",
            "更多",
            "首页",
            # 2026-04-10 新增：外贸侠/SEMrush 推广文本特征
            "获取竞争对手或潜在客户优劣的即时见解",
            "全面了解域名及其在线可见度",
            "分析域名随时间的增长趋势",
            "查看域名占据主导地位的市场",
            "发现为域名吸引自然和付费搜索流量的主题和关键词",
            "选择域名类型：根域名、子域名、子文件夹",
            "通过一站式获取域名增长趋势的关键数据来节省报告时间",
            "将报告轻松导出为 xls 或 csv",
            "比较不同国家中域名的自然搜索和付费搜索效果",
            "查看特定市场域名的自然份额",
            "将趋势导出为 xls 或 csv",
            "我们的专员将从头指导您逐步了解如何充分利用",
            "请求专属演示",
            "域名概览",
        ]

        # JS代码特征
        js_code_indicators = {
            "static_url",
            "is_legacy",
            "csrfToken",
            "cookie_domain",
            "searchbarApi",
            "PopupManager",
            "switchLanguage",
            "upgrade_button",
            "function(",
            "var w=window",
            "Intercom",
            "reattach_activator",
            "DOMContentLoaded",
            "wmxpro.com/static",
        }

        # 纯中文指标 — 真正的美国市场广告应该是英文
        # 如果广告文案全部是中文字符，极大概率是SEMrush平台文本
        def _is_mostly_chinese(text):
            """检查文本是否大部分是中文字符"""
            if not text:
                return False
            chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
            total_chars = sum(
                1 for c in text if c.isalpha() or "\u4e00" <= c <= "\u9fff"
            )
            if total_chars == 0:
                return False
            return chinese_chars / total_chars > 0.5  # 超过50%中文
            # 注意：即使headline含英文域名，description全是中文也是SEMrush UI

        def _descriptions_mostly_chinese(descriptions):
            """专门检查descriptions列表是否大部分中文"""
            if not descriptions or not isinstance(descriptions, list):
                return False
            all_desc = " ".join(str(d) for d in descriptions)
            return _is_mostly_chinese(all_desc)

        valid = []
        for ad in ad_copies:
            raw = ad.get("raw", "") or ""
            headline = ad.get("headline", "") or ""
            descriptions = ad.get("descriptions", []) or []
            desc_text = (
                " ".join(descriptions)
                if isinstance(descriptions, list)
                else str(descriptions)
            )
            combined = f"{headline} {raw} {desc_text}"

            # 检查是否包含SEMrush UI文本
            is_ui = any(marker in combined for marker in semrush_ui_markers)
            # 检查是否包含JS代码
            is_js = any(ind in combined for ind in js_code_indicators)
            # 太短的不太可能是广告
            is_short = len(raw.strip()) < 20 and len(headline.strip()) < 10
            # 太长的可能是页面描述
            is_long = len(raw) > 500
            # 大部分是中文 → 很可能是SEMrush平台UI文本，不是美国市场广告
            is_chinese_ui = _is_mostly_chinese(combined)
            # descriptions全部是中文 → 即使headline有英文域名，也是SEMrush UI
            is_desc_chinese = _descriptions_mostly_chinese(descriptions)

            # 新增：检查是否是"域名作为headline + 中文描述"的SEMrush UI
            # 真实的Google Ads广告不会只有域名作为headline
            is_domain_only_headline = False
            if headline and not raw:
                # headline只是域名（如 "beautybyearth.com"）
                import re

                domain_pattern = r"^[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}$"
                if re.match(domain_pattern, headline.strip()):
                    is_domain_only_headline = True

            # 新增：检查是否有真实的广告文案特征
            # 真实的Google Ads广告通常有：
            # - 吸引人的标题（不只是域名）
            # - 产品/服务描述（英文）
            # - 行动号召（Shop Now, Learn More等）
            has_ad_features = False
            ad_call_to_action = [
                "shop",
                "buy",
                "order",
                "get",
                "try",
                "free",
                "save",
                "best",
                "top",
                "now",
                "today",
                "limited",
                "offer",
                "discount",
                "sale",
                "learn",
                "discover",
                "find",
            ]
            headline_lower = headline.lower()
            desc_lower = desc_text.lower()
            if any(
                cta in headline_lower or cta in desc_lower for cta in ad_call_to_action
            ):
                has_ad_features = True
            # 或者有产品相关词汇
            product_words = [
                "product",
                "service",
                "solution",
                "quality",
                "natural",
                "organic",
                "premium",
            ]
            if any(pw in headline_lower or pw in desc_lower for pw in product_words):
                has_ad_features = True

            # 过滤条件：
            # 1. 包含SEMrush UI文本 → 过滤
            # 2. 包含JS代码 → 过滤
            # 3. 太短或太长 → 过滤
            # 4. 大部分是中文 → 过滤
            # 5. descriptions全是中文 → 过滤
            # 6. headline只是域名 + descriptions是中文 → 过滤
            # 7. 没有真实广告特征 + descriptions是中文 → 过滤
            should_filter = (
                is_ui
                or is_js
                or is_short
                or is_long
                or is_chinese_ui
                or is_desc_chinese
            )
            if is_domain_only_headline and is_desc_chinese:
                should_filter = True
            if not has_ad_features and is_desc_chinese:
                should_filter = True

            if not should_filter:
                valid.append(ad)

        return valid

    def _parse_api_competitors(self, api_data, data, comp_type="organic"):
        """从 API 响应中解析竞品数据"""
        if not api_data:
            return
        try:
            comp_list = None
            if isinstance(api_data, dict):
                for path in [
                    "data",
                    "competitors",
                    "results",
                    "data.data",
                    "data.records",
                ]:
                    parts = path.split(".")
                    obj = api_data
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    if isinstance(obj, list) and len(obj) > 0:
                        comp_list = obj
                        break
                if comp_list is None and isinstance(api_data, list):
                    comp_list = api_data

            if comp_list:
                existing_domains = set(c["domain"] for c in data.get("competitors", []))
                for item in comp_list[:10]:
                    if not isinstance(item, dict):
                        continue
                    domain = item.get("domain") or item.get("competitor_domain", "")
                    if domain and domain not in existing_domains:
                        data["competitors"].append(
                            {
                                "domain": domain,
                                "type": comp_type,
                                "common_keywords": item.get("common_keywords")
                                or item.get("keywords", ""),
                                "se_keywords": item.get("se_keywords")
                                or item.get("search_keywords", ""),
                            }
                        )
                        existing_domains.add(domain)
                print(
                    f"   [API解析] {comp_type}竞品: {len([c for c in data['competitors'] if c.get('type') == comp_type])} 条"
                )
            else:
                debug_file = (
                    OUTPUT_DIR
                    / f"semrush_api_comp_{comp_type}_raw_{int(time.time())}.json"
                )
                debug_file.write_text(
                    json.dumps(api_data, ensure_ascii=False, indent=2)[:50000],
                    encoding="utf-8",
                )
                print(
                    f"   [API解析] {comp_type}竞品格式未知，原始数据已保存: {debug_file}"
                )
        except Exception as e:
            print(f"   [API解析] {comp_type}竞品解析失败: {e}")

    def _parse_api_referring_sources(self, api_data, data):
        """从 API 响应中解析引用来源数据

        RPC格式: {jsonrpc, id, result: {sources: [{domain, mentions_count}, ...]}}
        """
        if not api_data:
            return
        try:
            result_obj = api_data.get("result", api_data)
            sources = None

            if isinstance(result_obj, dict) and "sources" in result_obj:
                sources = result_obj["sources"]
            elif isinstance(api_data, dict):
                # 通用搜索
                for path in ["data", "sources", "result.data", "result.sources"]:
                    parts = path.split(".")
                    obj = api_data
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part)
                        else:
                            obj = None
                            break
                    if isinstance(obj, list) and len(obj) > 0:
                        sources = obj
                        break

            if sources and isinstance(sources, list):
                for item in sources[:20]:
                    if not isinstance(item, dict):
                        continue
                    domain = item.get("domain", "")
                    mentions = item.get("mentions_count") or item.get("mentions", 0)
                    if domain:
                        data["referring_sources"].append(
                            {
                                "domain": domain,
                                "mentions": str(mentions),
                            }
                        )
                if data["referring_sources"]:
                    print(f"   [API解析] 引用来源: {len(data['referring_sources'])} 条")
        except Exception as e:
            print(f"   [API解析] 引用来源解析失败: {e}")

    def _extract_data_via_js(self, data, page_text=""):
        """通过JavaScript执行直接从页面DOM提取结构化数据

        SEMrush页面的数据以React组件渲染，DOM中有结构化的表格行、
        数据属性等。通过JS遍历DOM可以更精确地提取数据。
        """
        try:
            # === 提取概览页关键词主题 ===
            if not data["organic_keywords"].get("top_keywords"):
                kw_topics = self.page.evaluate("""() => {
                    const results = [];
                    // SEMrush概览页的"关键主题"区域
                    const topicEls = document.querySelectorAll('[class*="topic"], [class*="Topic"], [data-at*="topic"]');
                    topicEls.forEach(el => {
                        const text = el.textContent || '';
                        if (text.length > 3 && text.length < 100) {
                            results.push(text.trim());
                        }
                    });
                    // 备选：查找包含流量数据的卡片
                    const cards = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="metric"], [class*="Metric"]');
                    cards.forEach(card => {
                        const spans = card.querySelectorAll('span, div, p');
                        let cardText = '';
                        spans.forEach(s => { cardText += (s.textContent || '') + ' | '; });
                        if (cardText.includes('流量') || cardText.includes('Traffic') || cardText.includes('关键词') || cardText.includes('Keyword')) {
                            results.push(cardText.trim());
                        }
                    });
                    return results.slice(0, 20);
                }""")
                if kw_topics:
                    # 保存主题数据供调试
                    try:
                        topic_file = (
                            OUTPUT_DIR / f"semrush_js_topics_{int(time.time())}.json"
                        )
                        topic_file.write_text(
                            json.dumps(kw_topics, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    except:
                        pass

            # === 提取概览页上的关键词表格（如果有关键词列表） ===
            if not data["organic_keywords"].get("top_keywords"):
                js_keywords = self.page.evaluate("""() => {
                    const keywords = [];
                    // 方法1：查找表格行
                    const rows = document.querySelectorAll('tr, [role="row"], [class*="TableRow"], [class*="table-row"]');
                    for (let i = 0; i < Math.min(rows.length, 50); i++) {
                        const cells = rows[i].querySelectorAll('td, [role="cell"], [class*="Cell"]');
                        if (cells.length >= 3) {
                            const row_data = [];
                            cells.forEach(c => row_data.push((c.textContent || '').trim()));
                            keywords.push(row_data);
                        }
                    }
                    
                    // 方法2：查找关键词链接（SEMrush中关键词通常是可点击链接）
                    if (keywords.length === 0) {
                        const kwLinks = document.querySelectorAll('a[href*="keyword"], a[data-at*="keyword"], [class*="keyword-link"]');
                        kwLinks.forEach(link => {
                            const text = (link.textContent || '').trim();
                            if (text.length > 2 && text.length < 100 && !text.includes('Semrush') && !text.includes('查看')) {
                                // 获取同一行的其他数据
                                const parent = link.closest('tr, [role="row"], [class*="Row"]');
                                if (parent) {
                                    keywords.push([text, parent.textContent || '']);
                                }
                            }
                        });
                    }
                    
                    return keywords.slice(0, 30);
                }""")
                if js_keywords and len(js_keywords) > 0:
                    # 保存JS提取的关键词数据
                    try:
                        js_kw_file = (
                            OUTPUT_DIR / f"semrush_js_keywords_{int(time.time())}.json"
                        )
                        js_kw_file.write_text(
                            json.dumps(js_keywords, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        print(
                            f"   [JS提取] 关键词行数据已保存: {js_kw_file.name} ({len(js_keywords)}行)"
                        )
                    except:
                        pass

                    # 尝试从JS提取的数据中解析关键词
                    self._parse_js_keyword_rows(js_keywords, data)

            # === 提取广告文案（从广告研究区域） ===
            if not data["ad_copies"]:
                js_ads = self.page.evaluate("""() => {
                    const ads = [];
                    // 查找广告文案区域
                    // SEMrush广告文案通常在 class 包含 "ad" 的容器中
                    const adContainers = document.querySelectorAll(
                        '[class*="ad-copy"], [class*="AdCopy"], [class*="text-ad"], [class*="TextAd"], ' +
                        '[class*="creative"], [class*="Creative"], [data-at*="ad-copy"]'
                    );
                    
                    adContainers.forEach(container => {
                        const adData = {};
                        // 标题
                        const headline = container.querySelector('[class*="headline"], [class*="Headline"], h3, h4');
                        if (headline) adData.headline = headline.textContent.trim();
                        // 描述
                        const desc = container.querySelector('[class*="description"], [class*="Description"], p');
                        if (desc) adData.description = desc.textContent.trim();
                        // URL
                        const url = container.querySelector('a[href]');
                        if (url) adData.url = url.href;
                        
                        if (adData.headline || adData.description) {
                            ads.push(adData);
                        }
                    });
                    
                    // 备选：查找所有包含美元符号和广告相关文本的块
                    if (ads.length === 0) {
                        const allText = document.querySelectorAll('[class*="position"], [class*="Position"]');
                        allText.forEach(el => {
                            const text = (el.textContent || '').trim();
                            // 检查是否看起来像广告（有URL和描述文本）
                            if (text.includes('$') && text.length > 30 && text.length < 300) {
                                ads.push({raw: text});
                            }
                        });
                    }
                    
                    return ads.slice(0, 20);
                }""")
                if js_ads and len(js_ads) > 0:
                    # 过滤并添加有效的广告文案
                    for ad in js_ads:
                        headline = ad.get("headline", "")
                        desc = ad.get("description", "")
                        url = ad.get("url", "")
                        raw = ad.get("raw", "")

                        # 只添加英文广告文案（美国市场）
                        combined = f"{headline} {desc} {raw}"
                        chinese_chars = sum(
                            1 for c in combined if "\u4e00" <= c <= "\u9fff"
                        )
                        total_alpha = sum(
                            1
                            for c in combined
                            if c.isalpha() or "\u4e00" <= c <= "\u9fff"
                        )
                        if (
                            total_alpha > 0
                            and chinese_chars / max(total_alpha, 1) > 0.5
                        ):
                            continue  # 跳过中文UI文本

                        if headline or desc or raw:
                            data["ad_copies"].append(
                                {
                                    "headline": headline,
                                    "descriptions": [desc] if desc else [],
                                    "url": url,
                                    "raw": raw or f"{headline} {desc}",
                                }
                            )

                    if data["ad_copies"]:
                        # 应用过滤
                        data["ad_copies"] = self._filter_valid_ads(
                            data["ad_copies"], data.get("domain", "")
                        )
                        print(f"   [JS提取] 广告文案: {len(data['ad_copies'])} 条")

            # === 提取竞品数据（从概览页） ===
            if not data["competitors"]:
                js_comps = self.page.evaluate("""() => {
                    const comps = [];
                    // 查找竞品域名链接
                    const domainLinks = document.querySelectorAll('a[href*="analytics/overview"], a[href*="domain"]');
                    domainLinks.forEach(link => {
                        const href = link.href || '';
                        const domainMatch = href.match(/[?&]q=([^&]+)/);
                        if (domainMatch) {
                            comps.push(decodeURIComponent(domainMatch[1]));
                        }
                    });
                    return [...new Set(comps)].slice(0, 10);
                }""")
                if js_comps:
                    for comp_domain in js_comps:
                        if comp_domain != data.get("domain", ""):
                            data["competitors"].append(
                                {
                                    "domain": comp_domain,
                                    "type": "organic",  # 概览页通常是自然搜索竞品
                                }
                            )
                    print(
                        f"   [JS提取] 竞品域名: {[c['domain'] for c in data['competitors'][:5]]}"
                    )

        except Exception as e:
            print(f"   [JS提取] 失败: {e}")

    def _parse_js_keyword_rows(self, js_rows, data):
        """从JS提取的关键词行数据中解析关键词

        JS提取的行数据格式：每行是一个数组，包含单元格文本
        注意：需要过滤掉概览页的国家/地区行（如"US", "CA", "全世界"等）
        """
        import re

        keywords = []

        # 国家/地区代码黑名单（概览页"按国家/地区进行比较"表格数据）
        country_codes = {
            "US",
            "UK",
            "DE",
            "FR",
            "ES",
            "IT",
            "BR",
            "IN",
            "JP",
            "AU",
            "CA",
            "MX",
            "RU",
            "NL",
            "PL",
            "TR",
            "SE",
            "NO",
            "DK",
            "FI",
            "BE",
            "AT",
            "CH",
            "PT",
            "CZ",
            "IE",
            "NZ",
            "ZA",
            "SG",
            "HK",
            "TW",
            "KR",
            "TH",
            "PH",
            "MY",
            "ID",
            "VN",
            "AR",
            "CL",
            "CO",
            "PE",
            "EC",
            "VE",
            "全世界",
            "全球",
            "Worldwide",
            "Global",
            "Sortable",
        }
        # 两字母国家代码模式
        country_pattern = re.compile(r"^[A-Z]{2}$")

        for row in js_rows:
            if not isinstance(row, list) or len(row) < 3:
                continue

            # 第一列通常是关键词
            kw_text = str(row[0]).strip()
            # 过滤掉表头和无效数据
            if kw_text in ("关键词", "Keyword", "Sortable", "", "—"):
                continue
            # 过滤纯数字（排名列）
            if kw_text.isdigit():
                continue
            # 关键词应该包含字母
            if not any(c.isalpha() for c in kw_text):
                continue
            # 过滤国家/地区代码
            if kw_text in country_codes or country_pattern.match(kw_text):
                continue
            # 过滤中文地区名（如"全世界"）或纯中文短文本（2-4个汉字，可能是国家名）
            if len(kw_text) <= 4 and all("\u4e00" <= c <= "\u9fff" for c in kw_text):
                continue

            kw_entry = {"keyword": kw_text}

            # 尝试从其他列提取数据
            for cell_text in row[1:]:
                cell_text = str(cell_text).strip()
                # 匹配排名
                pos_match = re.match(r"^(\d+)$", cell_text)
                if pos_match and "position" not in kw_entry:
                    kw_entry["position"] = int(pos_match.group(1))
                    continue
                # 匹配搜索量
                vol_match = re.match(r"^([0-9.,]+[KMB]?)$", cell_text)
                if vol_match and "volume" not in kw_entry:
                    kw_entry["volume"] = vol_match.group(1)
                    continue
                # 匹配CPC
                cpc_match = re.match(r"^\$?([0-9.]+)$", cell_text)
                if cpc_match and "cpc" not in kw_entry:
                    kw_entry["cpc"] = cpc_match.group(1)
                    continue
                # 匹配意图
                if cell_text in (
                    "C",
                    "I",
                    "N",
                    "B",
                    "T",
                    "Commercial",
                    "Informational",
                    "Navigational",
                    "Transactional",
                ):
                    kw_entry["intent"] = cell_text
                    continue

            if len(kw_entry) > 1:  # 至少有关键词+一个其他字段
                keywords.append(kw_entry)
                if len(keywords) >= 30:
                    break

        if keywords:
            data["organic_keywords"]["top_keywords"] = keywords
            print(f"   [JS提取] 解析到 {len(keywords)} 个关键词")

    def _extract_traffic_from_text(self, page_text, data):
        """从页面文本中提取流量数据"""
        import re

        try:
            # 匹配流量数字模式：如 "16.7K", "33.4K", "50.1K"
            # 尝试找到 "自然流量" 相关数字
            organic_match = re.search(r"自然流量[^0-9]*([0-9.,]+[KMB]?)", page_text)
            if organic_match:
                data["traffic"]["organic"] = organic_match.group(1)

            paid_match = re.search(r"付费流量[^0-9]*([0-9.,]+[KMB]?)", page_text)
            if paid_match:
                data["traffic"]["paid"] = paid_match.group(1)

            brand_match = re.search(r"品牌流量[^0-9]*([0-9.,]+[KMB]?)", page_text)
            if brand_match:
                data["traffic"]["branded"] = brand_match.group(1)

            # 流量成本
            cost_match = re.search(
                r"(?:流量成本|流量价值)[^0-9$]*\$?([0-9.,]+[KMB]?)", page_text
            )
            if cost_match:
                data["traffic"]["cost"] = cost_match.group(1)

            # 权威分数
            auth_match = re.search(
                r"(?:权威分数|Authority Score)[^0-9]*([0-9]+)", page_text
            )
            if auth_match:
                data["traffic"]["authority_score"] = int(auth_match.group(1))

            # 自然关键词总数
            kw_match = re.search(r"自然搜索关键词[^0-9]*([0-9.,]+[KMB]?)", page_text)
            if kw_match:
                data["organic_keywords"]["total"] = kw_match.group(1)

            # 付费关键词总数
            paid_kw_match = re.search(r"付费关键词[^0-9]*([0-9.,]+[KMB]?)", page_text)
            if paid_kw_match:
                data["paid_keywords"]["total"] = paid_kw_match.group(1)

            print(
                f"   流量提取: organic={data['traffic'].get('organic')}, "
                f"paid={data['traffic'].get('paid')}, "
                f"auth={data['traffic'].get('authority_score')}"
            )

        except Exception as e:
            print(f"   流量提取失败: {e}")

    def _extract_competitors_from_text(self, page_text, data):
        """从页面文本中提取竞品数据（区分引用来源 vs SEO竞品 vs 付费竞品）"""
        import re

        try:
            # 1. 提取"主要自然搜索竞争对手"（真正的SEO竞品）
            # 概览页结构：主要自然搜索竞争对手 → 竞争程度 共同关键词 SE关键词 → 域名+数字
            organic_comp_headers = [
                "主要自然搜索竞争对手",
                "自然搜索竞争对手",
                "自然搜索竞品",
                "Top Organic Competitors",
                "Organic Competitors",
                "主要自然搜索竞品",
            ]
            for header in organic_comp_headers:
                if header in page_text:
                    idx = page_text.find(header)
                    section = page_text[idx : idx + 2000]
                    # 格式：域名\n共同关键词数\nSE关键词数
                    domain_number = re.findall(
                        r"([a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2})?)\n([0-9.,]+[KMB]?)",
                        section,
                    )
                    seen = set()
                    for domain, num in domain_number:
                        if domain not in seen and domain != data.get("domain", ""):
                            seen.add(domain)
                            data["competitors"].append(
                                {
                                    "domain": domain,
                                    "type": "organic",
                                    "common_keywords": num,
                                }
                            )
                            if len(data["competitors"]) >= 10:
                                break
                    if data["competitors"]:
                        print(
                            f"   SEO竞品: {[c['domain'] for c in data['competitors'] if c.get('type') == 'organic'][:5]}"
                        )
                    break

            # 2. 提取"引用来源"（单独存储，不混入竞品）
            ref_headers = [
                "主要的引用来源",
                "引用来源",
                "Main Referring Sources",
                "Referring Sources",
            ]
            for header in ref_headers:
                if header in page_text:
                    idx = page_text.find(header)
                    section = page_text[idx : idx + 1000]
                    domain_number = re.findall(
                        r"([a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2})?)\n([0-9.,]+[KMB]?)",
                        section,
                    )
                    refs = []
                    for domain, num in domain_number:
                        refs.append({"domain": domain, "mentions": num})
                        if len(refs) >= 5:
                            break
                    if refs:
                        data["referring_sources"] = refs
                        print(f"   引用来源: {[r['domain'] for r in refs]}")
                    break

            # 3. 提取"主要付费搜索竞争对手"
            paid_comp_headers = [
                "主要付费搜索竞争对手",
                "付费搜索竞争对手",
                "付费搜索竞品",
                "Top Paid Competitors",
                "Paid Competitors",
                "广告竞品",
            ]
            for header in paid_comp_headers:
                if header in page_text:
                    idx = page_text.find(header)
                    section = page_text[idx : idx + 1500]
                    domain_number = re.findall(
                        r"([a-z0-9][-a-z0-9]*\.[a-z]{2,}(?:\.[a-z]{2})?)\n([0-9.,]+[KMB]?)",
                        section,
                    )
                    seen_paid = set(c["domain"] for c in data["competitors"])
                    for domain, num in domain_number:
                        if domain not in seen_paid:
                            seen_paid.add(domain)
                            data["competitors"].append(
                                {
                                    "domain": domain,
                                    "type": "paid",
                                    "common_keywords": num,
                                }
                            )
                            if len(data["competitors"]) >= 15:
                                break
                    paid_comps = [
                        c["domain"]
                        for c in data["competitors"]
                        if c.get("type") == "paid"
                    ]
                    if paid_comps:
                        print(f"   付费竞品: {paid_comps[:5]}")
                    break

            print(f"   总竞品数: {len(data['competitors'])}")

        except Exception as e:
            print(f"   竞品提取失败: {e}")

    def _extract_keywords_data(self, data):
        """切换到关键词标签页，提取关键词表格（自然+付费）"""
        import re

        print("   📋 尝试提取关键词数据...")

        # ===== 第一部分：自然搜索关键词 =====
        self._extract_organic_keywords(data)

        # ===== 第二部分：付费搜索关键词 =====
        self._extract_paid_keywords(data)

    def _extract_organic_keywords(self, data):
        """提取自然搜索关键词"""
        import re

        print("   📋 提取自然搜索关键词...")
        try:
            # 尝试点击关键词相关标签
            kw_tabs = [
                "text=自然搜索关键词",
                "text=关键词",
                "text=Organic Keywords",
                "text=Keywords",
                "[class*='keyword'] a",
                "[class*='tab'] >> text=关键词",
            ]
            for tab_sel in kw_tabs:
                try:
                    tab = self.page.locator(tab_sel).first
                    if tab.is_visible(timeout=2000):
                        tab.click()
                        print(f"   已点击关键词标签: {tab_sel}")
                        time.sleep(5)
                        break
                except:
                    continue

            # 等待数据加载
            time.sleep(3)

            # === 滚动加载更多关键词行 ===
            # SEMrush关键词表格是懒加载的，需要滚动才能加载更多行
            print("   滚动加载关键词表格...")
            try:
                # 找到关键词表格容器并滚动
                table_selectors = [
                    '[class*="Keyword"] [class*="Table"]',
                    '[class*="keyword"] [class*="table"]',
                    '[class*="Table"][class*="scroll"]',
                    '[data-at="keyword-table"]',
                    '[class*="tbody"]',
                    "table",
                ]
                scrolled = False
                for sel in table_selectors:
                    try:
                        table_el = self.page.locator(sel).first
                        if table_el.is_visible(timeout=2000):
                            # 在表格容器内向下滚动多次
                            for scroll_i in range(5):
                                table_el.evaluate(
                                    "el => el.scrollTop = el.scrollHeight"
                                )
                                time.sleep(1)
                            scrolled = True
                            print(f"   已滚动关键词表格: {sel}")
                            break
                    except:
                        continue

                if not scrolled:
                    # 兜底：在页面上使用Page Down滚动
                    for scroll_i in range(3):
                        self.page.keyboard.press("PageDown")
                        time.sleep(1)
                    # 再滚回关键词区域
                    try:
                        kw_heading = self.page.locator(
                            'h2:has-text("关键词"), h2:has-text("Keyword")'
                        ).first
                        if kw_heading.is_visible(timeout=2000):
                            kw_heading.scroll_into_view_if_needed(timeout=3000)
                            time.sleep(2)
                    except:
                        pass
            except Exception as e:
                print(f"   滚动关键词表格失败: {e}")

            # 方法1：直接从页面文本中解析关键词表格
            try:
                page_text = self.page.inner_text("body", timeout=10000)
                # wmxpro关键词表格格式：关键词\n意图\n排名\n搜索量\nCPC\n流量%
                # 每行一个关键词，字段用换行分隔
                # 找到关键词表格区域
                kw_section = ""
                for marker in [
                    "关键词\n意图\n排名",
                    "Keyword\nIntent\nPosition",
                    "关键词\n意图",
                ]:
                    if marker in page_text:
                        idx = page_text.find(marker)
                        # 跳过表头
                        kw_section = page_text[
                            idx + len(marker) : idx + len(marker) + 5000
                        ]
                        break

                if kw_section:
                    keywords = []
                    # 按关键词模式匹配：关键词字母开头 + 意图字母 + 排名数字 + 搜索量 + CPC + 流量%
                    # 格式：keyword\nC|I|N\n数字\n数字K?\n$数字\n数字%
                    kw_pattern = re.compile(
                        r"([a-zA-Z][a-zA-Z0-9 \-\+\.]+?)\n"  # 关键词
                        r"([CINBT])\n"  # 意图 (Commercial/Informational/Navigational/Brand/Transactional)
                        r"(\d+)\n"  # 排名
                        r"([0-9.,]+[KMB]?)\n"  # 搜索量
                        r"([0-9.]+)\n"  # CPC
                        r"([0-9.]+)",  # 流量%
                        re.MULTILINE,
                    )
                    for m in kw_pattern.finditer(kw_section):
                        keywords.append(
                            {
                                "keyword": m.group(1).strip(),
                                "intent": m.group(2),
                                "position": int(m.group(3)),
                                "volume": m.group(4),
                                "cpc": m.group(5),
                                "traffic_pct": m.group(6),
                            }
                        )
                        if len(keywords) >= 30:
                            break

                    if keywords:
                        data["organic_keywords"]["top_keywords"] = keywords
                        print(f"   解析到 {len(keywords)} 个结构化自然关键词")
                    else:
                        # 降级：逐行解析
                        self._parse_keywords_fallback(kw_section, data)
                else:
                    # 方法2：从原始行元素提取
                    self._extract_keywords_from_rows(data)

                # 方法3：截图+行级DOM提取关键词
                if not data["organic_keywords"].get("top_keywords"):
                    print("   文本解析未获得关键词，尝试截图+行级DOM提取...")
                    self._extract_keywords_by_row_dom(data)

            except Exception as e:
                print(f"   自然关键词文本解析失败: {e}")
                self._extract_keywords_from_rows(data)
                # 再次尝试行级DOM提取
                if not data["organic_keywords"].get("top_keywords"):
                    self._extract_keywords_by_row_dom(data)

        except Exception as e:
            print(f"   自然关键词标签提取失败: {e}")

    def _extract_keywords_by_row_dom(self, data):
        """截图+行级DOM提取关键词：在关键词页面用截图保存+行级元素定位提取

        当文本解析无法提取到关键词时（通常是表格懒加载未完成），
        用行级DOM元素定位直接获取表格行的文本内容。
        """
        import re

        domain = data.get("domain", "")
        print("   📸 截图+行级DOM提取关键词...")

        try:
            # 截取当前页面截图（调试用）
            screenshot_path = (
                OUTPUT_DIR / f"semrush_kw_page_{domain}_{int(time.time())}.png"
            )
            self.page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"   关键词页面截图已保存: {screenshot_path}")

            # 查找关键词表格行
            row_selectors = [
                '[role="row"]',
                "tr",
                '[class*="TableRow"]',
                '[class*="tableRow"]',
                '[data-at*="row"]',
            ]

            row_texts = []
            for sel in row_selectors:
                try:
                    rows = self.page.locator(sel)
                    count = rows.count()
                    if count > 1:  # 至少2行（1表头+1数据）
                        print(f"   找到 {count} 个行元素: {sel}")
                        for i in range(min(count, 50)):
                            try:
                                row_text = rows.nth(i).inner_text(timeout=2000)
                                if row_text and len(row_text.strip()) > 5:
                                    row_texts.append(row_text.strip())
                            except:
                                continue
                        if len(row_texts) > 1:  # 至少有数据行
                            break
                except:
                    continue

            if row_texts:
                # 保存行级数据到调试文件
                try:
                    rows_debug = (
                        OUTPUT_DIR / f"semrush_kw_rows_{domain}_{int(time.time())}.txt"
                    )
                    rows_debug.write_text(
                        "\n---ROW---\n".join(row_texts), encoding="utf-8"
                    )
                    print(f"   关键词行级数据已保存: {rows_debug}")
                except:
                    pass

                # 解析行级文本为关键词
                keywords = []
                # 表头行特征
                header_markers = [
                    "关键词",
                    "Keyword",
                    "意图",
                    "Intent",
                    "排名",
                    "Position",
                    "搜索量",
                    "Volume",
                    "CPC",
                    "流量",
                    "Traffic",
                    "Sortable",
                ]

                for row_text in row_texts:
                    # 跳过表头行
                    if any(m in row_text for m in header_markers):
                        continue

                    # 尝试从行文本中提取关键词
                    # SEMrush 关键词行格式可能是：
                    # keyword\nC\n1\n2.4K\n$1.23\n3.2%
                    # 或者：keyword  C  1  2.4K  $1.23  3.2%

                    # 按换行分割
                    parts = row_text.split("\n")
                    parts = [p.strip() for p in parts if p.strip()]

                    if len(parts) >= 3:
                        # 第一个非数字部分通常是关键词
                        kw = ""
                        intent = ""
                        position = ""
                        volume = ""
                        cpc = ""
                        traffic = ""

                        for p in parts:
                            # 意图标记（C/I/N/B/T）
                            if p in ("C", "I", "N", "B", "T"):
                                intent = p
                            # 纯数字（排名）
                            elif re.match(r"^\d+$", p) and not position:
                                position = p
                            # 搜索量（数字+K/M/B或纯数字）
                            elif re.match(r"^[0-9.,]+[KMB]?$", p) and not volume:
                                if not position:  # 第一个数字给position
                                    position = p
                                else:
                                    volume = p
                            # CPC（$开头）
                            elif re.match(r"^\$?[0-9.]+$", p) and not cpc:
                                cpc = p
                            # 流量%
                            elif re.match(r"^[0-9.]+%$", p):
                                traffic = p
                            # 关键词文本（含英文字母，非纯数字）
                            elif re.search(r"[a-zA-Z]{2,}", p) and not kw:
                                kw = p

                        if kw:
                            kw_data = {"keyword": kw[:200]}
                            if intent:
                                kw_data["intent"] = intent
                            if position:
                                kw_data["position"] = position
                            if volume:
                                kw_data["volume"] = volume
                            if cpc:
                                kw_data["cpc"] = cpc
                            if traffic:
                                kw_data["traffic_pct"] = traffic.rstrip("%")
                            keywords.append(kw_data)

                    if len(keywords) >= 30:
                        break

                if keywords:
                    data["organic_keywords"]["top_keywords"] = keywords
                    print(f"   行级DOM提取到 {len(keywords)} 个关键词")
                else:
                    print(
                        f"   行级DOM解析未获得有效关键词（{len(row_texts)}行原始数据）"
                    )
            else:
                print("   未找到关键词表格行元素")

        except Exception as e:
            print(f"   截图+行级DOM关键词提取失败: {e}")

    def _ocr_screenshot(self, screenshot_path, data_type="keywords"):
        """使用百度文档解析API对截图进行OCR识别

        Args:
            screenshot_path: 截图文件路径
            data_type: 数据类型 ("keywords", "paid_keywords", "ad_copies")

        Returns:
            解析后的文本内容，或 None 如果失败
        """
        import subprocess
        import json

        print(f"   🔍 OCR解析截图: {screenshot_path}")

        try:
            # 调用百度文档解析技能
            skill_dir = Path(
                os.environ.get(
                    "SKILL_DIR",
                    r"C:\Users\wuhj\AppData\Roaming\qianfan-desktop-app\qianfan_desk_xdg\cef125b44eb141059bd483c6175d5948\data\skills\official\baidu-document-parse",
                )
            )
            parse_script = skill_dir / "scripts" / "parse.py"

            if not parse_script.exists():
                print(f"   OCR脚本不存在: {parse_script}")
                return None

            # 构建请求参数
            request_params = {
                "file_path": str(screenshot_path),
                "file_name": Path(screenshot_path).name,
            }

            # 调用解析脚本
            result = subprocess.run(
                ["python", str(parse_script), json.dumps(request_params)],
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
            )

            if result.returncode != 0:
                print(f"   OCR解析失败: {result.stderr}")
                return None

            ocr_text = result.stdout.strip()
            if ocr_text:
                print(f"   OCR解析成功，文本长度: {len(ocr_text)}")
                # 保存OCR结果用于调试
                ocr_output = OUTPUT_DIR / f"ocr_{data_type}_{int(time.time())}.txt"
                ocr_output.write_text(ocr_text, encoding="utf-8")
                print(f"   OCR结果已保存: {ocr_output}")
                return ocr_text

            return None

        except subprocess.TimeoutExpired:
            print("   OCR解析超时")
            return None
        except Exception as e:
            print(f"   OCR解析异常: {e}")
            return None

    def _extract_paid_keywords_by_ocr(self, data):
        """截图+OCR提取付费关键词

        当其他方法都无法获取付费关键词时，使用截图+OCR作为最终备选方案
        """
        import re

        domain = data.get("domain", "")
        print("   📸 截图+OCR提取付费关键词...")

        try:
            # 1. 确保在广告研究页面的关键词标签
            current_url = self.page.url
            if "adwords" not in current_url:
                # 导航到广告研究页面
                base_url = "/".join(self.page.url.split("/")[:3])
                ad_url = f"{base_url}/analytics/adwords/positions?db=us&q={domain}&searchType=domain"
                self.page.goto(ad_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(3)

            # 2. 尝试点击关键词标签
            for tab_sel in [
                "text=关键词",
                "text=Keywords",
                "text=排名",
                "text=Positions",
            ]:
                try:
                    tab = self.page.locator(tab_sel).first
                    if tab.is_visible(timeout=3000):
                        tab.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # 3. 等待数据加载
            time.sleep(3)

            # 4. 截取关键词表格区域
            screenshot_path = (
                OUTPUT_DIR / f"paid_keywords_{domain}_{int(time.time())}.png"
            )

            # 尝试定位关键词表格区域
            table_selectors = [
                '[role="table"]',
                '[class*="Table"]',
                '[class*="table"]',
                '[data-at*="table"]',
                "table",
            ]

            table_found = False
            for sel in table_selectors:
                try:
                    table = self.page.locator(sel).first
                    if table.is_visible(timeout=3000):
                        table.screenshot(path=str(screenshot_path))
                        table_found = True
                        print(f"   已截取关键词表格: {sel}")
                        break
                except:
                    continue

            if not table_found:
                # 截取整个页面
                self.page.screenshot(path=str(screenshot_path), full_page=False)
                print(f"   已截取整个页面")

            print(f"   截图已保存: {screenshot_path}")

            # 5. OCR解析
            ocr_text = self._ocr_screenshot(screenshot_path, "paid_keywords")

            if ocr_text:
                # 6. 从OCR文本中提取关键词
                keywords = self._parse_keywords_from_ocr_text(ocr_text, "paid")
                if keywords:
                    data["paid_keywords"]["top_keywords"] = keywords
                    print(f"   OCR提取到 {len(keywords)} 个付费关键词")
                    return True

            return False

        except Exception as e:
            print(f"   截图+OCR提取付费关键词失败: {e}")
            return False

    def _extract_ad_copies_by_ocr(self, data):
        """截图+OCR提取广告文案

        当其他方法都无法获取广告文案时，使用截图+OCR作为最终备选方案
        """
        import re

        domain = data.get("domain", "")
        print("   📸 截图+OCR提取广告文案...")

        try:
            # 1. 确保在广告研究页面
            current_url = self.page.url
            if "adwords" not in current_url:
                base_url = "/".join(self.page.url.split("/")[:3])
                ad_url = f"{base_url}/analytics/adwords/positions?db=us&q={domain}&searchType=domain"
                self.page.goto(ad_url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(3)

            # 2. 尝试点击广告副本标签
            for tab_sel in [
                "text=广告副本",
                "text=文字广告",
                "text=Ad Copies",
                "text=Text Ads",
            ]:
                try:
                    tab = self.page.locator(tab_sel).first
                    if tab.is_visible(timeout=3000):
                        tab.click()
                        time.sleep(2)
                        break
                except:
                    continue

            # 3. 等待数据加载
            time.sleep(3)

            # 4. 截取广告区域
            screenshot_path = OUTPUT_DIR / f"ad_copies_{domain}_{int(time.time())}.png"

            # 尝试定位广告区域
            ad_selectors = [
                '[class*="Ad"]',
                '[class*="ad-"]',
                '[data-at*="ad"]',
                '[class*="creative"]',
            ]

            ad_found = False
            for sel in ad_selectors:
                try:
                    ad_area = self.page.locator(sel).first
                    if ad_area.is_visible(timeout=3000):
                        ad_area.screenshot(path=str(screenshot_path))
                        ad_found = True
                        print(f"   已截取广告区域: {sel}")
                        break
                except:
                    continue

            if not ad_found:
                # 截取整个页面
                self.page.screenshot(path=str(screenshot_path), full_page=False)
                print(f"   已截取整个页面")

            print(f"   截图已保存: {screenshot_path}")

            # 5. OCR解析
            ocr_text = self._ocr_screenshot(screenshot_path, "ad_copies")

            if ocr_text:
                # 6. 从OCR文本中提取广告文案
                ad_copies = self._parse_ad_copies_from_ocr_text(ocr_text, domain)
                if ad_copies:
                    # 过滤无效广告
                    valid_ads = self._filter_valid_ads(ad_copies, domain)
                    if valid_ads:
                        data["ad_copies"] = valid_ads
                        print(f"   OCR提取到 {len(valid_ads)} 条广告文案")
                        return True

            return False

        except Exception as e:
            print(f"   截图+OCR提取广告文案失败: {e}")
            return False

    def _parse_keywords_from_ocr_text(self, ocr_text, keyword_type="organic"):
        """从OCR文本中解析关键词

        Args:
            ocr_text: OCR识别的文本
            keyword_type: 关键词类型 ("organic" 或 "paid")

        Returns:
            关键词列表
        """
        import re

        keywords = []
        lines = ocr_text.split("\n")

        # 跳过表头行
        header_found = False
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if (
                "keyword" in line_lower
                or "关键词" in line_lower
                or "volume" in line_lower
            ):
                header_found = True
                continue
            if header_found:
                # 解析数据行
                # 典型格式: "keyword name  volume  cpc  position  traffic"
                parts = line.split()
                if len(parts) >= 2:
                    # 第一个部分通常是关键词
                    keyword = parts[0]
                    # 检查是否是有效的关键词（包含字母）
                    if re.match(r"^[a-zA-Z]", keyword) and 3 <= len(keyword) <= 80:
                        kw = {"keyword": keyword}
                        # 尝试解析其他字段
                        for part in parts[1:]:
                            if re.match(r"^\d+[,.]?\d*[KMB]?$", part):
                                # 数字，可能是 volume 或 traffic
                                if "volume" not in kw:
                                    kw["volume"] = part
                            elif re.match(r"^\d+\.\d+$", part):
                                # 小数，可能是 CPC
                                if "cpc" not in kw:
                                    kw["cpc"] = part
                            elif part.isdigit():
                                # 整数，可能是 position
                                if "position" not in kw:
                                    kw["position"] = int(part)
                        keywords.append(kw)
                        if len(keywords) >= 30:
                            break

        return keywords

    def _parse_ad_copies_from_ocr_text(self, ocr_text, domain):
        """从OCR文本中解析广告文案

        Args:
            ocr_text: OCR识别的文本
            domain: 目标域名

        Returns:
            广告文案列表
        """
        import re

        ad_copies = []
        lines = ocr_text.split("\n")

        current_ad = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否是标题行（通常包含域名或产品名称）
            if domain in line.lower() or re.match(
                r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$", line
            ):
                if current_ad and current_ad.get("headline"):
                    ad_copies.append(current_ad)
                current_ad = {"headline": line, "descriptions": [], "url": ""}
            elif current_ad:
                # 添加到描述
                if len(line) > 20:  # 忽略太短的行
                    current_ad["descriptions"].append(line)

        # 添加最后一个广告
        if current_ad and current_ad.get("headline"):
            ad_copies.append(current_ad)

        return ad_copies

    def _extract_paid_keywords(self, data):
        """提取付费搜索关键词 — 从概览页的'主要付费关键词'区域提取"""
        import re

        print("   📋 提取付费搜索关键词...")
        try:
            # 滚动页面确保内容加载
            for i in range(3):
                self.page.evaluate("window.scrollBy(0, 500)")
                time.sleep(0.3)

            # 使用正确的选择器定位"主要付费关键词"区域
            # data-at="do-paid-keywords" aria-label="主要付费关键词"
            paid_keywords = []
            try:
                paid_kw_section = self.page.locator(
                    '[data-at="do-paid-keywords"]'
                ).first
                if paid_kw_section.is_visible(timeout=5000):
                    paid_kw_section.scroll_into_view_if_needed(timeout=5000)
                    time.sleep(1)
                    print("   找到主要付费关键词区域")

                    # 提取区域内的文本
                    section_text = paid_kw_section.inner_text()
                    print(f"   主要付费关键词区域文本长度: {len(section_text)}")

                    # 解析关键词数据
                    # 格式：关键词 排名 搜索量 CPC 流量
                    lines = [l.strip() for l in section_text.split("\n") if l.strip()]

                    # 找到表头位置
                    header_idx = -1
                    for i, line in enumerate(lines):
                        if "关键词" in line:
                            header_idx = i
                            break

                    if header_idx >= 0:
                        # 跳过表头行
                        data_start = header_idx + 1
                        # 跳过 "Sortable" 等非数据行
                        while data_start < len(lines) and lines[data_start] in [
                            "Sortable",
                            "打开完整的",
                            "查看详情",
                        ]:
                            data_start += 1

                        # 解析关键词数据
                        i = data_start
                        while i < len(lines) - 4 and len(paid_keywords) < 20:
                            line = lines[i]
                            # 跳过非数据行
                            if line in [
                                "Sortable",
                                "打开完整的",
                                "查看详情",
                            ] or line.startswith("<"):
                                i += 1
                                continue
                            # 检查是否是关键词（不是纯数字）
                            if not re.match(r"^[\d,.$%]+$", line) and len(line) > 2:
                                kw = line
                                try:
                                    pos = (
                                        int(lines[i + 1].replace(",", ""))
                                        if i + 1 < len(lines)
                                        else 0
                                    )
                                    vol = (
                                        lines[i + 2].replace(",", "")
                                        if i + 2 < len(lines)
                                        else "0"
                                    )
                                    cpc = lines[i + 3] if i + 3 < len(lines) else "0"
                                    traffic = (
                                        lines[i + 4] if i + 4 < len(lines) else "0"
                                    )

                                    paid_keywords.append(
                                        {
                                            "keyword": kw,
                                            "position": pos,
                                            "volume": vol,
                                            "cpc": cpc,
                                            "traffic": traffic,
                                        }
                                    )
                                    i += 5
                                except:
                                    i += 1
                            else:
                                i += 1

                    if paid_keywords:
                        print(
                            f"   从主要付费关键词区域提取到 {len(paid_keywords)} 个关键词"
                        )
                else:
                    print("   未找到主要付费关键词区域")
            except Exception as e:
                print(f"   定位主要付费关键词区域失败: {e}")

            if paid_keywords:
                data["paid_keywords"]["top_keywords"] = paid_keywords
            else:
                print("   概览页付费关键词区域未找到结构化关键词")

        except Exception as e:
            print(f"   付费关键词提取失败: {e}")

    def _parse_keywords_fallback(self, text, data):
        """降级关键词解析：从文本块中逐个提取"""
        import re

        keywords = []
        # 简单匹配：英文字母开头的短语 + 后面跟的数字
        lines = text.split("\n")
        i = 0
        while i < len(lines) - 1 and len(keywords) < 30:
            line = lines[i].strip()
            # 跳过表头、空行、纯数字行
            if (
                not line
                or re.match(r"^[0-9.,KMB%]+$", line)
                or line in ("C", "I", "N", "B", "T")
            ):
                i += 1
                continue
            # 看起来像关键词（包含英文字母，长度3-80）
            if re.match(r"^[a-zA-Z]", line) and 3 <= len(line) <= 80:
                kw = {"keyword": line}
                # 尝试读取后续字段
                remaining = lines[i + 1 : i + 6]
                for j, r in enumerate(remaining):
                    r = r.strip()
                    if r in ("C", "I", "N", "B", "T") and "intent" not in kw:
                        kw["intent"] = r
                    elif re.match(r"^\d+$", r) and "position" not in kw:
                        kw["position"] = int(r)
                    elif re.match(r"^[0-9.,]+[KMB]?$", r) and "volume" not in kw:
                        kw["volume"] = r
                    elif re.match(r"^[0-9.]+$", r) and "cpc" not in kw and len(r) <= 6:
                        kw["cpc"] = r
                keywords.append(kw)
            i += 1

        if keywords:
            data["organic_keywords"]["top_keywords"] = keywords
            print(f"   降级解析到 {len(keywords)} 个关键词")

    def _parse_paid_keywords_fallback(self, text, data):
        """降级付费关键词解析：从文本块中逐个提取"""
        import re

        keywords = []
        lines = text.split("\n")
        i = 0
        while i < len(lines) - 1 and len(keywords) < 30:
            line = lines[i].strip()
            if (
                not line
                or re.match(r"^[0-9.,KMB%]+$", line)
                or line in ("C", "I", "N", "B", "T")
            ):
                i += 1
                continue
            if re.match(r"^[a-zA-Z]", line) and 3 <= len(line) <= 80:
                kw = {"keyword": line}
                remaining = lines[i + 1 : i + 6]
                for j, r in enumerate(remaining):
                    r = r.strip()
                    if r in ("C", "I", "N", "B", "T") and "intent" not in kw:
                        kw["intent"] = r
                    elif re.match(r"^\d+$", r) and "position" not in kw:
                        kw["position"] = int(r)
                    elif re.match(r"^[0-9.,]+[KMB]?$", r) and "volume" not in kw:
                        kw["volume"] = r
                    elif re.match(r"^[0-9.]+$", r) and "cpc" not in kw and len(r) <= 6:
                        kw["cpc"] = r
                keywords.append(kw)
            i += 1

        if keywords:
            data["paid_keywords"]["top_keywords"] = keywords
            print(f"   降级解析到 {len(keywords)} 个付费关键词")

    def _extract_keywords_from_rows(self, data):
        """从行元素中提取关键词"""
        try:
            rows = self.page.locator(
                '[class*="Row"], [class*="row"], [role="row"], tr'
            ).all()
            keywords = []
            for row in rows[:50]:
                try:
                    text = row.inner_text()
                    if not text or len(text) < 5:
                        continue
                    parts = [p.strip() for p in text.split("\n") if p.strip()]
                    if len(parts) >= 2:
                        first = parts[0]
                        import re

                        if not re.match(r"^[0-9.,KMB%]+$", first) and len(first) > 2:
                            keywords.append(
                                {
                                    "keyword": first[:100],
                                    "raw": text[:200],
                                }
                            )
                except:
                    continue
            if keywords:
                data["organic_keywords"]["top_keywords"] = keywords[:30]
                print(f"   从行元素提取到 {len(keywords)} 个关键词")
        except:
            pass

    def _extract_ads_data(self, data):
        """从概览页的'文字广告样本'区域提取广告文案"""
        import re

        print("   📋 从概览页提取广告数据（文字广告样本）...")
        try:
            # Step 1: 等待页面稳定
            print("   等待页面加载...")
            try:
                self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            time.sleep(2)

            # Step 2: 滚动到页面底部，确保所有内容加载
            print("   滚动页面加载所有内容...")
            for i in range(15):
                self.page.evaluate("window.scrollBy(0, 800)")
                time.sleep(0.3)
            time.sleep(3)

            # Step 3: 使用正确的选择器定位"文字广告样本"区域
            # data-at="do-paid-sampleads" aria-label="文字广告样本"
            ad_copies = []
            try:
                sample_ads_section = self.page.locator('[data-at="do-paid-sampleads"]')
                count = sample_ads_section.count()
                print(f"   找到 {count} 个文字广告样本区域元素")

                if count > 0:
                    first_section = sample_ads_section.first
                    # 直接获取文本，不滚动
                    try:
                        section_text = first_section.inner_text(timeout=10000)
                    except:
                        # 如果 inner_text 失败，尝试 evaluate
                        try:
                            section_text = first_section.evaluate("el => el.innerText")
                        except Exception as e2:
                            print(f"   获取文本失败: {e2}")
                            section_text = ""

                    print(f"   文字广告样本区域文本长度: {len(section_text)}")

                    # 保存调试文本
                    debug_file = (
                        OUTPUT_DIR
                        / f"semrush_ad_section_{data.get('domain', '')}_{int(time.time())}.txt"
                    )
                    debug_file.write_text(section_text, encoding="utf-8")
                    print(f"   广告区域调试文本已保存: {debug_file}")

                    # 解析广告文案
                    ad_copies = self._parse_text_ads_from_section(
                        section_text, data.get("domain", "")
                    )
                    if ad_copies:
                        print(f"   从文字广告样本解析到 {len(ad_copies)} 条广告")
                else:
                    print("   未找到文字广告样本区域元素")
            except Exception as e:
                print(f"   定位文字广告样本区域失败: {e}")

            # Step 3: 如果文本解析失败，尝试DOM方式
            if not ad_copies:
                print("   文本解析未找到广告，尝试DOM提取...")
                self._extract_ads_from_dom(data)
                ad_copies = data.get("ad_copies", [])

            # Step 4: 质量校验 — 过滤掉无效广告
            if ad_copies:
                valid_ads = self._filter_valid_ads(ad_copies, data.get("domain", ""))
                if len(valid_ads) < len(ad_copies):
                    print(f"   质量过滤：{len(ad_copies)} → {len(valid_ads)} 条")
                ad_copies = valid_ads

            data["ad_copies"] = ad_copies
            print(f"   概览页提取到 {len(ad_copies)} 条广告文案")

        except Exception as e:
            print(f"   概览页广告提取失败: {e}")
            import traceback

            traceback.print_exc()

    def _parse_text_ads_from_section(self, section_text, domain):
        """从'文字广告样本'区域的文本解析广告文案

        实际格式：
        文字广告样本

        38

        Self Tanners – Beauty by Earth | Beauty by Earth
        https://www.beautybyearth.com
        From self tanner body lotions, mousses...
        Buy 2 Get 1 Free | Code B2G1 | No Orange Fake Tan, Just You
        https://www.beautybyearth.com
        No Harsh Chemicals, Natural, Plant-Based Ingredients...
        Beauty by Earth
        https://www.beautybyearth.com
        ...

        每条广告格式：标题 + URL + 描述（可能多行）
        URL 是新广告的分隔符
        """
        import re

        ads = []

        if not section_text:
            return ads

        lines = section_text.strip().split("\n")

        # 跳过标题行（"文字广告样本"）和数字行
        start_idx = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "文字广告样本" or line.isdigit():
                start_idx = i + 1
                continue
            if line and not line.isdigit() and "文字广告样本" not in line:
                break

        # 解析广告：使用 URL 作为分隔符
        current_ad = {}
        for i in range(start_idx, len(lines)):
            line = lines[i].strip()

            # 跳过空行
            if not line:
                continue

            # 跳过"查看详情"
            if line in ["查看详情", "View details"]:
                continue

            # URL 行 - 可能是新广告的开始
            if line.startswith("http"):
                if current_ad.get("url") and current_ad.get("headline"):
                    # 已有 URL，说明这是新广告的开始
                    ads.append(current_ad)
                    current_ad = {"url": line}
                else:
                    current_ad["url"] = line
            elif not current_ad.get("headline"):
                # 标题行（还没有标题）
                current_ad["headline"] = line
            else:
                # 描述行
                if "descriptions" not in current_ad:
                    current_ad["descriptions"] = []
                current_ad["descriptions"].append(line)

        # 添加最后一条广告
        if current_ad and current_ad.get("headline"):
            ads.append(current_ad)

        # 构建 raw 字段并过滤无效广告
        valid_ads = []
        for ad in ads:
            # 必须有标题和 URL
            if not ad.get("headline") or not ad.get("url"):
                continue

            parts = [ad["headline"]]
            if ad.get("descriptions"):
                parts.extend(ad["descriptions"])
            ad["raw"] = "\n".join(parts)

            # 过滤掉 SEMrush UI 文本
            if any(
                x in ad["headline"] for x in ["查看详情", "View details", "全面了解"]
            ):
                continue

            valid_ads.append(ad)

        return valid_ads

    def _parse_paid_keywords_from_section(self, section_text):
        """从'主要付费关键词'区域的文本解析付费关键词

        实际格式（每行一个字段）：
        主要付费关键词

        38

        关键词
        排名
        搜索量
        CPC (USD)
        流量 (%)
        Sortable
        beauty by earth self tanner
        1
        8,100
        1.00
        18.91
        beauty by earth self tanner
        1
        8,100
        2.26
        18.91
        """
        import re

        keywords = []

        if not section_text:
            return keywords

        lines = section_text.strip().split("\n")

        # 找到表头结束位置（"Sortable" 后面开始是数据）
        start_idx = 0
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "Sortable":
                start_idx = i + 1
                break

        # 从 start_idx 开始，每 5 行是一条关键词数据
        # 顺序：关键词、排名、搜索量、CPC、流量百分比
        i = start_idx
        while i + 4 < len(lines):
            keyword = lines[i].strip()
            position_str = lines[i + 1].strip()
            volume_str = lines[i + 2].strip()
            cpc_str = lines[i + 3].strip()
            traffic_str = lines[i + 4].strip()

            # 跳过"查看详情"等非数据行
            if keyword in ["查看详情", "View details", ""]:
                break

            try:
                # 解析数字
                position = int(position_str)
                volume = int(volume_str.replace(",", ""))
                cpc = float(cpc_str.replace("$", ""))
                traffic = float(traffic_str)

                keywords.append(
                    {
                        "keyword": keyword,
                        "position": position,
                        "volume": volume,
                        "cpc": cpc,
                        "traffic_percent": traffic,
                    }
                )
            except (ValueError, IndexError):
                pass

            # 移动到下一条关键词
            i += 5

        return keywords

    def _parse_ad_samples_from_text(self, text, domain):
        """从'文字广告样本'标记后的文本中解析广告文案

        SEMrush概览页"文字广告样本"实际格式（已确认）：
        Headline1 – Brand | Brand    https://www.example.com
        Description line 1. Description line 2. More description text.

        特征：
        - 第一行：标题（可能有竖线|分隔多标题）+ 可选URL（https://...）
        - 标题和URL之间有多个空格分隔
        - 第二行起：描述文本
        - 广告之间通常有空行或明显分隔
        """
        import re

        ads = []

        # SEMrush UI 文本黑名单
        skip_words = {
            "Sortable",
            "导出",
            "更多",
            "筛选",
            "下载",
            "查看详情",
            "按",
            "Tab",
            "启用",
            "图形",
            "图表",
            "访问",
            "模块",
            "Cookie",
            "设置",
            "联系我们",
            "版权所有",
            "Semrush",
            "全部时间",
            "导出成",
            "PDF",
            "发送反馈",
            "用户手册",
            "域名概览",
            "SEO",
            "根域名",
            "首页",
            "反向链接",
            "Backlinks",
            "桌面设备",
            "增长审核",
            "按国家",
            "AI 搜索",
            "AI 可见度",
            "广告研究",
            "Advertising Research",
            "搜索量",
            "CPC",
            "CPC (USD)",
            "流量",
            "流量 (%)",
            "竞争对手",
            "竞争程度",
            "共同关键词",
            "付费关键词",
            "付费搜索流量",
            "竞争排名图谱",
            "谷歌 SERP 上的排名",
            "主要付费搜索竞争对手",
            "自然搜索关键词",
            "自然搜索流量",
            "自然关键词",
            "引用域名",
            "引用IP",
            "引用来源",
            "广告文案",
            "Ad Copies",
            "广告副本",
            "广告拷贝",
            "文字广告样本",
            "Sample Text Ads",
            "Text Ad Samples",
            "US",
            "UK",
            "DE",
            "全世界",
            "中文",
            "English",
            "2-3",
            "other",
            "展开",
            "收起",
            "查看全部",
            # SEMrush平台功能描述（不是真实广告文案）
            "全面了解域名及其在线可见度",
            "分析域名随时间的增长趋势",
            "查看域名占据主导地位的市场",
            "发现为域名吸引自然和付费搜索流量的主题和关键词",
            "比较不同国家中域名的自然搜索和付费搜索效果",
            "查看特定市场域名的自然份额",
            "将趋势导出为 xls 或 csv",
            "将报告轻松导出为 xls 或 csv",
            "节省用于摘要分析的时间",
            "揭示和分析特定国家或全球的关键指标",
            "通过一站式获取域名增长趋势的关键数据来节省报告时间",
            "评估域名在特定时期内的自然流量、付费流量和反向链接的进度",
            "获取免费一对一专属演示",
            "我们的专员将从头指导您逐步了解如何充分利用 Semrush 平台",
            "请勿出售我的个人信息",
            "请求专属演示",
            "获取完整分析",
            "比较域名",
            "增长审核",
            "按国家进行比较",
            "选择域名类型：根域名、子域名、子文件夹",
            "查看套餐和价格",
            "开始使用 Semrush",
        }
        nav_patterns = [
            r'^按["""\u201c\u201d]Tab["""\u201c\u201d]启用',
            r"^图形图表",
            r"^访问模块",
            r"^©\s*\d{4}",
            r"^Semrush",
            r"^Cookie",
            r"^联系我们",
            r"^域名概览",
            r"^用户手册",
            r"^发送反馈",
            r"^导出成",
            r"^查看详情",
            r"^桌面设备",
            r"^增长审核",
            r"^按国家",
            r"^AI 搜索",
            r"^AI 可见度",
            r"^SEO$",
            r"^首页$",
            r"^反向链接",
            r"^Backlinks",
            r"^广告研究$",
            r"^\d+[-~]\d+$",
        ]

        def is_noise(line):
            if not line or len(line) <= 2:
                return True
            if line in skip_words:
                return True
            for pat in nav_patterns:
                if re.match(pat, line):
                    return True
            return False

        def looks_like_ad_headline(line):
            """判断一行是否像广告标题行（含英文、可能有URL）"""
            # 必须包含英文
            if not re.search(r"[a-zA-Z]{2,}", line):
                return False
            # 广告标题行特征：
            # 1. 包含URL（https://...）
            # 2. 包含竖线分隔符（|）
            # 3. 包含品牌名+短标题（长度<150）
            has_url = bool(re.search(r"https?://", line))
            has_pipe = "|" in line
            # 标题行通常不会太长（除非带URL），也不会太短
            if has_url or has_pipe:
                return True
            # 不带URL和竖线的行：可能是只有标题（较短）
            if 5 <= len(line) <= 80 and re.search(r"[a-zA-Z]{3,}", line):
                return True
            return False

        def looks_like_description(line):
            """判断一行是否像广告描述"""
            # 描述通常较长，包含英文句子
            if len(line) < 10:
                return False
            if not re.search(r"[a-zA-Z]{3,}", line):
                return False
            # 描述通常有完整句子特征
            return True

        lines = text.split("\n")
        i = 0
        while i < len(lines) and len(ads) < 20:
            line = lines[i].strip()
            if is_noise(line):
                i += 1
                continue

            # 策略1: 识别"标题行 + URL"格式
            # 格式：Headline1 – Brand | Brand    https://www.example.com
            url_match = re.search(r"(https?://\S+)", line)
            if url_match:
                url = url_match.group(1).rstrip(",;.")
                # 标题部分 = URL之前的所有内容
                headline_part = line[: url_match.start()].strip()
                # 清理标题：去掉尾部多余空格和特殊符号
                headline_part = re.sub(r"\s{2,}", " ", headline_part).strip()

                if headline_part and re.search(r"[a-zA-Z]{2,}", headline_part):
                    ad = {
                        "headline": headline_part[:120],
                        "url": url,
                    }
                    # 读取下一行作为描述
                    desc_lines = []
                    j = i + 1
                    while j < len(lines) and len(desc_lines) < 3:
                        next_line = lines[j].strip()
                        if is_noise(next_line):
                            j += 1
                            continue
                        if not next_line:
                            break
                        # 如果下一行也是标题行（带URL或竖线），停止
                        if re.search(r"https?://", next_line):
                            break
                        if looks_like_description(next_line):
                            desc_lines.append(next_line)
                        else:
                            break
                        j += 1

                    if desc_lines:
                        ad["descriptions"] = desc_lines
                    ad["raw"] = line
                    if len(headline_part) > 5:  # 标题至少5字符
                        ads.append(ad)
                    i = j
                    continue

            # 策略2: 竖线分隔标题行（不带URL）
            # 格式：Headline1 | Headline2 | Headline3
            if "|" in line and len(line) <= 180:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                headlines = [p for p in parts if 3 <= len(p) <= 60]
                if len(headlines) >= 2:
                    combined = " ".join(headlines)
                    if not re.search(r"[a-zA-Z]{3,}", combined):
                        i += 1
                        continue
                    ad = {"headline": line[:120], "headlines_parts": headlines}
                    # 读取后续的描述和URL
                    desc_lines = []
                    j = i + 1
                    while j < len(lines) and len(desc_lines) < 4:
                        next_line = lines[j].strip()
                        if is_noise(next_line):
                            j += 1
                            continue
                        if not next_line:
                            break
                        # URL行
                        if (
                            next_line.startswith("http")
                            or next_line.startswith("www.")
                            or re.match(
                                r"^[a-z0-9][-a-z0-9.]*\.(com|net|org|io|co)", next_line
                            )
                        ):
                            ad["url"] = next_line
                            break
                        # 描述行
                        if looks_like_description(next_line):
                            desc_lines.append(next_line)
                        else:
                            break
                        j += 1
                    if desc_lines:
                        ad["descriptions"] = desc_lines[:3]
                    ad["raw"] = line + "\n" + "\n".join(desc_lines)
                    ads.append(ad)
                    i = j + 1
                    continue

            # 策略3: 逐行组装（标题→描述→URL）
            if looks_like_ad_headline(line):
                ad_buffer = [line]
                j = i + 1
                while j < len(lines) and len(ad_buffer) < 6:
                    next_line = lines[j].strip()
                    if is_noise(next_line):
                        j += 1
                        continue
                    if not next_line:
                        break
                    ad_buffer.append(next_line)
                    j += 1

                if len(ad_buffer) >= 2:
                    ad = self._assemble_ad_copy(ad_buffer, domain)
                    if ad:
                        ads.append(ad)
                i = j + 1
            else:
                i += 1

        if ads:
            print(f"   从文字广告样本解析到 {len(ads)} 条广告")
        return ads

    def _parse_ad_lines_from_overview(self, lines, domain):
        """从概览页广告研究区域的文本行中解析广告（降级策略）"""
        import re

        ads = []

        skip_words = {
            "Sortable",
            "导出",
            "更多",
            "筛选",
            "下载",
            "查看详情",
            "按",
            "Tab",
            "启用",
            "图形",
            "图表",
            "访问",
            "模块",
            "Cookie",
            "设置",
            "联系我们",
            "版权所有",
            "Semrush",
            "全部时间",
            "导出成",
            "PDF",
            "发送反馈",
            "用户手册",
            "域名概览",
            "SEO",
            "根域名",
            "首页",
            "反向链接",
            "Backlinks",
            "桌面设备",
            "增长审核",
            "按国家",
            "AI 搜索",
            "AI 可见度",
            "广告研究",
            "Advertising Research",
            "US",
            "UK",
            "DE",
            "全世界",
            "全部时间",
            "中文",
            "English",
            # SEMrush 概览页广告区域UI标签
            "搜索量",
            "CPC",
            "CPC (USD)",
            "流量",
            "流量 (%)",
            "竞争对手",
            "竞争程度",
            "共同关键词",
            "付费关键词",
            "付费搜索流量",
            "竞争排名图谱",
            "谷歌 SERP 上的排名",
            "主要付费搜索竞争对手",
            "自然搜索关键词",
            "自然搜索流量",
            "自然关键词",
            "引用域名",
            "引用IP",
            "引用来源",
            "广告文案",
            "Ad Copies",
            "广告副本",
            "广告拷贝",
            "文字广告样本",
            "Sample Text Ads",
            "Text Ad Samples",
            "2-3",
            "other",
            "展开",
            "收起",
            "查看全部",
        }
        nav_patterns = [
            r'^按["""\u201c\u201d]Tab["""\u201c\u201d]启用',
            r"^图形图表",
            r"^访问模块",
            r"^©\s*\d{4}",
            r"^Semrush",
            r"^Cookie",
            r"^联系我们",
            r"^域名概览",
            r"^用户手册",
            r"^发送反馈",
            r"^导出成",
            r"^查看详情",
            r"^桌面设备",
            r"^增长审核",
            r"^按国家",
            r"^AI 搜索",
            r"^AI 可见度",
            r"^SEO$",
            r"^首页$",
            r"^反向链接",
            r"^Backlinks",
            r"^广告研究$",
            r"^\d+[-~]\d+$",  # 范围如 "2-3"
        ]

        def is_noise(line):
            if not line or len(line) <= 2:
                return True
            if line in skip_words:
                return True
            for pat in nav_patterns:
                if re.match(pat, line):
                    return True
            return False

        # 逐行扫描，寻找有意义的广告文本块
        buffer = []
        for line in lines:
            line = line.strip()
            if is_noise(line):
                if buffer and len(buffer) >= 2:
                    ad = self._assemble_ad_copy(buffer, domain)
                    if ad:
                        ads.append(ad)
                buffer = []
                continue
            if not line:
                if buffer and len(buffer) >= 2:
                    ad = self._assemble_ad_copy(buffer, domain)
                    if ad:
                        ads.append(ad)
                buffer = []
                continue
            buffer.append(line)

        # 处理最后剩余
        if buffer and len(buffer) >= 2:
            ad = self._assemble_ad_copy(buffer, domain)
            if ad:
                ads.append(ad)

        if ads:
            print(f"   从概览页广告区域解析到 {len(ads)} 条广告")
        return ads

    def _extract_ads_by_screenshot(self, data):
        """截图+行级DOM提取：在广告研究子页面用截图保存+行级元素定位提取广告

        原理：先截图保存用于调试，然后用 page.locator() 精确定位
        SEMrush 广告研究页面的表格行元素，逐行提取文本。
        这比 inner_text('body') 更精确，因为：
        1. 只提取表格中的数据行，不包含导航/footer等噪声
        2. 不受外贸侠包装层JS代码干扰
        3. 截图可用于人工验证OCR结果的正确性
        """
        import re

        ads = []
        domain = data.get("domain", "")
        print("   📸 截图+行级DOM提取广告数据...")

        try:
            # Step 1: 截取当前页面截图（调试用）
            screenshot_path = (
                OUTPUT_DIR / f"semrush_ads_page_{domain}_{int(time.time())}.png"
            )
            self.page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"   页面截图已保存: {screenshot_path}")

            # Step 2: 在页面上查找广告数据表格的行
            # SEMrush广告研究页面的表格通常使用 [role="row"] 或 <tr>
            # 数据行通常包含关键词/URL等可识别内容

            # 先尝试：直接定位所有 [role="row"] 或 tr 行
            row_selectors = [
                '[role="row"]',  # ARIA row
                "tr",  # HTML table row
                '[class*="TableRow"]',  # SEMrush自定义class
                '[class*="tableRow"]',  # SEMrush自定义class
                '[class*="AdCopy"]',  # 广告文案专用class
                '[data-at*="row"]',  # SEMrush data-at属性
            ]

            row_texts = []
            for sel in row_selectors:
                try:
                    rows = self.page.locator(sel)
                    count = rows.count()
                    if count > 0:
                        print(f"   找到 {count} 个行元素: {sel}")
                        # 逐行提取文本（最多30行）
                        for i in range(min(count, 30)):
                            try:
                                row_text = rows.nth(i).inner_text(timeout=2000)
                                if row_text and len(row_text.strip()) > 5:
                                    row_texts.append(row_text.strip())
                            except:
                                continue
                        if row_texts:
                            break
                except:
                    continue

            if row_texts:
                print(f"   提取到 {len(row_texts)} 行文本数据")
                # 保存行级数据到调试文件
                try:
                    rows_debug = (
                        OUTPUT_DIR / f"semrush_ad_rows_{domain}_{int(time.time())}.txt"
                    )
                    rows_debug.write_text(
                        "\n---ROW---\n".join(row_texts), encoding="utf-8"
                    )
                    print(f"   行级数据已保存: {rows_debug}")
                except:
                    pass

                # 解析行级文本为广告文案
                for row_text in row_texts:
                    # SEMrush 广告研究页面的典型行格式：
                    # Headline1 | Headline2 | Headline3    https://www.example.com
                    # Description line 1. Description line 2.

                    # 跳过表头行
                    if any(
                        h in row_text
                        for h in [
                            "关键词",
                            "Keyword",
                            "意图",
                            "Intent",
                            "搜索量",
                            "Volume",
                            "CPC",
                            "Sortable",
                            "排名",
                            "Position",
                            "流量",
                            "Traffic",
                        ]
                    ):
                        continue

                    # 跳过SEMrush UI文本
                    semrush_ui_markers = [
                        "获取完整分析",
                        "全面了解域名",
                        "分析域名随时间",
                        "查看域名占据主导",
                        "发现为域名吸引",
                        "比较不同国家",
                        "将报告轻松导出",
                        "请勿出售我的个人信息",
                        "开始使用 Semrush",
                        "查看套餐和价格",
                        "Cookie 设置",
                        "使用条款",
                        "隐私政策",
                        "请求专属演示",
                        "获取免费一对一",
                        "我们的专员将从头指导",
                    ]
                    if any(m in row_text for m in semrush_ui_markers):
                        continue

                    ad = self._parse_single_ad_row(row_text, domain)
                    if ad:
                        ads.append(ad)

            # Step 3: 如果行级提取失败，用区域截图+全页面文本解析
            if not ads:
                print("   行级提取未获得有效广告，尝试区域截图+全文本解析...")
                # 对页面中部（广告数据区域）截取区域截图
                try:
                    # 滚动到页面中部（广告表格通常在页面中间）
                    self.page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight / 3)"
                    )
                    time.sleep(2)
                    region_screenshot = (
                        OUTPUT_DIR
                        / f"semrush_ads_region_{domain}_{int(time.time())}.png"
                    )
                    self.page.screenshot(path=str(region_screenshot), full_page=False)
                    print(f"   区域截图已保存: {region_screenshot}")
                except:
                    pass

                # 尝试从全页面文本中解析
                try:
                    full_text = self.page.inner_text("body", timeout=10000)
                    if full_text:
                        ads = self._parse_ad_samples_from_text(full_text, domain)
                        # 使用完整的过滤函数过滤掉SEMrush UI文本
                        ads = self._filter_valid_ads(ads, domain)
                except:
                    pass

            if ads:
                # 应用完整的过滤函数
                ads = self._filter_valid_ads(ads, domain)
                if ads:
                    print(f"   截图+行级提取获得 {len(ads)} 条广告")
                else:
                    print("   截图+行级提取的广告全部被过滤为无效")
            else:
                print("   截图+行级提取未获得有效广告")

        except Exception as e:
            print(f"   截图+行级提取失败: {e}")
            import traceback

            traceback.print_exc()

        return ads

    def _parse_single_ad_row(self, row_text, domain):
        """解析单行广告文本为结构化广告数据

        SEMrush广告研究页面的行格式：
        1. 带URL：Headline1 | Headline2 | Headline3    https://www.example.com
                    Description line 1. Description line 2.
        2. 纯文本：Headline text
                    Description text
        """
        import re

        if not row_text or len(row_text) < 10:
            return None

        # 检查是否包含英文文本（广告文案必须是英文的，目标市场是US）
        if not re.search(r"[a-zA-Z]{3,}", row_text):
            return None

        # 尝试提取URL
        url = ""
        url_match = re.search(r"(https?://\S+)", row_text)
        if url_match:
            url = url_match.group(1).rstrip(",;.")
            # URL之前的部分是标题
            headline_part = row_text[: url_match.start()].strip()
        else:
            headline_part = row_text

        # 清理标题
        headline_part = re.sub(r"\s{2,}", " ", headline_part).strip()

        # 跳过太短或太长的标题
        if len(headline_part) < 3 or len(headline_part) > 200:
            return None

        # 构建广告对象
        ad = {
            "headline": headline_part[:120],
            "raw": row_text[:500],
        }
        if url:
            ad["url"] = url

        # 如果有竖线分隔，可能是多标题
        if "|" in headline_part:
            parts = [p.strip() for p in headline_part.split("|") if p.strip()]
            ad["headlines_parts"] = parts[:3]

        # 描述：如果行文本比标题长很多，剩余部分作为描述
        if len(row_text) > len(headline_part) + 20:
            desc_part = row_text[len(headline_part) :].strip()
            # 去掉URL部分
            if url:
                desc_part = desc_part.replace(url, "").strip()
            if desc_part and len(desc_part) > 10:
                # 按句号分割成多个描述
                desc_lines = [
                    d.strip()
                    for d in re.split(r"[.!?]\s", desc_part)
                    if d.strip() and len(d.strip()) > 5
                ]
                if desc_lines:
                    ad["descriptions"] = desc_lines[:3]
                else:
                    ad["descriptions"] = [desc_part[:200]]

        return ad
        """从概览页DOM中提取广告文案（改进版，针对概览页的Shadow DOM结构）"""
        ads = []
        try:
            # 方法1: 查找广告研究section下的所有文本块
            # 概览页的section通过 h2[data-at="section-title"] 标识
            # 找到"广告研究"标题，然后获取其父容器中的所有文本
            try:
                # 定位广告研究section
                ad_section_el = self.page.locator(
                    'h2[data-at="section-title"]:has-text("广告研究")'
                ).first
                if ad_section_el.is_visible(timeout=3000):
                    # 获取该section的祖先容器
                    # 向上3层到section容器
                    container = ad_section_el.evaluate_handle(
                        'el => el.closest("[data-at]") || el.parentElement?.parentElement?.parentElement'
                    )
                    if container:
                        container_el = container.as_element()
                        if container_el:
                            section_text = container_el.inner_text()
                            if section_text and len(section_text) > 50:
                                print(
                                    f"   广告研究section文本长度: {len(section_text)}"
                                )
                                # 尝试从section文本中解析
                                lines = section_text.split("\n")
                                # 跳过标题行
                                content_start = 0
                                for i, line in enumerate(lines):
                                    if (
                                        "广告研究" in line
                                        or "Advertising Research" in line
                                    ):
                                        content_start = i + 1
                                        break
                                remaining = lines[content_start:]
                                ads = self._parse_ad_lines_from_overview(
                                    remaining, data.get("domain", "")
                                )
            except Exception as e:
                print(f"   DOM section提取失败: {e}")

            # 方法2: 使用JS直接查找包含广告文本的shadow DOM
            if not ads:
                try:
                    # 在整个页面中搜索可能包含广告的shadow DOM
                    ad_texts = self.page.evaluate("""() => {
                        const results = [];
                        // 搜索所有元素（包括shadow DOM）
                        const allEls = document.querySelectorAll('*');
                        for (const el of allEls) {
                            if (el.shadowRoot) {
                                const text = el.shadowRoot.textContent?.trim();
                                if (text && text.length > 50 && text.length < 5000) {
                                    // 检查是否包含广告相关内容
                                    const lower = text.toLowerCase();
                                    if (lower.includes('headline') || lower.includes('description') ||
                                        lower.includes('title') || lower.includes('广告') ||
                                        lower.includes('sample') || lower.includes('creative')) {
                                        results.push(text.substring(0, 2000));
                                    }
                                }
                            }
                        }
                        return results;
                    }""")
                    if ad_texts:
                        print(
                            f"   从Shadow DOM找到 {len(ad_texts)} 个可能包含广告的元素"
                        )
                        for text in ad_texts[:5]:
                            lines = text.split("\n")
                            parsed = self._parse_ad_lines_from_overview(
                                lines, data.get("domain", "")
                            )
                            ads.extend(parsed)
                except Exception as e:
                    print(f"   Shadow DOM提取失败: {e}")

            # 方法3: 旧的DOM提取兜底
            if not ads:
                self._extract_ads_from_dom(data)
                ads = data.get("ad_copies", [])

        except Exception as e:
            print(f"   DOM v2提取失败: {e}")

        return ads

    def _extract_ads_from_subpage(self, data):
        """兜底方法：跳转到广告研究子页面提取广告文案

        外贸侠SEMrush导航URL结构（从HTML源码确认）：
        - 广告研究: /analytics/adwords/positions  (data-has-domain-query, data-has-db)
        - 自然排名: /analytics/organic/overview   (data-has-domain-query, data-has-db)
        - 错误路径: /advertising/ad-copies/{domain} 会被重定向回概览页
        """
        import re

        ads = []
        print("   🔄 跳转到广告研究子页面...")
        try:
            current_url = self.page.url
            domain = data.get("domain", "")

            # 导航到广告研究子页面
            base = "/".join(current_url.split("/")[:3])

            # 从当前URL提取db参数
            db_param = "us"  # 默认US市场
            db_match = re.search(r"[?&]db=(\w+)", current_url)
            if db_match:
                db_param = db_match.group(1)

            # 使用正确的广告研究URL路径（从SEMrush导航HTML确认）
            # 路径1: /analytics/adwords/positions（广告研究 - 按域名查询）
            ad_url = f"{base}/analytics/adwords/positions?db={db_param}&q={domain}&searchType=domain"
            print(f"   导航到: {ad_url}")
            self.page.goto(ad_url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(5)
            try:
                self.page.wait_for_load_state("networkidle", timeout=15000)
            except:
                pass

            print(f"   广告子页面URL: {self.page.url}")

            # 检查是否被重定向回概览页
            actual_url = self.page.url
            if "/analytics/overview" in actual_url:
                print("   ⚠️ 被重定向回概览页，尝试点击侧边栏导航...")
                # 尝试通过点击侧边栏"广告研究"链接导航
                try:
                    ad_nav = self.page.locator(
                        'srf-sidebar-list-item[nav-item="analytics.advertising_research:domain:index"]'
                    ).first
                    if ad_nav.is_visible(timeout=3000):
                        ad_nav.click()
                        time.sleep(5)
                        print(f"   点击侧边栏后URL: {self.page.url}")
                except Exception as nav_e:
                    print(f"   侧边栏导航失败: {nav_e}")

            # 等待数据加载
            time.sleep(3)

            # 尝试在广告研究页面上切换到"广告副本"子标签
            try:
                ad_copy_tabs = [
                    "text=广告副本",
                    "text=文字广告",
                    "text=Ad Copies",
                    "text=Text Ads",
                    '[data-at*="ad-copies"]',
                    'a:has-text("广告副本")',
                    'a:has-text("Ad Copies")',
                ]
                for tab_sel in ad_copy_tabs:
                    try:
                        tab = self.page.locator(tab_sel).first
                        if tab.is_visible(timeout=2000):
                            tab.click()
                            print(f"   已点击广告副本标签: {tab_sel}")
                            time.sleep(3)
                            break
                    except:
                        continue
            except:
                pass

            # 提取页面文本
            page_text = ""
            try:
                page_text = self.page.inner_text("body", timeout=10000)
            except:
                pass

            if page_text:
                # 保存子页面调试文本
                try:
                    debug_file = (
                        OUTPUT_DIR
                        / f"semrush_ad_subpage_{domain}_{int(time.time())}.txt"
                    )
                    debug_file.write_text(page_text[:50000], encoding="utf-8")
                    print(f"   子页面文本已保存: {debug_file}")
                except:
                    pass

                # 在子页面文本中查找广告内容
                # 子页面结构通常：标题行（Headline1 | Headline2 | Headline3）→ 描述 → URL
                ad_copies = self._parse_ad_samples_from_text(page_text, domain)
                if ad_copies:
                    # 过滤无效广告
                    valid_ads = self._filter_valid_ads(ad_copies, domain)
                    if valid_ads:
                        print(
                            f"   从子页面解析到 {len(valid_ads)} 条广告（原始{len(ad_copies)}条）"
                        )
                        return valid_ads
                    else:
                        print(
                            f"   子页面解析到 {len(ad_copies)} 条广告，但全部被过滤为无效"
                        )

                # 尝试截图+行级DOM提取
                print("   文本解析未获得有效广告，尝试截图+行级提取...")
                ad_copies = self._extract_ads_by_screenshot(data)
                if ad_copies:
                    return ad_copies

                # 尝试DOM提取
                self._extract_ads_from_dom(data)
                ads = data.get("ad_copies", [])
                if ads:
                    # 过滤DOM提取的结果
                    ads = self._filter_valid_ads(ads, domain)

        except Exception as e:
            print(f"   广告子页面提取失败: {e}")

        return ads

    def _assemble_ad_copy(self, buffer, target_domain):
        """将文本行缓冲区组装成广告文案结构"""
        import re

        # 过滤明显不是广告的行
        filtered = []
        # SEMrush UI 文本黑名单（中文+英文）
        ui_blacklist = {
            "搜索量",
            "CPC",
            "CPC (USD)",
            "流量",
            "流量 (%)",
            "竞争对手",
            "竞争程度",
            "共同关键词",
            "付费关键词",
            "付费搜索流量",
            "竞争排名图谱",
            "谷歌 SERP 上的排名",
            "主要付费搜索竞争对手",
            "自然搜索关键词",
            "自然搜索流量",
            "自然关键词",
            "引用域名",
            "引用IP",
            "引用来源",
            "广告文案",
            "广告副本",
            "广告拷贝",
            "文字广告样本",
            "广告研究",
            "反向链接",
            "Sortable",
            "导出",
            "更多",
            "筛选",
            "下载",
            "查看详情",
            "查看全部",
            "展开",
            "收起",
            "2-3",
            "other",
            "US",
            "UK",
            "DE",
            "全世界",
        }
        # SEMrush平台功能描述文本黑名单（这些是SEMrush自己的UI描述，不是广告文案）
        semrush_ui_descriptions = {
            "全面了解域名及其在线可见度",
            "分析域名随时间的增长趋势",
            "查看域名占据主导地位的市场",
            "发现为域名吸引自然和付费搜索流量的主题和关键词",
            "比较不同国家中域名的自然搜索和付费搜索效果",
            "查看特定市场域名的自然份额",
            "将趋势导出为 xls 或 csv",
            "将报告轻松导出为 xls 或 csv",
            "节省用于摘要分析的时间",
            "揭示和分析特定国家或全球的关键指标",
            "通过一站式获取域名增长趋势的关键数据来节省报告时间",
            "评估域名在特定时期内的自然流量、付费流量和反向链接的进度",
            "获取免费一对一专属演示",
            "我们的专员将从头指导您逐步了解如何充分利用 Semrush 平台",
            "请勿出售我的个人信息",
        }
        # JS/JSON代码特征关键词（外贸侠包装层代码）
        js_code_indicators = {
            "static_url",
            "is_legacy",
            "csrfToken",
            "cookie_domain",
            "searchbarApiV1Config",
            "PopupManager",
            "switchLanguage",
            "upgrade_button",
            "foldersApiV1Config",
            "toolQueryType",
            "function(",
            "var w=window",
            "Intercom",
            "reattach_activator",
            "DOMContentLoaded",
            "createElement",
            "parentNode.insertBefore",
            "attachEvent",
            "addEventListener",
            "wmxpro.com/static",
        }
        for line in buffer:
            # 跳过纯数字行、百分比行、UI提示
            if re.match(r"^[0-9.,%KMB]+$", line):
                continue
            if re.match(r"^[+-]?[0-9.]+%$", line):
                continue
            if re.match(r"^\d+[-~]\d+$", line):  # 范围如 "2-3"
                continue
            if "按" in line and "Tab" in line:
                continue
            if "启用" in line or "图形" in line or "图表" in line:
                continue
            if line in ui_blacklist:
                continue
            # 跳过SEMrush平台功能描述文本（不是广告文案）
            if line in semrush_ui_descriptions:
                continue
            # 跳过纯中文且像UI标签的行（≤6个中文字符，不含英文/数字/标点）
            if len(line) <= 6 and re.match(r"^[\u4e00-\u9fff]+$", line):
                # 纯中文短词大多是UI标签
                continue
            # 跳过JS/JSON代码行（外贸侠包装层）
            line_lower = line.lower()
            if any(indicator in line_lower for indicator in js_code_indicators):
                continue
            # 跳过多行JSON对象（含多个 "key": value 模式）
            if len(re.findall(r'"[a-z_]+":\s', line)) >= 2:
                continue
            # 跳过纯代码特征行（大括号、分号、等号赋值）
            if re.match(r'^[{"]', line) and ('":' in line or '":' in line):
                continue
            filtered.append(line)

        if len(filtered) < 2:
            return None

        # Google Ads 格式：标题（≤30字符）+ 描述（≤90字符）+ 显示URL
        headline = ""
        descriptions = []
        url = ""

        # 第一行通常是标题（短，≤60字符）
        for line in filtered:
            if len(line) <= 60 and not headline:
                headline = line
            elif (
                line.startswith("http")
                or line.startswith("www.")
                or re.match(r"^[a-z0-9][-a-z0-9.]*\.(com|net|org|io)", line)
            ):
                url = line
            elif 5 < len(line) <= 150:
                descriptions.append(line)

        # 标题太短或太长就不算有效
        if len(headline) < 3:
            headline = ""

        if not headline and not descriptions:
            return None

        # 关键验证：真实广告应该至少有一部分是英文内容
        # 因为 Google Ads 面向美国市场，广告文案一定是英文
        all_text = (headline + " " + " ".join(descriptions)).lower()
        has_english = bool(re.search(r"[a-z]{3,}", all_text))
        if not has_english:
            # 纯中文的内容不太可能是Google Ads广告文案
            return None

        return {
            "headline": headline[:60],
            "descriptions": descriptions[:3],
            "url": url,
            "raw": "\n".join(filtered)[:300],
        }

    def _extract_ads_from_dom(self, data):
        """从DOM元素提取广告文案"""
        try:
            ad_els = self.page.locator(
                '[class*="ad-copy"], [class*="AdCopy"], [class*="creative"], '
                '[class*="Creative"], [class*="snippet"], [class*="Snippet"], '
                '[class*="adText"], [class*="AdText"], [class*="textAd"]'
            ).all()
            for el in ad_els[:20]:
                try:
                    text = el.inner_text().strip()
                    if text and 10 < len(text) < 500:
                        if text not in [a.get("raw", "") for a in data["ad_copies"]]:
                            data["ad_copies"].append(
                                {
                                    "raw": text[:300],
                                }
                            )
                except:
                    continue
            if data["ad_copies"]:
                print(f"   从DOM元素提取到 {len(data['ad_copies'])} 条广告")
        except:
            pass

    def _extract_serp_distribution(self, page_text, data):
        """提取SERP分布数据"""
        import re

        try:
            # SERP 分布：如 "自然搜索 95.3% AI Overviews 1.4%"
            serp_patterns = [
                (r"自然搜索[^0-9]*([0-9.]+)%", "organic"),
                (r"AI Overviews[^0-9]*([0-9.]+)%", "ai_overviews"),
                (r"精选摘要[^0-9]*([0-9.]+)%", "featured_snippet"),
                (r"其他 SERP[^0-9]*([0-9.]+)%", "other_serp"),
                (r"图片包[^0-9]*([0-9.]+)%", "image_pack"),
                (r"视频[^0-9]*([0-9.]+)%", "video"),
            ]
            for pattern, key in serp_patterns:
                match = re.search(pattern, page_text)
                if match:
                    data["serp_distribution"][key] = float(match.group(1))

            if data["serp_distribution"]:
                print(f"   SERP分布: {data['serp_distribution']}")

        except Exception as e:
            print(f"   SERP分布提取失败: {e}")

    def _extract_country_traffic(self, page_text, data):
        """提取按国家/地区划分的流量数据

        概览页上的格式：
        按国家/地区划分
        国家  可见度  提及
        全世界  25    2.3K
        US     47    1.9K
        CA     28    119
        AU     28    81
        """
        import re

        try:
            # 查找"按国家/地区划分"区域
            country_section = ""
            markers = ["按国家/地区划分", "按国家划分", "By Country"]
            for marker in markers:
                idx = page_text.find(marker)
                if idx >= 0:
                    # 取标记后500字符
                    country_section = page_text[idx : idx + 500]
                    break

            if not country_section:
                return

            # 解析国家数据
            # 格式：国家代码 + 数字 + 数字
            # 国家代码：US, UK, DE, CA, AU, JP, FR, IT, ES, BR, IN, MX, NL, PL, RU, TR, ID, TH, VN, PH 等
            country_pattern = re.compile(
                r"\b(全世界|US|UK|DE|CA|AU|JP|FR|IT|ES|BR|IN|MX|NL|PL|RU|TR|ID|TH|VN|PH|CN|KR|TW|HK|SG|MY|NZ|ZA|AE|SA|EG|NG|KE|AR|CL|CO|PE|VE)\s+(\d+)\s+([\d.KM]+)",
                re.IGNORECASE,
            )

            countries = []
            for match in country_pattern.finditer(country_section):
                country = match.group(1).upper()
                if country == "全世界":
                    country = "GLOBAL"
                visibility = int(match.group(2))
                mentions = match.group(3)

                # 转换提及数（如 2.3K -> 2300）
                mentions_num = 0
                if mentions:
                    mentions = mentions.upper()
                    if "K" in mentions:
                        mentions_num = float(mentions.replace("K", "")) * 1000
                    elif "M" in mentions:
                        mentions_num = float(mentions.replace("M", "")) * 1000000
                    else:
                        try:
                            mentions_num = int(mentions)
                        except:
                            pass

                countries.append(
                    {
                        "country": country,
                        "visibility": visibility,
                        "mentions": int(mentions_num) if mentions_num else 0,
                    }
                )

            if countries:
                data["country_traffic"] = countries
                print(f"   按国家/地区划分: {len(countries)} 个国家/地区")

        except Exception as e:
            print(f"   国家/地区数据提取失败: {e}")

    def save_data(self, data, merchant_id, domain):
        """保存数据到文件"""
        self.output_file = OUTPUT_DIR / f"semrush_collected_{merchant_id}.json"

        output = {
            "merchant_id": merchant_id,
            "domain": domain,
            "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data": data,
        }

        self.output_file.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n💾 数据已保存: {self.output_file}")
        return str(self.output_file)

    def collect(self, merchant_id, domain):
        """执行完整采集流程"""
        print("=" * 60)
        print(f"🚀 开始采集 SEMrush 数据")
        print(f"   商户ID: {merchant_id}")
        print(f"   域名: {domain}")
        print("=" * 60)

        # 重置API拦截数据（每次采集前清空）
        self._api_responses = {
            "overview": None,
            "organic_keywords": None,
            "paid_keywords": None,
            "ad_copies": None,
            "competitors_organic": None,
            "competitors_paid": None,
            "referring_sources": None,
            "raw_api_urls": [],
        }
        self._rpc_dump_count = 0

        try:
            # 1. 连接 Chrome（含自动启动）
            if not self.connect():
                return {"success": False, "error": "Chrome 调试模式启动/连接失败"}

            # 2. 创建新页面
            self.page = self.context.new_page()
            self._setup_api_interceptor()
            print("✅ 创建新页面（已启用API拦截器）")

            # 3. 先打开外贸侠登录页，检查登录状态
            if not self.open_login_page():
                return {"success": False, "error": "外贸侠登录失败或超时"}

            # 4. 导航到 SEMrush 高级版（如果需要）
            if not self.navigate_to_semrush():
                return {"success": False, "error": "无法导航到 SEMrush 高级版"}

            # 5. 访问 SEMrush 概览页（带查询参数）
            url = f"{WMXPRO_URL}&q={domain}"
            print(f"\n🌐 访问 SEMrush 概览页...")
            print(f"   URL: {url}")
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 等待页面加载
            time.sleep(10)
            try:
                self.page.wait_for_load_state("networkidle", timeout=30000)
            except:
                pass

            print(f"✅ 页面已加载: {self.page.url}")

            # 4. 滚动页面以触发懒加载元素
            print("\n📜 滚动页面以加载懒加载元素...")
            try:
                # 滚动到底部
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)
                # 滚动回顶部
                self.page.evaluate("window.scrollTo(0, 0)")
                time.sleep(2)
                # 再次滚动到中间位置
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                time.sleep(2)
                print("   滚动完成")
            except Exception as e:
                print(f"   滚动失败: {e}")

            # 5. 检查并提取广告和付费关键词数据
            print("\n📊 提取广告和付费关键词数据...")

            # 提取文字广告样本
            ad_copies = []
            try:
                sample_ads = self.page.locator('[data-at="do-paid-sampleads"]')
                count = sample_ads.count()
                print(f"   文字广告样本区域元素数量: {count}")
                if count > 0:
                    section_text = sample_ads.first.inner_text(timeout=10000)
                    print(f"   文字广告样本区域文本长度: {len(section_text)}")
                    ad_copies = self._parse_text_ads_from_section(section_text, domain)
                    if ad_copies:
                        print(f"   从文字广告样本解析到 {len(ad_copies)} 条广告")
            except Exception as e:
                print(f"   提取文字广告样本失败: {e}")

            # 提取付费关键词
            paid_keywords = []
            try:
                paid_kw = self.page.locator('[data-at="do-paid-keywords"]')
                count = paid_kw.count()
                print(f"   主要付费关键词区域元素数量: {count}")
                if count > 0:
                    section_text = paid_kw.first.inner_text(timeout=10000)
                    print(f"   主要付费关键词区域文本长度: {len(section_text)}")
                    paid_keywords = self._parse_paid_keywords_from_section(section_text)
                    if paid_keywords:
                        print(
                            f"   从主要付费关键词解析到 {len(paid_keywords)} 个关键词"
                        )
            except Exception as e:
                print(f"   提取付费关键词失败: {e}")

            # 6. 提取其他数据
            data = self.extract_data()

            # 7. 合并广告和付费关键词数据
            if ad_copies:
                data["ad_copies"] = ad_copies
            if paid_keywords:
                data["paid_keywords"]["top_keywords"] = paid_keywords

            # 8. 保存数据
            output_path = self.save_data(data, merchant_id, domain)

            print("\n" + "=" * 60)
            print("✅ 采集完成！")
            print(f"📁 输出文件: {output_path}")
            print("=" * 60)

            return {
                "success": True,
                "output_file": output_path,
                "data_summary": {
                    "domain": data.get("domain", ""),
                    "organic_traffic": data.get("traffic", {}).get("organic", ""),
                    "paid_traffic": data.get("traffic", {}).get("paid", ""),
                    "authority_score": data.get("traffic", {}).get(
                        "authority_score", ""
                    ),
                    "organic_keywords_total": data.get("organic_keywords", {}).get(
                        "total", ""
                    ),
                    "paid_keywords_total": data.get("paid_keywords", {}).get(
                        "total", ""
                    ),
                    "top_organic_keywords_count": len(
                        data.get("organic_keywords", {}).get("top_keywords", [])
                    ),
                    "top_paid_keywords_count": len(
                        data.get("paid_keywords", {}).get("top_keywords", [])
                    ),
                    "competitors_count": len(data.get("competitors", [])),
                    "referring_sources_count": len(data.get("referring_sources", [])),
                    "ad_copies_count": len(data.get("ad_copies", [])),
                    "serp_distribution": data.get("serp_distribution", {}),
                },
            }

        except Exception as e:
            print(f"\n❌ 采集过程中出错: {e}")
            import traceback

            traceback.print_exc()
            return {"success": False, "error": str(e)}

        finally:
            # 注意：不关闭 browser，保持 Chrome 继续运行
            # 只断开 Playwright 连接
            try:
                # 先移除API拦截器，避免关闭后异步回调报 TargetClosedError
                if self.page and hasattr(self, "_api_listener"):
                    try:
                        self.page.remove_listener("response", self._api_listener)
                    except:
                        pass
            except:
                pass
            try:
                if self._playwright:
                    self._playwright.stop()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(description="外贸侠 SEMrush 数据采集")
    parser.add_argument("merchant_id", help="商户ID")
    parser.add_argument("domain", help="要采集的域名")
    parser.add_argument(
        "--chrome-ws", default=CHROME_WS, help="Chrome DevTools WebSocket URL"
    )

    args = parser.parse_args()

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 执行采集
    collector = WaimaoxiaSemrushCollector(chrome_ws=args.chrome_ws)
    result = collector.collect(args.merchant_id, args.domain)

    # 输出结果
    print("\n" + "-" * 60)
    print("RESULT_JSON_START")
    print(json.dumps(result, ensure_ascii=False))
    print("RESULT_JSON_END")

    # 保存到数据库
    if result.get("success") and result.get("data"):
        try:
            import requests

            save_url = "http://localhost:5055/api/save_semrush_data"
            save_data = {
                "merchant_id": args.merchant_id,
                "domain": args.domain,
                "data": result["data"],
            }
            resp = requests.post(save_url, json=save_data, timeout=10)
            save_result = resp.json()
            if save_result.get("success"):
                print(f"\n✅ 数据已保存到数据库")
            else:
                print(f"\n⚠️ 保存到数据库失败: {save_result.get('error')}")
        except Exception as e:
            print(f"\n⚠️ 保存到数据库异常: {e}")

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
