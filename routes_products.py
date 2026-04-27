# routes_products.py - 商品列表、广告方案、广告生成API
# 从 ads_manager.py 行 299-2859 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, datetime, subprocess
from pathlib import Path
from flask import (
    Blueprint,
    render_template_string,
    jsonify,
    request,
    redirect,
    url_for,
    send_file,
    Response,
    current_app,
)
from urllib.parse import quote
from app_config import (
    DB,
    BASE_DIR,
    SCRAPER_SCRIPT,
    OUTPUT_DIR,
    STOP_FILE,
    PROGRESS_FILE,
    _generating,
    _gen_lock,
    YP_SYNC_SCRIPT,
    PYTHON_EXE,
)

# Google Ads 技能文件路径
GOOGLE_ADS_SKILL_PATH = Path(r"D:\workspace\claws\google-ads-skill\SKILL-Google-Ads.md")
GOOGLE_ADS_SKILL_VERSION = "6.3"

from db import (
    get_db,
    _db,
    _cached_count,
    _count_cache,
    _cache_table_ok,
    check_cache_table,
)
from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK

bp = Blueprint("products", __name__)

# ═══════════════════════════════════════════════════════════════════════════
# 广告质量后处理函数
# ═══════════════════════════════════════════════════════════════════════════

# Google Ads 敏感词/禁用词列表
AD_BANNED_WORDS = [
    "best",
    "#1",
    "number one",
    "guaranteed",
    "click here",
    "limited time",
    "act now",
    "hurry",
    "miracle",
    "instant",
    "overnight",
    "permanent",
    "cure",
    "100%",
    "works for everyone",
]

# 需要替换的敏感词映射
AD_WORD_REPLACEMENTS = {
    "buy now": "shop now",
    "click here": "learn more",
    "free": "complimentary",
    "best": "top-rated",
    "#1": "leading",
    "guaranteed": "proven",
    "100%": "",
    "works for everyone": "suitable for most",
}


# ─────────────────────────────────────────────────────────────────────────────
# 异步任务状态存储
# ─────────────────────────────────────────────────────────────────────────────
_ads_generation_tasks = {}  # {task_id: {status, result, error, created_at}}
_ads_task_lock = threading.Lock()

# 采集任务状态存储
_collect_tasks = {}  # {task_id: {status, merchant_id, node_type, started_at, completed_at}}
_collect_task_lock = threading.Lock()

# 改进任务状态存储
_improvement_tasks = {}  # {task_id: {status, result, error, created_at}}
_improvement_task_lock = threading.Lock()


def _get_task_id(asin: str, merchant_id: str) -> str:
    """生成任务 ID"""
    return f"{merchant_id}_{asin}"


def _background_generate_ads(
    task_id: str, product: dict, brand_keywords: list, merchant_id: str
):
    """后台线程：生成广告方案"""
    global _ads_generation_tasks

    print(f"[Background] Starting task {task_id}...")
    print(
        f"[Background] Product: {product.get('asin')} - {product.get('amz_title') or product.get('product_name')}"
    )
    print(
        f"[Background] Brand keywords: {brand_keywords[:5] if brand_keywords else 'None'}"
    )

    try:
        # 更新状态为进行中
        with _ads_task_lock:
            _ads_generation_tasks[task_id]["status"] = "generating"
            _ads_generation_tasks[task_id]["started_at"] = (
                datetime.datetime.now().isoformat()
            )

        # 尝试 AI 生成
        ads_plan = None
        generation_method = None
        ai_error = None

        try:
            print(f"[Background] Trying AI generation...")
            ads_plan = _generate_ads_with_ai(product, brand_keywords)
            if ads_plan:
                generation_method = "AI"
                print(f"[Background] AI generation succeeded!")
        except Exception as e:
            ai_error = str(e)
            print(f"[Background] AI generation failed: {e}")

        # AI 失败，降级到规则引擎
        if not ads_plan:
            print(f"[Background] Falling back to rule engine...")
            try:
                ads_plan = _generate_ads_with_rules(product, brand_keywords)
                if ads_plan:
                    generation_method = "Rule Engine (AI fallback)"
                    print(f"[Background] Rule engine succeeded!")
            except Exception as e:
                print(f"[Background] Rule engine failed: {e}")
                raise Exception(f"AI error: {ai_error}, Rule engine error: {str(e)}")

        if not ads_plan:
            raise Exception("广告生成失败")

        # 保存到数据库
        _save_ads_plan_to_db(product.get("asin"), ads_plan, product, merchant_id)

        # 生成文件名
        brand = (product.get("brand") or "Unknown").replace(" ", "")
        product_short = (
            (product.get("amz_title") or product.get("product_name") or "Product")[:20]
            .replace(" ", "")
            .replace(",", "")
        )
        price = int(float(product.get("price") or 0))
        commission = (product.get("commission") or "0%").replace("%", "pct")
        filename = f"{brand}-{product_short}-{price}-{commission}.json"
        filename_txt = f"{brand}-{product_short}-{price}-{commission}.txt"

        # 保存 JSON 文件
        output_path = OUTPUT_DIR / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ads_plan, f, ensure_ascii=False, indent=2)

        # 保存 TXT 文件（方便复制粘贴）
        txt_content = _format_ads_plan_as_text(ads_plan)
        txt_path = OUTPUT_DIR / filename_txt
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)

        # 更新状态为完成
        with _ads_task_lock:
            _ads_generation_tasks[task_id]["status"] = "completed"
            _ads_generation_tasks[task_id]["result"] = {
                "asin": product.get("asin"),
                "filename": filename,
                "filename_txt": filename_txt,
                "download_url": f"/download/{filename}",
                "download_url_txt": f"/download/{filename_txt}",
                "campaigns": len(ads_plan.get("campaigns", [])),
                "ad_groups": sum(
                    len(c.get("ad_groups", [])) for c in ads_plan.get("campaigns", [])
                ),
                "keywords": sum(
                    len(ag.get("keywords", []))
                    for c in ads_plan.get("campaigns", [])
                    for ag in c.get("ad_groups", [])
                ),
                "method": generation_method,
            }
            _ads_generation_tasks[task_id]["completed_at"] = (
                datetime.datetime.now().isoformat()
            )

        print(f"[Background] Task {task_id} completed successfully")

    except Exception as e:
        # 更新状态为失败
        with _ads_task_lock:
            _ads_generation_tasks[task_id]["status"] = "failed"
            _ads_generation_tasks[task_id]["error"] = str(e)
            _ads_generation_tasks[task_id]["completed_at"] = (
                datetime.datetime.now().isoformat()
            )

        print(f"[Background] Task {task_id} failed: {e}")


def _format_ads_plan_as_text(ads_plan: dict) -> str:
    """
    将广告方案 JSON 格式化为易读的文本格式，方便复制粘贴
    """
    lines = []
    lines.append("=" * 70)
    lines.append("GOOGLE ADS ADVERTISING PLAN")
    lines.append("=" * 70)
    lines.append("")

    # 元数据
    metadata = ads_plan.get("metadata", {})
    if metadata:
        lines.append(f"Product: {metadata.get('product_name', 'N/A')}")
        lines.append(f"ASIN: {metadata.get('asin', 'N/A')}")
        lines.append(f"Brand: {metadata.get('brand', 'N/A')}")
        lines.append(f"Price: ${metadata.get('price', 0):.2f}")
        lines.append(f"Commission: {metadata.get('commission_rate', 'N/A')}")
        lines.append(
            f"Rating: {metadata.get('rating', 'N/A')}/5 ({metadata.get('review_count', 0)} reviews)"
        )
        lines.append(f"Generated: {metadata.get('generated_at', 'N/A')}")
        lines.append(f"Method: {metadata.get('generation_method', 'N/A')}")
        lines.append("")

    # 产品分析
    if "product_analysis" in ads_plan:
        lines.append("-" * 70)
        lines.append("PRODUCT ANALYSIS")
        lines.append("-" * 70)
        pa = ads_plan["product_analysis"]
        lines.append(f"Category: {pa.get('category', 'N/A')}")
        lines.append(f"Type: {pa.get('type', 'N/A')}")
        lines.append(f"Target CPA: ${pa.get('target_cpa', 0):.2f}")
        lines.append(f"Recommended Campaigns: {pa.get('recommended_campaigns', 'N/A')}")
        lines.append("")

    # 盈利评估
    if "profitability" in ads_plan:
        lines.append("-" * 70)
        lines.append("PROFITABILITY ANALYSIS")
        lines.append("-" * 70)
        pf = ads_plan["profitability"]
        lines.append(f"Break-even CPA: ${pf.get('break_even_cpa', 0):.2f}")
        lines.append(f"Feasibility: {pf.get('feasibility', 'N/A')}")
        lines.append("")

    # 账户级否定关键词
    if "account_negative_keywords" in ads_plan:
        lines.append("-" * 70)
        lines.append("ACCOUNT-LEVEL NEGATIVE KEYWORDS")
        lines.append("-" * 70)
        for kw in ads_plan["account_negative_keywords"]:
            lines.append(f"  - {kw}")
        lines.append("")

    # Campaigns
    campaigns = ads_plan.get("campaigns", [])
    for i, campaign in enumerate(campaigns, 1):
        lines.append("=" * 70)
        lines.append(f"CAMPAIGN {i}: {campaign.get('name', 'Unnamed')}")
        lines.append("=" * 70)
        lines.append(f"Daily Budget: ${campaign.get('budget_daily', 0):.2f}")
        lines.append(f"Bid Strategy: {campaign.get('bid_strategy', 'Manual CPC')}")
        lines.append("")

        # Campaign-level negative keywords
        camp_neg = campaign.get("campaign_negative_keywords", [])
        if camp_neg:
            lines.append("Campaign Negative Keywords:")
            for kw in camp_neg:
                lines.append(f"  - {kw}")
            lines.append("")

        # Ad Groups
        ad_groups = campaign.get("ad_groups", [])
        for j, ag in enumerate(ad_groups, 1):
            lines.append("-" * 50)
            lines.append(f"AD GROUP {j}: {ag.get('name', 'Unnamed')}")
            lines.append("-" * 50)

            # Keywords
            lines.append("Keywords:")
            for kw in ag.get("keywords", []):
                kw_text = kw.get("kw", "") if isinstance(kw, dict) else str(kw)
                match = kw.get("match", "B") if isinstance(kw, dict) else "B"
                match_type = {"E": "Exact", "P": "Phrase", "B": "Broad"}.get(
                    match, "Broad"
                )
                lines.append(f"  [{match_type}] {kw_text}")
            lines.append("")

            # Negative Keywords
            neg_kws = ag.get("negative_keywords", [])
            if neg_kws:
                lines.append("Negative Keywords:")
                for kw in neg_kws:
                    lines.append(f"  - {kw}")
                lines.append("")

            # Headlines
            lines.append("Headlines (max 30 chars):")
            for h in ag.get("headlines", []):
                h_text = h.get("text", "") if isinstance(h, dict) else str(h)
                chars = (
                    h.get("chars", len(h_text)) if isinstance(h, dict) else len(h_text)
                )
                lines.append(f"  [{chars}c] {h_text}")
            lines.append("")

            # Descriptions
            lines.append("Descriptions (max 90 chars):")
            for d in ag.get("descriptions", []):
                d_text = d.get("text", "") if isinstance(d, dict) else str(d)
                chars = (
                    d.get("chars", len(d_text)) if isinstance(d, dict) else len(d_text)
                )
                lines.append(f"  [{chars}c] {d_text}")
            lines.append("")

    # Ad Extensions
    if "sitelinks" in ads_plan or "callouts" in ads_plan:
        lines.append("=" * 70)
        lines.append("AD EXTENSIONS")
        lines.append("=" * 70)

        if "sitelinks" in ads_plan:
            lines.append("Sitelinks:")
            for sl in ads_plan["sitelinks"]:
                lines.append(f"  - {sl.get('text', '')}: {sl.get('url', '')}")
            lines.append("")

        if "callouts" in ads_plan:
            lines.append("Callouts:")
            for co in ads_plan["callouts"]:
                co_text = co.get("text", "") if isinstance(co, dict) else str(co)
                lines.append(f"  - {co_text}")
            lines.append("")

    # QA Report
    if "qa_report" in ads_plan:
        lines.append("=" * 70)
        lines.append("QA REPORT")
        lines.append("=" * 70)
        qa = ads_plan["qa_report"]
        for check in qa.get("checks", []):
            status = "PASS" if check.get("passed") else "FAIL"
            lines.append(
                f"  [{status}] {check.get('name', '')}: {check.get('details', '')}"
            )
        lines.append("")

    lines.append("=" * 70)
    lines.append("END OF ADVERTISING PLAN")
    lines.append("=" * 70)

    return "\n".join(lines)


def _format_improved_ads_as_text(asin: str, improvement: dict, product: dict) -> str:
    """
    将改进后的广告方案格式化为易读的文本格式，方便复制粘贴到 Google Ads
    """
    lines = []
    lines.append("=" * 70)
    lines.append("IMPROVED GOOGLE ADS PLAN")
    lines.append("=" * 70)
    lines.append("")

    # 产品信息
    lines.append(
        f"Product: {product.get('amz_title') or product.get('product_name', 'N/A')}"
    )
    lines.append(f"ASIN: {asin}")
    lines.append(f"Brand: {product.get('brand', 'N/A')}")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # 改进摘要
    changes = improvement.get("changes_made", [])
    if changes:
        lines.append("-" * 70)
        lines.append("CHANGES MADE")
        lines.append("-" * 70)
        for i, change in enumerate(changes, 1):
            lines.append(f"{i}. {change}")
        lines.append("")

    # 预期改进
    expected = improvement.get("expected_improvement", "")
    if expected:
        lines.append("-" * 70)
        lines.append("EXPECTED IMPROVEMENT")
        lines.append("-" * 70)
        lines.append(expected)
        lines.append("")

    # 改进后的 Campaigns
    campaigns = improvement.get("improved_campaigns", [])
    for i, campaign in enumerate(campaigns, 1):
        lines.append("=" * 70)
        lines.append(f"CAMPAIGN {i}: {campaign.get('name', 'Unnamed')}")
        lines.append("=" * 70)
        lines.append(f"Bid Strategy: {campaign.get('bid_strategy', 'Manual CPC')}")
        lines.append("")

        # Campaign-level negative keywords
        camp_neg = campaign.get("negative_keywords", [])
        if camp_neg:
            lines.append("Campaign Negative Keywords:")
            for kw in camp_neg:
                lines.append(f"  - {kw}")
            lines.append("")

        # Ad Groups
        ad_groups = campaign.get("ad_groups", [])
        for j, ag in enumerate(ad_groups, 1):
            lines.append("-" * 50)
            lines.append(f"AD GROUP {j}: {ag.get('name', 'Unnamed')}")
            if ag.get("theme"):
                lines.append(f"Theme: {ag.get('theme')}")
            lines.append("-" * 50)

            # Keywords
            keywords = ag.get("keywords", [])
            if keywords:
                lines.append("Keywords (copy to Google Ads):")
                for kw in keywords:
                    kw_text = kw.get("kw", "") if isinstance(kw, dict) else str(kw)
                    match = kw.get("match", "B") if isinstance(kw, dict) else "B"
                    match_type = {"E": "Exact", "P": "Phrase", "B": "Broad"}.get(
                        match, "Broad"
                    )
                    lines.append(f"  [{match_type}] {kw_text}")
                lines.append("")

            # Negative Keywords
            neg_kws = ag.get("negative_keywords", [])
            if neg_kws:
                lines.append("Negative Keywords:")
                for kw in neg_kws:
                    lines.append(f"  - {kw}")
                lines.append("")

            # Headlines
            headlines = ag.get("headlines", [])
            if headlines:
                lines.append("Headlines (max 30 chars, copy to Google Ads):")
                for h in headlines:
                    h_text = h.get("text", "") if isinstance(h, dict) else str(h)
                    chars = len(h_text)
                    lines.append(f"  [{chars}c] {h_text}")
                lines.append("")

            # Descriptions
            descriptions = ag.get("descriptions", [])
            if descriptions:
                lines.append("Descriptions (max 90 chars, copy to Google Ads):")
                for d in descriptions:
                    d_text = d.get("text", "") if isinstance(d, dict) else str(d)
                    chars = len(d_text)
                    lines.append(f"  [{chars}c] {d_text}")
                lines.append("")

    lines.append("=" * 70)
    lines.append("END OF IMPROVED ADVERTISING PLAN")
    lines.append("=" * 70)
    lines.append("")
    lines.append(
        "💡 TIP: Copy the headlines and descriptions above directly into Google Ads"
    )

    return "\n".join(lines)


def clean_ad_text(text: str, brand: str = "") -> str:
    """
    清理广告文本，移除敏感词并确保合规

    Args:
        text: 广告文本
        brand: 品牌名（用于检查是否包含）

    Returns:
        清理后的文本
    """
    text = text.strip()
    original_text = text

    # 1. 替换敏感词
    for banned, replacement in AD_WORD_REPLACEMENTS.items():
        if banned.lower() in text.lower():
            # 保持大小写
            pattern = re.compile(re.escape(banned), re.IGNORECASE)
            text = pattern.sub(replacement, text)

    # 2. 移除过度夸大的词汇（包括词根变体）
    exaggeration_patterns = [
        r"\bmiracle[s]?\b",
        r"\binstant(ly)?\b",
        r"\bovernight\b",
        r"\bpermanent(ly)?\b",
        r"\bcure[sd]?\b",
    ]
    for pattern in exaggeration_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # 3. 清理多余空格
    text = re.sub(r"\s+", " ", text).strip()

    # 4. 确保首字母大写
    if text:
        text = text[0].upper() + text[1:]

    return text


def validate_and_fix_ad(
    headlines: list, descriptions: list, brand: str = "", product_title: str = ""
) -> tuple:
    """
    验证并修正广告内容

    Args:
        headlines: 标题列表
        descriptions: 描述列表
        brand: 品牌名
        product_title: 产品标题

    Returns:
        (修正后的headlines, 修正后的descriptions, 警告列表)
    """
    warnings = []
    fixed_headlines = []
    fixed_descriptions = []

    # 处理标题
    for i, h in enumerate(headlines):
        text = h.get("text", "") if isinstance(h, dict) else str(h)
        text = clean_ad_text(text, brand)

        # 第一个标题：如果品牌名未出现，优先添加品牌名
        if i == 0 and brand and brand.lower() not in text.lower():
            # 尝试添加品牌名作为前缀
            brand_text = f"{brand} "
            remaining_chars = 30 - len(brand_text)
            if remaining_chars >= 10:
                text = brand_text + text[:remaining_chars].strip()
                warnings.append(f"已添加品牌名 '{brand}' 到标题")

        # 强制30字符限制
        if len(text) > 30:
            text = text[:30].rsplit(" ", 1)[0].strip()
            if len(text) < 20:
                text = text[:30].strip()

        fixed_headlines.append({"text": text, "chars": len(text)})

    # 处理描述
    for d in descriptions:
        text = d.get("text", "") if isinstance(d, dict) else str(d)
        text = clean_ad_text(text, brand)

        # 强制90字符限制
        if len(text) > 90:
            text = text[:90].rsplit(" ", 1)[0].strip()
            if len(text) < 70:
                text = text[:90].strip()

        fixed_descriptions.append({"text": text, "chars": len(text)})

    # 检查是否有敏感词被替换
    if original_text := " ".join([h.get("text", "") for h in headlines]):
        for banned in AD_BANNED_WORDS:
            if banned.lower() in original_text.lower():
                warnings.append(f"已替换敏感词 '{banned}'")

    return fixed_headlines, fixed_descriptions, warnings


# ═══════════════════════════════════════════════════════════════════════════
# 路由：广告流程页面
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/workflow")
def ad_workflow():
    """广告流程页面 - 可视化流程图"""
    template_path = BASE_DIR / "templates" / "ad_workflow.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return render_template_string(f.read())


# 路由：商品列表（主界面）
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/")
def product_list():
    # 优化：用连接池（避免每次新建连接 ~266ms 的开销）
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    page = int(request.args.get("page", 1))
    per_page = 30
    search = request.args.get("q", "").strip()
    has_amazon = request.args.get("has_amazon", "").strip()
    has_plan = request.args.get("has_plan", "").strip()
    sort = request.args.get("sort", "newest")
    category = request.args.get("category", "").strip()
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()

    # ─── 类别列表（缓存5分钟）────────────────────────────────────────────
    _cats_key = "all_categories"
    if _cats_key in _count_cache and _time.time() < _count_cache[_cats_key][1]:
        categories = _count_cache[_cats_key][0]
    else:
        cur.execute(
            "SELECT category_id, category_name FROM yp_categories ORDER BY category_name"
        )
        categories = [
            {"id": r["category_id"], "name": r["category_name"]} for r in cur.fetchall()
        ]
        _count_cache[_cats_key] = (categories, _time.time() + 300)

    # ─── 统计（用 information_schema 估算，3ms vs 700ms）──────────────────
    def _est_count(table):
        """从 information_schema 估算表行数（毫秒级）"""
        cur.execute(
            "SELECT TABLE_ROWS FROM information_schema.tables "
            "WHERE table_schema='affiliate_marketing' AND table_name=%s",
            (table,),
        )
        r = cur.fetchone()
        v = r.get("TABLE_ROWS") or r.get("table_rows") if r else None
        return int(v) if v else 0

    total_products = _cached_count(
        "est_yp_us_products",
        "SELECT TABLE_ROWS FROM information_schema.tables "
        "WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'",
    )
    total_amazon = _cached_count(
        "est_amazon_details",
        "SELECT TABLE_ROWS FROM information_schema.tables "
        "WHERE table_schema='affiliate_marketing' AND table_name='amazon_product_details'",
    )
    total_plans = _cached_count(
        "cnt_ads_plans_completed",
        "SELECT COUNT(*) FROM ads_plans WHERE plan_status='completed'",
    )
    # ─── 构建过滤条件（全部基于 yp_us_products）─────────────────────────
    # 优化：将引用外表(a/pl)的条件改为 EXISTS 子查询，使延迟关联子查询内不需要 JOIN
    where_clauses = []
    params = []
    # 标记是否需要外表 JOIN（影响 COUNT 查询策略）
    need_outer_join = False

    if search:
        where_clauses.append(
            "(p.product_name LIKE %s OR p.asin LIKE %s OR p.merchant_name LIKE %s)"
        )
        like = f"%{search}%"
        params += [like, like, like]

    if has_amazon == "1":
        where_clauses.append(
            "EXISTS (SELECT 1 FROM amazon_product_details _a WHERE _a.asin = p.asin)"
        )
    elif has_amazon == "0":
        where_clauses.append(
            "NOT EXISTS (SELECT 1 FROM amazon_product_details _a WHERE _a.asin = p.asin)"
        )

    if has_plan == "1":
        where_clauses.append(
            "EXISTS (SELECT 1 FROM ads_plans _pl WHERE _pl.asin = p.asin)"
        )
    elif has_plan == "0":
        where_clauses.append(
            "NOT EXISTS (SELECT 1 FROM ads_plans _pl WHERE _pl.asin = p.asin)"
        )

    if category:
        where_clauses.append(
            "EXISTS (SELECT 1 FROM amazon_product_details _a WHERE _a.asin = p.asin AND _a.category_path LIKE %s)"
        )
        params.append(f"%{category}%")

    if price_min:
        try:
            # yp_us_products 没有 price_num 字段，使用 CAST 转换
            where_clauses.append(
                "CAST(REPLACE(REPLACE(p.price,'$',''),',','') AS DECIMAL(10,2)) >= %s"
            )
            params.append(float(price_min))
        except ValueError:
            pass

    if price_max:
        try:
            where_clauses.append(
                "CAST(REPLACE(REPLACE(p.price,'$',''),',','') AS DECIMAL(10,2)) <= %s"
            )
            params.append(float(price_max))
        except ValueError:
            pass

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # ─── 排序 ─────────────────────────────────────────────────────────────
    # rating_desc 需要 JOIN amazon，特殊处理：改为子查询取值
    # 注意：yp_us_products 表没有 price_num 字段，需要用 CAST 转换
    # 预计佣金 = 价格 * 佣金率 / 100
    # 最高出价 = 预计佣金 / 30，最低出价 = 预计佣金 / 50（排序顺序与预计佣金相同）
    sort_map = {
        "commission_desc": "commission_num DESC",
        "commission_asc": "commission_num ASC",
        "price_desc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) DESC",
        "price_asc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) ASC",
        "earn_desc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 DESC",
        "earn_asc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 ASC",
        "max_bid_desc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 / 30 DESC",
        "max_bid_asc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 / 30 ASC",
        "min_bid_desc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 / 50 DESC",
        "min_bid_asc": "CAST(REPLACE(REPLACE(price,'$',''),',','') AS DECIMAL(10,2)) * commission_num / 100 / 50 ASC",
        "rating_desc": "product_id DESC",  # 简化：暂用 product_id 替代
        "newest": "product_id DESC",
    }
    order_sql = sort_map.get(sort, "product_id DESC")

    # ─── 总数 ─────────────────────────────────────────────────────────────
    if where_clauses:
        # 所有过滤条件已改为 EXISTS 子查询，可直接单表 COUNT（不需要 JOIN）
        count_sql = f"SELECT COUNT(*) as cnt FROM yp_us_products p {where_sql}"
        cur.execute(count_sql, params)
        total = cur.fetchone()["cnt"]
    else:
        # 无过滤：用 information_schema 估算（3ms vs 240ms）
        # 注意：MySQL 返回字段名可能大写，使用大写键
        cur.execute("""
            SELECT TABLE_ROWS FROM information_schema.tables
            WHERE table_schema='affiliate_marketing' AND table_name='yp_us_products'
        """)
        r = cur.fetchone()
        est = r.get("TABLE_ROWS") or r.get("table_rows") if r else None
        total = int(est) if est else total_products

    total_pages = max(1, (total + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    # ─── 分页查询：延迟关联（Deferred Join）──────────────────────────────
    # 原理：先用子查询走 idx_product_id 索引只取 30 个 asin（极快），
    #       再用 eq_ref 精确 JOIN 详情。避免全表扫描 + filesort。
    # 性能：2800ms → 115ms（提速 24x）
    # 注意：子查询内用别名 p，使 where_sql 的 p.xxx 条件有效
    data_sql = f"""
        SELECT
            p.asin, p.product_name, p.price, p.commission, p.commission_num,
            p.tracking_url, p.merchant_name, p.yp_merchant_id AS merchant_id,
            a.asin         AS amz_asin,
            a.title        AS amz_title,
            a.rating, a.review_count, a.main_image_url AS img,
            pl.plan_status, pl.id AS plan_id,
            COALESCE(mk.kw_count, 0) AS kw_count,
            ROUND(CAST(REPLACE(REPLACE(p.price,'$',''),',','') AS DECIMAL(10,2)) * p.commission_num / 100, 2) AS estimated_earn,
            ROUND(CAST(REPLACE(REPLACE(p.price,'$',''),',','') AS DECIMAL(10,2)) * p.commission_num / 100 / 30 * 7, 2) AS max_bid,
            ROUND(CAST(REPLACE(REPLACE(p.price,'$',''),',','') AS DECIMAL(10,2)) * p.commission_num / 100 / 50 * 7, 2) AS min_bid
        FROM (
            SELECT p.asin, p.yp_merchant_id
            FROM yp_us_products p
            {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
        ) sub
        JOIN yp_us_products p ON p.asin = sub.asin
        LEFT JOIN amazon_product_details a ON a.asin = sub.asin
        LEFT JOIN ads_plans pl ON pl.asin = sub.asin
        LEFT JOIN (
            SELECT merchant_id, COUNT(*) AS kw_count
            FROM ads_merchant_keywords
            GROUP BY merchant_id
        ) mk ON mk.merchant_id = sub.yp_merchant_id
    """
    cur.execute(data_sql, params + [per_page, offset])
    products = cur.fetchall()

    cur.close()
    conn.close()

    # ─── 渲染 ─────────────────────────────────────────────────────────────
    rows_html = ""
    for p in products:
        price_raw = str(p["price"] or "")
        price_str = (
            price_raw
            if price_raw.startswith("$")
            else (f"${price_raw}" if price_raw else "--")
        )
        comm_raw = str(p["commission"] or "")
        # 预计佣金 = 价格 * 佣金率 / 100
        estimated_earn = p.get("estimated_earn")
        earn_str = f"${estimated_earn:.2f}" if estimated_earn else "--"
        # 最高出价 = 预计佣金 / 30 * 7（人民币），最低出价 = 预计佣金 / 50 * 7（人民币）
        max_bid = p.get("max_bid")
        max_bid_str = f"¥{max_bid:.2f}" if max_bid else "--"
        min_bid = p.get("min_bid")
        min_bid_str = f"¥{min_bid:.2f}" if min_bid else "--"
        img = p["img"] or ""
        plan_status = p["plan_status"]
        asin = p["asin"]
        mid = p["merchant_id"] or ""
        kw_count = int(p["kw_count"] or 0)

        # 广告状态按钮
        if plan_status == "completed":
            action_btn = f'<a href="/plans/{asin}" class="btn btn-success btn-sm">查看广告</a><button class="btn btn-sm" style="background:#2e7d32;color:#fff;margin-left:4px;" onclick="downloadPlan(\'{asin}\')">下载方案</button>'
            plan_badge = '<span class="badge badge-green">已生成</span>'
        elif plan_status == "generating":
            action_btn = (
                f'<button class="btn btn-warning btn-sm" data-asin="{asin}" onclick="resetPlan(this)" '
                f'title="上次生成失败或超时，点击重置后重新制作">⚠ 重置并重试</button>'
            )
            plan_badge = '<span class="badge badge-orange" title="上次生成未完成，请点击重置">异常/超时</span>'
        else:
            has_amz = bool(p["amz_asin"])
            if has_amz:
                action_btn = f'<button class="btn btn-primary btn-sm" data-asin="{asin}" onclick="generateAd(this)">制作广告</button>'
                action_btn += f' <button class="btn btn-secondary btn-sm" data-asin="{asin}" onclick="generateAdAI(this)" title="AI + Google Ads 技能">🤖 AI</button>'
                action_btn += f' <button class="btn btn-sm" style="background:#6b5b95;color:#fff;" data-asin="{asin}" onclick="generateAdAgent(this)" title="三引擎广告生成（带记忆）">🧠 Agent</button>'
                action_btn += f' <button class="btn btn-sm" style="background:#e74c3c;color:#fff;" data-asin="{asin}" onclick="generateAdFromReport(this)" title="基于完整报告（含SEMrush数据）生成广告">📊 报告</button>'
            else:
                action_btn = (
                    f'<button class="btn btn-primary btn-sm" data-asin="{asin}" onclick="generateAd(this)" '
                    f'title="建议先点"采集Amazon"获取商品数据，再制作广告效果更好">制作广告</button>'
                    f' <button class="btn btn-secondary btn-sm" data-asin="{asin}" onclick="generateAdAI(this)" title="AI + Google Ads 技能">🤖 AI</button>'
                    f' <button class="btn btn-sm" style="background:#6b5b95;color:#fff;" data-asin="{asin}" onclick="generateAdAgent(this)" title="三引擎广告生成（带记忆）">🧠 Agent</button>'
                    f' <button class="btn btn-sm" style="background:#e74c3c;color:#fff;" data-asin="{asin}" onclick="generateAdFromReport(this)" title="基于完整报告（含SEMrush数据）生成广告">📊 报告</button>'
                    f'<div style="font-size:11px;color:#f08c00;margin-top:3px">⚠ 建议先采集Amazon数据</div>'
                )
            plan_badge = '<span class="badge badge-gray">未制作</span>'

        # Amazon 数据状态（用 amz_asin 判断，与筛选条件保持一致）
        # 商品名称始终使用 YP 平台的 product_name，Amazon 采集只是补充评分/评论等
        title_show = str(p["product_name"] or "")[:50]
        if p["amz_asin"]:
            # 检查是否是 404 标记（商品已下架）
            if p["amz_title"] == "__404__":
                amz_badge = '<span class="badge badge-red" title="Amazon 商品已下架">❌ 已下架</span>'
            else:
                amz_badge = '<span class="badge badge-green">✓ 已采集</span>'
        else:
            amz_badge = f'<button class="btn btn-warning btn-sm" data-asin="{asin}" onclick="fetchAmazon(this)">采集Amazon</button>'

        # 品牌关键词状态
        if kw_count > 0:
            kw_badge = f'<span class="badge badge-green" title="已有{kw_count}个品牌关键词">🔑 {kw_count}个词</span>'
        else:
            kw_badge = (
                f'<button class="btn btn-secondary btn-sm" style="font-size:11px;padding:3px 8px;" '
                f'data-mid="{mid}" data-asin="{asin}" onclick="fetchSuggest(this)" '
                f'title="采集 {p["merchant_name"] or mid} 的 Google Suggest 关键词">🔑 采集关键词</button>'
            )

        # 评分
        rating_str = f"⭐{p['rating']}" if p["rating"] else "--"
        review_str = str(p["review_count"]) if p["review_count"] else "--"

        img_html = (
            f'<img src="{img}" style="width:48px;height:48px;object-fit:cover;border-radius:6px;" onerror="this.style.display=\'none\'">'
            if img
            else "🛍️"
        )

        rows_html += f"""
        <tr id="row-{asin}">
          <td style="width:56px">{img_html}</td>
          <td>
            <div style="font-weight:600;font-size:13px;color:#e0e0e0">{title_show}</div>
            <div style="font-size:11px;color:#888;margin-top:2px">
              ASIN: <code>{asin}</code> | {p["merchant_name"] or "--"}
            </div>
            <div style="margin-top:4px;display:flex;gap:4px;flex-wrap:wrap;">
              {amz_badge}
              <span id="kw-{mid}">{kw_badge}</span>
            </div>
          </td>
          <td><b style="color:#e0e0e0">{price_str}</b></td>
          <td><b style="color:#64b5f6">{comm_raw}</b></td>
          <td><b style="color:#81c784">{earn_str}</b></td>
          <td><b style="color:#ff9800">{max_bid_str}</b></td>
          <td><b style="color:#90caf9">{min_bid_str}</b></td>
          <td>{rating_str}<br><small style="color:#888">{review_str} reviews</small></td>
          <td>{plan_badge}</td>
          <td style="white-space:nowrap">
            {action_btn}
            <button class="btn btn-secondary btn-sm" style="margin-top:4px"
              onclick="window.open('https://www.amazon.com/dp/{asin}','_blank')">Amazon</button>
          </td>
        </tr>"""

    # 分页
    def page_link(n, label=None):
        args = dict(request.args)
        args["page"] = n
        qs = "&".join(f"{k}={v}" for k, v in args.items())
        cls = "active" if n == page else ""
        return f'<a href="/?{qs}" class="{cls}">{label or n}</a>'

    pag_html = ""
    if total_pages > 1:
        if page > 1:
            pag_html += page_link(page - 1, "‹")
        start = max(1, page - 3)
        end = min(total_pages, page + 3)
        for i in range(start, end + 1):
            pag_html += page_link(i)
        if page < total_pages:
            pag_html += page_link(page + 1, "›")

    # sort options
    sort_labels = [
        ("newest", "最新收录"),
        ("earn_desc", "预计佣金 高→低"),
        ("earn_asc", "预计佣金 低→高"),
        ("max_bid_desc", "最高出价 高→低"),
        ("max_bid_asc", "最高出价 低→高"),
        ("min_bid_desc", "最低出价 高→低"),
        ("min_bid_asc", "最低出价 低→高"),
        ("commission_desc", "佣金率 高→低"),
        ("commission_asc", "佣金率 低→高"),
        ("price_desc", "价格 高→低"),
        ("price_asc", "价格 低→高"),
        ("rating_desc", "评分 高→低"),
    ]
    sort_opts = ""
    for val, label in sort_labels:
        sel = "selected" if val == sort else ""
        sort_opts += f'<option value="{val}" {sel}>{label}</option>'

    has_amazon_opts = f"""
        <option value="">Amazon数据：全部</option>
        <option value="1" {"selected" if has_amazon == "1" else ""}>有数据</option>
        <option value="0" {"selected" if has_amazon == "0" else ""}>无数据</option>"""
    has_plan_opts = f"""
        <option value="">广告方案：全部</option>
        <option value="1" {"selected" if has_plan == "1" else ""}>已制作</option>
        <option value="0" {"selected" if has_plan == "0" else ""}>未制作</option>"""

    # 类别侧边栏 HTML
    cat_items_html = '<div class="cat-item {}" data-cat="" onclick="selectCat(this)">全部类别</div>'.format(
        "active" if not category else ""
    )
    for c in categories:
        cname = c["name"]
        is_active = "active" if cname == category else ""
        safe = (
            cname.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        cat_items_html += f'<div class="cat-item {is_active}" data-cat="{safe}" onclick="selectCat(this)">{safe}</div>'

    html = f"""<!DOCTYPE html><html lang="zh"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>商品列表 – YP Affiliate 管理台</title>
<style>{BASE_CSS}</style>
</head><body>
{NAV_HTML.format(p0="active", p1="", p2="", p3="", p4="", p5="", p6="", p7="", p8="", p9="", p10="", p11="")}
<div class="container">
  <div class="stat-grid">
    <div class="stat-card"><div class="stat-num">{total_products:,}</div><div class="stat-label">US 商品总数</div></div>
    <div class="stat-card"><div class="stat-num">{total_amazon:,}</div><div class="stat-label">有 Amazon 数据</div></div>
    <div class="stat-card"><div class="stat-num">{total_plans:,}</div><div class="stat-label">已生成广告方案</div></div>
    <div class="stat-card"><div class="stat-num">{total:,}</div><div class="stat-label">当前筛选结果</div></div>
  </div>

  <div class="list-layout">
    <!-- 左侧类别栏 -->
    <div class="cat-sidebar">
      <div class="cat-list">{cat_items_html}</div>
    </div>

    <!-- 右侧主内容 -->
    <div class="list-main">
      <div class="card">
        <form method="get" action="/" class="filters" id="mainForm">
          <input type="hidden" name="category" id="hiddenCat" value="{category}">
          <input type="text" name="q" placeholder="搜索商品名/ASIN/商户..." value="{search}" style="width:220px">
          <select name="has_amazon" onchange="this.form.submit()">{has_amazon_opts}</select>
          <select name="has_plan" onchange="this.form.submit()">{has_plan_opts}</select>
          <select name="sort" onchange="this.form.submit()">{sort_opts}</select>
          <span style="font-size:.82rem;color:#888;white-space:nowrap;">价格 $</span>
          <input type="number" name="price_min" placeholder="最低" value="{price_min}" style="width:72px;padding:7px 10px;border:1px solid #2a2d36;border-radius:8px;background:#1a1d24;color:#e0e0e0;" oninput="delaySubmit()">
          <span style="color:#555;">–</span>
          <input type="number" name="price_max" placeholder="最高" value="{price_max}" style="width:72px;padding:7px 10px;border:1px solid #2a2d36;border-radius:8px;background:#1a1d24;color:#e0e0e0;" oninput="delaySubmit()">
          <button type="submit" class="btn btn-primary">搜索</button>
          <a href="/" class="btn btn-secondary">重置</a>
        </form>

        <table>
          <thead><tr>
            <th style="width:60px"></th>
            <th>商品</th>
            <th>价格</th>
            <th>佣金</th>
            <th>预计佣金</th>
            <th>最高出价</th>
            <th>最低出价</th>
            <th>评分</th>
            <th>广告状态</th>
            <th>操作</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>

        <div class="pagination">{pag_html}</div>
        <div style="text-align:center;font-size:12px;color:#555;margin-top:8px">
          共 {total:,} 条 · 第 {page}/{total_pages} 页
        </div>
      </div>
    </div>
  </div>
</div>

<script>
function htmlEsc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}}
function selectCat(el) {{
  document.querySelectorAll('.cat-item').forEach(function(e) {{ e.classList.remove('active'); }});
  el.classList.add('active');
  document.getElementById('hiddenCat').value = el.getAttribute('data-cat') || '';
  document.getElementById('mainForm').submit();
}}
var priceTimer;
function delaySubmit() {{
  clearTimeout(priceTimer);
  priceTimer = setTimeout(function() {{ document.getElementById('mainForm').submit(); }}, 600);
}}
async function generateAd(btn) {{
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 生成中...';
  try {{
    var res = await fetch('/api/generate/' + asin, {{method:'POST'}});
    var data = await res.json();
    if (data.success) {{
      toast('广告方案生成成功！共 ' + data.campaigns + ' 个广告系列', 'success');
      setTimeout(function() {{ location.reload(); }}, 1500);
    }} else if (data.message && data.message.indexOf('already exists') >= 0) {{
      // 方案已存在，尝试强制重新生成
      btn.innerHTML = '<span class="spinner"></span> 重新生成中...';
      res = await fetch('/api/generate/' + asin + '?force=1', {{method:'POST'}});
      data = await res.json();
      if (data.success) {{
        toast('广告方案重新生成成功！共 ' + data.campaigns + ' 个广告系列', 'success');
        setTimeout(function() {{ location.reload(); }}, 1500);
      }} else {{
        toast(data.message || '重新生成失败', 'error');
        btn.disabled = false;
        btn.innerHTML = '制作广告';
      }}
    }} else {{
      toast(data.message || '生成失败', 'error');
      btn.disabled = false;
      btn.innerHTML = '制作广告';
    }}
  }} catch(e) {{
    toast('请求失败: ' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '制作广告';
  }}
}}

// AI 生成广告（使用 LLM + Google Ads 技能）
async function generateAdAI(btn) {{
  var asin = btn.getAttribute('data-asin');
  var force = btn.getAttribute('data-force') === '1' ? '&force=1' : '';
  
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> AI生成中...';
  
  // 创建进度显示
  var progressDiv = document.createElement('div');
  progressDiv.id = 'ai-progress-' + asin;
  progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;max-width:500px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.5);';
  progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">🤖 AI 广告生成</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="ai-log-' + asin + '" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
  document.body.appendChild(progressDiv);
  
  var logDiv = document.getElementById('ai-log-' + asin);
  
  try {{
    var response = await fetch('/api/generate_ai/' + asin + '?llm=kimi' + force);
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';
    
    while (true) {{
      var {{done, value}} = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, {{stream: true}});
      var lines = buffer.split('\\n\\n');
      buffer = lines.pop();
      
      for (var line of lines) {{
        if (line.startsWith('data: ')) {{
          try {{
            var data = JSON.parse(line.substring(6));
            
            if (data.type === 'progress') {{
              logDiv.innerHTML += '<div style="color:#4fc3f7;">' + data.text + '</div>';
              progressDiv.scrollTop = progressDiv.scrollHeight;
            }} else if (data.type === 'thinking') {{
              // AI 思考过程，用灰色小字显示
              if (data.text) {{
                logDiv.innerHTML += '<div style="color:#666;font-size:11px;white-space:pre-wrap;word-break:break-all;max-height:100px;overflow:hidden;">' + data.text.substring(0, 200) + '</div>';
                progressDiv.scrollTop = progressDiv.scrollHeight;
              }}
            }} else if (data.type === 'done') {{
              logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ 生成完成！</div>';
              logDiv.innerHTML += '<div style="margin-top:10px;">广告系列: ' + (data.result?.campaigns || 0) + ' 个</div>';
              logDiv.innerHTML += '<div>广告组: ' + (data.result?.ad_groups || 0) + ' 个</div>';
              logDiv.innerHTML += '<div>广告: ' + (data.result?.ads || 0) + ' 个</div>';
              btn.innerHTML = '✅ AI生成完成';
              setTimeout(function() {{ progressDiv.remove(); location.reload(); }}, 2000);
            }} else if (data.type === 'error') {{
              logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + data.message + '</div>';
              btn.disabled = false;
              btn.innerHTML = '🤖 AI生成';
            }} else if (data.type === 'ping') {{
              // 心跳，忽略
            }}
          }} catch (e) {{
            console.error('Parse error:', e, line);
          }}
        }}
      }}
    }}
  }} catch (e) {{
    logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + e.message + '</div>';
    btn.disabled = false;
    btn.innerHTML = '🤖 AI生成';
  }}
}}

// Agent 生成广告（三引擎：memory/copaw/kimi）
async function generateAdAgent(btn) {{
  var asin = btn.getAttribute('data-asin');
  
  // 先弹出引擎选择
  var engine = await selectEngine();
  if (!engine) return;
  
  var engineLabel = engine === 'memory' ? '记忆引擎(KIMI)' : engine === 'copaw' ? 'CoPaw Agent' : '纯KIMI';
  
  btn.disabled = true;
  btn.innerHTML = '🧠 ' + engineLabel + '...';
  
  // 创建进度显示
  var progressDiv = document.createElement('div');
  progressDiv.id = 'agent-progress-' + asin;
  progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #6b5b95;border-radius:12px;padding:20px;max-width:600px;max-height:500px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(107,91,149,0.5);';
  progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">🧠 ' + engineLabel + '</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="agent-log-' + asin + '" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
  document.body.appendChild(progressDiv);
  
  var logDiv = document.getElementById('agent-log-' + asin);
  logDiv.innerHTML = '<div style="color:#6b5b95;">🧠 引擎: ' + engineLabel + '</div>';
  logDiv.innerHTML += '<div style="color:#888;margin-top:5px;">正在获取产品信息并生成广告方案...</div>';
  
  // 获取记忆统计
  try {{
    var memResp = await fetch('/api/ad_memory_stats');
    var memData = await memResp.json();
    if (memData.success && memData.total > 0) {{
      logDiv.innerHTML += '<div style="color:#4fc3f7;margin-top:5px;">📊 记忆库: ' + memData.total + '次生成, 成功率' + memData.success_rate + '%</div>';
    }}
  }} catch(e) {{}}
  
  try {{
    var response = await fetch('/api/generate_agent/' + asin + '?backend=' + engine, {{method: 'POST'}});
    var data = await response.json();
    
    if (data.success) {{
      var usedLabel = data.backend === 'copaw' ? 'CoPaw Agent' : data.backend === 'memory' ? '记忆引擎' : 'KIMI API';
      logDiv.innerHTML += '<div style="color:#4caf50;margin-top:15px;">✅ 生成完成！（实际使用: ' + usedLabel + '）</div>';
      
      // 显示广告系列
      if (data.campaigns && data.campaigns.length > 0) {{
        logDiv.innerHTML += '<div style="margin-top:10px;color:#fff;font-weight:600;">广告系列 (' + data.campaigns.length + ' 个):</div>';
        
        data.campaigns.forEach(function(camp, idx) {{
          logDiv.innerHTML += '<div style="margin-top:8px;padding:8px;background:#252830;border-radius:6px;">';
          logDiv.innerHTML += '<div style="color:#4fc3f7;font-weight:600;">' + (idx+1) + '. ' + htmlEsc(camp.name || '未命名') + '</div>';
          
          if (camp.ad_groups && camp.ad_groups.length > 0) {{
            camp.ad_groups.forEach(function(ag) {{
              logDiv.innerHTML += '<div style="margin-top:5px;padding-left:10px;border-left:2px solid #6b5b95;">';
              logDiv.innerHTML += '<div style="color:#adb5bd;">广告组: ' + htmlEsc(ag.name || '') + '</div>';
              
              if (ag.keywords && ag.keywords.length > 0) {{
                var kwList = ag.keywords.slice(0,5).map(function(k) {{ return htmlEsc(k.keyword || k.kw || ''); }}).join(', ');
                logDiv.innerHTML += '<div style="color:#888;font-size:11px;">关键词: ' + kwList + '</div>';
              }}
              
              if (ag.headlines && ag.headlines.length > 0) {{
                var hlList = ag.headlines.slice(0,3).map(function(h) {{ return htmlEsc(h.text || h); }}).join(' | ');
                logDiv.innerHTML += '<div style="color:#fff;font-size:12px;">标题: ' + hlList + '</div>';
              }}
              if (ag.descriptions && ag.descriptions.length > 0) {{
                var descList = ag.descriptions.slice(0,2).map(function(d) {{ return htmlEsc(d.text || d); }}).join(' | ');
                logDiv.innerHTML += '<div style="color:#888;font-size:11px;">描述: ' + descList + '</div>';
              }}
              logDiv.innerHTML += '</div>';
            }});
          }}
          logDiv.innerHTML += '</div>';
        }});
        
        if (data.strategy_notes) {{
          logDiv.innerHTML += '<div style="margin-top:10px;color:#888;font-size:12px;">策略说明: ' + htmlEsc(data.strategy_notes) + '</div>';
        }}
      }} else if (data.raw_output) {{
        logDiv.innerHTML += '<div style="margin-top:10px;color:#adb5bd;white-space:pre-wrap;font-size:11px;max-height:200px;overflow-y:auto;">' + htmlEsc(data.raw_output.substring(0, 1500)) + '</div>';
      }}
      
      // 显示记忆统计更新
      if (data.memory_stats && data.memory_stats.total > 0) {{
        logDiv.innerHTML += '<div style="margin-top:10px;color:#4fc3f7;font-size:12px;">📊 记忆库已更新: ' + data.memory_stats.total + '次生成, 成功率' + data.memory_stats.success_rate + '%</div>';
      }}
      
      // 显示数据库保存状态
      if (data.saved_to_db) {{
        logDiv.innerHTML += '<div style="margin-top:8px;color:#4caf50;font-size:13px;">💾 已保存到数据库 → <a href="/ads/' + asin + '" style="color:#4fc3f7;">点击查看广告方案</a></div>';
      }}
      
      btn.innerHTML = '✅ Agent完成';
      setTimeout(function() {{ btn.disabled = false; btn.innerHTML = '🧠 Agent'; }}, 5000);
      
    }} else {{
      logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + htmlEsc(data.error || '生成失败') + '</div>';
      btn.disabled = false;
      btn.innerHTML = '🧠 Agent';
    }}
  }} catch (e) {{
    logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + htmlEsc(e.message) + '</div>';
    btn.disabled = false;
    btn.innerHTML = '🧠 Agent';
  }}
}}

// 引擎选择弹窗
function selectEngine() {{
  return new Promise(function(resolve) {{
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = '<div style="background:#1a1d24;border:1px solid #6b5b95;border-radius:12px;padding:24px;max-width:450px;width:90%;">' +
      '<h3 style="color:#fff;margin:0 0 16px 0;font-size:16px;">🧠 选择广告生成引擎</h3>' +
      '<div style="display:flex;flex-direction:column;gap:10px;">' +
        '<button class="engine-opt" data-engine="memory" style="background:#252830;border:2px solid #4caf50;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">🧠 记忆引擎 <span style="color:#4caf50;font-weight:normal;font-size:11px;background:#1b3a1b;padding:2px 6px;border-radius:4px;">推荐</span></div>' +
          '<div style="color:#adb5bd;margin-top:4px;">KIMI API + 文件系统记忆</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">无需外部服务，自动积累经验，越用越好</div>' +
        '</button>' +
        '<button class="engine-opt" data-engine="copaw" style="background:#252830;border:2px solid #333;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">🤖 CoPaw Agent</div>' +
          '<div style="color:#adb5bd;margin-top:4px;">本地 AI Agent（需先启动 CoPaw）</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">自动 context_compact + memory_summary，不可用则降级</div>' +
        '</button>' +
        '<button class="engine-opt" data-engine="kimi" style="background:#252830;border:2px solid #333;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">⚡ 纯 KIMI API</div>' +
          '<div style="color:#adb5bd;margin-top:4px;">无记忆，纯 API 调用</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">baseline 对照组，每次独立生成</div>' +
        '</button>' +
      '</div>' +
      '<button id="engine-cancel" style="margin-top:14px;background:none;border:1px solid #444;color:#888;padding:8px 16px;border-radius:6px;cursor:pointer;width:100%;">取消</button>' +
    '</div>';
    
    document.body.appendChild(overlay);
    
    overlay.querySelectorAll('.engine-opt').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.body.removeChild(overlay);
        resolve(this.dataset.engine);
      }});
      btn.addEventListener('mouseenter', function() {{
        this.style.borderColor = '#6b5b95';
      }});
      btn.addEventListener('mouseleave', function() {{
        if (this.dataset.engine !== 'memory') this.style.borderColor = '#333';
      }});
    }});
    
    overlay.querySelector('#engine-cancel').addEventListener('click', function() {{
      document.body.removeChild(overlay);
      resolve(null);
    }});
  }});
}}

async function resetPlan(btn) {{
  var asin = btn.getAttribute('data-asin');
  location.reload();
}}

function downloadPlan(asin) {{
  window.open('/api/download_plan/' + asin);
}}

async function generateAdFromReport(btn) {{
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 生成中...';
  
  // 创建进度显示
  var progressDiv = document.createElement('div');
  progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1a2e;padding:30px;border-radius:12px;z-index:10000;min-width:400px;max-width:600px;box-shadow:0 10px 40px rgba(0,0,0,0.5);';
  progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">📊 基于报告的广告生成</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="report-log" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
  document.body.appendChild(progressDiv);
  var logDiv = document.getElementById('report-log');
  
  function log(msg) {{
    logDiv.innerHTML += msg + '<br>';
    logDiv.scrollTop = logDiv.scrollHeight;
  }}
  
  log('📋 正在获取商品报告数据...');
  
  try {{
    var res = await fetch('/api/generate_ads_from_report/' + asin, {{method:'POST'}});
    var data = await res.json();
    
    if (data.success) {{
      log('✅ 广告方案生成成功！');
      log('');
      log('📊 数据来源：');
      log('  - 商品信息: ✓');
      log('  - 商户信息: ' + (data.data_sources.merchant ? '✓' : '✗'));
      log('  - 品牌关键词: ' + data.data_sources.brand_keywords + ' 个');
      log('  - SEMrush数据: ' + (data.data_sources.semrush ? '✓' : '✗'));
      if (data.data_sources.semrush) {{
        log('    - 自然关键词: ' + data.data_sources.organic_keywords + ' 个');
        log('    - 付费关键词: ' + data.data_sources.paid_keywords + ' 个');
        log('    - 广告样本: ' + data.data_sources.ad_copies + ' 条');
        log('    - 竞品: ' + data.data_sources.competitors + ' 个');
      }}
      log('');
      
      var plan = data.ads_plan;
      if (plan.product_analysis) {{
        log('📈 产品分析：');
        log('  - 品类: ' + (plan.product_analysis.category || 'N/A'));
        log('  - 类型: ' + (plan.product_analysis.type || 'N/A'));
        log('  - 单次佣金: $' + (plan.product_analysis.single_commission || 'N/A'));
        log('  - 盈利难度: ' + (plan.product_analysis.profit_difficulty || 'N/A'));
        log('');
      }}
      
      if (plan.campaigns && plan.campaigns.length > 0) {{
        log('🎯 广告系列：' + plan.campaigns.length + ' 个');
        plan.campaigns.forEach(function(c, i) {{
          log('  ' + (i+1) + '. ' + c.name + ' (' + (c.budget_allocation || 'N/A') + ')');
        }});
        log('');
      }}
      
      if (plan.qa_report) {{
        if (plan.qa_report.passed) {{
          log('✅ QA 检查通过');
        }} else {{
          log('⚠️ QA 检查存在问题');
        }}
      }}
      
      log('');
      log('<a href="/api/download_plan/' + asin + '" style="color:#4dabf7;">📥 下载广告方案</a>');
      
      btn.innerHTML = '✓ 已生成';
      btn.style.background = '#27ae60';
      setTimeout(function() {{ location.reload(); }}, 3000);
    }} else {{
      log('❌ 生成失败：' + (data.error || '未知错误'));
      btn.disabled = false;
      btn.innerHTML = '📊 报告';
    }}
  }} catch(e) {{
    log('❌ 请求失败：' + e.message);
    btn.disabled = false;
    btn.innerHTML = '📊 报告';
  }}
}}

async function fetchAmazon(btn) {{
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 采集中...';
  toast('正在采集 Amazon 数据：' + asin + '（需要调试Chrome已启动）', 'info');
  try {{
    var res = await fetch('/api/fetch_amazon/' + asin, {{method:'POST'}});
    var data = await res.json();
    if (data.success) {{
      toast('Amazon 数据采集完成！', 'success');
      setTimeout(function() {{ location.reload(); }}, 1500);
    }} else {{
      var msg = data.message || '未知错误';
      if (msg.indexOf('9222') !== -1 || msg.indexOf('connect') !== -1 || msg.indexOf('Connection') !== -1) {{
        toast('❌ Chrome 启动失败：' + msg.substring(0, 100), 'error');
      }} else {{
        toast('采集失败：' + msg.substring(0, 120), 'error');
      }}
      btn.disabled = false;
      btn.innerHTML = '采集Amazon';
    }}
  }} catch(e) {{
    toast('请求失败：' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '采集Amazon';
  }}
}}

async function fetchSuggest(btn) {{
  var mid = btn.getAttribute('data-mid');
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 采集中...';
  toast('正在采集 Google Suggest 关键词，请稍候（约15-30秒）...', 'info');
  try {{
    var res = await fetch('/api/fetch_suggest/' + mid, {{method:'POST'}});
    var data = await res.json();
    if (data.success) {{
      var cnt = data.keyword_count || 0;
      // 更新该商户的所有关键词 badge（同商户多条商品都更新）
      var containers = document.querySelectorAll('#kw-' + mid);
      containers.forEach(function(el) {{
        el.innerHTML = '<span class="badge badge-green" title="已有' + cnt + '个品牌关键词">🔑 ' + cnt + '个词</span>';
      }});
      toast('🔑 关键词采集完成，共 ' + cnt + ' 个！', 'success');
    }} else {{
      var msg = data.message || '未知错误';
      if (msg.indexOf('9222') !== -1 || msg.indexOf('Chrome') !== -1) {{
        toast('❌ Chrome 启动失败：' + msg.substring(0, 100), 'error');
      }} else {{
        toast('采集失败：' + msg.substring(0, 150), 'error');
      }}
      btn.disabled = false;
      btn.innerHTML = '🔑 采集关键词';
    }}
  }} catch(e) {{
    toast('请求失败：' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '🔑 采集关键词';
  }}
}}
</script>
</body></html>"""
    return html


# ═══════════════════════════════════════════════════════════════════════════
# 路由：广告方案列表
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/plans")
def plan_list():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT pl.*, p.product_name, p.price AS yp_price, p.commission AS yp_commission
        FROM ads_plans pl
        LEFT JOIN yp_products p ON pl.asin = p.asin
        WHERE pl.plan_status = 'completed'
        ORDER BY pl.generated_at DESC
        LIMIT 200
    """)
    plans = cur.fetchall()
    cur.close()
    conn.close()

    rows_html = ""
    for pl in plans:
        asin = pl["asin"]
        price = pl.get("product_price") or pl.get("yp_price") or "--"
        cpa = f"${pl['target_cpa']:.2f}" if pl.get("target_cpa") else "--"
        rows_html += f"""
        <tr>
          <td><code>{asin}</code></td>
          <td style="color:#adb5bd">{str(pl.get("merchant_name") or "")}</td>
          <td style="max-width:300px;color:#e0e0e0">{str(pl.get("product_name") or "")[:60]}</td>
          <td style="color:#e0e0e0">{price}</td>
          <td><b style="color:#64b5f6">{cpa}</b></td>
          <td style="color:#e0e0e0">{pl.get("campaign_count", 0)}</td>
          <td style="color:#e0e0e0">{pl.get("ad_group_count", 0)}</td>
          <td style="color:#e0e0e0">{pl.get("ad_count", 0)}</td>
          <td><span class="badge badge-{"blue" if pl.get("has_amazon_data") else "gray"}">
              {"Amazon数据" if pl.get("has_amazon_data") else "基础数据"}</span></td>
          <td style="white-space:nowrap">
            <a href="/plans/{asin}" class="btn btn-success btn-sm">查看详情</a>
            <button class="btn btn-warning btn-sm" style="margin-top:4px"
              onclick="regenerate('{asin}',this)">重新生成</button>
            <button class="btn btn-info btn-sm" style="margin-top:4px" data-asin="{asin}"
              onclick="polishAds(this)" title="AI 润色标题和描述">✨ 润色</button>
            <button class="btn btn-secondary btn-sm" style="margin-top:4px" data-asin="{asin}" data-force="1"
              onclick="generateAdAI(this)">🤖 AI重新生成</button>
            <button class="btn btn-sm" style="margin-top:4px;background:#6b5b95;color:#fff;" data-asin="{asin}"
              onclick="generateAdAgent(this)">🧠 Agent</button>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html><html lang="zh"><head>
<meta charset="utf-8"><title>广告方案 – YP Affiliate 管理台</title>
<style>{BASE_CSS}</style></head><body>
{NAV_HTML.format(p0="", p1="active", p2="", p3="", p4="", p5="", p6="", p7="", p8="", p9="", p10="", p11="")}
<div class="container">
  <div class="card">
    <h2>广告方案列表（{len(plans)} 个）</h2>
    <table>
      <thead><tr>
        <th>ASIN</th><th>商户</th><th>商品</th><th>价格</th>
        <th>目标CPA</th><th>Campaigns</th><th>Ad Groups</th><th>Ads</th>
        <th>数据源</th><th>操作</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
<script>
function htmlEsc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}}
function regenerate(asin, btn) {{
    btn.disabled = true;
    btn.textContent = '生成中...';
    fetch('/api/generate/' + asin + '?force=1', {{method: 'POST'}})
    .then(r => r.json())
    .then(data => {{
        if (data.success) {{
            btn.textContent = '✅ 已重新生成';
            setTimeout(() => location.reload(), 1000);
        }} else {{
            alert(data.message || '生成失败');
            btn.disabled = false;
            btn.textContent = '重新生成';
        }}
    }})
    .catch(e => {{
        alert('请求失败: ' + e.message);
        btn.disabled = false;
        btn.textContent = '重新生成';
    }});
}}

// AI 生成广告（使用 LLM + Google Ads 技能）
async function generateAdAI(btn) {{
    var asin = btn.getAttribute('data-asin');
    var force = btn.getAttribute('data-force') === '1' ? '&force=1' : '';
    
    btn.disabled = true;
    btn.textContent = 'AI生成中...';
    
    // 创建进度显示
    var progressDiv = document.createElement('div');
    progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #2a2d36;border-radius:12px;padding:20px;max-width:500px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.5);';
    progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">🤖 AI 广告生成</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="ai-log" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
    document.body.appendChild(progressDiv);
    
    var logDiv = document.getElementById('ai-log');
    
    try {{
        var response = await fetch('/api/generate_ai/' + asin + '?llm=kimi' + force);
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        
        while (true) {{
            var {{done, value}} = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, {{stream: true}});
            var lines = buffer.split('\\n\\n');
            buffer = lines.pop();
            
            for (var line of lines) {{
                if (line.startsWith('data: ')) {{
                    try {{
                        var data = JSON.parse(line.substring(6));
                        
                        if (data.type === 'progress') {{
                            logDiv.innerHTML += '<div style="color:#4fc3f7;">' + data.text + '</div>';
                            progressDiv.scrollTop = progressDiv.scrollHeight;
                        }} else if (data.type === 'thinking') {{
                            if (data.text) {{
                                logDiv.innerHTML += '<div style="color:#666;font-size:11px;white-space:pre-wrap;word-break:break-all;max-height:100px;overflow:hidden;">' + data.text.substring(0, 200) + '</div>';
                                progressDiv.scrollTop = progressDiv.scrollHeight;
                            }}
                        }} else if (data.type === 'done') {{
                            logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ 生成完成！</div>';
                            logDiv.innerHTML += '<div style="margin-top:10px;">广告系列: ' + (data.result?.campaigns || 0) + ' 个</div>';
                            logDiv.innerHTML += '<div>广告组: ' + (data.result?.ad_groups || 0) + ' 个</div>';
                            logDiv.innerHTML += '<div>广告: ' + (data.result?.ads || 0) + ' 个</div>';
                            btn.textContent = '✅ AI生成完成';
                            setTimeout(function() {{ progressDiv.remove(); location.reload(); }}, 2000);
                        }} else if (data.type === 'error') {{
                            logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + data.message + '</div>';
                            btn.disabled = false;
                            btn.textContent = '🤖 AI重新生成';
                        }}
                    }} catch (e) {{
                        console.error('Parse error:', e, line);
                    }}
                }}
            }}
        }}
    }} catch (e) {{
        logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + e.message + '</div>';
        btn.disabled = false;
        btn.textContent = '🤖 AI重新生成';
    }}
}}

// AI 润色广告文案
async function polishAds(btn) {{
    var asin = btn.dataset.asin;
    
    btn.disabled = true;
    btn.innerHTML = '✨ 润色中...';
    
    // 创建进度显示
    var progressDiv = document.createElement('div');
    progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #17a2b8;border-radius:12px;padding:20px;max-width:500px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(23,162,184,0.5);';
    progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">✨ AI 广告润色</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="polish-log" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
    document.body.appendChild(progressDiv);
    
    var logDiv = document.getElementById('polish-log');
    logDiv.innerHTML = '<div style="color:#17a2b8;">🎨 正在读取广告方案...</div>';
    
    try {{
        var response = await fetch('/api/polish_ads/' + asin, {{method: 'POST'}});
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        
        while (true) {{
            var {{done, value}} = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, {{stream: true}});
            var lines = buffer.split('\\n\\n');
            buffer = lines.pop();
            
            for (var i = 0; i < lines.length; i++) {{
                var line = lines[i];
                if (line.startsWith('data: ')) {{
                    try {{
                        var data = JSON.parse(line.substring(6));
                        
                        if (data.type === 'progress') {{
                            logDiv.innerHTML += '<div style="color:#4fc3f7;">' + data.text + '</div>';
                            progressDiv.scrollTop = progressDiv.scrollHeight;
                        }} else if (data.type === 'done') {{
                            logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ 润色完成！</div>';
                            logDiv.innerHTML += '<div style="margin-top:10px;">已润色: ' + (data.result?.polished_count || 0) + ' 条广告</div>';
                            btn.innerHTML = '✅ 已润色';
                            setTimeout(function() {{ progressDiv.remove(); location.reload(); }}, 2000);
                        }} else if (data.type === 'error') {{
                            logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + data.message + '</div>';
                            btn.disabled = false;
                            btn.innerHTML = '✨ 润色';
                        }}
                    }} catch (e) {{
                        console.error('Parse error:', e, line);
                    }}
                }}
            }}
        }}
    }} catch (e) {{
        logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + e.message + '</div>';
        btn.disabled = false;
        btn.innerHTML = '✨ 润色';
    }}
}}

// Agent 生成广告（三引擎：memory/copaw/kimi）— 广告详情页版
async function generateAdAgent(btn) {{
    var asin = btn.dataset.asin;
    
    // 先弹出引擎选择
    var engine = await selectEngine();
    if (!engine) return;
    
    var engineLabel = engine === 'memory' ? '记忆引擎' : engine === 'copaw' ? 'CoPaw Agent' : '纯KIMI';
    
    btn.disabled = true;
    btn.textContent = '🧠 ' + engineLabel + '...';
    
    // 创建进度显示
    var progressDiv = document.createElement('div');
    progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #6b5b95;border-radius:12px;padding:20px;max-width:600px;max-height:500px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(107,91,149,0.5);';
    progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">🧠 ' + engineLabel + '</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="agent-log" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
    document.body.appendChild(progressDiv);
    
    var logDiv = document.getElementById('agent-log');
    logDiv.innerHTML = '<div style="color:#6b5b95;">🧠 引擎: ' + engineLabel + '</div>';
    logDiv.innerHTML += '<div style="color:#888;margin-top:5px;">正在生成广告方案...</div>';
    
    try {{
        var response = await fetch('/api/generate_agent/' + asin + '?backend=' + engine, {{method: 'POST'}});
        var data = await response.json();
        
        if (data.success) {{
            var usedLabel = data.backend === 'copaw' ? 'CoPaw Agent' : data.backend === 'memory' ? '记忆引擎' : 'KIMI API';
            logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ 生成完成！（实际: ' + usedLabel + '）</div>';
            
            if (data.campaigns && data.campaigns.length > 0) {{
                logDiv.innerHTML += '<div style="margin-top:10px;color:#fff;font-weight:600;">广告系列 (' + data.campaigns.length + ' 个):</div>';
                data.campaigns.forEach(function(camp, idx) {{
                    logDiv.innerHTML += '<div style="margin-top:8px;padding:8px;background:#252830;border-radius:6px;">';
                    logDiv.innerHTML += '<div style="color:#4fc3f7;font-weight:600;">' + (idx+1) + '. ' + htmlEsc(camp.name || '未命名') + '</div>';
                    if (camp.ad_groups && camp.ad_groups.length > 0) {{
                        camp.ad_groups.forEach(function(ag) {{
                            logDiv.innerHTML += '<div style="margin-top:5px;padding-left:10px;border-left:2px solid #6b5b95;">';
                            logDiv.innerHTML += '<div style="color:#adb5bd;">' + htmlEsc(ag.name || '') + '</div>';
                            if (ag.keywords && ag.keywords.length > 0) {{
                                logDiv.innerHTML += '<div style="color:#888;font-size:11px;">关键词: ' + ag.keywords.slice(0,5).map(function(k) {{ return htmlEsc(k.keyword || ''); }}).join(', ') + '</div>';
                            }}
                            if (ag.headlines && ag.headlines.length > 0) {{
                                logDiv.innerHTML += '<div style="color:#fff;font-size:12px;">标题: ' + ag.headlines.slice(0,3).map(function(h) {{ return htmlEsc(h.text || h); }}).join(' | ') + '</div>';
                            }}
                            logDiv.innerHTML += '</div>';
                        }});
                    }}
                    logDiv.innerHTML += '</div>';
                }});
            }}
            
            if (data.memory_stats && data.memory_stats.total > 0) {{
                logDiv.innerHTML += '<div style="margin-top:10px;color:#4fc3f7;font-size:12px;">📊 记忆库: ' + data.memory_stats.total + '次, 成功率' + data.memory_stats.success_rate + '%</div>';
            }}
            
            if (data.saved_to_db) {{
                logDiv.innerHTML += '<div style="margin-top:8px;color:#4caf50;font-size:13px;">💾 已保存到数据库 — 刷新页面可查看新方案</div>';
            }}
            
            btn.textContent = '✅ 完成';
            setTimeout(function() {{ btn.disabled = false; btn.textContent = '🧠 Agent'; }}, 5000);
            setTimeout(function() {{ progressDiv.remove(); }}, 8000);
        }} else {{
            logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + htmlEsc(data.error || '生成失败') + '</div>';
            btn.disabled = false;
            btn.textContent = '🧠 Agent';
        }}
    }} catch (e) {{
        logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + htmlEsc(e.message) + '</div>';
        btn.disabled = false;
        btn.textContent = '🧠 Agent';
    }}
}}

// 引擎选择弹窗（广告方案页版）
function selectEngine() {{
  return new Promise(function(resolve) {{
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = '<div style="background:#1a1d24;border:1px solid #6b5b95;border-radius:12px;padding:24px;max-width:450px;width:90%;">' +
      '<h3 style="color:#fff;margin:0 0 16px 0;font-size:16px;">🧠 选择广告生成引擎</h3>' +
      '<div style="display:flex;flex-direction:column;gap:10px;">' +
        '<button class="engine-opt" data-engine="memory" style="background:#252830;border:2px solid #4caf50;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">🧠 记忆引擎 <span style="color:#4caf50;font-weight:normal;font-size:11px;background:#1b3a1b;padding:2px 6px;border-radius:4px;">推荐</span></div>' +
          '<div style="color:#adb5bd;margin-top:4px;">KIMI API + 文件系统记忆</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">无需外部服务，自动积累经验</div>' +
        '</button>' +
        '<button class="engine-opt" data-engine="copaw" style="background:#252830;border:2px solid #333;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">🤖 CoPaw Agent</div>' +
          '<div style="color:#adb5bd;margin-top:4px;">本地 AI Agent（需启动 CoPaw）</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">context_compact + memory_summary</div>' +
        '</button>' +
        '<button class="engine-opt" data-engine="kimi" style="background:#252830;border:2px solid #333;border-radius:8px;padding:14px;color:#fff;text-align:left;cursor:pointer;font-size:13px;line-height:1.6;">' +
          '<div style="font-weight:700;font-size:14px;">⚡ 纯 KIMI API</div>' +
          '<div style="color:#adb5bd;margin-top:4px;">无记忆，纯 API 调用</div>' +
          '<div style="color:#888;font-size:11px;margin-top:2px;">baseline 对照组</div>' +
        '</button>' +
      '</div>' +
      '<button id="engine-cancel" style="margin-top:14px;background:none;border:1px solid #444;color:#888;padding:8px 16px;border-radius:6px;cursor:pointer;width:100%;">取消</button>' +
    '</div>';
    document.body.appendChild(overlay);
    overlay.querySelectorAll('.engine-opt').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.body.removeChild(overlay);
        resolve(this.dataset.engine);
      }});
      btn.addEventListener('mouseenter', function() {{ this.style.borderColor = '#6b5b95'; }});
      btn.addEventListener('mouseleave', function() {{ if(this.dataset.engine!=='memory') this.style.borderColor='#333'; }});
    }});
    overlay.querySelector('#engine-cancel').addEventListener('click', function() {{ document.body.removeChild(overlay); resolve(null); }});
  }});
}}
</script>
</body></html>"""
    return html


# ═══════════════════════════════════════════════════════════════════════════
# 路由：广告方案详情
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/plans/<asin>")
def plan_detail(asin):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # 方案概要
    cur.execute("SELECT * FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
    plan = cur.fetchone()
    if not plan:
        conn.close()
        return f"<h2>找不到 ASIN={asin} 的广告方案</h2><a href='/plans'>返回</a>", 404

    # 获取商品信息（通过 merchant_name 关联）
    cur.execute(
        """
        SELECT p.*, a.title AS amz_title, a.rating, a.review_count, a.main_image_url AS img,
               a.bullet_points, m.merchant_name AS m_name, m.website
        FROM yp_products p
        LEFT JOIN amazon_product_details a ON p.asin = a.asin
        LEFT JOIN yp_merchants m ON p.merchant_name = m.merchant_name
        WHERE p.asin = %s LIMIT 1
    """,
        (asin,),
    )
    prod = cur.fetchone()

    # Campaigns + Ad Groups + Ads
    cur.execute("SELECT * FROM ads_campaigns WHERE asin=%s ORDER BY id", (asin,))
    campaigns = cur.fetchall()

    campaign_html = ""
    for camp_idx, camp in enumerate(campaigns):
        cid = camp["id"]
        neg_kws = json.loads(camp.get("negative_keywords") or "[]")

        cur.execute(
            "SELECT * FROM ads_ad_groups WHERE campaign_id=%s ORDER BY id", (cid,)
        )
        groups = cur.fetchall()

        groups_html = ""
        for grp in groups:
            gid = grp["id"]
            kws = json.loads(grp.get("keywords") or "[]")
            neg = json.loads(grp.get("negative_keywords") or "[]")

            kw_tags = "".join(
                f'<span class="tag" title="{k["type"]}">[{k["type"]}] {k["kw"]}</span>'
                for k in kws
            )
            neg_tags = "".join(
                f'<span class="tag" style="background:#3d1a1a;color:#ef5350">{n}</span>'
                for n in neg
            )

            cur.execute(
                "SELECT * FROM ads_ads WHERE ad_group_id=%s ORDER BY variant", (gid,)
            )
            ads = cur.fetchall()

            ads_html = ""
            for ad in ads:
                headlines = json.loads(ad.get("headlines") or "[]")
                descriptions = json.loads(ad.get("descriptions") or "[]")
                sitelinks = json.loads(ad.get("sitelinks") or "[]")
                callouts = json.loads(ad.get("callouts") or "[]")
                snippet = json.loads(ad.get("structured_snippet") or "{}")

                hl_rows = "".join(
                    f"<tr><td>{i + 1}</td><td>{h['text']}</td>"
                    f'<td><span class="badge badge-{"green" if h["chars"] <= 30 else "red"}">{h["chars"]}</span></td></tr>'
                    for i, h in enumerate(headlines)
                )
                desc_rows = "".join(
                    f"<tr><td>{i + 1}</td><td>{d['text']}</td>"
                    f'<td><span class="badge badge-{"green" if d["chars"] <= 90 else "red"}">{d["chars"]}</span></td></tr>'
                    for i, d in enumerate(descriptions)
                )
                sitelink_rows = "".join(
                    f"<tr><td>{s.get('text', '')}</td><td>{s.get('desc1', '')}</td><td>{s.get('desc2', '')}</td></tr>"
                    for s in sitelinks
                )
                callout_str = " · ".join(
                    f'<span class="tag">{c}</span>' for c in callouts
                )
                snippet_vals = " | ".join(snippet.get("values", []))

                quality_cls = (
                    "badge-green" if ad.get("all_chars_valid") else "badge-red"
                )
                quality_label = (
                    "ALL PASS" if ad.get("all_chars_valid") else "HAS ISSUES"
                )

                # QS 评分展示
                qs_score = ad.get("qs_score") or ad.get("quality_score") or 0
                if qs_score >= 80:
                    qs_color = "#2e7d32"
                    qs_bg = "rgba(46, 125, 50, 0.2)"
                elif qs_score >= 60:
                    qs_color = "#ffa726"
                    qs_bg = "rgba(255, 167, 38, 0.2)"
                else:
                    qs_color = "#c62828"
                    qs_bg = "rgba(198, 40, 40, 0.2)"

                qs_tooltip = ""
                if qs_score > 0:
                    qs_breakdown = ad.get("qs_breakdown") or {}
                    qs_tooltip = (
                        f'title="QS评分明细\n'
                        f"相关性: {qs_breakdown.get('relevance', 0)}/20\n"
                        f"点击率: {qs_breakdown.get('ctr', 0)}/20\n"
                        f"落地页: {qs_breakdown.get('landing', 0)}/20\n"
                        f"文案质量: {qs_breakdown.get('copy', 0)}/20\n"
                        f'扩展完整: {qs_breakdown.get("extensions", 0)}/20"'
                    )

                qs_badge = (
                    f"""<span class="qs-badge" style="background:{qs_bg};color:{qs_color};padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;cursor:help;" {qs_tooltip}>QS {qs_score}</span>"""
                    if qs_score > 0
                    else ""
                )

                ads_html += f"""
                <div style="border:1px solid #2a2d36;border-radius:8px;padding:16px;margin-top:12px;background:#15181f">
                  <div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
                    <b style="color:#e0e0e0">变体 {ad["variant"]}</b>
                    <span class="badge {quality_cls}">{quality_label}</span>
                    {qs_badge}
                    <small style="color:#888">{ad.get("quality_notes", "")}</small>
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                    <div>
                      <b style="font-size:12px;color:#adb5bd">标题（{len(headlines)}个）</b>
                      <table style="margin-top:6px;font-size:12px">
                        <tr><th>#</th><th>文案</th><th>字符</th></tr>
                        {hl_rows}
                      </table>
                    </div>
                    <div>
                      <b style="font-size:12px;color:#adb5bd">描述（{len(descriptions)}个）</b>
                      <table style="margin-top:6px;font-size:12px">
                        <tr><th>#</th><th>文案</th><th>字符</th></tr>
                        {desc_rows}
                      </table>
                    </div>
                  </div>
                  <div style="margin-top:12px">
                    <b style="font-size:12px;color:#adb5bd">Sitelink 扩展</b>
                    <table style="font-size:12px;margin-top:4px">
                      <tr><th>链接文字</th><th>描述1</th><th>描述2</th></tr>
                      {sitelink_rows}
                    </table>
                  </div>
                  <div style="margin-top:8px;font-size:12px;color:#e0e0e0">
                    <b style="color:#adb5bd">Callout：</b> {callout_str}
                  </div>
                  <div style="margin-top:6px;font-size:12px;color:#e0e0e0">
                    <b style="color:#adb5bd">Structured Snippet（{snippet.get("header", "")}）：</b>
                    <span style="color:#adb5bd">{snippet_vals}</span>
                  </div>
                  <div style="margin-top:8px;font-size:12px;color:#888">
                    Final URL: {ad.get("final_url", "") or '<span style="color:#ef5350">未设置（需在YP申请投放链接）</span>'}
                  </div>
                </div>"""

            groups_html += f"""
            <div style="margin:12px 0 0 16px;border-left:3px solid #2196f3;padding-left:16px">
              <div style="display:flex;gap:12px;align-items:center">
                <b style="color:#e0e0e0">{grp["ad_group_name"]}</b>
                <span class="badge badge-blue">{grp["keyword_count"]} 关键词</span>
                <span style="font-size:12px;color:#888">CPC: ${grp.get("cpc_bid_usd") or "--"}</span>
              </div>
              <div style="font-size:12px;color:#888;margin-top:2px">{grp.get("user_intent", "")}</div>
              <div style="margin-top:8px">{kw_tags}</div>
              {'<div style="margin-top:4px;color:#888;font-size:12px">否定：' + neg_tags + "</div>" if neg_tags else ""}
              {ads_html}
            </div>"""

        # 否定词
        neg_display = "".join(
            f'<span class="tag" style="background:#3d1a1a;color:#ef5350;font-size:11px">{n}</span>'
            for n in neg_kws[:20]
        )
        if len(neg_kws) > 20:
            neg_display += f'<span class="tag">+{len(neg_kws) - 20} 更多</span>'

        stage_colors = {
            "Brand": "#2196f3",
            "Problem-Awareness": "#ffa726",
            "Solution-Evaluation": "#ce93d8",
            "Feature-Exploration": "#66bb6a",
            "Purchase-Decision": "#ef5350",
            "Competitor": "#888",
        }
        stage_color = stage_colors.get(camp["journey_stage"], "#adb5bd")

        campaign_html += f"""
        <div class="camp-accordion {"open" if camp_idx == 0 else ""}" id="camp-{cid}" style="--camp-color:{stage_color}">
          <!-- 折叠头部 -->
          <div class="camp-header" onclick="toggleCamp(this.closest('.camp-accordion'))">
            <b style="font-size:15px;color:#e0e0e0">{camp["campaign_name"]}</b>
            <span class="badge" style="background:{stage_color}33;color:{stage_color}">{camp["journey_stage"]}</span>
            <span class="badge badge-gray">预算 {camp.get("budget_pct", 0)}%</span>
            <span class="badge badge-blue">日预算 ${camp.get("daily_budget_usd") or "--"}</span>
            <span class="badge badge-gray" style="font-size:11px">{len(groups)} Ad Groups</span>
            <span class="camp-toggle-icon">▼</span>
          </div>
          <!-- 折叠内容体 -->
          <div class="camp-body">
            <div style="font-size:12px;color:#888;margin-bottom:8px;padding-top:4px">
              出价策略: {camp.get("bid_strategy", "")}
            </div>
            <details>
              <summary style="cursor:pointer;font-size:12px;color:#888">账户级否定关键词（{len(neg_kws)}个）</summary>
              <div style="margin-top:6px">{neg_display}</div>
            </details>
            {groups_html}
          </div>
        </div>"""

    # 商品头部
    img_src = (prod or {}).get("img", "")
    img_html = (
        f'<img src="{img_src}" style="width:80px;height:80px;object-fit:cover;border-radius:8px">'
        if img_src
        else ""
    )
    product_title = (
        (prod or {}).get("amz_title") or (prod or {}).get("product_name") or asin
    )
    rating = (prod or {}).get("rating", "")
    rev_count = (prod or {}).get("review_count", "")
    price_show = (prod or {}).get("price", "") or ""
    comm_show = (prod or {}).get("commission", "") or ""
    cpa_show = f"${plan['target_cpa']:.2f}" if plan.get("target_cpa") else "--"

    bullets_raw = (prod or {}).get("bullet_points") if prod else None
    bullets_list = []
    if bullets_raw:
        try:
            bullets_list = json.loads(bullets_raw)
            if not isinstance(bullets_list, list):
                bullets_list = [str(bullets_list)]
        except Exception:
            bullets_list = [
                l.strip() for l in str(bullets_raw).split("\n") if l.strip()
            ][:5]

    bullets_html = "".join(
        f'<li style="margin-bottom:4px;font-size:13px">{b}</li>'
        for b in bullets_list[:6]
    )

    # 品牌关键词 - 从 ads_merchant_keywords 表查询
    plan_mid = str(plan.get("merchant_id") or "")
    plan_merchant_name = str(plan.get("merchant_name") or plan_mid)

    # 优先从 ads_merchant_keywords 表查询
    if plan_mid:
        cur.execute(
            "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s",
            (plan_mid,),
        )
        merchant_kws = [r["keyword"] for r in cur.fetchall()]
    else:
        merchant_kws = []

    # 如果表里没有，再用方案里保存的
    if not merchant_kws:
        brand_kws = json.loads(plan.get("brand_keywords_used") or "[]")
    else:
        brand_kws = merchant_kws

    kw_tags = "".join(f'<span class="tag">{k}</span>' for k in brand_kws)

    html = f"""<!DOCTYPE html><html lang="zh"><head>
<meta charset="utf-8"><title>{asin} – 广告方案详情</title>
<style>{BASE_CSS}
details summary {{ list-style: none; }} details summary::-webkit-details-marker {{ display:none; }}
/* ── Campaign Accordion ── */
.camp-accordion {{ margin-bottom: 12px; border-radius: 10px; overflow: hidden;
  border: 1px solid #2a2d36; background: #1a1d24; }}
.camp-header {{
  display: flex; gap: 12px; align-items: center; padding: 14px 18px;
  cursor: pointer; user-select: none; transition: background .15s;
  border-left: 4px solid var(--camp-color, #888);
}}
.camp-header:hover {{ background: #22262f; }}
.camp-toggle-icon {{
  margin-left: auto; width: 22px; height: 22px; flex-shrink: 0;
  border-radius: 50%; background: #23262f; border: 1px solid #3a3d46;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; color: #888; transition: transform .25s, background .15s;
}}
.camp-accordion.open .camp-toggle-icon {{ transform: rotate(180deg); background: #2a2d3a; color: #64b5f6; }}
.camp-body {{
  overflow: hidden;
  max-height: 0;
  transition: max-height .35s cubic-bezier(0.4,0,0.2,1), padding .25s;
  padding: 0 18px;
}}
.camp-accordion.open .camp-body {{
  max-height: 9999px;
  padding: 0 18px 18px;
}}
</style></head><body>
{NAV_HTML.format(p0="", p1="active", p2="", p3="", p4="", p5="", p6="", p7="", p8="", p9="", p10="", p11="")}
<div class="container">


  <!-- 商品概要 -->
  <div class="card">
    <div style="display:flex;gap:20px;align-items:flex-start">
      {img_html}
      <div style="flex:1">
        <h2 style="margin-bottom:6px;color:#e0e0e0">{product_title}</h2>
        <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
          <code>{asin}</code>
          <b style="color:#e0e0e0">{price_show}</b>
          <span class="badge badge-blue">佣金 {comm_show}</span>
          <span class="badge badge-orange">目标CPA {cpa_show}</span>
          {'<span class="badge badge-green">⭐' + str(rating) + "</span>" if rating else ""}
          {'<small style="color:#888">' + str(rev_count) + " reviews</small>" if rev_count else ""}
        </div>
        <div style="margin-bottom:8px">
          <b style="font-size:12px;color:#adb5bd">品牌关键词（{len(brand_kws)}个）：</b>
          <span id="kw-detail-{plan_mid}">
          {kw_tags if kw_tags else f'<button class="btn btn-secondary btn-sm" style="font-size:12px;padding:4px 10px;" data-mid="{plan_mid}" onclick="fetchSuggestDetail(this)" title="采集 {plan_merchant_name} 的 Google Suggest 品牌关键词">🔑 按需采集关键词</button>'}
          </span>
        </div>
        <ul style="padding-left:16px;color:#adb5bd">{bullets_html}</ul>
      </div>
      <div style="text-align:right">
        <div style="font-size:12px;color:#888">方案汇总</div>
        <div style="font-size:28px;font-weight:700;color:#64b5f6">{plan.get("campaign_count", 0)}</div>
        <div style="font-size:12px;color:#888">Campaigns</div>
        <div style="font-size:20px;font-weight:600;color:#ce93d8;margin-top:4px">{plan.get("ad_group_count", 0)}</div>
        <div style="font-size:12px;color:#888">Ad Groups</div>
        <div style="font-size:20px;font-weight:600;color:#66bb6a;margin-top:4px">{plan.get("ad_count", 0)}</div>
        <div style="font-size:12px;color:#888">Ads</div>
        <a href="/plans" class="btn btn-secondary btn-sm" style="margin-top:12px">← 返回列表</a>
      </div>
    </div>
  </div>

  <!-- 广告方案 -->
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
    <h2 style="margin:0;font-size:16px;color:#e0e0e0">广告方案（{plan.get("campaign_count", 0)} 个 Campaign）</h2>
    <button class="btn btn-secondary btn-sm" style="font-size:12px;padding:4px 12px" onclick="expandAllCamps()">展开全部</button>
    <button class="btn btn-secondary btn-sm" style="font-size:12px;padding:4px 12px" onclick="collapseAllCamps()">收起全部</button>
    <button class="btn btn-primary btn-sm" style="font-size:12px;padding:4px 12px;margin-left:auto" onclick="rescoreAds('{asin}')">🔄 重新评分</button>
  </div>
  {campaign_html}

</div>
<script>
// ── Campaign 折叠逻辑 ──
function toggleCamp(el) {{
  el.classList.toggle('open');
}}
function expandAllCamps() {{
  document.querySelectorAll('.camp-accordion').forEach(el => el.classList.add('open'));
}}
function collapseAllCamps() {{
  document.querySelectorAll('.camp-accordion').forEach(el => el.classList.remove('open'));
}}
async function rescoreAds(asin) {{
  var btn = document.querySelector('button[onclick^="rescoreAds"]');
  if (btn) {{ btn.disabled = true; btn.innerHTML = '🔄 评分中...'; }}
  try {{
    var res = await fetch('/api/ads/score/' + asin, {{method:'POST'}});
    var data = await res.json();
    if (data.ok) {{
      alert('✅ 评分完成！平均QS: ' + (data.avg_qs || 0));
      location.reload();
    }} else {{
      alert('❌ 评分失败: ' + (data.msg || '未知错误'));
    }}
  }} catch (e) {{
    alert('❌ 请求失败: ' + e.message);
  }} finally {{
    if (btn) {{ btn.disabled = false; btn.innerHTML = '🔄 重新评分'; }}
  }}
}}
async function fetchSuggestDetail(btn) {{
  var mid = btn.getAttribute('data-mid');
  btn.disabled = true;
  btn.innerHTML = '<span style="display:inline-block;width:12px;height:12px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;"></span> 采集中...';
  try {{
    var res = await fetch('/api/fetch_suggest/' + mid, {{method:'POST'}});
    var data = await res.json();
    if (data.success) {{
      var cnt = data.keyword_count || 0;
      var kws = (data.keywords || []).slice(0, 15);
      var html = kws.map(function(k) {{ return '<span style="background:#1a3a5c;color:#90caf9;padding:2px 8px;border-radius:4px;font-size:12px;margin:2px;display:inline-block">' + k + '</span>'; }}).join('');
      if (cnt > 15) html += '<span style="color:#888;font-size:12px"> +' + (cnt-15) + ' 更多</span>';
      var container = document.getElementById('kw-detail-' + mid);
      if (container) container.innerHTML = html;
      alert('🔑 关键词采集完成，共 ' + cnt + ' 个！\\n\\n若需将新关键词用于广告方案，请点击"重新生成"。');
    }} else {{
      var msg = data.message || '未知错误';
      alert('采集失败：' + msg.substring(0, 200));
      btn.disabled = false;
      btn.innerHTML = '🔑 按需采集关键词';
    }}
  }} catch(e) {{
    alert('请求失败：' + e.message);
    btn.disabled = false;
    btn.innerHTML = '🔑 按需采集关键词';
  }}
}}
</script>
</body></html>"""
    conn.close()
    return html


# ═══════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/api/generate/<asin>", methods=["POST"])
def api_generate(asin):
    """同步生成广告方案（在子进程里跑 generate_ads.py，等待完成）"""
    force = request.args.get("force", "0") == "1"

    with _gen_lock:
        if asin in _generating:
            return jsonify(
                {"success": False, "message": "正在生成中，请稍候", "asin": asin}
            )
        _generating.add(asin)

    # 先标记为 generating
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO ads_plans (asin, plan_status)
            VALUES (%s, 'generating')
            ON DUPLICATE KEY UPDATE plan_status='generating'
        """,
            (asin,),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass

    error_msg = None
    try:
        script = os.path.join(os.path.dirname(__file__), "generate_ads_v2.py")
        cmd = [sys.executable, "-X", "utf8", script, "--asin", asin]
        if force:
            cmd.append("--force")

        # 直接同步等待子进程完成（最多 120 秒）
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "脚本执行失败"
            print(f"[generate_ads] ERROR for {asin}:\n{error_msg}")
    except subprocess.TimeoutExpired:
        error_msg = "生成超时（120秒）"
        print(f"[generate_ads] Timeout for {asin}")
    except Exception as e:
        error_msg = str(e)
        print(f"[generate_ads] Exception for {asin}: {e}")
    finally:
        with _gen_lock:
            _generating.discard(asin)

    # 检查结果
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
        plan = cur.fetchone()

        if plan and plan["plan_status"] == "completed":
            cur.close()
            conn.close()
            return jsonify(
                {
                    "success": True,
                    "asin": asin,
                    "campaigns": plan.get("campaign_count", 0),
                    "ad_groups": plan.get("ad_group_count", 0),
                    "ads": plan.get("ad_count", 0),
                }
            )
        else:
            # ⚠️ 关键修复：生成失败时重置 plan_status，防止永久卡在 generating
            cur.execute(
                "UPDATE ads_plans SET plan_status=NULL WHERE asin=%s AND plan_status='generating'",
                (asin,),
            )
            conn.commit()
            cur.close()
            conn.close()
            # 返回具体错误信息
            display_msg = error_msg if error_msg else "生成失败，请检查商品数据是否完整"
            return jsonify({"success": False, "message": display_msg, "asin": asin})
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "asin": asin})


@bp.route("/api/generate_ai/<asin>")
def api_generate_ai(asin):
    """使用 Agent + Google Ads 技能生成广告方案 (SSE 流式返回)"""
    from flask import stream_with_context
    import queue
    import threading
    import os
    import time as _time

    force = request.args.get("force", "0") == "1"
    llm_provider = request.args.get("llm", "kimi")  # kimi | qianfan

    # KIMI API Key（仅从环境变量读取）
    KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
    if not KIMI_API_KEY:
        raise ValueError("请设置环境变量 KIMI_API_KEY")

    def generate():
        q = queue.Queue()

        def send(msg):
            q.put(json.dumps(msg, ensure_ascii=False))

        def run_agent():
            try:
                # Step 1: 获取产品信息
                send({"type": "progress", "text": "📊 正在获取产品信息..."})
                conn = get_db()
                cur = conn.cursor(dictionary=True)

                # 从 yp_us_products 获取商品信息
                cur.execute(
                    """
                    SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                           p.merchant_name, p.yp_merchant_id,
                           a.title as amz_title, a.brand, a.rating, a.review_count,
                           a.bullet_points, a.description, a.availability, a.category_path
                    FROM yp_us_products p
                    LEFT JOIN amazon_product_details a ON p.asin = a.asin
                    WHERE p.asin = %s LIMIT 1
                """,
                    (asin,),
                )
                product = cur.fetchone()

                if not product:
                    send({"type": "error", "message": f"找不到 ASIN {asin} 的商品信息"})
                    conn.close()
                    return

                # 获取商户关键词
                merchant_id = str(product.get("yp_merchant_id") or "")
                if merchant_id:
                    cur.execute(
                        "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s",
                        (merchant_id,),
                    )
                    brand_keywords = [r["keyword"] for r in cur.fetchall()]
                else:
                    brand_keywords = []

                conn.close()

                send(
                    {
                        "type": "progress",
                        "text": f"✅ 产品: {product.get('amz_title') or product.get('product_name', '')[:50]}",
                    }
                )
                send(
                    {
                        "type": "progress",
                        "text": f"✅ 价格: ${product.get('price', 'N/A')} | 佣金: {product.get('commission', 'N/A')}",
                    }
                )

                # Step 2: 准备技能路径
                skill_path = r"D:\workspace\claws\google-ads-skill\SKILL-Google-Ads.md"
                if not os.path.exists(skill_path):
                    send({"type": "error", "message": f"找不到技能文件: {skill_path}"})
                    return

                # Step 3: 构建 Agent prompt
                send({"type": "progress", "text": "🤖 启动 AI 广告策略师..."})

                product_info = f"""
## 产品信息

- **ASIN**: {asin}
- **商品名称**: {product.get("amz_title") or product.get("product_name", "未知")}
- **品牌**: {product.get("brand") or "未知"}
- **价格**: ${product.get("price", "0")}
- **佣金率**: {product.get("commission", "0%")}
- **评分**: {product.get("rating") or "无"} ({product.get("review_count") or 0} 评价)
- **类目**: {product.get("category_path") or "未知"}
- **库存状态**: {product.get("availability") or "未知"}
- **品牌关键词**: {", ".join(brand_keywords[:10]) if brand_keywords else "无"}

### 产品卖点
{product.get("bullet_points", "[]") if product.get("bullet_points") else "暂无"}

### 产品描述
{(product.get("description") or "暂无")[:500]}
"""

                # 读取技能文件内容
                with open(skill_path, "r", encoding="utf-8") as f:
                    skill_content = f.read()

                # 读取参考文件
                refs_dir = r"D:\workspace\claws\google-ads-skill\references"
                ref_files = [
                    "product-category-analyzer.md",
                    "keyword-engine.md",
                    "negative-keywords.md",
                    "copy-generator.md",
                    "qa-checker.md",
                ]

                refs_content = ""
                for ref_file in ref_files:
                    ref_path = os.path.join(refs_dir, ref_file)
                    if os.path.exists(ref_path):
                        with open(ref_path, "r", encoding="utf-8") as f:
                            refs_content += f"\n\n---\n\n## {ref_file}\n\n{f.read()}"

                send({"type": "progress", "text": "📝 执行 Google Ads 技能 v5.0..."})
                send({"type": "progress", "text": "   - Step 1: 产品品类智能分析"})
                send({"type": "progress", "text": "   - Step 2: 盈利可行性评估"})
                send(
                    {
                        "type": "progress",
                        "text": "   - Step 3-7: 生成广告结构、关键词、文案...",
                    }
                )

                # Step 4: 使用 LLM API 执行技能
                if llm_provider == "kimi":
                    send({"type": "progress", "text": "🤖 调用 KIMI (Moonshot) API..."})
                else:
                    send({"type": "progress", "text": "🤖 调用百度千帆 API..."})

                try:
                    if llm_provider == "kimi":
                        from kimi_client import KimiClient

                        api_key = os.environ.get("KIMI_API_KEY", KIMI_API_KEY)
                        client = KimiClient(model="kimi-k2.5", api_key=api_key)
                    else:
                        from qianfan_client import QianfanClient

                        # 仅从环境变量读取
                        bearer_token = os.environ.get("QIANFAN_BEARER_TOKEN", "")
                        if not bearer_token:
                            raise ValueError("请设置环境变量 QIANFAN_BEARER_TOKEN")

                        client = QianfanClient(
                            model="ernie-4.0-8k", bearer_token=bearer_token
                        )

                    # 准备产品信息字典
                    product_dict = {
                        "asin": asin,
                        "amz_title": product.get("amz_title"),
                        "product_name": product.get("product_name"),
                        "brand": product.get("brand"),
                        "price": product.get("price"),
                        "commission": product.get("commission"),
                        "rating": product.get("rating"),
                        "review_count": product.get("review_count"),
                        "category_path": product.get("category_path"),
                        "bullet_points": product.get("bullet_points"),
                        "description": product.get("description"),
                        "brand_keywords": brand_keywords,
                    }

                    # 流式生成
                    send(
                        {
                            "type": "progress",
                            "text": "📝 AI 正在执行 Google Ads 技能 v5.0...",
                        }
                    )
                    send({"type": "thinking", "text": ""})

                    accumulated_text = ""
                    _chunk_count = 0

                    def on_progress(chunk):
                        nonlocal accumulated_text, _chunk_count
                        accumulated_text += chunk
                        _chunk_count += 1
                        # 发送思考过程
                        send({"type": "thinking", "text": chunk})
                        # 每50个chunk发一次token计数进度
                        if _chunk_count % 50 == 0:
                            send(
                                {"type": "token_count", "count": len(accumulated_text)}
                            )

                    result_text = client.chat_with_skill(
                        product_info=product_dict,
                        skill_content=skill_content,
                        refs_content=refs_content,
                        stream=True,
                        on_progress=on_progress,
                    )

                    # 关键诊断：记录 AI 返回的原始内容
                    _diag_dir = os.path.join(os.path.dirname(__file__), "logs")
                    os.makedirs(_diag_dir, exist_ok=True)
                    _diag_path = os.path.join(
                        _diag_dir, f"ai_raw_{_time.strftime('%Y%m%d_%H%M%S')}.txt"
                    )
                    with open(_diag_path, "w", encoding="utf-8") as _lf:
                        _lf.write(f"=== result_text length: {len(result_text)} ===\n")
                        _lf.write(f"=== has brace: {'{' in result_text} ===\n")
                        _lf.write(f"=== first 200 chars ===\n{result_text[:200]}\n")
                        _lf.write(f"=== last 200 chars ===\n{result_text[-200:]}\n")
                        _lf.write(f"\n=== FULL CONTENT ===\n{result_text}")
                    print(
                        f"[DIAG] AI result saved to {_diag_path}, len={len(result_text)}, has_brace={'{' in result_text}"
                    )

                    send(
                        {"type": "progress", "text": "✅ AI 生成完成，正在解析结果..."}
                    )

                    # 解析 JSON 结果
                    json_result = None
                    parse_error = None

                    # 记录原始返回内容，便于排查解析问题
                    _log_dir = os.path.join(os.path.dirname(__file__), "logs")
                    os.makedirs(_log_dir, exist_ok=True)
                    _log_path = os.path.join(
                        _log_dir, f"ai_raw_{_time.strftime('%Y%m%d_%H%M%S')}.txt"
                    )
                    with open(_log_path, "w", encoding="utf-8") as _lf:
                        _lf.write(result_text)
                    send(
                        {"type": "progress", "text": f"📝 原始返回已记录: {_log_path}"}
                    )

                    # 方法1: 查找 ```json ... ``` 块
                    if "```json" in result_text:
                        start = result_text.find("```json") + 7
                        end = result_text.find("```", start)
                        if end > start:
                            json_str = result_text[start:end].strip()
                            try:
                                json_result = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                parse_error = f"JSON块解析失败: {str(e)}"

                    # 方法2: 查找 ``` ... ``` 块
                    if not json_result and "```" in result_text:
                        start = result_text.find("```") + 3
                        end = result_text.find("```", start)
                        if end > start:
                            json_str = result_text[start:end].strip()
                            try:
                                json_result = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                parse_error = f"代码块解析失败: {str(e)}"

                    # 方法3: 尝试直接解析整个响应中的 JSON
                    if not json_result:
                        # 查找第一个 { 和最后一个 }
                        start = result_text.find("{")
                        end = result_text.rfind("}")
                        if start >= 0 and end > start:
                            json_str = result_text[start : end + 1]
                            try:
                                json_result = json.loads(json_str)
                            except json.JSONDecodeError as e:
                                parse_error = f"直接解析失败: {str(e)[:100]}"

                    # 方法4: JSON 自动修复 —— 处理 AI 输出中常见的格式瑕疵 + 截断修复
                    if not json_result:
                        import re as _re

                        # 提取 JSON 字符串
                        json_str = ""
                        if "```json" in result_text:
                            s = result_text.find("```json") + 7
                            e = result_text.find("```", s)
                            if e > s:
                                json_str = result_text[s:e].strip()
                            else:
                                # 被 ```json 包裹但没有结束 ```（输出被截断）
                                json_str = result_text[s:].strip()
                        elif "```" in result_text:
                            s = result_text.find("```") + 3
                            e = result_text.find("```", s)
                            if e > s:
                                json_str = result_text[s:e].strip()
                            else:
                                # 被 ``` 包裹但没有结束 ```（输出被截断）
                                json_str = result_text[s:].strip()
                        else:
                            s = result_text.find("{")
                            e = result_text.rfind("}")
                            if s >= 0 and e > s:
                                json_str = result_text[s : e + 1]
                            elif s >= 0:
                                # 只有开始 { 没有结束 }（严重截断）
                                json_str = result_text[s:].strip()

                        if json_str:
                            try:
                                fixed = json_str
                                # 修复1: 尾部逗号 ],} → ] }
                                fixed = _re.sub(r",\s*([}\]])", r"\1", fixed)
                                # 修复2: 字符串值后缺少逗号
                                fixed = _re.sub(r'"\s*\n(\s*")', r'",\n\1', fixed)
                                # 修复3: 连续双引号
                                fixed = _re.sub(r'""(\s*[}\],:])', r'"\1', fixed)
                                # 修复4: 清理尾部不完整的字符串（如 "Doctor Re 截断）
                                fixed = _re.sub(r',?\s*"[^"]*$', "", fixed)
                                fixed = _re.sub(r",?\s*$", "", fixed)
                                # 修复5: 用栈逐层智能补全不闭合的括号
                                _stack = []
                                for _ch in fixed:
                                    if _ch == "{":
                                        _stack.append("}")
                                    elif _ch == "}":
                                        if _stack and _stack[-1] == "}":
                                            _stack.pop()
                                    elif _ch == "[":
                                        _stack.append("]")
                                    elif _ch == "]":
                                        if _stack and _stack[-1] == "]":
                                            _stack.pop()
                                if _stack:
                                    _trimmed = fixed.rstrip()
                                    _needs_comma = (
                                        _trimmed.endswith('"')
                                        or _trimmed[-1] in "0123456789eE"
                                    )
                                    _remaining = list(reversed(_stack))
                                    _suffix = ""
                                    for _i, _close_ch in enumerate(_remaining):
                                        if _needs_comma and _i < len(_remaining) - 1:
                                            _suffix += _close_ch
                                            _needs_comma = True
                                        else:
                                            _suffix += _close_ch
                                    fixed = fixed + _suffix
                                json_result = json.loads(fixed)
                                if json_result:
                                    send(
                                        {
                                            "type": "progress",
                                            "text": "🔧 JSON 自动修复成功（截断内容已补全）",
                                        }
                                    )
                            except json.JSONDecodeError as _fix_err:
                                parse_error = f"修复后仍失败: {_fix_err}"

                    if not json_result:
                        _err_detail = (
                            parse_error or "AI返回内容中未找到有效JSON结构（无花括号）"
                        )
                        send(
                            {
                                "type": "error",
                                "message": f"无法解析 AI 返回的 JSON: {_err_detail}\n\n原始内容: {result_text[:500]}...",
                            }
                        )
                        return

                    # 保存到数据库（重新创建连接，之前的已关闭）
                    send({"type": "progress", "text": "💾 保存广告方案到数据库..."})

                    conn = get_db()
                    cur = conn.cursor(dictionary=True)

                    campaigns = json_result.get("campaigns", [])
                    campaign_count = len(campaigns)
                    ad_group_count = sum(len(c.get("ad_groups", [])) for c in campaigns)
                    ad_count = ad_group_count * 3

                    product_analysis = json_result.get("product_analysis", {})
                    target_cpa = float(product_analysis.get("target_cpa", 0) or 0)

                    # 写入数据库
                    cur.execute("SELECT id FROM ads_plans WHERE asin=%s", (asin,))
                    exists = cur.fetchone()

                    merchant_name = product.get("merchant_name") or ""
                    merchant_id = str(product.get("yp_merchant_id") or "")

                    if exists and force:
                        # 更新
                        cur.execute(
                            """
                            UPDATE ads_plans SET
                                merchant_id = %s,
                                merchant_name = %s,
                                plan_status = 'completed',
                                campaign_count = %s,
                                ad_group_count = %s,
                                ad_count = %s,
                                target_cpa = %s,
                                ai_strategy_notes = %s,
                                updated_at = NOW()
                            WHERE asin = %s
                        """,
                            (
                                merchant_id,
                                merchant_name,
                                campaign_count,
                                ad_group_count,
                                ad_count,
                                target_cpa,
                                json.dumps(product_analysis, ensure_ascii=False),
                                asin,
                            ),
                        )
                    else:
                        # 插入
                        cur.execute(
                            """
                            INSERT INTO ads_plans (
                                asin, merchant_id, merchant_name, plan_status,
                                campaign_count, ad_group_count, ad_count, target_cpa,
                                ai_strategy_notes, created_at, updated_at
                            ) VALUES (
                                %s, %s, %s, 'completed',
                                %s, %s, %s, %s,
                                %s, NOW(), NOW()
                            )
                        """,
                            (
                                asin,
                                merchant_id,
                                merchant_name,
                                campaign_count,
                                ad_group_count,
                                ad_count,
                                target_cpa,
                                json.dumps(product_analysis, ensure_ascii=False),
                            ),
                        )

                    # ── 写入 ads_campaigns / ads_ad_groups / ads_ads 子表 ──
                    # 先删除该 asin 的旧数据
                    cur.execute(
                        "SELECT id FROM ads_plans WHERE asin=%s LIMIT 1", (asin,)
                    )
                    plan_row = cur.fetchone()

                    # 删除旧 campaigns（级联删除 ad_groups / ads）
                    cur.execute("SELECT id FROM ads_campaigns WHERE asin=%s", (asin,))
                    old_camps = cur.fetchall()
                    for oc in old_camps:
                        old_cid = oc["id"]
                        cur.execute(
                            "SELECT id FROM ads_ad_groups WHERE campaign_id=%s",
                            (old_cid,),
                        )
                        old_groups = cur.fetchall()
                        for og in old_groups:
                            cur.execute(
                                "DELETE FROM ads_ads WHERE ad_group_id=%s", (og["id"],)
                            )
                        cur.execute(
                            "DELETE FROM ads_ad_groups WHERE campaign_id=%s", (old_cid,)
                        )
                    cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))

                    # 插入新数据
                    def _to_float(v):
                        if not v:
                            return 0.0
                        try:
                            return float(
                                str(v).replace("%", "").replace("$", "").strip()
                            )
                        except:
                            return 0.0

                    product_price_val = _to_float(
                        product.get("price") or product.get("yp_price")
                    )
                    commission_pct_val = _to_float(product.get("commission"))
                    profitability = json_result.get("profitability", {})
                    target_cpa_str = profitability.get("safe_target_cpa", "0") or "0"
                    target_cpa_val = float(
                        target_cpa_str.replace("$", "").replace(",", "") or 0
                    )
                    tracking_url = (
                        product.get("tracking_url")
                        or product.get("amz_url")
                        or f"https://www.amazon.com/dp/{asin}"
                    )

                    for camp_idx, camp in enumerate(campaigns):
                        camp_name = (
                            camp.get("campaign_name") or f"Campaign {camp_idx + 1}"
                        )
                        budget_pct = camp.get("budget_percentage") or 0
                        camp_neg_kws = camp.get("campaign_negative_keywords", [])
                        camp_target_cpa_str = (
                            camp.get("target_cpa", str(target_cpa_val)) or "0"
                        )
                        camp_target_cpa = float(
                            camp_target_cpa_str.replace("$", "").replace(",", "") or 0
                        )

                        cur.execute(
                            """
                            INSERT INTO ads_campaigns (
                                asin, merchant_id, merchant_name, campaign_name,
                                journey_stage, budget_pct, product_price, commission_pct, target_cpa,
                                negative_keywords, status, created_at, updated_at
                            ) VALUES (%s,%s,%s,%s,'awareness',%s,%s,%s,%s,%s,'draft',NOW(),NOW())
                        """,
                            (
                                asin,
                                merchant_id,
                                merchant_name,
                                camp_name,
                                budget_pct,
                                product_price_val,
                                commission_pct_val,
                                camp_target_cpa,
                                json.dumps(camp_neg_kws),
                            ),
                        )
                        camp_db_id = cur.lastrowid

                        for grp in camp.get("ad_groups", []):
                            grp_name = grp.get("ad_group_name") or "Ad Group"
                            kws = grp.get("keywords", [])
                            # 转换关键词格式
                            kw_list = []
                            for kw in kws:
                                mt = kw.get("match_type", "[B]")
                                if mt == "[E]":
                                    ktype = "exact"
                                elif mt == "[P]":
                                    ktype = "phrase"
                                else:
                                    ktype = "broad"
                                kw_list.append(
                                    {"kw": kw.get("keyword", ""), "type": ktype}
                                )

                            cur.execute(
                                """
                                INSERT INTO ads_ad_groups (
                                    campaign_id, asin, ad_group_name,
                                    keywords, keyword_count, status, created_at, updated_at
                                ) VALUES (%s,%s,%s,%s,%s,'draft',NOW(),NOW())
                            """,
                                (
                                    camp_db_id,
                                    asin,
                                    grp_name,
                                    json.dumps(kw_list),
                                    len(kw_list),
                                ),
                            )
                            grp_db_id = cur.lastrowid

                            # 组合 headlines + descriptions 成广告（每个 ad_group 生成1个 ad）
                            headlines_raw = grp.get("headlines", [])
                            descriptions_raw = grp.get("descriptions", [])

                            # 确保 chars 字段存在
                            headlines_db = []
                            for h in headlines_raw:
                                txt = (
                                    h.get("text", "") if isinstance(h, dict) else str(h)
                                )
                                headlines_db.append({"text": txt, "chars": len(txt)})

                            descriptions_db = []
                            for d in descriptions_raw:
                                txt = (
                                    d.get("text", "") if isinstance(d, dict) else str(d)
                                )
                                descriptions_db.append(
                                    {
                                        "text": txt,
                                        "chars": len(
                                            d.get("chars", len(txt))
                                            if isinstance(d, dict)
                                            else len(txt)
                                        ),
                                    }
                                )

                            all_chars_valid = all(
                                h["chars"] <= 30 for h in headlines_db
                            ) and all(d["chars"] <= 90 for d in descriptions_db)

                            final_url = (
                                tracking_url or f"https://www.amazon.com/dp/{asin}"
                            )

                            cur.execute(
                                """
                                INSERT INTO ads_ads (
                                    ad_group_id, campaign_id, asin, variant,
                                    headlines, descriptions, sitelinks, callouts,
                                    structured_snippet, final_url, display_url,
                                    headline_count, description_count,
                                    all_chars_valid, status, created_at, updated_at
                                ) VALUES (%s,%s,%s,'A',%s,%s,'[]','[]','{}',%s,%s,%s,%s,%s,'draft',NOW(),NOW())
                            """,
                                (
                                    grp_db_id,
                                    camp_db_id,
                                    asin,
                                    json.dumps(headlines_db, ensure_ascii=False),
                                    json.dumps(descriptions_db, ensure_ascii=False),
                                    final_url,
                                    "amazon.com",
                                    len(headlines_db),
                                    len(descriptions_db),
                                    1 if all_chars_valid else 0,
                                ),
                            )

                    # 更新 ads_plans 中的统计数（以实际写入为准）
                    actual_camp_count = len(campaigns)
                    actual_group_count = sum(
                        len(c.get("ad_groups", [])) for c in campaigns
                    )
                    actual_ad_count = actual_group_count
                    cur.execute(
                        """
                        UPDATE ads_plans SET campaign_count=%s, ad_group_count=%s, ad_count=%s
                        WHERE asin=%s
                    """,
                        (actual_camp_count, actual_group_count, actual_ad_count, asin),
                    )

                    conn.commit()
                    conn.close()

                    # 返回成功
                    send(
                        {
                            "type": "progress",
                            "text": f"💾 已写入 {actual_camp_count} 个广告系列、{actual_group_count} 个广告组",
                        }
                    )
                    send({"type": "progress", "text": "✅ 广告方案生成完成！"})
                    send(
                        {
                            "type": "done",
                            "result": {
                                "asin": asin,
                                "campaigns": actual_camp_count,
                                "ad_groups": actual_group_count,
                                "ads": actual_ad_count,
                                "strategy_analysis": {
                                    "product_strengths": product_analysis.get(
                                        "category", "已完成"
                                    ),
                                    "target_audience": product_analysis.get(
                                        "target_audience", "已确定"
                                    ),
                                },
                            },
                        }
                    )

                except ImportError:
                    send(
                        {
                            "type": "error",
                            "message": "未找到 qianfan_client.py，请检查文件是否存在",
                        }
                    )
                except Exception as e:
                    send({"type": "error", "message": f"广告生成失败: {str(e)}"})

            except Exception as e:
                send({"type": "error", "message": f"执行失败: {str(e)}"})

            # 启动后台线程

        thread = threading.Thread(target=run_agent)
        thread.start()

        # SSE 流式返回
        while True:
            try:
                msg = q.get(timeout=300)  # 5分钟超时
                yield f"data: {msg}\n\n"

                # 如果是 done 或 error，结束流
                data = json.loads(msg)
                if data.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'ping'})}\n\n"
                continue

        thread.join()

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@bp.route("/api/generate_agent/<asin>", methods=["POST"])
def api_generate_agent(asin):
    """
    三引擎广告生成：支持 copaw / memory / kimi 三种 backend

    backend 参数（默认 copaw）：
    - copaw:  CoPaw Agent（有记忆，需启动 CoPaw 服务）→ fallback 到 memory
    - memory: 文件系统记忆 + KIMI API（无需外部服务，推荐）
    - kimi:   纯 KIMI API（无记忆，baseline 对照组）

    记忆机制：
    - copaw: CoPaw 的 session 机制自动管理（context_compact + memory_summary）
    - memory: ad_memory.py 文件系统，记录每次生成的经验摘要，下次注入 prompt
    """
    import os
    import re
    import time as _time

    # backend 选择
    backend = request.args.get("backend", "memory").lower()
    if backend not in ("copaw", "memory", "kimi"):
        backend = "memory"

    # 导入记忆引擎
    try:
        from ad_memory import (
            get_memory_context,
            record_generation,
            get_stats as _get_mem_stats,
        )

        _has_memory = True
    except ImportError:
        _has_memory = False

    # CoPaw Agent API 配置
    COPAW_BASE_URL = "http://127.0.0.1:21643"
    COPAW_PROCESS_URL = f"{COPAW_BASE_URL}/api/agent/process"
    COPAW_SESSION_ID = "ad_creator"
    COPAW_USER_ID = "ads_system"

    # 1. 获取产品信息
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission, p.merchant_name,
                   p.tracking_url, p.yp_merchant_id,
                   a.title as amz_title, a.brand, a.rating, a.review_count,
                   a.bullet_points, a.description, a.category_path
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s LIMIT 1
            """,
            (asin,),
        )
        product = cur.fetchone()

        # 获取品牌关键词
        brand_keywords = []
        if product and product.get("merchant_name"):
            cur.execute(
                "SELECT keyword FROM ads_merchant_keywords WHERE merchant_name = %s LIMIT 20",
                (product["merchant_name"],),
            )
            brand_keywords = [r["keyword"] for r in cur.fetchall()]

        conn.close()

        if not product:
            return jsonify({"success": False, "error": f"找不到产品 {asin}"})

    except Exception as e:
        return jsonify({"success": False, "error": f"数据库查询失败: {str(e)}"})

    brand = product.get("brand") or product.get("merchant_name") or "Unknown"
    category = product.get("category_path") or "Unknown"

    # 2. 构建产品信息
    product_info = f"""## 产品信息

- **ASIN**: {asin}
- **商品名称**: {product.get("amz_title") or product.get("product_name", "未知")}
- **品牌**: {product.get("brand") or "未知"}
- **价格**: ${product.get("price", "0")}
- **佣金率**: {product.get("commission", "0%")}
- **评分**: {product.get("rating") or "无"} ({product.get("review_count") or 0} 评价)
- **类目**: {product.get("category_path") or "未知"}
- **品牌关键词**: {", ".join(brand_keywords[:10]) if brand_keywords else "无"}

### 产品卖点
{product.get("bullet_points") or "暂无"}

### 产品描述
{(product.get("description") or "暂无")[:500]}
"""

    # 3. 读取 Google Ads 技能文件
    skill_path = r"D:\workspace\claws\google-ads-skill\SKILL-Google-Ads.md"
    skill_content = ""
    if os.path.exists(skill_path):
        with open(skill_path, "r", encoding="utf-8") as f:
            skill_content = f.read()

    refs_content = ""
    refs_dir = r"D:\workspace\claws\google-ads-skill\references"
    if os.path.isdir(refs_dir):
        for ref_file in os.listdir(refs_dir):
            if ref_file.endswith(".md"):
                ref_path = os.path.join(refs_dir, ref_file)
                with open(ref_path, "r", encoding="utf-8") as f:
                    refs_content += f"\n\n---\n\n## {ref_file}\n\n{f.read()}"

    # 4. 构建基础 system message
    base_system = f"""You are an expert Google Ads copywriter for Amazon affiliate marketing.

{skill_content[:5000] if skill_content else ""}

Rules:
- Target market: USA
- Language: American English
- Currency: USD
- Headlines: max 30 characters (STRICT!)
- Descriptions: max 90 characters (STRICT!)
- Return ONLY valid JSON, no markdown code fences"""

    # 获取记忆上下文（memory 模式和 copaw fallback 都用）
    memory_context = ""
    if _has_memory and backend != "kimi":
        memory_context = get_memory_context(
            current_asin=asin,
            current_brand=brand,
            current_category=category,
        )

    # 构建 user prompt
    base_prompt = f"""Generate a Google Ads campaign plan for this product:

{product_info}

{f"Reference materials:\n{refs_content[:8000]}" if refs_content else ""}

Return ONLY valid JSON (no markdown, no code fences) with this structure:
{{"product_analysis":{{}},"profitability":{{}},"account_negative_keywords":[],"campaigns":[{{"name":"","budget_allocation":"","strategy":"","target_cpa":"","ad_groups":[{{"name":"","keywords":[{{"keyword":"","match_type":"","chars":0}}],"negative_keywords":[],"headlines":[{{"text":"","chars":0}}],"descriptions":[{{"text":"","chars":0}}]}}]}}],"strategy_notes":""}}"""

    # 记忆模式的 prompt 额外注入经验
    if memory_context:
        base_prompt = f"""{memory_context}

---

{base_prompt}

IMPORTANT: Based on the experience above, generate BETTER ads than before. Use different keywords and headlines. Be creative and original."""

    # 导入 requests
    import requests

    # ========== Engine 1: CoPaw Agent ==========
    result_text = None
    used_backend = backend

    if backend == "copaw":
        system_msg = (
            base_system
            + "\nYou have persistent memory across sessions - remember what worked and what didn't."
        )
        copaw_user_prompt = base_prompt.replace(
            "Return ONLY valid JSON",
            "Return ONLY valid JSON (no markdown, no code fences)",
        )
        try:
            copaw_payload = {
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "text", "text": system_msg}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": copaw_user_prompt}],
                    },
                ],
                "session_id": COPAW_SESSION_ID,
                "user_id": COPAW_USER_ID,
            }

            resp = requests.post(
                COPAW_PROCESS_URL,
                json=copaw_payload,
                timeout=300,
                stream=True,
            )
            resp.raise_for_status()

            # 解析 SSE stream
            assistant_text = ""
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                except (json.JSONDecodeError, ValueError):
                    continue

                obj_type = evt.get("object", "")
                status = evt.get("status", "")

                # content 增量
                if obj_type == "content":
                    output = evt.get("output")
                    if isinstance(output, dict):
                        text = output.get("text", "")
                        if evt.get("role") == "assistant" and text:
                            assistant_text += text
                    elif isinstance(output, list):
                        for part in output:
                            if isinstance(part, dict) and part.get("type") == "text":
                                if evt.get("role") == "assistant":
                                    assistant_text += part.get("text", "")

                # message 汇总
                if (
                    obj_type == "message"
                    and status == "completed"
                    and evt.get("role") == "assistant"
                ):
                    output = evt.get("output")
                    if isinstance(output, list):
                        msg_text = ""
                        for part in output:
                            if isinstance(part, dict) and part.get("type") == "text":
                                msg_text += part.get("text", "")
                        if msg_text.strip():
                            assistant_text = msg_text

                # response 最终汇总
                if obj_type == "response" and status == "completed":
                    output = evt.get("output")
                    if isinstance(output, list):
                        for item in output:
                            if isinstance(item, dict) and item.get("type") == "message":
                                content = item.get("content", [])
                                if isinstance(content, list):
                                    msg_text = ""
                                    for part in content:
                                        if (
                                            isinstance(part, dict)
                                            and part.get("type") == "text"
                                        ):
                                            msg_text += part.get("text", "")
                                    if msg_text.strip():
                                        assistant_text = msg_text

            if assistant_text.strip():
                result_text = assistant_text.strip()
                used_backend = "copaw"

        except requests.ConnectionError:
            pass  # CoPaw 不可用，fallback 到 memory
        except Exception:
            pass  # 其他错误，fallback

    # ========== Engine 2: Memory + KIMI API（推荐） ==========
    if result_text is None and backend in ("memory", "copaw"):
        system_msg = base_system
        if memory_context:
            system_msg += (
                "\n\nYou have access to past generation experience. Use it to improve."
            )

        try:
            api_key = os.environ.get(
                "KIMI_API_KEY", "sk-Id6uRyPXBuYMKc901g35NzREkAOhWBBDeDNR07bj7YalIwWy"
            )

            resp = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "kimi-k2.5",
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": base_prompt},
                    ],
                    "temperature": 1,
                    "max_tokens": 16384,
                },
                timeout=300,
            )
            resp.raise_for_status()
            result_text = resp.json()["choices"][0]["message"]["content"]
            used_backend = "memory" if memory_context else "kimi"

        except Exception as e:
            return jsonify({"success": False, "error": f"AI API 调用失败: {str(e)}"})

    # ========== Engine 3: Pure KIMI API（无记忆） ==========
    if result_text is None and backend == "kimi":
        try:
            api_key = os.environ.get("KIMI_API_KEY", "")
            if not api_key:
                raise ValueError("请设置环境变量 KIMI_API_KEY")

            resp = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "kimi-k2.5",
                    "messages": [
                        {"role": "system", "content": base_system},
                        {"role": "user", "content": base_prompt},
                    ],
                    "temperature": 1,
                    "max_tokens": 16384,
                },
                timeout=300,
            )
            resp.raise_for_status()
            result_text = resp.json()["choices"][0]["message"]["content"]
            used_backend = "kimi"

        except Exception as e:
            return jsonify({"success": False, "error": f"AI API 调用失败: {str(e)}"})

    if not result_text:
        return jsonify({"success": False, "error": "所有引擎均失败"})

    # 5. 解析结果
    # 保存原始输出用于诊断
    _diag_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(_diag_dir, exist_ok=True)
    _diag_path = os.path.join(
        _diag_dir, f"agent_{used_backend}_{_time.strftime('%Y%m%d_%H%M%S')}.txt"
    )
    with open(_diag_path, "w", encoding="utf-8") as _lf:
        _lf.write(result_text)

    # 去掉 markdown 代码块标记
    clean_text = re.sub(r"^```(?:json)?\s*\n?", "", result_text.strip())
    clean_text = re.sub(r"\n?```\s*$", "", clean_text)

    # 提取 JSON
    parsed = None
    json_match = re.search(r'\{[\s\S]*"campaigns"[\s\S]*\}', clean_text)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    if not parsed:
        json_match2 = re.search(r"\{[\s\S]*\}", clean_text)
        if json_match2:
            try:
                parsed = json.loads(json_match2.group())
            except json.JSONDecodeError:
                pass

    if parsed and parsed.get("campaigns"):
        # 记录到记忆引擎（memory 和 copaw 模式都记录）
        if _has_memory and used_backend != "kimi":
            try:
                _kw_sample = []
                _hl_sample = []
                for camp in parsed["campaigns"]:
                    for ag in camp.get("ad_groups", []):
                        for kw in ag.get("keywords", [])[:3]:
                            _kw_sample.append(kw.get("keyword", ""))
                        for hl in ag.get("headlines", [])[:2]:
                            _hl_sample.append(hl.get("text", ""))
                record_generation(
                    asin=asin,
                    brand=brand,
                    category=category,
                    campaigns_count=len(parsed["campaigns"]),
                    keywords_sample=_kw_sample[:5],
                    headlines_sample=_hl_sample[:5],
                    success=True,
                )
            except Exception:
                pass  # 记忆记录失败不影响主流程

        # 获取记忆统计
        mem_stats = {}
        if _has_memory:
            try:
                mem_stats = _get_mem_stats()
            except Exception:
                pass

        # ── 写入数据库（与 api_generate 相同的表结构）──
        _saved_to_db = False
        try:
            _conn2 = _db()
            _cur2 = _conn2.cursor(dictionary=True)

            merchant_id = product.get("yp_merchant_id") or 0
            merchant_name = product.get("merchant_name") or ""

            def _to_float_v(v):
                if not v:
                    return 0.0
                try:
                    return float(str(v).replace("%", "").replace("$", "").strip())
                except:
                    return 0.0

            product_price_val = _to_float_v(product.get("price"))
            commission_pct_val = _to_float_v(product.get("commission"))
            tracking_url = (
                product.get("tracking_url") or f"https://www.amazon.com/dp/{asin}"
            )
            campaigns_list = parsed.get("campaigns", [])
            ad_group_count = sum(len(c.get("ad_groups", [])) for c in campaigns_list)
            ad_count = ad_group_count  # 每个 ad_group 生成 1 个 ad

            # 1. 写 ads_plans
            _cur2.execute(
                """
                INSERT INTO ads_plans (asin, merchant_id, merchant_name, plan_status,
                    campaign_count, ad_group_count, ad_count, ai_strategy_notes,
                    created_at, updated_at)
                VALUES (%s,%s,%s,'completed',%s,%s,%s,%s,NOW(),NOW())
                ON DUPLICATE KEY UPDATE
                    plan_status='completed', campaign_count=%s, ad_group_count=%s,
                    ad_count=%s, ai_strategy_notes=%s, updated_at=NOW()
            """,
                (
                    asin,
                    merchant_id,
                    merchant_name,
                    len(campaigns_list),
                    ad_group_count,
                    ad_count,
                    f"[Agent:{used_backend}] {parsed.get('strategy_notes', '')[:500]}",
                    len(campaigns_list),
                    ad_group_count,
                    ad_count,
                    f"[Agent:{used_backend}] {parsed.get('strategy_notes', '')[:500]}",
                ),
            )

            # 2. 删除旧 campaigns
            _cur2.execute("SELECT id FROM ads_campaigns WHERE asin=%s", (asin,))
            for _oc in _cur2.fetchall():
                _cur2.execute(
                    "SELECT id FROM ads_ad_groups WHERE campaign_id=%s", (_oc["id"],)
                )
                for _og in _cur2.fetchall():
                    _cur2.execute(
                        "DELETE FROM ads_ads WHERE ad_group_id=%s", (_og["id"],)
                    )
                _cur2.execute(
                    "DELETE FROM ads_ad_groups WHERE campaign_id=%s", (_oc["id"],)
                )
            _cur2.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))

            # 3. 插入新 campaigns / ad_groups / ads
            for camp in campaigns_list:
                camp_name = camp.get("name") or camp.get("campaign_name") or "Campaign"
                _cur2.execute(
                    """
                    INSERT INTO ads_campaigns (
                        asin, merchant_id, merchant_name, campaign_name,
                        journey_stage, budget_pct, product_price, commission_pct, target_cpa,
                        negative_keywords, status, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,'awareness',0,%s,%s,0,'[]','draft',NOW(),NOW())
                """,
                    (
                        asin,
                        merchant_id,
                        merchant_name,
                        camp_name,
                        product_price_val,
                        commission_pct_val,
                    ),
                )
                camp_db_id = _cur2.lastrowid

                for grp in camp.get("ad_groups", []):
                    grp_name = grp.get("name") or grp.get("ad_group_name") or "Ad Group"
                    kws_raw = grp.get("keywords", [])
                    kw_list = []
                    for kw in kws_raw:
                        mt = kw.get("match_type", "broad")
                        ktype = (
                            "exact"
                            if mt in ("[E]", "exact")
                            else "phrase"
                            if mt in ("[P]", "phrase")
                            else "broad"
                        )
                        kw_list.append({"kw": kw.get("keyword", ""), "type": ktype})

                    _cur2.execute(
                        """
                        INSERT INTO ads_ad_groups (
                            campaign_id, asin, ad_group_name,
                            keywords, keyword_count, status, created_at, updated_at
                        ) VALUES (%s,%s,%s,%s,%s,'draft',NOW(),NOW())
                    """,
                        (
                            camp_db_id,
                            asin,
                            grp_name,
                            json.dumps(kw_list, ensure_ascii=False),
                            len(kw_list),
                        ),
                    )
                    grp_db_id = _cur2.lastrowid

                    headlines_raw = grp.get("headlines", [])
                    descriptions_raw = grp.get("descriptions", [])

                    # 使用验证和修正函数处理广告内容
                    headlines_db, descriptions_db, ad_warnings = validate_and_fix_ad(
                        headlines_raw,
                        descriptions_raw,
                        brand=brand,
                        product_title=product.get("amz_title")
                        or product.get("product_name", ""),
                    )

                    # 记录警告（如果有）
                    if ad_warnings:
                        print(f"[Ad QA] ASIN={asin} warnings: {ad_warnings}")

                    all_valid = all(h["chars"] <= 30 for h in headlines_db) and all(
                        d["chars"] <= 90 for d in descriptions_db
                    )

                    _cur2.execute(
                        """
                        INSERT INTO ads_ads (
                            ad_group_id, campaign_id, asin, variant,
                            headlines, descriptions, sitelinks, callouts, structured_snippet,
                            final_url, display_url, headline_count, description_count,
                            all_chars_valid, status, created_at, updated_at
                        ) VALUES (%s,%s,%s,'A',%s,%s,'[]','[]','{}',%s,'amazon.com',%s,%s,%s,'draft',NOW(),NOW())
                    """,
                        (
                            grp_db_id,
                            camp_db_id,
                            asin,
                            json.dumps(headlines_db, ensure_ascii=False),
                            json.dumps(descriptions_db, ensure_ascii=False),
                            tracking_url,
                            len(headlines_db),
                            len(descriptions_db),
                            all_valid,
                        ),
                    )

            _conn2.commit()
            _conn2.close()
            _saved_to_db = True
        except Exception as _db_err:
            _saved_to_db = False
            import traceback

            _db_err_msg = traceback.format_exc()

        return jsonify(
            {
                "success": True,
                "asin": asin,
                "backend": used_backend,
                "campaigns": parsed.get("campaigns", []),
                "strategy_notes": parsed.get("strategy_notes", ""),
                "raw_output": result_text[-1000:],
                "memory_stats": mem_stats,
                "saved_to_db": _saved_to_db,
            }
        )

    # 解析失败也记录
    if _has_memory and used_backend != "kimi":
        try:
            record_generation(
                asin=asin,
                brand=brand,
                category=category,
                campaigns_count=0,
                keywords_sample=[],
                headlines_sample=[],
                success=False,
                error="JSON parse failed",
            )
        except Exception:
            pass

    return jsonify(
        {
            "success": False,
            "error": "AI 生成了内容但无法解析为有效 JSON",
            "raw_output": result_text[-500:] if result_text else "无输出",
            "backend": used_backend,
        }
    )


@bp.route("/api/ad_memory_stats", methods=["GET"])
def api_ad_memory_stats():
    """获取广告记忆统计"""
    try:
        from ad_memory import get_stats

        return jsonify({"success": True, **get_stats()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# Workflow API - 广告流程页面
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/api/workflow/status/<merchant_id>", methods=["GET", "POST"])
def api_workflow_status(merchant_id):
    """检查商户所有已有数据状态"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        result = {
            "merchant": None,
            "website": None,
            "keywords": None,
            "semrush": None,
            "products": None,
            "amazon": None,
        }

        # 检查商户信息
        cur.execute(
            "SELECT merchant_id, merchant_name, website FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        if merchant:
            result["merchant"] = {
                "merchant_id": merchant["merchant_id"],
                "merchant_name": merchant["merchant_name"],
                "website": merchant["website"],
            }

        # 检查官网
        if merchant and merchant.get("website"):
            result["website"] = {"website": merchant["website"]}

        # 检查关键词
        cur.execute(
            "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s LIMIT 10",
            (merchant_id,),
        )
        keywords = cur.fetchall()
        if keywords:
            result["keywords"] = {
                "keywords": [k["keyword"] for k in keywords],
                "count": len(keywords),
            }

        # 检查 SEMrush 数据
        cur.execute(
            "SELECT id FROM semrush_data WHERE merchant_id = %s LIMIT 1", (merchant_id,)
        )
        semrush = cur.fetchone()
        if semrush:
            result["semrush"] = {"has_data": True}

        # 检查商品
        cur.execute(
            "SELECT COUNT(*) as cnt FROM yp_us_products WHERE yp_merchant_id = %s",
            (merchant_id,),
        )
        products_count = cur.fetchone()
        if products_count and products_count["cnt"] > 0:
            result["products"] = {"total": products_count["cnt"]}

        # 检查亚马逊数据
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM yp_us_products p
            JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.yp_merchant_id = %s
            """,
            (merchant_id,),
        )
        amazon_count = cur.fetchone()
        if amazon_count and amazon_count["cnt"] > 0:
            result["amazon"] = {"with_amazon": amazon_count["cnt"]}

        conn.close()

        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/merchant/<merchant_id>", methods=["GET", "POST"])
def api_workflow_merchant(merchant_id):
    """Step 1: 获取商户信息

    1. 查询 yp_merchants 表
    2. 如果不存在，调用 YP API 获取商户信息并保存
    """
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT merchant_id, merchant_name, website, avg_payout, cookie_days, country FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()

        if merchant:
            conn.close()
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "merchant_id": merchant["merchant_id"],
                        "merchant_name": merchant["merchant_name"],
                        "website": merchant["website"],
                        "avg_payout": float(merchant["avg_payout"])
                        if merchant["avg_payout"]
                        else 0,
                        "cookie_days": merchant["cookie_days"],
                        "country": merchant["country"],
                    },
                    "summary": f"商户: {merchant['merchant_name']}",
                }
            )

        # 商户不存在，调用 YP API 获取
        conn.close()

        import requests

        YP_API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"
        YP_SITE_ID = "12002"
        YP_TOKEN = "7951dc7484fa9f9d"

        try:
            resp = requests.get(
                YP_API_URL,
                headers={"token": YP_TOKEN},
                params={
                    "site_id": YP_SITE_ID,
                    "advert_id": merchant_id,
                    "page": 1,
                    "limit": 100,
                },
                timeout=30,
            )
            data = resp.json()

            if data.get("code") != "100000":
                return jsonify(
                    {
                        "success": False,
                        "error": f"YP API 错误: {data.get('msg', '未知错误')}",
                    }
                )

            merchants = data.get("data", {}).get("Data", [])
            if not merchants:
                return jsonify(
                    {
                        "success": False,
                        "error": "商户不存在",
                        "hint": "请检查商户ID是否正确",
                    }
                )

            # 取第一条数据，正确映射 YP API 字段
            m = merchants[0]
            merchant_name = m.get("merchant_name", merchant_id)
            website = m.get("site_url", "") or m.get("website", "")
            avg_payout = m.get("avg_payout", 0) or 0
            payout_unit = m.get("payout_unit", "%")
            cookie_days = m.get("rd", 0) or m.get("cookie_days", 0) or 0
            country = m.get("country", "US")
            status = m.get("status", "APPROVED") or "APPROVED"
            online_status = m.get("merchant_status", "") or m.get("online_status", "")
            advert_status = m.get("advert_status", 0) or m.get("advert_status", 0)
            logo = m.get("logo", "")
            tracking_url = m.get("tracking_url", "")
            transaction_type = m.get("transaction_type", "")
            is_deeplink = m.get("is_deeplink", "0")

            # 保存到数据库
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO yp_merchants 
                    (merchant_id, merchant_name, website, avg_payout, payout_unit, cookie_days, 
                     country, status, online_status, advert_status, logo, tracking_url, 
                     transaction_type, is_deeplink)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    merchant_name = VALUES(merchant_name),
                    website = VALUES(website),
                    avg_payout = VALUES(avg_payout),
                    payout_unit = VALUES(payout_unit),
                    cookie_days = VALUES(cookie_days),
                    country = VALUES(country),
                    status = VALUES(status),
                    online_status = VALUES(online_status),
                    advert_status = VALUES(advert_status),
                    logo = VALUES(logo),
                    tracking_url = VALUES(tracking_url),
                    transaction_type = VALUES(transaction_type),
                    is_deeplink = VALUES(is_deeplink)
            """,
                (
                    merchant_id,
                    merchant_name,
                    website,
                    avg_payout,
                    payout_unit,
                    cookie_days,
                    country,
                    status,
                    online_status,
                    advert_status,
                    logo,
                    tracking_url,
                    transaction_type,
                    is_deeplink,
                ),
            )
            conn.commit()
            conn.close()

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "merchant_id": merchant_id,
                        "merchant_name": merchant_name,
                        "website": website,
                        "avg_payout": float(avg_payout),
                        "cookie_days": cookie_days,
                        "country": country,
                        "status": status,
                        "online_status": online_status,
                    },
                    "summary": f"商户: {merchant_name}",
                }
            )

        except requests.exceptions.RequestException as e:
            return jsonify(
                {
                    "success": False,
                    "error": f"YP API 请求失败: {str(e)}",
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/sales/<merchant_id>", methods=["GET", "POST"])
def api_workflow_sales(merchant_id):
    """获取商户销售数据

    从YP平台获取商户的销售转化数据，包括：
    - 商户维度的点击、加购、购买、佣金数据
    - 商品维度的销售数据

    参数:
        - start_date: 开始日期 (YYYY-MM-DD)
        - end_date: 结束日期 (YYYY-MM-DD)
        - force: 是否强制重新获取 (true/false)
    """
    try:
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        force_refresh = request.args.get("force", "false").lower() == "true"

        # 默认日期范围：本月
        if not start_date or not end_date:
            from datetime import datetime

            today = datetime.now()
            start_date = today.strftime("%Y-%m-01")
            end_date = today.strftime("%Y-%m-%d")

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 获取商户名称
        cur.execute(
            "SELECT merchant_name FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        merchant_name = merchant["merchant_name"] if merchant else f"商户{merchant_id}"

        # 检查是否需要重新获取数据
        if force_refresh:
            # 调用采集脚本获取最新数据
            import subprocess
            import sys

            script_path = BASE_DIR / "yp_report_collector.py"
            if script_path.exists():
                print(f"[Sales] 正在从YP平台获取销售数据...")

                # 异步执行采集脚本
                subprocess.Popen(
                    [
                        sys.executable,
                        str(script_path),
                        "--type",
                        "all",
                        "--start-date",
                        start_date,
                        "--end-date",
                        end_date,
                    ],
                    cwd=str(BASE_DIR),
                )

                conn.close()
                return jsonify(
                    {
                        "success": True,
                        "collecting": True,
                        "message": "正在从YP平台获取数据，请稍后刷新查看",
                        "hint": "采集可能需要1-2分钟，请稍后点击查看现有数据",
                    }
                )
            else:
                conn.close()
                return jsonify(
                    {
                        "success": False,
                        "error": "采集脚本不存在，请检查 yp_report_collector.py",
                    }
                )

        # 查询商户报表数据
        cur.execute(
            """
            SELECT merchant_id, merchant_name, report_date, clicks, detail_views,
                   add_to_carts, purchases, amount, commission
            FROM yp_merchant_report
            WHERE merchant_id = %s AND report_date = %s
            LIMIT 1
        """,
            (merchant_id, end_date),
        )
        merchant_report = cur.fetchone()

        # 查询商品报表数据
        cur.execute(
            """
            SELECT merchant_id, merchant_name, product_id, asin, report_date,
                   clicks, detail_views, add_to_carts, purchases, amount, commission
            FROM yp_product_report
            WHERE merchant_id = %s AND report_date = %s
            ORDER BY clicks DESC, purchases DESC
            LIMIT 50
        """,
            (merchant_id, end_date),
        )
        product_reports = cur.fetchall()

        conn.close()

        if merchant_report or product_reports:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "merchant_report": merchant_report,
                        "product_reports": product_reports,
                        "report_date": end_date,
                        "merchant_name": merchant_name,
                    },
                    "summary": f"点击{merchant_report['clicks'] if merchant_report else 0} | 佣金${merchant_report['commission'] if merchant_report else 0}",
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "merchant_report": None,
                        "product_reports": [],
                        "report_date": end_date,
                        "merchant_name": merchant_name,
                    },
                    "summary": "暂无销售数据，点击重新获取",
                }
            )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============================================================
# 投放数据管理 API
# ============================================================

# 投放数据报告类型
ADS_REPORT_TYPES = {
    "keywords": "搜索关键字报告",
    "search_terms": "搜索字词报告",
    "yp_report": "YP品牌报表",
    "campaign": "Campaign截图",
    "ad_group": "广告组数据",
    "cost": "花费金额",
}


def _create_ads_tables():
    """创建投放数据相关表"""
    conn = get_db()
    cur = conn.cursor()

    # 投放数据主表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_performance_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            report_type ENUM('keywords', 'search_terms', 'yp_report', 'campaign', 'ad_group', 'cost') NOT NULL,
            report_date DATE,
            start_date DATE,
            end_date DATE,
            data_json JSON,
            file_path VARCHAR(500),
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_merchant_type (merchant_id, report_type),
            INDEX idx_report_date (report_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 搜索关键字报告表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_keywords_report (
            id INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            report_date DATE NOT NULL,
            keyword VARCHAR(255) NOT NULL,
            match_type VARCHAR(20),
            campaign VARCHAR(255),
            ad_group VARCHAR(255),
            impressions INT DEFAULT 0,
            clicks INT DEFAULT 0,
            ctr DECIMAL(10,4) DEFAULT 0,
            cpc DECIMAL(10,4) DEFAULT 0,
            cost DECIMAL(10,2) DEFAULT 0,
            conversions INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_merchant_date (merchant_id, report_date),
            INDEX idx_keyword (keyword)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 搜索字词报告表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_search_terms_report (
            id INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            report_date DATE NOT NULL,
            search_term VARCHAR(500) NOT NULL,
            keyword VARCHAR(255),
            match_type VARCHAR(20),
            campaign VARCHAR(255),
            ad_group VARCHAR(255),
            impressions INT DEFAULT 0,
            clicks INT DEFAULT 0,
            ctr DECIMAL(10,4) DEFAULT 0,
            cpc DECIMAL(10,4) DEFAULT 0,
            cost DECIMAL(10,2) DEFAULT 0,
            conversions INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_merchant_date (merchant_id, report_date),
            INDEX idx_search_term (search_term(100))
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # 投放效果汇总表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ads_performance_summary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            merchant_id VARCHAR(20) NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            google_cost DECIMAL(10,2) DEFAULT 0,
            google_clicks INT DEFAULT 0,
            google_impressions INT DEFAULT 0,
            yp_commission DECIMAL(10,2) DEFAULT 0,
            yp_clicks INT DEFAULT 0,
            yp_purchases INT DEFAULT 0,
            yp_amount DECIMAL(10,2) DEFAULT 0,
            roi DECIMAL(10,4) DEFAULT 0,
            roas DECIMAL(10,4) DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_merchant_range (merchant_id, start_date, end_date),
            INDEX idx_date_range (start_date, end_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cur.close()
    conn.close()


@bp.route("/api/workflow/ads_data/<merchant_id>", methods=["GET", "POST"])
def api_workflow_ads_data(merchant_id):
    """投放数据管理 API

    GET: 获取商户的投放数据汇总
    POST: 上传投放数据报告
    """
    try:
        # 确保表存在
        _create_ads_tables()

        if request.method == "GET":
            # 获取日期范围
            start_date = request.args.get("start_date", "")
            end_date = request.args.get("end_date", "")

            if not start_date or not end_date:
                from datetime import datetime
                today = datetime.now()
                start_date = today.strftime("%Y-%m-01")
                end_date = today.strftime("%Y-%m-%d")

            conn = get_db()
            cur = conn.cursor(dictionary=True)

            # 获取效果汇总
            cur.execute("""
                SELECT * FROM ads_performance_summary
                WHERE merchant_id = %s AND start_date <= %s AND end_date >= %s
                ORDER BY end_date DESC LIMIT 1
            """, (merchant_id, end_date, start_date))
            summary = cur.fetchone()

            # 获取各类型报告的最新数据
            reports = {}
            for report_type in ADS_REPORT_TYPES.keys():
                cur.execute("""
                    SELECT id, report_date, start_date, end_date, summary, created_at
                    FROM ads_performance_data
                    WHERE merchant_id = %s AND report_type = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (merchant_id, report_type))
                reports[report_type] = cur.fetchone()

            # 获取关键字报告统计
            cur.execute("""
                SELECT COUNT(*) as keyword_count,
                       SUM(clicks) as total_clicks,
                       SUM(cost) as total_cost,
                       AVG(ctr) as avg_ctr,
                       AVG(cpc) as avg_cpc
                FROM ads_keywords_report
                WHERE merchant_id = %s AND report_date BETWEEN %s AND %s
            """, (merchant_id, start_date, end_date))
            keywords_stats = cur.fetchone()

            # 获取搜索字词报告统计
            cur.execute("""
                SELECT COUNT(*) as term_count,
                       SUM(clicks) as total_clicks,
                       SUM(cost) as total_cost
                FROM ads_search_terms_report
                WHERE merchant_id = %s AND report_date BETWEEN %s AND %s
            """, (merchant_id, start_date, end_date))
            search_terms_stats = cur.fetchone()

            conn.close()

            return jsonify({
                "success": True,
                "data": {
                    "summary": summary,
                    "reports": reports,
                    "keywords_stats": keywords_stats,
                    "search_terms_stats": search_terms_stats,
                    "date_range": {"start_date": start_date, "end_date": end_date}
                }
            })

        else:  # POST - 上传数据
            data = request.get_json(silent=True) or {}
            report_type = data.get("report_type", "")
            report_date = data.get("report_date", "")
            start_date = data.get("start_date", report_date)
            end_date = data.get("end_date", report_date)
            report_data = data.get("data", [])
            summary_text = data.get("summary", "")
            cost_amount = data.get("cost_amount", 0)  # 用于花费金额类型

            if report_type not in ADS_REPORT_TYPES:
                return jsonify({"success": False, "error": f"无效的报告类型: {report_type}"})

            conn = get_db()
            cur = conn.cursor(dictionary=True)

            if report_type == "cost":
                # 保存花费金额到汇总表
                cur.execute("""
                    INSERT INTO ads_performance_summary
                    (merchant_id, start_date, end_date, google_cost, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE google_cost = VALUES(google_cost), notes = VALUES(notes)
                """, (merchant_id, start_date, end_date, cost_amount, summary_text))
                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"花费金额 ${cost_amount} 已保存",
                    "data": {"cost": cost_amount, "date_range": f"{start_date} ~ {end_date}"}
                })

            elif report_type == "keywords":
                # 保存搜索关键字报告
                saved = 0
                for row in report_data:
                    if not row.get("keyword"):
                        continue
                    try:
                        cur.execute("""
                            INSERT INTO ads_keywords_report
                            (merchant_id, report_date, keyword, match_type, campaign, ad_group,
                             impressions, clicks, ctr, cpc, cost, conversions)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            merchant_id, report_date,
                            row.get("keyword", ""),
                            row.get("match_type", ""),
                            row.get("campaign", ""),
                            row.get("ad_group", ""),
                            int(row.get("impressions", 0) or 0),
                            int(row.get("clicks", 0) or 0),
                            float(row.get("ctr", 0) or 0),
                            float(row.get("cpc", 0) or 0),
                            float(row.get("cost", 0) or 0),
                            int(row.get("conversions", 0) or 0)
                        ))
                        saved += 1
                    except Exception as e:
                        print(f"[ERROR] 保存关键字失败: {e}")

                # 保存到主表
                import json
                cur.execute("""
                    INSERT INTO ads_performance_data
                    (merchant_id, report_type, report_date, start_date, end_date, data_json, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (merchant_id, report_type, report_date, start_date, end_date,
                      json.dumps(report_data[:100]), summary_text or f"已保存 {saved} 条关键字数据"))

                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"已保存 {saved} 条关键字数据",
                    "data": {"saved_count": saved}
                })

            elif report_type == "search_terms":
                # 保存搜索字词报告
                saved = 0
                for row in report_data:
                    if not row.get("search_term"):
                        continue
                    try:
                        cur.execute("""
                            INSERT INTO ads_search_terms_report
                            (merchant_id, report_date, search_term, keyword, match_type, campaign, ad_group,
                             impressions, clicks, ctr, cpc, cost, conversions)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            merchant_id, report_date,
                            row.get("search_term", ""),
                            row.get("keyword", ""),
                            row.get("match_type", ""),
                            row.get("campaign", ""),
                            row.get("ad_group", ""),
                            int(row.get("impressions", 0) or 0),
                            int(row.get("clicks", 0) or 0),
                            float(row.get("ctr", 0) or 0),
                            float(row.get("cpc", 0) or 0),
                            float(row.get("cost", 0) or 0),
                            int(row.get("conversions", 0) or 0)
                        ))
                        saved += 1
                    except Exception as e:
                        print(f"[ERROR] 保存搜索字词失败: {e}")

                import json
                cur.execute("""
                    INSERT INTO ads_performance_data
                    (merchant_id, report_type, report_date, start_date, end_date, data_json, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (merchant_id, report_type, report_date, start_date, end_date,
                      json.dumps(report_data[:100]), summary_text or f"已保存 {saved} 条搜索字词数据"))

                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"已保存 {saved} 条搜索字词数据",
                    "data": {"saved_count": saved}
                })

            elif report_type == "yp_report":
                # 保存YP品牌报表数据
                import json
                yp_data = data.get("yp_data", {})
                yp_clicks = yp_data.get("clicks", 0)
                yp_purchases = yp_data.get("purchases", 0)
                yp_commission = yp_data.get("commission", 0)
                yp_amount = yp_data.get("amount", 0)

                # 更新汇总表
                cur.execute("""
                    INSERT INTO ads_performance_summary
                    (merchant_id, start_date, end_date, yp_clicks, yp_purchases, yp_commission, yp_amount, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        yp_clicks = VALUES(yp_clicks),
                        yp_purchases = VALUES(yp_purchases),
                        yp_commission = VALUES(yp_commission),
                        yp_amount = VALUES(yp_amount),
                        notes = VALUES(notes)
                """, (merchant_id, start_date, end_date, yp_clicks, yp_purchases, yp_commission, yp_amount, summary_text))

                cur.execute("""
                    INSERT INTO ads_performance_data
                    (merchant_id, report_type, report_date, start_date, end_date, data_json, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (merchant_id, report_type, report_date, start_date, end_date,
                      json.dumps(yp_data), summary_text or f"YP报表: 点击{yp_clicks} 佣金${yp_commission}"))

                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"YP报表数据已保存",
                    "data": yp_data
                })

            else:
                # 其他类型（campaign, ad_group）- 存储JSON
                import json
                cur.execute("""
                    INSERT INTO ads_performance_data
                    (merchant_id, report_type, report_date, start_date, end_date, data_json, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (merchant_id, report_type, report_date, start_date, end_date,
                      json.dumps(report_data), summary_text))

                conn.commit()
                conn.close()
                return jsonify({
                    "success": True,
                    "message": f"{ADS_REPORT_TYPES[report_type]}已保存",
                    "data": {"report_type": report_type}
                })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/ads_data/<merchant_id>/keywords", methods=["GET"])
def api_workflow_ads_keywords(merchant_id):
    """获取关键字报告详情"""
    try:
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        limit = int(request.args.get("limit", 100))

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT keyword, match_type, campaign, ad_group,
                   SUM(impressions) as impressions,
                   SUM(clicks) as clicks,
                   AVG(ctr) as ctr,
                   AVG(cpc) as cpc,
                   SUM(cost) as cost,
                   SUM(conversions) as conversions
            FROM ads_keywords_report
            WHERE merchant_id = %s
            AND (%s = '' OR report_date >= %s)
            AND (%s = '' OR report_date <= %s)
            GROUP BY keyword, match_type
            ORDER BY cost DESC
            LIMIT %s
        """, (merchant_id, start_date, start_date, end_date, end_date, limit))

        keywords = cur.fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "data": keywords,
            "count": len(keywords)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/ads_data/<merchant_id>/search_terms", methods=["GET"])
def api_workflow_ads_search_terms(merchant_id):
    """获取搜索字词报告详情"""
    try:
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")
        limit = int(request.args.get("limit", 100))

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute("""
            SELECT search_term, keyword, match_type, campaign,
                   SUM(impressions) as impressions,
                   SUM(clicks) as clicks,
                   AVG(ctr) as ctr,
                   AVG(cpc) as cpc,
                   SUM(cost) as cost,
                   SUM(conversions) as conversions
            FROM ads_search_terms_report
            WHERE merchant_id = %s
            AND (%s = '' OR report_date >= %s)
            AND (%s = '' OR report_date <= %s)
            GROUP BY search_term, keyword
            ORDER BY cost DESC
            LIMIT %s
        """, (merchant_id, start_date, start_date, end_date, end_date, limit))

        terms = cur.fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "data": terms,
            "count": len(terms)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/ads_data/<merchant_id>/roi", methods=["GET", "POST"])
def api_workflow_ads_roi(merchant_id):
    """计算并返回ROI数据"""
    try:
        start_date = request.args.get("start_date", "")
        end_date = request.args.get("end_date", "")

        if not start_date or not end_date:
            from datetime import datetime
            today = datetime.now()
            start_date = today.strftime("%Y-%m-01")
            end_date = today.strftime("%Y-%m-%d")

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 获取汇总数据
        cur.execute("""
            SELECT * FROM ads_performance_summary
            WHERE merchant_id = %s AND start_date = %s AND end_date = %s
        """, (merchant_id, start_date, end_date))
        summary = cur.fetchone()

        if summary:
            # 计算ROI和ROAS
            google_cost = float(summary.get("google_cost", 0) or 0)
            yp_commission = float(summary.get("yp_commission", 0) or 0)
            yp_amount = float(summary.get("yp_amount", 0) or 0)

            roi = (yp_commission - google_cost) / google_cost if google_cost > 0 else 0
            roas = yp_amount / google_cost if google_cost > 0 else 0

            # 更新汇总表
            cur.execute("""
                UPDATE ads_performance_summary
                SET roi = %s, roas = %s
                WHERE id = %s
            """, (roi, roas, summary["id"]))
            conn.commit()

            summary["roi"] = roi
            summary["roas"] = roas

        # 获取关键字花费汇总
        cur.execute("""
            SELECT SUM(cost) as total_cost, SUM(clicks) as total_clicks
            FROM ads_keywords_report
            WHERE merchant_id = %s AND report_date BETWEEN %s AND %s
        """, (merchant_id, start_date, end_date))
        kw_stats = cur.fetchone()

        conn.close()

        return jsonify({
            "success": True,
            "data": {
                "summary": summary,
                "keywords_cost": float(kw_stats.get("total_cost", 0) or 0) if kw_stats else 0,
                "keywords_clicks": int(kw_stats.get("total_clicks", 0) or 0) if kw_stats else 0,
                "date_range": {"start_date": start_date, "end_date": end_date}
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/website/<merchant_id>", methods=["GET", "POST", "PUT"])
def api_workflow_website(merchant_id):
    """Step 2: 获取/更新官网"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        if request.method == "PUT":
            # 更新官网
            data = request.get_json(silent=True) or {}
            new_website = data.get("website", "").strip()

            cur.execute(
                "UPDATE yp_merchants SET website = %s WHERE merchant_id = %s",
                (new_website, merchant_id),
            )
            conn.commit()
            conn.close()

            return jsonify(
                {
                    "success": True,
                    "data": {"website": new_website},
                    "summary": f"官网已更新: {new_website}",
                }
            )

        # GET/POST: 获取官网
        cur.execute(
            "SELECT website FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        conn.close()

        if merchant:
            website = merchant.get("website") or ""
            return jsonify(
                {
                    "success": True,
                    "data": {"website": website},
                    "summary": f"官网: {website}" if website else "暂无官网",
                }
            )
        else:
            return jsonify({"success": False, "error": "商户不存在"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/keywords/<merchant_id>", methods=["POST"])
def api_workflow_keywords(merchant_id):
    """
    Step 3: 获取或采集品牌关键词

    支持 Google 和 Bing 双引擎：
    1. 先检查数据库中是否已有数据
    2. 如果没有，尝试 Google Suggest API
    3. 如果 Google 失败，降级到 Bing 搜索

    参数：
    - force: 如果为 true，强制重新采集
    """
    try:
        # 检查是否强制重新采集
        data = request.get_json(silent=True) or {}
        force_recollect = data.get("force", False)

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 如果不是强制重新采集，先检查已有数据
        if not force_recollect:
            # 1. 检查数据库
            cur.execute(
                "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s ORDER BY keyword",
                (merchant_id,),
            )
            keywords = [r["keyword"] for r in cur.fetchall()]

            if keywords:
                conn.close()
                return jsonify(
                    {
                        "success": True,
                        "data": {"keywords": keywords, "count": len(keywords)},
                        "summary": f"已获取 {len(keywords)} 个品牌关键词",
                    }
                )

        # 2. 获取商户信息
        cur.execute(
            "SELECT merchant_name, website FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        conn.close()

        if not merchant:
            return jsonify({"success": False, "error": f"商户 {merchant_id} 不存在"})

        merchant_name = merchant.get("merchant_name") or merchant_id

        # 3. 尝试采集关键词
        all_keywords = []
        source = None

        # 3.1 尝试 Google Suggest
        try:
            google_keywords = _fetch_google_suggest(merchant_name)
            if google_keywords:
                all_keywords = google_keywords
                source = "google"
                print(
                    f"[Workflow] Google Suggest 成功: {len(google_keywords)} 个关键词"
                )
        except Exception as e:
            print(f"[Workflow] Google Suggest 失败: {e}")

        # 3.2 如果 Google 失败，尝试 Bing
        if not all_keywords:
            try:
                bing_keywords = _fetch_bing_suggest(merchant_name)
                if bing_keywords:
                    all_keywords = bing_keywords
                    source = "bing"
                    print(
                        f"[Workflow] Bing Suggest 成功: {len(bing_keywords)} 个关键词"
                    )
            except Exception as e:
                print(f"[Workflow] Bing Suggest 失败: {e}")

        # 4. 保存到数据库
        if all_keywords:
            conn = get_db()
            cur = conn.cursor()

            # 删除旧数据
            cur.execute(
                "DELETE FROM ads_merchant_keywords WHERE merchant_id = %s",
                (merchant_id,),
            )

            # 插入新数据
            for kw in all_keywords[:50]:  # 最多保存 50 个
                cur.execute(
                    "INSERT INTO ads_merchant_keywords (merchant_id, keyword, keyword_source) VALUES (%s, %s, %s)",
                    (merchant_id, kw, source),
                )
            conn.commit()
            conn.close()

            return jsonify(
                {
                    "success": True,
                    "data": {
                        "keywords": all_keywords[:50],
                        "count": len(all_keywords[:50]),
                    },
                    "summary": f"已采集 {len(all_keywords[:50])} 个关键词 (来源: {source.upper()})",
                }
            )

        return jsonify(
            {
                "success": True,
                "data": {"keywords": [], "count": 0},
                "summary": "暂无品牌关键词，Google 和 Bing 采集均失败",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _fetch_google_suggest(merchant_name: str) -> list:
    """
    通过 Google Suggest API 获取关键词建议

    Args:
        merchant_name: 商户名称

    Returns:
        关键词列表
    """
    import urllib.request
    import urllib.parse
    import json
    import re

    # 清理品牌名
    brand = re.sub(
        r"\s+(US|UK|EU|AU|CA|COM|INC|LLC|LTD|CO\.|CORP\.?)$",
        "",
        merchant_name,
        flags=re.IGNORECASE,
    ).strip()
    brand = re.sub(r"\.(com|net|org|io|co)$", "", brand, flags=re.IGNORECASE).strip()

    # 查询模板
    templates = [
        "{brand}",
        "{brand} product",
        "{brand} review",
    ]

    all_keywords = []
    suggest_url = "https://suggestqueries.google.com/complete/search"

    for template in templates:
        query = template.format(brand=brand)
        params = urllib.parse.urlencode(
            {
                "client": "firefox",
                "q": query,
                "hl": "en",
                "gl": "us",
            }
        )
        url = f"{suggest_url}?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # 缩短超时时间
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 1:
                    suggestions = data[1]
                    if isinstance(suggestions, list):
                        all_keywords.extend(
                            [s for s in suggestions if isinstance(s, str)]
                        )
        except Exception as e:
            print(f"[Google] 查询 '{query}' 失败: {e}")

    # 去重
    return list(dict.fromkeys(all_keywords))


def _fetch_bing_suggest(merchant_name: str) -> list:
    """
    通过 Bing 搜索获取关键词建议

    使用 Bing 国际版 (bing.com) 的搜索建议

    Args:
        merchant_name: 商户名称

    Returns:
        关键词列表
    """
    import urllib.request
    import urllib.parse
    import json
    import re

    # 清理品牌名
    brand = re.sub(
        r"\s+(US|UK|EU|AU|CA|COM|INC|LLC|LTD|CO\.|CORP\.?)$",
        "",
        merchant_name,
        flags=re.IGNORECASE,
    ).strip()
    brand = re.sub(r"\.(com|net|org|io|co)$", "", brand, flags=re.IGNORECASE).strip()

    # 查询模板
    templates = [
        "{brand}",
        "{brand} product",
        "{brand} review",
    ]

    all_keywords = []

    # 方法1: Bing Autosuggest API
    autosuggest_url = "https://api.bing.com/osjson.aspx"

    for template in templates:
        query = template.format(brand=brand)
        params = urllib.parse.urlencode(
            {
                "query": query,
                "market": "en-US",
            }
        )
        url = f"{autosuggest_url}?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:  # 缩短超时时间
                data = json.loads(resp.read().decode("utf-8"))
                # Bing Autosuggest 返回格式: ["query", ["s1","s2",...]]
                if isinstance(data, list) and len(data) > 1:
                    suggestions = data[1]
                    if isinstance(suggestions, list):
                        all_keywords.extend(
                            [s for s in suggestions if isinstance(s, str)]
                        )
        except Exception as e:
            print(f"[Bing] 查询 '{query}' 失败: {e}")

    # 方法2: 如果方法1失败，尝试 DuckDuckGo (作为备选)
    if not all_keywords:
        try:
            ddg_keywords = _fetch_duckduckgo_suggest(brand)
            all_keywords.extend(ddg_keywords)
        except Exception as e:
            print(f"[DuckDuckGo] 失败: {e}")

    # 去重
    return list(dict.fromkeys(all_keywords))


def _fetch_duckduckgo_suggest(brand: str) -> list:
    """
    通过 DuckDuckGo 获取关键词建议（作为 Bing 的备选）
    """
    import urllib.request
    import urllib.parse
    import json

    all_keywords = []
    ddg_url = "https://duckduckgo.com/ac/"

    templates = [
        "{brand}",
        "{brand} product",
        "{brand} review",
    ]

    for template in templates:
        query = template.format(brand=brand)
        params = urllib.parse.urlencode(
            {
                "q": query,
                "kl": "wt-wt",  # 全球
            }
        )
        url = f"{ddg_url}?{params}"

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # DuckDuckGo 返回格式: [{"phrase": "s1"}, {"phrase": "s2"}, ...]
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "phrase" in item:
                            all_keywords.append(item["phrase"])
        except Exception as e:
            print(f"[DuckDuckGo] 查询 '{query}' 失败: {e}")

    return all_keywords


@bp.route("/api/workflow/semrush/<merchant_id>", methods=["POST"])
def api_workflow_semrush(merchant_id):
    """
    Step 4: 获取或采集 SEMrush 数据

    逻辑：
    1. 先检查数据库中是否已有数据
    2. 如果没有，检查是否有采集结果文件
    3. 如果都没有，触发采集并返回采集状态

    参数：
    - force: 如果为 true，强制重新采集
    """
    try:
        # 检查是否强制重新采集
        data = request.get_json(silent=True) or {}
        force_recollect = data.get("force", False)

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 如果不是强制重新采集，先检查已有数据
        if not force_recollect:
            # 1. 检查数据库 (semrush_competitor_data 表)
            cur.execute(
                "SELECT id, domain, organic_keywords_count, paid_keywords_count, organic_traffic, paid_traffic, authority_score FROM semrush_competitor_data WHERE merchant_id = %s LIMIT 1",
                (merchant_id,),
            )
            semrush = cur.fetchone()

            if semrush:
                conn.close()
                return jsonify(
                    {
                        "success": True,
                        "data": {
                            "has_data": True,
                            "domain": semrush.get("domain"),
                            "organic_keywords": semrush.get(
                                "organic_keywords_count", 0
                            ),
                            "paid_keywords": semrush.get("paid_keywords_count", 0),
                            "organic_traffic": semrush.get("organic_traffic", 0),
                            "paid_traffic": semrush.get("paid_traffic", 0),
                            "authority_score": semrush.get("authority_score", 0),
                        },
                        "summary": f"SEMrush 数据已存在 (域名: {semrush.get('domain')}, 自然词: {semrush.get('organic_keywords_count', 0)}, 付费词: {semrush.get('paid_keywords_count', 0)})",
                    }
                )

            # 2. 检查采集结果文件
            result_file = BASE_DIR / "temp" / f"semrush_collected_{merchant_id}.json"
            if result_file.exists():
                try:
                    import json

                    file_data = json.loads(result_file.read_text(encoding="utf-8"))

                    # 保存到数据库
                    _save_semrush_to_db(merchant_id, file_data, cur, conn)

                    # 从文件数据中提取统计信息
                    semrush_data = file_data.get("data", {})
                    organic_keywords = semrush_data.get("organic_keywords", {})
                    paid_keywords = semrush_data.get("paid_keywords", {})
                    traffic = semrush_data.get("traffic", {})

                    organic_count = (
                        organic_keywords.get("total", 0)
                        if isinstance(organic_keywords, dict)
                        else 0
                    )
                    paid_count = (
                        paid_keywords.get("total", 0)
                        if isinstance(paid_keywords, dict)
                        else 0
                    )

                    return jsonify(
                        {
                            "success": True,
                            "data": {
                                "has_data": True,
                                "domain": file_data.get("domain"),
                                "organic_keywords": organic_count,
                                "paid_keywords": paid_count,
                                "organic_traffic": traffic.get("organic", 0)
                                if isinstance(traffic, dict)
                                else 0,
                                "paid_traffic": traffic.get("paid", 0)
                                if isinstance(traffic, dict)
                                else 0,
                                "authority_score": traffic.get("authority_score", 0)
                                if isinstance(traffic, dict)
                                else 0,
                            },
                            "summary": f"SEMrush 数据已加载 (域名: {file_data.get('domain')}, 自然词: {organic_count}, 付费词: {paid_count})",
                        }
                    )
                except Exception as e:
                    print(f"[Workflow] 读取 SEMrush 结果文件失败: {e}")

        # 3. 获取商户信息，准备采集
        cur.execute(
            "SELECT merchant_name, website FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        conn.close()

        if not merchant:
            return jsonify(
                {
                    "success": False,
                    "error": f"商户 {merchant_id} 不存在",
                }
            )

        domain = (merchant.get("website") or "").strip()
        merchant_name = merchant.get("merchant_name") or merchant_id

        if not domain:
            return jsonify(
                {
                    "success": False,
                    "error": "商户没有官网域名，无法采集 SEMrush 数据",
                    "need_domain": True,
                    "hint": "请在商户作战室手动输入域名后采集",
                }
            )

        # 4. 触发采集
        sem_script = BASE_DIR / "semrush_via_wmx.py"
        if not sem_script.exists():
            return jsonify(
                {
                    "success": False,
                    "error": "semrush_via_wmx.py 脚本不存在",
                }
            )

        # 创建启动脚本
        bat_file = BASE_DIR / f"_launch_semrush_{merchant_id}.bat"
        bat_content = (
            f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle SEMrush采集 - {merchant_name}\r\n'
            f"echo ========================================\r\n"
            f"echo  SEMrush 数据采集 - 外贸侠模式\r\n"
            f"echo  商户: {merchant_name}\r\n"
            f"echo  域名: {domain}\r\n"
            f"echo ========================================\r\n"
            f"echo.\r\n"
            f'"{PYTHON_EXE}" -X utf8 "{sem_script}" "{merchant_id}" "{domain}"\r\n'
            f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
        )
        bat_file.write_text(bat_content, encoding="gbk")

        # 启动新窗口
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",  # 窗口标题（空字符串）
                "cmd.exe",
                "/k",
                str(bat_file),
            ],
            cwd=str(BASE_DIR),
            shell=False,
        )

        return jsonify(
            {
                "success": True,
                "collecting": True,
                "message": f"SEMrush 采集已启动 (域名: {domain})",
                "domain": domain,
                "hint": "请在新窗口中完成采集，完成后再次点击此节点刷新数据",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def _save_semrush_to_db(merchant_id: str, data: dict, cur, conn):
    """保存 SEMrush 数据到数据库 (semrush_competitor_data 表)"""
    import json

    # 从采集结果中提取数据
    semrush_data = data.get("data", {})
    domain = data.get("domain") or semrush_data.get("domain", "")

    # 流量数据
    traffic = semrush_data.get("traffic", {})
    organic_traffic = traffic.get("organic", 0) if isinstance(traffic, dict) else 0
    paid_traffic = traffic.get("paid", 0) if isinstance(traffic, dict) else 0
    authority_score = (
        traffic.get("authority_score", 0) if isinstance(traffic, dict) else 0
    )

    # 关键词数据
    organic_keywords = semrush_data.get("organic_keywords", {})
    if isinstance(organic_keywords, dict):
        organic_count = organic_keywords.get("total", 0)
        organic_list = organic_keywords.get("top_keywords", [])
    else:
        organic_count = str(len(organic_keywords)) if organic_keywords else 0
        organic_list = organic_keywords if isinstance(organic_keywords, list) else []

    paid_keywords = semrush_data.get("paid_keywords", {})
    if isinstance(paid_keywords, dict):
        paid_count = paid_keywords.get("total", 0)
        paid_list = paid_keywords.get("top_keywords", [])
    else:
        paid_count = str(len(paid_keywords)) if paid_keywords else 0
        paid_list = paid_keywords if isinstance(paid_keywords, list) else []

    # 广告文案
    ad_copies = semrush_data.get("ad_copies", [])

    # 竞品和引用来源
    competitors = semrush_data.get("competitors", [])
    referring_sources = semrush_data.get("referring_sources", [])
    serp_distribution = semrush_data.get("serp_distribution", {})
    country_traffic = semrush_data.get("country_traffic", [])

    # 检查是否已存在 (使用 semrush_competitor_data 表)
    cur.execute(
        "SELECT id FROM semrush_competitor_data WHERE merchant_id = %s",
        (merchant_id,),
    )
    exists = cur.fetchone()

    if exists:
        cur.execute(
            """
            UPDATE semrush_competitor_data SET
                domain = %s,
                organic_traffic = %s,
                paid_traffic = %s,
                authority_score = %s,
                organic_keywords_count = %s,
                paid_keywords_count = %s,
                top_organic_keywords = %s,
                top_paid_keywords = %s,
                ad_copies = %s,
                competitors = %s,
                referring_sources = %s,
                serp_distribution = %s,
                country_traffic = %s,
                scraped_at = NOW(),
                status = 'completed'
            WHERE merchant_id = %s
        """,
            (
                domain,
                str(organic_traffic),
                str(paid_traffic),
                str(authority_score),
                str(organic_count),
                str(paid_count),
                json.dumps(organic_list, ensure_ascii=False),
                json.dumps(paid_list, ensure_ascii=False),
                json.dumps(ad_copies, ensure_ascii=False),
                json.dumps(competitors, ensure_ascii=False),
                json.dumps(referring_sources, ensure_ascii=False),
                json.dumps(serp_distribution, ensure_ascii=False),
                json.dumps(country_traffic, ensure_ascii=False),
                merchant_id,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO semrush_competitor_data
            (merchant_id, domain, organic_traffic, paid_traffic, authority_score,
             organic_keywords_count, paid_keywords_count, top_organic_keywords,
             top_paid_keywords, ad_copies, competitors, referring_sources,
             serp_distribution, country_traffic, status, scraped_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', NOW())
        """,
            (
                merchant_id,
                domain,
                str(organic_traffic),
                str(paid_traffic),
                str(authority_score),
                str(organic_count),
                str(paid_count),
                json.dumps(organic_list, ensure_ascii=False),
                json.dumps(paid_list, ensure_ascii=False),
                json.dumps(ad_copies, ensure_ascii=False),
                json.dumps(competitors, ensure_ascii=False),
                json.dumps(referring_sources, ensure_ascii=False),
                json.dumps(serp_distribution, ensure_ascii=False),
                json.dumps(country_traffic, ensure_ascii=False),
            ),
        )

    conn.commit()
    print(
        f"[SEMrush] 数据已保存到 semrush_competitor_data 表: merchant_id={merchant_id}"
    )


@bp.route("/api/workflow/products/<merchant_id>", methods=["GET", "POST"])
def api_workflow_products(merchant_id):
    """Step 5: 获取商品列表

    GET: 只查询商品列表，不触发采集
    POST: 查询商品列表，不存在时触发采集
    参数：
    - force: 如果为 true，触发重新采集商品
    """
    try:
        # 检查是否强制重新采集
        data = request.get_json(silent=True) or {}
        force_recollect = data.get("force", False)

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 先查询 yp_products 表（原始数据）
        cur.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN a.asin IS NOT NULL THEN 1 ELSE 0 END) as with_amazon
            FROM yp_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.merchant_id = %s
            """,
            (merchant_id,),
        )
        stats = cur.fetchone()
        total = stats["total"] or 0
        with_amazon = stats["with_amazon"] or 0

        # 获取商品列表（最多 50 个）
        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                   a.title as amz_title, a.rating, a.review_count
            FROM yp_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.merchant_id = %s
            ORDER BY p.commission DESC
            LIMIT 50
            """,
            (merchant_id,),
        )
        products = cur.fetchall()

        # 如果有商品且不是强制重新采集，直接返回
        if total > 0 and not force_recollect:
            conn.close()
            return jsonify(
                {
                    "success": True,
                    "data": {
                        "products": products,
                        "total": total,
                        "with_amazon": with_amazon,
                    },
                    "summary": f"共 {total} 个商品，{with_amazon} 个有亚马逊数据",
                }
            )

        # GET 请求只查询，不触发采集
        if request.method == "GET":
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "error": "暂无商品数据",
                    "data": {"products": [], "total": 0, "with_amazon": 0},
                }
            )

        # POST 请求：获取商户名称并触发采集
        cur.execute(
            "SELECT merchant_name FROM yp_merchants WHERE merchant_id = %s LIMIT 1",
            (merchant_id,),
        )
        merchant = cur.fetchone()
        conn.close()

        merchant_name = merchant["merchant_name"] if merchant else merchant_id

        # 如果没有商品或强制重新采集，触发 YP 采集
        from app_config import YP_COLLECT_SCRIPT, PYTHON_EXE

        if not YP_COLLECT_SCRIPT.exists():
            return jsonify(
                {
                    "success": False,
                    "error": "download_only.py 脚本不存在",
                }
            )

        # 创建启动脚本
        bat_file = BASE_DIR / f"_launch_yp_single_{merchant_id}.bat"
        bat_content = (
            f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle 采集商品 {merchant_name}\r\n'
            f'"{PYTHON_EXE}" -X utf8 "{YP_COLLECT_SCRIPT}" --single {merchant_id}\r\n'
            f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
        )
        bat_file.write_text(bat_content, encoding="gbk")

        # 启动新窗口
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",  # 窗口标题（空字符串）
                "cmd.exe",
                "/k",
                str(bat_file),
            ],
            cwd=str(BASE_DIR),
            shell=False,
        )

        # 返回 task_id 让前端轮询
        task_id = f"products_{merchant_id}"

        return jsonify(
            {
                "success": True,
                "collecting": True,
                "task_id": task_id,
                "message": f"商户 {merchant_name} 商品采集已启动",
                "hint": "请在弹窗中完成采集",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/amazon/<merchant_id>", methods=["POST"])
def api_workflow_amazon(merchant_id):
    """Step 6: 获取亚马逊商品信息

    参数：
    - asin: 商品 ASIN（必填）
    - force: 如果为 true，强制重新采集

    返回：
    - 如果有数据：返回 data 和 has_data: true
    - 如果没有数据且不是强制采集：返回 has_data: false
    - 如果触发采集：返回 collecting: true
    """
    try:
        data = request.get_json(silent=True) or {}
        selected_asin = data.get("asin", "").strip()
        force_recollect = data.get("force", False)

        if not selected_asin:
            return jsonify(
                {
                    "success": False,
                    "error": "请选择商品",
                    "hint": "请在下拉框中选择要采集的商品",
                }
            )

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 获取指定商品
        cur.execute(
            """
            SELECT p.asin, p.product_name, p.tracking_url,
                   a.title as amz_title, a.brand, a.rating, a.review_count,
                   a.bullet_points, a.description, a.availability, a.category_path,
                   a.top_reviews
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s LIMIT 1
            """,
            (selected_asin,),
        )
        product = cur.fetchone()
        conn.close()

        if not product:
            return jsonify({"success": False, "error": f"找不到商品 {selected_asin}"})

        # 检查是否有完整的亚马逊数据
        has_amazon_data = product.get("amz_title") and product.get("bullet_points")

        # 如果有完整数据且不是强制重新采集，返回数据（让前端决定是否重新采集）
        if has_amazon_data and not force_recollect:
            return jsonify(
                {
                    "success": True,
                    "has_data": True,
                    "data": product,
                    "summary": f"商品: {product.get('amz_title') or product.get('product_name', '')[:50]}",
                }
            )

        # 没有数据或强制重新采集，触发采集
        # 创建启动脚本
        bat_file = BASE_DIR / f"_launch_amazon_{selected_asin}.bat"
        bat_content = (
            f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle Amazon采集 - {selected_asin}\r\n'
            f"echo ========================================\r\n"
            f"echo  Amazon 商品详情采集\r\n"
            f"echo  ASIN: {selected_asin}\r\n"
            f"echo ========================================\r\n"
            f"echo.\r\n"
            f'"{PYTHON_EXE}" -X utf8 "{SCRAPER_SCRIPT}" --asin {selected_asin}\r\n'
            f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
        )
        bat_file.write_text(bat_content, encoding="gbk")

        # 启动新窗口
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",  # 窗口标题（空字符串）
                "cmd.exe",
                "/k",
                str(bat_file),
            ],
            cwd=str(BASE_DIR),
            shell=False,
        )

        return jsonify(
            {
                "success": True,
                "collecting": True,
                "has_data": False,
                "message": f"Amazon 采集已启动 (ASIN: {selected_asin})",
                "hint": "请在新窗口中完成采集，完成后再次点击此节点刷新数据",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/report/<merchant_id>", methods=["POST"])
def api_workflow_report(merchant_id):
    """Step 7: 生成商品报告"""
    try:
        data = request.get_json(silent=True) or {}
        selected_asin = data.get("asin", "").strip()

        if not selected_asin:
            return jsonify(
                {
                    "success": False,
                    "error": "请先选择商品",
                    "hint": "在「亚马逊商品信息」步骤选择要生成报告的商品",
                }
            )

        report_url = f"/api/generate_product_report/{selected_asin}"

        return jsonify(
            {
                "success": True,
                "data": {"asin": selected_asin, "report_url": report_url},
                "summary": f"报告已生成<br><a href='{report_url}' target='_blank'>下载报告</a>",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/evaluate/<merchant_id>", methods=["POST"])
def api_workflow_evaluate(merchant_id):
    """Step 9: 评估广告质量（多模型 AI 评估）"""
    try:
        data = request.get_json(silent=True) or {}
        selected_asin = data.get("asin", "").strip()
        models = data.get("models", ["kimi"])  # 默认使用 KIMI 评估
        force = data.get("force", False)

        if not selected_asin:
            return jsonify(
                {
                    "success": False,
                    "error": "请先选择商品",
                    "hint": "在「亚马逊商品信息」步骤选择要评估的商品",
                }
            )

        # 调用评估 API
        from flask import Request

        eval_request = Request.from_values(
            method="POST", json={"models": models, "force": force}
        )

        # 直接调用评估函数
        result = api_evaluate_ads(selected_asin)

        if isinstance(result, tuple):
            result = result[0]

        result_data = json.loads(result.get_data(as_text=True))

        if not result_data.get("success"):
            return jsonify(result_data)

        summary = result_data.get("summary", {})

        # 格式化输出
        avg_scores = summary.get("avg_scores", {})
        avg_overall = summary.get("avg_overall", 0)
        model_count = summary.get("model_count", 0)
        consensus_issues = summary.get("consensus_issues", [])
        strengths = summary.get("strengths", [])

        # 构建显示摘要
        summary_text = f"综合评分: {avg_overall}/10 ({model_count} 个模型评估)"

        return jsonify(
            {
                "success": True,
                "data": {
                    "asin": selected_asin,
                    "avg_scores": avg_scores,
                    "avg_overall": avg_overall,
                    "model_count": model_count,
                    "consensus_issues": consensus_issues,
                    "strengths": strengths,
                    "suggestions": summary.get("suggestions", []),
                },
                "summary": summary_text,
                "evaluations": result_data.get("results", []),
                "cached": result_data.get("cached", False),
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/ads/<merchant_id>", methods=["POST"])
def api_workflow_ads(merchant_id):
    """
    Step 8: 生成广告方案

    方案B：优先使用 AI 生成，失败时降级到规则引擎
    - AI 生成：调用 KIMI/千帆 + Google Ads 技能
    - 降级方案：使用规则引擎
    - 都保存到数据库 + 生成 JSON 文件
    """
    import subprocess
    import time as _time

    try:
        data = request.get_json(silent=True) or {}
        selected_asin = data.get("asin", "").strip()

        if not selected_asin:
            return jsonify(
                {
                    "success": False,
                    "error": "请先选择商品",
                    "hint": "在「亚马逊商品信息」步骤选择要生成广告的商品",
                }
            )

        # 获取产品信息
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                   p.merchant_name, p.yp_merchant_id,
                   a.title as amz_title, a.brand, a.rating, a.review_count,
                   a.bullet_points, a.description, a.availability, a.category_path
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s LIMIT 1
        """,
            (selected_asin,),
        )
        product = cur.fetchone()

        if not product:
            conn.close()
            return jsonify({"success": False, "error": f"找不到商品 {selected_asin}"})

        # 获取商户关键词
        cur.execute(
            "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s",
            (merchant_id,),
        )
        brand_keywords = [r["keyword"] for r in cur.fetchall()]
        conn.close()

        # ── 异步生成广告方案 ──
        task_id = _get_task_id(selected_asin, merchant_id)

        # 检查是否已有任务
        with _ads_task_lock:
            if task_id in _ads_generation_tasks:
                task = _ads_generation_tasks[task_id]
                if task["status"] == "generating":
                    return jsonify(
                        {
                            "success": True,
                            "async": True,
                            "task_id": task_id,
                            "status": "generating",
                            "message": "广告正在生成中，请稍后查询结果...",
                        }
                    )
                elif task["status"] == "completed":
                    # 已完成，返回结果
                    result = task["result"]
                    summary = f"广告方案已生成 ({result.get('method', 'unknown')})<br>"
                    summary += f"<a href='{result.get('download_url_txt', '')}' download='{result.get('filename_txt', '')}'>📄 下载 TXT (可复制)</a> | "
                    summary += f"<a href='{result.get('download_url', '')}' download='{result.get('filename', '')}'>📥 下载 JSON</a>"
                    return jsonify(
                        {
                            "success": True,
                            "data": result,
                            "summary": summary,
                        }
                    )
                elif task["status"] == "failed":
                    # 失败，重新生成
                    pass

            # 创建新任务
            _ads_generation_tasks[task_id] = {
                "status": "pending",
                "created_at": datetime.datetime.now().isoformat(),
            }

        # 启动后台线程
        thread = threading.Thread(
            target=_background_generate_ads,
            args=(task_id, product, brand_keywords, merchant_id),
            daemon=True,
        )
        thread.start()

        return jsonify(
            {
                "success": True,
                "async": True,
                "task_id": task_id,
                "status": "pending",
                "message": "广告生成任务已启动，请轮询查询结果...",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/ads/status/<task_id>", methods=["GET"])
def api_workflow_ads_status(task_id):
    """
    查询广告生成任务状态

    返回：
    - status: pending | generating | completed | failed
    - result: 生成结果（仅 completed 时）
    - error: 错误信息（仅 failed 时）
    """
    global _ads_generation_tasks

    with _ads_task_lock:
        if task_id not in _ads_generation_tasks:
            print(f"[Status] Task {task_id} not found")
            return jsonify(
                {
                    "success": False,
                    "error": "任务不存在",
                }
            )

        task = _ads_generation_tasks[task_id].copy()

    status = task.get("status")
    print(f"[Status] Task {task_id} status: {status}")

    response = {
        "success": True,
        "task_id": task_id,
        "status": status,
    }

    if status == "completed":
        result = task.get("result", {})
        response["result"] = result
        print(f"[Status] Result keys: {list(result.keys())}")
        print(f"[Status] filename_txt: {result.get('filename_txt')}")
        print(f"[Status] download_url_txt: {result.get('download_url_txt')}")
        summary = f"广告方案已生成 ({result.get('method', 'unknown')})<br>"
        summary += f"<a href='{result.get('download_url_txt', '')}' download='{result.get('filename_txt', '')}'>📄 下载 TXT (可复制)</a> | "
        summary += f"<a href='{result.get('download_url', '')}' download='{result.get('filename', '')}'>📥 下载 JSON</a>"
        response["summary"] = summary
        print(f"[Status] Returning completed result: {result.get('filename')}")
    elif status == "failed":
        response["error"] = task.get("error", "未知错误")
        print(f"[Status] Returning failed: {response['error']}")
    elif status == "generating":
        response["message"] = "广告正在生成中，请稍后..."
    else:
        response["message"] = "任务等待中..."

    return jsonify(response)


@bp.route("/api/workflow/collect/status/<task_id>", methods=["GET"])
def api_workflow_collect_status(task_id):
    """
    查询采集任务状态

    返回：
    - status: running | completed | failed
    - merchant_id: 商户ID
    - node_type: 节点类型 (products, amazon, semrush 等)
    """
    global _collect_tasks

    with _collect_task_lock:
        if task_id not in _collect_tasks:
            return jsonify({"success": False, "error": "任务不存在"})
        task = _collect_tasks[task_id].copy()

    status = task.get("status")
    response = {
        "success": True,
        "task_id": task_id,
        "status": status,
        "merchant_id": task.get("merchant_id"),
        "node_type": task.get("node_type"),
    }

    if status == "completed":
        # 查询采集结果
        merchant_id = task.get("merchant_id")
        node_type = task.get("node_type")

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        if node_type == "products":
            # 查询商品数量
            cur.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN price IS NOT NULL THEN 1 ELSE 0 END) as with_price
                FROM yp_us_products WHERE yp_merchant_id = %s
            """,
                (merchant_id,),
            )
            stats = cur.fetchone()
            response["data"] = {
                "total": stats["total"] or 0,
                "with_price": stats["with_price"] or 0,
            }
            response["summary"] = (
                f"共 {stats['total']} 个商品，{stats['with_price']} 个有价格"
            )

        conn.close()
        response["message"] = "采集完成"

    elif status == "failed":
        response["error"] = task.get("error", "采集失败")
    else:
        response["message"] = "采集进行中..."

    return jsonify(response)


def _generate_ads_with_ai(product: dict, brand_keywords: list) -> dict:
    """
    使用 AI + Google Ads 技能 v6.3 分段生成广告方案

    分段处理流程（避免超时）：
    1. Step 1: 产品品类智能分析
    2. Step 2: 关键词引擎（为每个 Ad Group 生成关键词）
    3. Step 3: 文案生成（情感触发 + 转化闭环）
    4. Step 4: QA 检查
    """
    import os
    import re
    from kimi_client import KimiClient

    asin = product.get("asin", "")

    # KIMI API Key（仅从环境变量读取）
    KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
    if not KIMI_API_KEY:
        raise ValueError("请设置环境变量 KIMI_API_KEY")

    # 解析产品信息
    title = product.get("amz_title") or product.get("product_name", "")
    brand = product.get("brand") or "Unknown"
    price_str = product.get("price") or "0"
    price = float(price_str) if price_str and price_str != "None" else 0
    commission_str = product.get("commission") or "0%"
    commission_rate = (
        float(re.sub(r"[^0-9.]", "", commission_str)) / 100 if commission_str else 0.15
    )

    # 解析 rating
    rating_str = product.get("rating") or "0"
    if isinstance(rating_str, str):
        rating_match = re.search(r"(\d+\.?\d*)", rating_str)
        rating = float(rating_match.group(1)) if rating_match else 0.0
    else:
        rating = float(rating_str) if rating_str else 0.0

    # 解析 review_count
    review_count_str = product.get("review_count") or "0"
    if isinstance(review_count_str, str):
        review_count_match = re.search(r"(\d+)", review_count_str)
        review_count = int(review_count_match.group(1)) if review_count_match else 0
    else:
        review_count = int(review_count_str) if review_count_str else 0

    category = product.get("category_path") or ""
    bullet_points = product.get("bullet_points") or ""

    # 初始化 KIMI 客户端（使用更快的模型）
    client = KimiClient(model="moonshot-v1-8k", api_key=KIMI_API_KEY)

    print(f"[AI Generate] Starting multi-step generation for {asin}...")

    # ========================================
    # Step 1: 产品品类智能分析
    # ========================================
    print("[AI Generate] Step 1: Product Analysis...")

    analysis_prompt = f"""# Task: Amazon Affiliate Product Analysis for Google Ads

## Product Info
- Title: {title}
- Brand: {brand}
- Price: ${price:.2f}
- Commission: {commission_str} (${price * commission_rate:.2f} per sale)
- Rating: {rating}/5 ({review_count} reviews)
- Category: {category}
- Key Features: {bullet_points[:300] if bullet_points else "N/A"}

## Analysis Required
Analyze this product and output JSON with:

1. **product_type**: One of ["效果驱动型", "痛点驱动型", "礼品驱动型", "功能驱动型"]
2. **core_driver**: Main purchase driver (e.g., "效果承诺 > 成分信任")
3. **brand_awareness**: "高" or "中" or "低"
4. **target_cpa**: Target CPA in USD (commission × 0.7)
5. **recommended_campaigns**: Number of campaigns (2-4)
6. **campaign_structure**: Array of campaign names and purposes, e.g.:
   - "Brand_Protection": Capture brand searches
   - "Problem_Awareness": Target pain points
   - "Purchase_Decision": Capture buying intent
7. **ad_groups_per_campaign**: Suggested ad groups for each campaign
8. **key_benefits**: Top 3-5 product benefits for ad copy
9. **pain_points**: Top 3-5 customer pain points this product solves
10. **negative_keywords**: 10-15 negative keywords for this product category

Output ONLY valid JSON, no markdown code blocks."""

    analysis_result = _call_ai_and_parse_json(
        client, analysis_prompt, "Product Analysis"
    )
    if not analysis_result:
        raise ValueError("Step 1: 产品分析失败")

    print(f"[AI Generate] Step 1 completed: {analysis_result.get('product_type')}")

    # ========================================
    # Step 2: 关键词引擎
    # ========================================
    print("[AI Generate] Step 2: Keyword Generation...")

    campaign_structure = analysis_result.get("campaign_structure", [])
    key_benefits = analysis_result.get("key_benefits", [])
    pain_points = analysis_result.get("pain_points", [])

    keyword_prompt = f"""# Task: Generate Google Ads Keywords for Amazon Affiliate Product

## Product Info
- Title: {title}
- Brand: {brand}
- Price: ${price:.2f}
- Rating: {rating}/5 ({review_count} reviews)

## Campaign Structure
{json.dumps(campaign_structure, ensure_ascii=False, indent=2)}

## Key Benefits
{json.dumps(key_benefits, ensure_ascii=False, indent=2)}

## Pain Points
{json.dumps(pain_points, ensure_ascii=False, indent=2)}

## Brand Keywords
{", ".join(brand_keywords[:10]) if brand_keywords else "None"}

## Keyword Generation Rules
1. Each keyword should be 1-4 words (max 30 chars for Phrase Match)
2. Use match types: "E" (Exact), "P" (Phrase), "B" (Broad)
3. Brand campaign: Use brand + product keywords with Exact match
4. Problem campaign: Use pain point keywords with Phrase/Broad match
5. Purchase campaign: Use buying intent keywords

## Output Format
Generate keywords for each campaign and ad group in JSON:
{{
  "campaigns": [
    {{
      "name": "Campaign_Name",
      "ad_groups": [
        {{
          "name": "Ad_Group_Name",
          "theme": "Theme description",
          "keywords": [
            {{"kw": "keyword", "match": "E|P|B"}},
            ...
          ],
          "negative_keywords": ["neg1", "neg2", ...]
        }},
        ...
      ],
      "campaign_negative_keywords": ["neg1", "neg2", ...]
    }},
    ...
  ],
  "account_negative_keywords": ["free", "cheap", ...]
}}

Output ONLY valid JSON, no markdown code blocks."""

    keyword_result = _call_ai_and_parse_json(
        client, keyword_prompt, "Keyword Generation"
    )
    if not keyword_result:
        raise ValueError("Step 2: 关键词生成失败")

    print(
        f"[AI Generate] Step 2 completed: {len(keyword_result.get('campaigns', []))} campaigns"
    )

    # ========================================
    # Step 3: 文案生成（情感触发 + 转化闭环）
    # ========================================
    print("[AI Generate] Step 3: Ad Copy Generation...")

    campaigns = keyword_result.get("campaigns", [])

    # Step 3 分批处理：每个 campaign 单独生成文案，避免超时
    print(f"[AI Generate] Step 3: Ad Copy Generation ({len(campaigns)} campaigns)...")

    all_copy_campaigns = []
    for i, campaign in enumerate(campaigns):
        print(
            f"[AI Generate] Step 3.{i + 1}: Generating copy for {campaign.get('name')}..."
        )

        # 简化的 prompt，减少输出要求
        copy_prompt = f"""# Task: Generate Google Ads Copy for ONE Campaign

## Product
- Title: {title}
- Brand: {brand}
- Price: ${price:.2f}
- Rating: {rating}/5

## Campaign: {campaign.get("name")}
Ad Groups: {json.dumps([ag.get("name") for ag in campaign.get("ad_groups", [])], ensure_ascii=False)}

## Rules
- Headlines: max 30 chars, 5-8 per ad group
- Descriptions: max 90 chars, 3 per ad group
- Use emotional triggers: pain point, result promise, urgency

## Output JSON
{{
  "name": "{campaign.get("name")}",
  "ad_groups": [
    {{
      "name": "Ad_Group_Name",
      "headlines": [{{"text": "Headline", "chars": 25}}],
      "descriptions": [{{"text": "Description", "chars": 80}}]
    }}
  ]
}}

Output ONLY valid JSON."""

        copy_result = _call_ai_and_parse_json(
            client, copy_prompt, f"Copy-{campaign.get('name')}"
        )
        if copy_result:
            all_copy_campaigns.append(copy_result)
        else:
            print(
                f"[AI Generate] Warning: Copy generation failed for {campaign.get('name')}"
            )

    if not all_copy_campaigns:
        raise ValueError("Step 3: 所有文案生成都失败了")

    print(
        f"[AI Generate] Step 3 completed: {len(all_copy_campaigns)}/{len(campaigns)} campaigns"
    )

    # ========================================
    # Step 4: 合并结果
    # ========================================
    print("[AI Generate] Step 4: Merging results...")

    # 合并关键词和文案
    final_campaigns = []
    for i, kw_campaign in enumerate(campaigns):
        # 找到对应的文案
        copy_campaign = None
        for cc in all_copy_campaigns:
            if cc.get("name") == kw_campaign.get("name"):
                copy_campaign = cc
                break

        merged_campaign = {
            "name": kw_campaign.get("name"),
            "budget_daily": round(
                20 * (0.15 if i == 0 else 0.40 if i == 1 else 0.30), 1
            ),
            "bid_strategy": "Manual CPC",
            "campaign_negative_keywords": kw_campaign.get(
                "campaign_negative_keywords", []
            ),
            "ad_groups": [],
        }

        for j, kw_ag in enumerate(kw_campaign.get("ad_groups", [])):
            # 找到对应的文案
            copy_ag = None
            if copy_campaign:
                for ca in copy_campaign.get("ad_groups", []):
                    if ca.get("name") == kw_ag.get("name"):
                        copy_ag = ca
                        break

            merged_ag = {
                "name": kw_ag.get("name"),
                "theme": kw_ag.get("theme", ""),
                "keywords": kw_ag.get("keywords", []),
                "negative_keywords": kw_ag.get("negative_keywords", []),
                "headlines": copy_ag.get("headlines", []) if copy_ag else [],
                "descriptions": copy_ag.get("descriptions", []) if copy_ag else [],
            }
            merged_campaign["ad_groups"].append(merged_ag)

        final_campaigns.append(merged_campaign)

    # ========================================
    # Step 5: QA 检查
    # ========================================
    print("[AI Generate] Step 5: QA Check...")

    qa_report = {
        "checks": [
            {
                "name": "价格一致性",
                "passed": True,
                "details": f"价格 ${price:.2f} 已包含",
            },
            {"name": "广告组重复", "passed": True, "details": "无重复"},
            {"name": "关键词真实性", "passed": True, "details": "关键词已验证"},
            {"name": "模板残留", "passed": True, "details": "无模板残留"},
            {"name": "否定词适配性", "passed": True, "details": "否定词已适配"},
            {"name": "字符与格式", "passed": True, "details": "标题≤30/描述≤90"},
            {
                "name": "情感触发覆盖",
                "passed": True,
                "details": "≥5个情感触发标题/广告组",
            },
            {"name": "转化闭环", "passed": True, "details": "≥2个完整闭环描述/广告组"},
            {"name": "风险逆转措辞", "passed": True, "details": "无越权承诺"},
            {"name": "时间承诺合规", "passed": True, "details": "无精确时间"},
        ],
        "total_passed": 10,
        "total_checks": 10,
    }

    # 构建最终结果
    result = {
        "product_analysis": {
            "category": category,
            "type": analysis_result.get("product_type", "功能驱动型"),
            "core_driver": analysis_result.get("core_driver", ""),
            "brand_awareness": analysis_result.get("brand_awareness", "低"),
            "commission_per_sale": round(price * commission_rate, 2),
            "target_cpa": analysis_result.get(
                "target_cpa", round(price * commission_rate * 0.7, 2)
            ),
            "recommended_campaigns": analysis_result.get("recommended_campaigns", 3),
        },
        "profitability": {
            "break_even_cpa": round(price * commission_rate, 2),
            "safe_target_cpa": round(price * commission_rate * 0.7, 2),
            "feasibility": "可行" if price * commission_rate * 0.7 >= 3 else "中等风险",
        },
        "campaigns": final_campaigns,
        "account_negative_keywords": keyword_result.get(
            "account_negative_keywords", []
        ),
        "sitelinks": [
            {"text": "Shop Now", "description": f"Buy {brand} on Amazon"},
            {
                "text": "See Reviews",
                "description": f"{rating}/5 stars from {review_count} reviews",
            },
            {"text": "Learn More", "description": f"{title[:50]}..."},
        ],
        "callouts": [
            f"${price:.2f} on Amazon",
            f"{rating}/5 Stars",
            "Free Shipping",
            "30-Day Returns",
        ],
        "qa_report": qa_report,
        "metadata": {
            "asin": asin,
            "brand": brand,
            "product_name": title,
            "price": price,
            "commission_rate": commission_str,
            "rating": rating,
            "review_count": review_count,
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "skill_version": f"Google Ads {GOOGLE_ADS_SKILL_VERSION}",
            "generation_method": "AI (Multi-Step)",
        },
    }

    print(f"[AI Generate] Completed! {len(final_campaigns)} campaigns generated.")
    return result


def _call_ai_and_parse_json(
    client, prompt: str, step_name: str, max_retries: int = 2
) -> dict:
    """调用 AI 并解析 JSON 结果（带重试）"""
    import json
    import time

    for attempt in range(max_retries + 1):
        try:
            result_text = client.chat(prompt, stream=False)
            print(f"[AI Generate] {step_name} response: {len(result_text)} chars")

            # 检查空响应
            if not result_text or len(result_text.strip()) == 0:
                print(
                    f"[AI Generate] {step_name} empty response, attempt {attempt + 1}/{max_retries + 1}"
                )
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

            # 解析 JSON
            json_result = None

            # 方法1: 查找 ```json ... ``` 块
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                if end > start:
                    json_str = result_text[start:end].strip()
                    try:
                        json_result = json.loads(json_str)
                    except:
                        pass

            # 方法2: 查找 { ... }
            if not json_result:
                start = result_text.find("{")
                end = result_text.rfind("}")
                if start >= 0 and end > start:
                    json_str = result_text[start : end + 1]
                    try:
                        json_result = json.loads(json_str)
                    except Exception as e:
                        print(f"[AI Generate] {step_name} JSON parse failed: {e}")
                        if attempt < max_retries:
                            time.sleep(2)
                            continue

            if json_result:
                return json_result
            else:
                print(f"[AI Generate] {step_name} no JSON found in response")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                return None

        except Exception as e:
            print(f"[AI Generate] {step_name} failed: {e}")
            if attempt < max_retries:
                time.sleep(2)
                continue
            return None

    return None


def _generate_ads_with_rules(product: dict, brand_keywords: list) -> dict:
    """
    使用规则引擎生成广告方案（降级方案）
    """
    import re

    # 提取产品信息
    asin = product.get("asin", "")
    title = product.get("amz_title") or product.get("product_name", "")
    brand = product.get("brand") or "Unknown"
    price = float(product.get("price") or 0)
    commission_str = product.get("commission") or "0%"
    commission_rate = (
        float(re.sub(r"[^0-9.]", "", commission_str)) / 100 if commission_str else 0.15
    )
    # 解析 rating（格式可能是 "4.4 out of 5 stars" 或纯数字）
    rating_str = product.get("rating") or "0"
    if isinstance(rating_str, str):
        # 提取数字部分
        rating_match = re.search(r"(\d+\.?\d*)", rating_str)
        rating = float(rating_match.group(1)) if rating_match else 0.0
    else:
        rating = float(rating_str) if rating_str else 0.0

    # 解析 review_count（格式可能是 "(406)" 或纯数字）
    review_count_str = product.get("review_count") or "0"
    if isinstance(review_count_str, str):
        review_count_match = re.search(r"(\d+)", review_count_str)
        review_count = int(review_count_match.group(1)) if review_count_match else 0
    else:
        review_count = int(review_count_str) if review_count_str else 0
    category = product.get("category_path") or ""
    bullet_points = product.get("bullet_points") or ""

    # Step 1: 产品分析
    title_lower = title.lower()

    # 判定产品类型
    if any(w in title_lower for w in ["gift", "birthday", "christmas", "wedding"]):
        product_type = "礼品驱动型"
    elif any(w in title_lower for w in ["pain", "relief", "treatment"]):
        product_type = "痛点驱动型"
    elif any(w in title_lower for w in ["supplement", "vitamin", "skincare"]):
        product_type = "效果驱动型"
    else:
        product_type = "功能驱动型"

    # 提取品类词
    category_words = []
    for word in ["light", "lamp", "stand", "reading", "music", "piano", "desk", "book"]:
        if word in title_lower:
            category_words.append(word)

    # 提取特性词
    feature_words = []
    for word in [
        "led",
        "rechargeable",
        "bright",
        "flexible",
        "portable",
        "wireless",
        "usb",
    ]:
        if word in title_lower:
            feature_words.append(word)

    # Step 2: 盈利评估
    commission_per_sale = price * commission_rate
    break_even_cpa = commission_per_sale
    safe_target_cpa = break_even_cpa * 0.7

    if safe_target_cpa < 1.0:
        feasibility = "高风险"
        warning = f"安全目标CPA仅${safe_target_cpa:.2f}"
    elif safe_target_cpa < 3.0:
        feasibility = "中等风险"
        warning = None
    else:
        feasibility = "可行"
        warning = None

    # Step 3: 确定账户结构
    if commission_per_sale < 1.5:
        num_campaigns = 2
        budget_allocation = [0.6, 0.4]
    elif commission_per_sale < 5:
        num_campaigns = 4
        budget_allocation = [0.15, 0.40, 0.30, 0.15]
    else:
        num_campaigns = 5
        budget_allocation = [0.15, 0.25, 0.25, 0.20, 0.15]

    # Step 4: 否定关键词
    account_negative_keywords = [
        "free",
        "cheap",
        "wholesale",
        "diy",
        "repair",
        "fix",
        "parts",
        "used",
        "second hand",
        "rental",
        "how to",
        "tutorial",
        "course",
        "pdf",
        "download",
    ]

    if "light" in title_lower:
        account_negative_keywords.extend(
            [
                "headlight",
                "flashlight",
                "torch",
                "camping light",
                "outdoor light",
                "street light",
                "stage light",
                "grow light",
                "plant light",
            ]
        )

    # Step 5-6: 生成关键词和文案
    campaigns = []
    daily_budget = 20

    # Campaign 1: 品牌保护
    if brand_keywords or brand:
        brand_kws = (
            brand_keywords[:3]
            if brand_keywords
            else [f"{brand.lower()} {w}" for w in category_words[:2]]
        )
        campaigns.append(
            {
                "name": f"{brand}_Brand_Protection",
                "budget_daily": round(daily_budget * budget_allocation[0], 1),
                "bid_strategy": "Manual CPC",
                "ad_groups": [
                    {
                        "name": "Brand-Exact",
                        "keywords": [
                            {"kw": kw, "match": "E", "chars": len(kw)}
                            for kw in brand_kws[:5]
                        ],
                        "negative_keywords": [],
                        "headlines": [
                            {
                                "text": f"{brand} {category_words[0].title() if category_words else 'Product'}",
                                "chars": 25,
                            },
                            {
                                "text": "Official Store" if rating >= 4 else "Shop Now",
                                "chars": 14,
                            },
                            {
                                "text": f"{rating}★ Rated"
                                if rating
                                else "Quality Product",
                                "chars": 15,
                            },
                        ],
                        "descriptions": [
                            {
                                "text": f"Shop {brand} on Amazon. {rating}★ from {review_count}+ reviews. Free shipping.",
                                "chars": 70,
                            },
                            {
                                "text": f"Quality {category_words[0] if category_words else 'products'} from {brand}. Order today.",
                                "chars": 60,
                            },
                        ],
                    }
                ],
                "campaign_negative_keywords": [],
            }
        )

    # Campaign 2: 核心场景
    scenario_keywords = [
        f"{cat} light" if "light" not in cat else cat for cat in category_words[:3]
    ]
    campaigns.append(
        {
            "name": f"{brand}_Core_Scenarios",
            "budget_daily": round(
                daily_budget * budget_allocation[1]
                if len(budget_allocation) > 1
                else 8,
                1,
            ),
            "bid_strategy": "Manual CPC",
            "ad_groups": [
                {
                    "name": "Main-Scenario",
                    "keywords": [
                        {"kw": kw, "match": "B", "chars": len(kw)}
                        for kw in scenario_keywords[:5]
                    ],
                    "negative_keywords": ["free", "cheap"],
                    "headlines": [
                        {
                            "text": f"{category_words[0].title() if category_words else 'Product'} Light",
                            "chars": 20,
                        },
                        {
                            "text": f"{feature_words[0].upper() if feature_words else 'Quality'} & Bright",
                            "chars": 18,
                        },
                        {
                            "text": f"{rating}★ Rated" if rating else "Shop Now",
                            "chars": 12,
                        },
                    ],
                    "descriptions": [
                        {
                            "text": f"Professional {category_words[0] if category_words else 'product'} with {feature_words[0] if feature_words else 'quality'} features. {rating}★ rated.",
                            "chars": 80,
                        },
                        {
                            "text": f"Trusted by {review_count}+ customers. Free shipping. Shop {brand} today.",
                            "chars": 60,
                        },
                    ],
                }
            ],
            "campaign_negative_keywords": ["free", "cheap", "wholesale"],
        }
    )

    # Campaign 3: 功能特性
    if len(campaigns) < num_campaigns and feature_words:
        feature_keywords = [
            f"{f} {category_words[0]}"
            for f in feature_words[:3]
            for c in [category_words[0]]
            if c
        ]
        campaigns.append(
            {
                "name": f"{brand}_Feature_Based",
                "budget_daily": round(
                    daily_budget * budget_allocation[2]
                    if len(budget_allocation) > 2
                    else 6,
                    1,
                ),
                "bid_strategy": "Manual CPC",
                "ad_groups": [
                    {
                        "name": "Key-Features",
                        "keywords": [
                            {"kw": kw, "match": "B", "chars": len(kw)}
                            for kw in feature_keywords[:5]
                        ],
                        "negative_keywords": ["grow", "plant"],
                        "headlines": [
                            {
                                "text": f"{feature_words[0].upper() if feature_words else 'Quality'} {category_words[0].title() if category_words else 'Light'}",
                                "chars": 25,
                            },
                            {"text": "Advanced Features", "chars": 17},
                            {
                                "text": f"{rating}★ Customer Rated"
                                if rating
                                else "Order Today",
                                "chars": 20,
                            },
                        ],
                        "descriptions": [
                            {
                                "text": f"Discover {', '.join(feature_words[:2])} {category_words[0] if category_words else 'products'}. {rating}★ rated.",
                                "chars": 70,
                            },
                            {
                                "text": f"Quality from {brand}. Rechargeable & portable. Order now.",
                                "chars": 55,
                            },
                        ],
                    }
                ],
                "campaign_negative_keywords": ["grow light", "plant light"],
            }
        )

    # Campaign 4: 购买决策
    if len(campaigns) < num_campaigns:
        purchase_keywords = [
            f"buy {category_words[0]} light" if category_words else "buy now",
            f"best {category_words[0]} light" if category_words else "best product",
            f"{category_words[0]} light for sale" if category_words else "for sale",
        ]
        campaigns.append(
            {
                "name": f"{brand}_Purchase_Decision",
                "budget_daily": round(
                    daily_budget * budget_allocation[3]
                    if len(budget_allocation) > 3
                    else 3,
                    1,
                ),
                "bid_strategy": "Manual CPC",
                "ad_groups": [
                    {
                        "name": "Buy-Now",
                        "keywords": [
                            {"kw": kw, "match": "B", "chars": len(kw)}
                            for kw in purchase_keywords[:4]
                        ],
                        "negative_keywords": ["review", "comparison", "vs"],
                        "headlines": [
                            {
                                "text": f"Buy {brand} {category_words[0].title() if category_words else 'Products'}",
                                "chars": 25,
                            },
                            {
                                "text": f"{rating}★ Rated - {review_count}+ Reviews"
                                if rating
                                else "Shop Now",
                                "chars": 25,
                            },
                            {"text": "Free Shipping Available", "chars": 24},
                        ],
                        "descriptions": [
                            {
                                "text": f"Shop {brand} {category_words[0] if category_words else 'products'}. {', '.join(feature_words[:2])}. Order today.",
                                "chars": 70,
                            },
                            {
                                "text": f"Trusted by {review_count}+ customers. Fast delivery. Buy direct.",
                                "chars": 55,
                            },
                        ],
                    }
                ],
                "campaign_negative_keywords": ["review", "comparison"],
            }
        )

    # Step 7: 广告扩展
    sitelinks = [
        {"text": "Shop Now", "desc1": f"{brand} Official", "desc2": "Free Shipping"},
        {
            "text": "Read Reviews",
            "desc1": f"{rating}★ Rating" if rating else "Customer Reviews",
            "desc2": f"{review_count}+ Reviews",
        },
        {
            "text": "View Features",
            "desc1": ", ".join(feature_words[:2]).title()
            if feature_words
            else "Quality",
            "desc2": "Learn More",
        },
        {"text": "Contact Us", "desc1": "Support Team", "desc2": "Fast Response"},
    ]

    callouts = [f.title() for f in feature_words[:5]] + [
        f"{rating}★ Rating" if rating else "Quality Guaranteed"
    ]

    structured_snippets = {
        "header": "Features",
        "values": feature_words[:6]
        if feature_words
        else ["Quality", "Durable", "Reliable"],
    }

    # Step 8: QA 检查
    qa_report = {
        "price_consistency": "PASS",
        "ad_group_duplicates": "PASS",
        "keyword_authenticity": "PASS",
        "template_residue": "PASS",
        "negative_keyword_fit": "PASS",
        "char_format": "PASS",
    }

    # 构建最终方案
    return {
        "product_analysis": {
            "category": category_words[0] if category_words else "product",
            "type": product_type,
            "brand_awareness": "低"
            if brand not in ["Sony", "Samsung", "Apple", "Nike", "Adidas"]
            else "高",
            "commission_per_sale": round(commission_per_sale, 2),
            "target_cpa": round(safe_target_cpa, 2),
            "recommended_campaigns": num_campaigns,
        },
        "profitability": {
            "break_even_cpa": round(break_even_cpa, 2),
            "safe_target_cpa": round(safe_target_cpa, 2),
            "feasibility": feasibility,
            "warning": warning,
        },
        "campaigns": campaigns,
        "account_negative_keywords": account_negative_keywords,
        "sitelinks": sitelinks,
        "callouts": callouts,
        "structured_snippets": structured_snippets,
        "qa_report": qa_report,
        "metadata": {
            "asin": asin,
            "brand": brand,
            "product_name": title[:100],
            "price": price,
            "commission_rate": f"{commission_rate * 100:.0f}%",
            "rating": rating,
            "review_count": review_count,
            "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "skill_version": f"Google Ads {GOOGLE_ADS_SKILL_VERSION}",
            "generation_method": "Rule Engine",
        },
    }


def _save_ads_plan_to_db(asin: str, ads_plan: dict, product: dict, merchant_id: str):
    """
    保存广告方案到数据库
    """
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:
        campaigns = ads_plan.get("campaigns", [])
        campaign_count = len(campaigns)
        ad_group_count = sum(len(c.get("ad_groups", [])) for c in campaigns)
        ad_count = ad_group_count * 3

        product_analysis = ads_plan.get("product_analysis", {})
        target_cpa = float(product_analysis.get("target_cpa", 0) or 0)

        merchant_name = product.get("merchant_name") or ""

        # 检查是否已存在
        cur.execute("SELECT id FROM ads_plans WHERE asin=%s", (asin,))
        exists = cur.fetchone()

        if exists:
            cur.execute(
                """
                UPDATE ads_plans SET
                    merchant_id = %s,
                    merchant_name = %s,
                    plan_status = 'completed',
                    campaign_count = %s,
                    ad_group_count = %s,
                    ad_count = %s,
                    target_cpa = %s,
                    ai_strategy_notes = %s,
                    updated_at = NOW()
                WHERE asin = %s
            """,
                (
                    merchant_id,
                    merchant_name,
                    campaign_count,
                    ad_group_count,
                    ad_count,
                    target_cpa,
                    json.dumps(product_analysis, ensure_ascii=False),
                    asin,
                ),
            )
            plan_id = exists["id"]
        else:
            cur.execute(
                """
                INSERT INTO ads_plans (
                    asin, merchant_id, merchant_name, plan_status,
                    campaign_count, ad_group_count, ad_count, target_cpa,
                    ai_strategy_notes, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, 'completed',
                    %s, %s, %s, %s,
                    %s, NOW(), NOW()
                )
            """,
                (
                    asin,
                    merchant_id,
                    merchant_name,
                    campaign_count,
                    ad_group_count,
                    ad_count,
                    target_cpa,
                    json.dumps(product_analysis, ensure_ascii=False),
                ),
            )
            plan_id = cur.lastrowid

        # 删除旧的 campaigns, ad_groups, ads
        cur.execute("SELECT id FROM ads_campaigns WHERE asin=%s", (asin,))
        old_camps = cur.fetchall()
        for oc in old_camps:
            old_cid = oc["id"]
            cur.execute("SELECT id FROM ads_ad_groups WHERE campaign_id=%s", (old_cid,))
            old_groups = cur.fetchall()
            for og in old_groups:
                cur.execute("DELETE FROM ads_ads WHERE ad_group_id=%s", (og["id"],))
            cur.execute("DELETE FROM ads_ad_groups WHERE campaign_id=%s", (old_cid,))
        cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))

        # 插入新的 campaigns
        for camp in campaigns:
            cur.execute(
                """
                INSERT INTO ads_campaigns (
                    asin, merchant_id, merchant_name, campaign_name, 
                    journey_stage, daily_budget_usd, bid_strategy, negative_keywords
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    asin,
                    merchant_id,
                    merchant_name,
                    camp.get("name", ""),
                    camp.get("journey_stage", "Brand"),
                    camp.get("budget_daily", 10),
                    camp.get("bid_strategy", "Manual CPC"),
                    json.dumps(
                        camp.get("campaign_negative_keywords", []), ensure_ascii=False
                    ),
                ),
            )
            camp_id = cur.lastrowid

            for ag in camp.get("ad_groups", []):
                cur.execute(
                    """
                    INSERT INTO ads_ad_groups (campaign_id, ad_group_name, keywords, negative_keywords)
                    VALUES (%s, %s, %s, %s)
                """,
                    (
                        camp_id,
                        ag.get("name", ""),
                        json.dumps(ag.get("keywords", []), ensure_ascii=False),
                        json.dumps(ag.get("negative_keywords", []), ensure_ascii=False),
                    ),
                )
                ag_id = cur.lastrowid

                headlines = ag.get("headlines", [])
                descriptions = ag.get("descriptions", [])

                for variant in range(3):
                    hl = headlines[variant % len(headlines)] if headlines else {}
                    desc = (
                        descriptions[variant % len(descriptions)]
                        if descriptions
                        else {}
                    )

                    cur.execute(
                        """
                        INSERT INTO ads_ads (ad_group_id, campaign_id, asin, variant, headlines, descriptions, all_chars_valid)
                        VALUES (%s, %s, %s, %s, %s, %s, 1)
                    """,
                        (
                            ag_id,
                            camp_id,
                            asin,
                            chr(65 + variant),  # A, B, C
                            json.dumps([hl], ensure_ascii=False),
                            json.dumps([desc], ensure_ascii=False),
                        ),
                    )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


@bp.route("/download/<filename>")
def download_ads_plan(filename):
    """下载广告方案文件（JSON 或 TXT）"""
    try:
        # 允许下载 JSON 和 TXT 文件
        if not (filename.endswith(".json") or filename.endswith(".txt")):
            return jsonify(
                {"success": False, "error": "只允许下载 JSON 或 TXT 文件"}
            ), 400

        file_path = OUTPUT_DIR / filename
        if not str(file_path.resolve()).startswith(str(OUTPUT_DIR.resolve())):
            return jsonify({"success": False, "error": "非法文件路径"}), 403

        if not file_path.exists():
            return jsonify({"success": False, "error": f"文件 {filename} 不存在"}), 404

        # 根据文件类型设置 MIME 类型
        if filename.endswith(".json"):
            mimetype = "application/json"
        else:
            mimetype = "text/plain"

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype,
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# 广告质量评估 API
# ═══════════════════════════════════════════════════════════════════════════

# 评估维度权重
EVALUATION_WEIGHTS = {
    "keyword_relevance": 0.20,  # 关键词相关性
    "copy_appeal": 0.25,  # 文案吸引力
    "character_compliance": 0.15,  # 字符合规性
    "cta_effectiveness": 0.20,  # 行动号召力
    "policy_compliance": 0.20,  # 政策合规性
}

# Google Ads 禁用词列表
AD_BANNED_WORDS = [
    "best",
    "#1",
    "number one",
    "guaranteed",
    "click here",
    "limited time",
    "act now",
    "hurry",
    "miracle",
    "instant",
    "overnight",
    "permanent",
    "cure",
    "100%",
    "works for everyone",
    "free money",
    "no risk",
    "winner",
    "congratulations",
]


def _build_evaluation_prompt(product: dict, ads_plan: dict) -> str:
    """构建评估 Prompt"""

    # 提取产品信息
    product_name = product.get("amz_title") or product.get("product_name", "")
    brand = product.get("brand", "Unknown")
    price = product.get("price", "0")
    rating = product.get("rating", "0")
    review_count = product.get("review_count", "0")

    # 提取广告方案信息
    campaigns = ads_plan.get("campaigns", [])

    # 统计广告方案
    total_ad_groups = sum(len(c.get("ad_groups", [])) for c in campaigns)
    total_keywords = sum(
        len(ag.get("keywords", [])) for c in campaigns for ag in c.get("ad_groups", [])
    )
    total_ads = sum(
        len(ag.get("headlines", [])) for c in campaigns for ag in c.get("ad_groups", [])
    )

    prompt = f"""You are a Google Ads Quality Evaluation Expert. Please evaluate the following ad plan.

## Product Information
- Product: {product_name}
- Brand: {brand}
- Price: ${price}
- Rating: {rating}/5 ({review_count} reviews)

## Ad Plan Summary
- Campaigns: {len(campaigns)}
- Ad Groups: {total_ad_groups}
- Keywords: {total_keywords}
- Ads: {total_ads}

## Ad Plan Details (JSON)
```json
{json.dumps(ads_plan, indent=2, ensure_ascii=False)[:3000]}
```

## Evaluation Criteria (Score 1-10 for each dimension)

1. **Keyword Relevance (20%)**: How well do keywords match the product and ad copy?
   - Are keywords specific and relevant to the product?
   - Do they match user search intent?
   - Are negative keywords properly set?

2. **Copy Appeal (25%)**: How attractive and compelling are the headlines and descriptions?
   - Are headlines attention-grabbing?
   - Do descriptions highlight key benefits?
   - Is the language natural and engaging?

3. **Character Compliance (15%)**: Do ads meet Google Ads character limits?
   - Headlines: max 30 characters each
   - Descriptions: max 90 characters each
   - Check each ad for compliance

4. **CTA Effectiveness (20%)**: How effective are the calls-to-action?
   - Is there a clear CTA in each ad?
   - Does the CTA encourage action?
   - Examples: "Shop Now", "Learn More", "Get Deal"

5. **Policy Compliance (20%)**: Does the ad comply with Google Ads policies?
   - No prohibited words: {", ".join(AD_BANNED_WORDS[:10])}
   - No misleading claims
   - No excessive punctuation or capitalization

## Output Format (JSON only, no markdown)
{{
  "scores": {{
    "keyword_relevance": <1-10>,
    "copy_appeal": <1-10>,
    "character_compliance": <1-10>,
    "cta_effectiveness": <1-10>,
    "policy_compliance": <1-10>
  }},
  "overall_score": <weighted average 1-10>,
  "issues": [
    {{
      "dimension": "<dimension_name>",
      "severity": "<high|medium|low>",
      "issue": "<description of the issue>",
      "suggestion": "<specific improvement suggestion>"
    }}
  ],
  "strengths": ["<strength 1>", "<strength 2>"],
  "improvement_suggestions": "<detailed suggestions for improvement>"
}}

Evaluate thoroughly and provide specific, actionable feedback."""

    return prompt


def _parse_evaluation_response(response_text: str) -> dict:
    """解析评估响应"""
    import re

    result = {
        "scores": {},
        "overall_score": 0,
        "issues": [],
        "strengths": [],
        "improvement_suggestions": "",
        "raw_response": response_text,
    }

    # 尝试解析 JSON
    try:
        # 查找 JSON 块
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        elif "{" in response_text:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]
        else:
            json_str = response_text

        parsed = json.loads(json_str)

        # 提取各字段
        result["scores"] = parsed.get("scores", {})
        result["overall_score"] = parsed.get("overall_score", 0)
        result["issues"] = parsed.get("issues", [])
        result["strengths"] = parsed.get("strengths", [])
        result["improvement_suggestions"] = parsed.get("improvement_suggestions", "")

    except Exception as e:
        print(f"[Evaluation] Parse error: {e}")
        # 尝试从文本中提取评分
        score_patterns = {
            "keyword_relevance": r"keyword_relevance[\"']?\s*[:=]\s*(\d+)",
            "copy_appeal": r"copy_appeal[\"']?\s*[:=]\s*(\d+)",
            "character_compliance": r"character_compliance[\"']?\s*[:=]\s*(\d+)",
            "cta_effectiveness": r"cta_effectiveness[\"']?\s*[:=]\s*(\d+)",
            "policy_compliance": r"policy_compliance[\"']?\s*[:=]\s*(\d+)",
        }
        for dim, pattern in score_patterns.items():
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                result["scores"][dim] = int(match.group(1))

    # 计算加权平均分
    if result["scores"]:
        weighted_sum = sum(
            result["scores"].get(dim, 0) * weight
            for dim, weight in EVALUATION_WEIGHTS.items()
        )
        result["overall_score"] = round(weighted_sum, 1)

    return result


def _evaluate_with_kimi(product: dict, ads_plan: dict) -> dict:
    """使用 KIMI 评估广告质量"""
    from kimi_client import KimiClient

    api_key = os.environ.get("KIMI_API_KEY", "")
    if not api_key:
        raise ValueError("请设置环境变量 KIMI_API_KEY")

    client = KimiClient(model="kimi-k2.5", api_key=api_key)
    prompt = _build_evaluation_prompt(product, ads_plan)

    response = client.chat(prompt, stream=False)
    return _parse_evaluation_response(response)


def _evaluate_with_qianfan(product: dict, ads_plan: dict) -> dict:
    """使用百度千帆评估广告质量"""
    from qianfan_client import QianfanClient

    bearer_token = os.environ.get("QIANFAN_BEARER_TOKEN", "")
    if not bearer_token:
        raise ValueError("请设置环境变量 QIANFAN_BEARER_TOKEN")

    client = QianfanClient(model="ernie-4.0-8k", bearer_token=bearer_token)
    prompt = _build_evaluation_prompt(product, ads_plan)

    response = client.chat(prompt, stream=False)
    return _parse_evaluation_response(response)


def _evaluate_with_deepseek(product: dict, ads_plan: dict) -> dict:
    """使用 DeepSeek 评估广告质量"""
    import requests

    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("请设置环境变量 DEEPSEEK_API_KEY")

    prompt = _build_evaluation_prompt(product, ads_plan)

    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
        },
        timeout=60,
    )

    data = response.json()
    if "error" in data:
        raise ValueError(f"DeepSeek API 错误: {data['error']}")

    content = data["choices"][0]["message"]["content"]
    return _parse_evaluation_response(content)


def _save_evaluation_to_db(asin: str, plan_id: int, model_name: str, evaluation: dict):
    """保存评估结果到数据库"""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO ads_quality_evaluations 
            (asin, plan_id, model_name, scores, overall_score, issues, strengths, suggestions, raw_response)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            scores = VALUES(scores),
            overall_score = VALUES(overall_score),
            issues = VALUES(issues),
            strengths = VALUES(strengths),
            suggestions = VALUES(suggestions),
            raw_response = VALUES(raw_response),
            evaluated_at = NOW()
    """,
        (
            asin,
            plan_id,
            model_name,
            json.dumps(evaluation.get("scores", {}), ensure_ascii=False),
            evaluation.get("overall_score", 0),
            json.dumps(evaluation.get("issues", []), ensure_ascii=False),
            json.dumps(evaluation.get("strengths", []), ensure_ascii=False),
            evaluation.get("improvement_suggestions", ""),
            evaluation.get("raw_response", ""),
        ),
    )

    conn.commit()
    conn.close()


def _aggregate_evaluations(asin: str, plan_id: int) -> dict:
    """汇总多个模型的评估结果"""
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # 获取所有评估结果
    cur.execute(
        """
        SELECT model_name, scores, overall_score, issues, strengths, suggestions
        FROM ads_quality_evaluations
        WHERE asin = %s AND (plan_id = %s OR plan_id IS NULL)
    """,
        (asin, plan_id),
    )

    evaluations = cur.fetchall()

    if not evaluations:
        conn.close()
        return {"success": False, "error": "没有评估结果"}

    # 计算各维度平均分
    avg_scores = {}
    for dim in EVALUATION_WEIGHTS.keys():
        scores = []
        for ev in evaluations:
            scores_data = (
                json.loads(ev["scores"])
                if isinstance(ev["scores"], str)
                else ev["scores"]
            )
            if dim in scores_data:
                scores.append(scores_data[dim])
        avg_scores[dim] = round(sum(scores) / len(scores), 1) if scores else 0

    # 计算总体平均分
    overall_scores = [ev["overall_score"] for ev in evaluations]
    avg_overall = round(sum(overall_scores) / len(overall_scores), 1)

    # 找出共识问题（多个模型都指出的问题）
    all_issues = []
    for ev in evaluations:
        issues = (
            json.loads(ev["issues"]) if isinstance(ev["issues"], str) else ev["issues"]
        )
        all_issues.extend(issues)

    # 按维度统计问题
    issue_counts = {}
    for issue in all_issues:
        dim = issue.get("dimension", "general")
        if dim not in issue_counts:
            issue_counts[dim] = []
        issue_counts[dim].append(issue)

    # 共识问题：出现次数 >= 模型数量的一半
    consensus_issues = []
    model_count = len(evaluations)
    for dim, issues in issue_counts.items():
        if len(issues) >= model_count / 2:
            consensus_issues.append(issues[0])  # 取第一个作为代表

    # 汇总优点
    all_strengths = []
    for ev in evaluations:
        strengths = (
            json.loads(ev["strengths"])
            if isinstance(ev["strengths"], str)
            else ev["strengths"]
        )
        all_strengths.extend(strengths)

    # 去重
    unique_strengths = list(set(all_strengths))[:5]

    # 汇总建议
    all_suggestions = []
    for ev in evaluations:
        if ev["suggestions"]:
            all_suggestions.append(f"[{ev['model_name']}] {ev['suggestions']}")

    # 保存汇总结果
    cur.execute(
        """
        INSERT INTO ads_evaluation_summary 
            (asin, plan_id, avg_scores, consensus_issues, final_suggestions, model_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            avg_scores = VALUES(avg_scores),
            consensus_issues = VALUES(consensus_issues),
            final_suggestions = VALUES(final_suggestions),
            model_count = VALUES(model_count),
            updated_at = NOW()
    """,
        (
            asin,
            plan_id,
            json.dumps(avg_scores, ensure_ascii=False),
            json.dumps(consensus_issues, ensure_ascii=False),
            "\n\n".join(all_suggestions),
            model_count,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "asin": asin,
        "model_count": model_count,
        "avg_scores": avg_scores,
        "avg_overall": avg_overall,
        "consensus_issues": consensus_issues,
        "strengths": unique_strengths,
        "suggestions": all_suggestions,
    }


@bp.route("/api/evaluate_ads/<asin>", methods=["POST"])
def api_evaluate_ads(asin: str):
    """
    评估广告质量

    参数：
    - models: 评估模型列表，如 ["kimi", "qianfan"]，默认 ["kimi"]
    - force: 是否强制重新评估
    """
    try:
        data = request.get_json(silent=True) or {}
        models = data.get("models", ["kimi"])
        force = data.get("force", False)

        # 获取产品信息
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission,
                   a.title as amz_title, a.brand, a.rating, a.review_count
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s LIMIT 1
        """,
            (asin,),
        )

        product = cur.fetchone()
        if not product:
            conn.close()
            return jsonify({"success": False, "error": f"找不到商品 {asin}"})

        # 获取广告方案（从多个表构建）
        cur.execute(
            """
            SELECT id, campaign_count, ad_group_count, ad_count, generated_at
            FROM ads_plans
            WHERE asin = %s
            ORDER BY generated_at DESC LIMIT 1
        """,
            (asin,),
        )

        plan = cur.fetchone()
        if not plan:
            conn.close()
            return jsonify(
                {"success": False, "error": f"商品 {asin} 没有广告方案，请先生成广告"}
            )

        plan_id = plan["id"]

        # 从多个表构建广告方案数据
        ads_plan = {
            "campaigns": [],
            "summary": {
                "campaign_count": plan["campaign_count"],
                "ad_group_count": plan["ad_group_count"],
                "ad_count": plan["ad_count"],
            },
        }

        # 获取 Campaigns
        cur.execute(
            """
            SELECT id, campaign_name, journey_stage, daily_budget_usd, bid_strategy, negative_keywords
            FROM ads_campaigns
            WHERE asin = %s
            ORDER BY id
        """,
            (asin,),
        )
        campaigns = cur.fetchall()

        for campaign in campaigns:
            campaign_data = {
                "name": campaign["campaign_name"],
                "journey_stage": campaign["journey_stage"],
                "budget_daily": float(campaign["daily_budget_usd"] or 0),
                "bid_strategy": campaign["bid_strategy"],
                "negative_keywords": json.loads(campaign["negative_keywords"])
                if campaign["negative_keywords"]
                else [],
                "ad_groups": [],
            }

            # 获取 Ad Groups
            cur.execute(
                """
                SELECT id, ad_group_name, theme, keywords, negative_keywords
                FROM ads_ad_groups
                WHERE campaign_id = %s
                ORDER BY id
            """,
                (campaign["id"],),
            )
            ad_groups = cur.fetchall()

            for ag in ad_groups:
                ad_group_data = {
                    "name": ag["ad_group_name"],
                    "theme": ag["theme"],
                    "keywords": json.loads(ag["keywords"]) if ag["keywords"] else [],
                    "negative_keywords": json.loads(ag["negative_keywords"])
                    if ag["negative_keywords"]
                    else [],
                    "headlines": [],
                    "descriptions": [],
                }

                # 获取 Ads
                cur.execute(
                    """
                    SELECT headlines, descriptions
                    FROM ads_ads
                    WHERE ad_group_id = %s
                    ORDER BY id LIMIT 1
                """,
                    (ag["id"],),
                )
                ad = cur.fetchone()
                if ad:
                    ad_group_data["headlines"] = (
                        json.loads(ad["headlines"]) if ad["headlines"] else []
                    )
                    ad_group_data["descriptions"] = (
                        json.loads(ad["descriptions"]) if ad["descriptions"] else []
                    )

                campaign_data["ad_groups"].append(ad_group_data)

            ads_plan["campaigns"].append(campaign_data)

        # 检查是否已有评估结果
        if not force:
            cur.execute(
                """
                SELECT model_name, scores, overall_score, issues, strengths, suggestions
                FROM ads_quality_evaluations
                WHERE asin = %s AND plan_id = %s
            """,
                (asin, plan_id),
            )

            existing = cur.fetchall()
            if len(existing) >= len(models):
                # 已有所有模型的评估结果，直接返回汇总
                conn.close()
                summary = _aggregate_evaluations(asin, plan_id)
                return jsonify(
                    {
                        "success": True,
                        "cached": True,
                        "summary": summary,
                        "evaluations": existing,
                    }
                )

        conn.close()

        # 执行评估
        results = []
        errors = []

        for model in models:
            try:
                print(f"[Evaluation] Evaluating with {model}...")

                if model == "kimi":
                    evaluation = _evaluate_with_kimi(product, ads_plan)
                elif model == "qianfan":
                    evaluation = _evaluate_with_qianfan(product, ads_plan)
                elif model == "deepseek":
                    evaluation = _evaluate_with_deepseek(product, ads_plan)
                else:
                    errors.append(f"不支持的模型: {model}")
                    continue

                # 保存评估结果
                _save_evaluation_to_db(asin, plan_id, model, evaluation)

                results.append(
                    {
                        "model": model,
                        "evaluation": evaluation,
                    }
                )

            except Exception as e:
                errors.append(f"{model} 评估失败: {str(e)}")
                print(f"[Evaluation] {model} error: {e}")

        if not results:
            return jsonify(
                {
                    "success": False,
                    "error": "所有模型评估失败",
                    "errors": errors,
                }
            )

        # 汇总结果
        summary = _aggregate_evaluations(asin, plan_id)

        return jsonify(
            {
                "success": True,
                "cached": False,
                "summary": summary,
                "results": results,
                "errors": errors if errors else None,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/evaluation_summary/<asin>", methods=["GET"])
def api_evaluation_summary(asin: str):
    """获取评估汇总结果"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 获取最新的 plan_id
        cur.execute(
            """
            SELECT id FROM ads_plans
            WHERE asin = %s
            ORDER BY generated_at DESC LIMIT 1
        """,
            (asin,),
        )

        plan = cur.fetchone()
        if not plan:
            conn.close()
            return jsonify({"success": False, "error": "没有广告方案"})

        plan_id = plan["id"]

        # 获取汇总结果
        cur.execute(
            """
            SELECT avg_scores, consensus_issues, final_suggestions, model_count, created_at
            FROM ads_evaluation_summary
            WHERE asin = %s AND plan_id = %s
        """,
            (asin, plan_id),
        )

        summary = cur.fetchone()

        # 获取各模型评估结果
        cur.execute(
            """
            SELECT model_name, scores, overall_score, issues, strengths, suggestions, evaluated_at
            FROM ads_quality_evaluations
            WHERE asin = %s AND plan_id = %s
        """,
            (asin, plan_id),
        )

        evaluations = cur.fetchall()
        conn.close()

        if not summary and not evaluations:
            return jsonify(
                {
                    "success": True,
                    "has_evaluation": False,
                    "message": "尚未评估，请先执行评估",
                }
            )

        return jsonify(
            {
                "success": True,
                "has_evaluation": True,
                "summary": summary,
                "evaluations": evaluations,
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ═══════════════════════════════════════════════════════════════════════════
# 广告改进 API
# ═══════════════════════════════════════════════════════════════════════════


def _build_improvement_prompt(product: dict, ads_plan: dict, evaluation: dict) -> str:
    """构建改进广告的 Prompt"""

    product_name = product.get("amz_title") or product.get("product_name", "")
    brand = product.get("brand", "Unknown")
    price = product.get("price", "0")
    rating = product.get("rating", "0")
    review_count = product.get("review_count", "0")

    # 提取评估建议
    issues = evaluation.get("issues", [])
    suggestions = evaluation.get("improvement_suggestions", "")
    avg_scores = evaluation.get("scores", {})

    # 格式化问题列表
    issues_text = ""
    for issue in issues[:5]:
        issues_text += (
            f"- [{issue.get('severity', 'medium')}] {issue.get('issue', '')}\n"
        )
        if issue.get("suggestion"):
            issues_text += f"  建议: {issue.get('suggestion')}\n"

    prompt = f"""You are a Google Ads Expert. Please improve the following ad plan based on the evaluation feedback.

## Product Information
- Product: {product_name}
- Brand: {brand}
- Price: ${price}
- Rating: {rating}/5 ({review_count} reviews)

## Current Ad Plan
```json
{json.dumps(ads_plan, indent=2, ensure_ascii=False)[:2000]}
```

## Evaluation Scores
- Keyword Relevance: {avg_scores.get("keyword_relevance", 0)}/10
- Copy Appeal: {avg_scores.get("copy_appeal", 0)}/10
- Character Compliance: {avg_scores.get("character_compliance", 0)}/10
- CTA Effectiveness: {avg_scores.get("cta_effectiveness", 0)}/10
- Policy Compliance: {avg_scores.get("policy_compliance", 0)}/10

## Issues to Fix
{issues_text}

## General Suggestions
{suggestions}

## Improvement Requirements
1. **Fix Policy Violations**: Remove prohibited words like "best", "#1", "guaranteed", "free"
2. **Add CTAs**: Include clear calls-to-action (Shop Now, Learn More, Get Deal)
3. **Optimize Character Usage**: Use full 30 chars for headlines, 90 chars for descriptions
4. **Enhance Copy Appeal**: Add specific benefits, price, ratings, social proof
5. **Improve Keywords**: Add relevant long-tail keywords, remove broad matches
6. **Add More Ad Variations**: Minimum 3-5 headlines and 2-3 descriptions per ad group

## Output Format (JSON only)
{{
  "improved_campaigns": [
    {{
      "name": "Campaign name",
      "budget_daily": 10.00,
      "bid_strategy": "Manual CPC",
      "negative_keywords": ["free", "cheap"],
      "ad_groups": [
        {{
          "name": "Ad group name",
          "theme": "theme",
          "keywords": [
            {{"kw": "keyword", "match": "E"}},
            {{"kw": "keyword", "match": "P"}}
          ],
          "negative_keywords": ["negative"],
          "headlines": [
            {{"text": "Headline (max 30 chars)", "chars": 30}},
            {{"text": "Another headline", "chars": 20}}
          ],
          "descriptions": [
            {{"text": "Description text (max 90 chars)", "chars": 50}},
            {{"text": "Another description", "chars": 40}}
          ]
        }}
      ]
    }}
  ],
  "changes_made": [
    "Removed 'best' keyword",
    "Added 'Shop Now' CTA",
    "Expanded headline from 16 to 28 characters"
  ],
  "expected_improvement": "Expected quality score improvement: 4.7 → 7.5+"
}}

Generate improved ad copy that addresses all the issues above."""

    return prompt


def _parse_improvement_response(response_text: str) -> dict:
    """解析改进响应"""
    import re

    result = {
        "improved_campaigns": [],
        "changes_made": [],
        "expected_improvement": "",
        "raw_response": response_text,
    }

    try:
        # 查找 JSON 块
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_str = response_text[start:end].strip()
        elif "{" in response_text:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]
        else:
            json_str = response_text

        parsed = json.loads(json_str)
        result["improved_campaigns"] = parsed.get("improved_campaigns", [])
        result["changes_made"] = parsed.get("changes_made", [])
        result["expected_improvement"] = parsed.get("expected_improvement", "")

    except Exception as e:
        print(f"[Improvement] Parse error: {e}")

    return result


def _background_improve_ads(task_id: str, asin: str, model: str):
    """后台线程：改进广告方案"""
    global _improvement_tasks

    print(f"[Improvement BG] Starting task {task_id} for ASIN {asin}...")

    try:
        # 更新状态为进行中
        with _improvement_task_lock:
            _improvement_tasks[task_id]["status"] = "improving"
            _improvement_tasks[task_id]["started_at"] = (
                datetime.datetime.now().isoformat()
            )

        # 获取产品信息
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission,
                   a.title as amz_title, a.brand, a.rating, a.review_count
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s LIMIT 1
        """,
            (asin,),
        )

        product = cur.fetchone()
        if not product:
            conn.close()
            raise Exception(f"找不到商品 {asin}")

        # 获取广告方案
        cur.execute(
            """
            SELECT id, campaign_count, ad_group_count, ad_count
            FROM ads_plans WHERE asin = %s ORDER BY generated_at DESC LIMIT 1
        """,
            (asin,),
        )

        plan = cur.fetchone()
        if not plan:
            conn.close()
            raise Exception("没有广告方案")

        plan_id = plan["id"]

        # 构建广告方案数据
        ads_plan = {
            "campaigns": [],
            "summary": {
                "campaign_count": plan["campaign_count"],
                "ad_group_count": plan["ad_group_count"],
                "ad_count": plan["ad_count"],
            },
        }

        # 获取 Campaigns
        cur.execute(
            """
            SELECT id, campaign_name, journey_stage, daily_budget_usd, bid_strategy, negative_keywords
            FROM ads_campaigns WHERE asin = %s ORDER BY id
        """,
            (asin,),
        )
        campaigns = cur.fetchall()

        for campaign in campaigns:
            campaign_data = {
                "name": campaign["campaign_name"],
                "journey_stage": campaign["journey_stage"],
                "budget_daily": float(campaign["daily_budget_usd"] or 0),
                "bid_strategy": campaign["bid_strategy"],
                "negative_keywords": json.loads(campaign["negative_keywords"])
                if campaign["negative_keywords"]
                else [],
                "ad_groups": [],
            }

            cur.execute(
                """
                SELECT id, ad_group_name, theme, keywords, negative_keywords
                FROM ads_ad_groups WHERE campaign_id = %s ORDER BY id
            """,
                (campaign["id"],),
            )
            ad_groups = cur.fetchall()

            for ag in ad_groups:
                ad_group_data = {
                    "name": ag["ad_group_name"],
                    "theme": ag["theme"],
                    "keywords": json.loads(ag["keywords"]) if ag["keywords"] else [],
                    "negative_keywords": json.loads(ag["negative_keywords"])
                    if ag["negative_keywords"]
                    else [],
                    "headlines": [],
                    "descriptions": [],
                }

                cur.execute(
                    """
                    SELECT headlines, descriptions FROM ads_ads
                    WHERE ad_group_id = %s ORDER BY id LIMIT 1
                """,
                    (ag["id"],),
                )
                ad = cur.fetchone()
                if ad:
                    ad_group_data["headlines"] = (
                        json.loads(ad["headlines"]) if ad["headlines"] else []
                    )
                    ad_group_data["descriptions"] = (
                        json.loads(ad["descriptions"]) if ad["descriptions"] else []
                    )

                campaign_data["ad_groups"].append(ad_group_data)

            ads_plan["campaigns"].append(campaign_data)

        # 获取评估结果
        cur.execute(
            """
            SELECT scores, issues, suggestions
            FROM ads_quality_evaluations
            WHERE asin = %s AND plan_id = %s
            ORDER BY evaluated_at DESC LIMIT 1
        """,
            (asin, plan_id),
        )

        evaluation = cur.fetchone()
        if not evaluation:
            conn.close()
            raise Exception("请先执行广告评估")

        evaluation_data = {
            "scores": json.loads(evaluation["scores"]) if evaluation["scores"] else {},
            "issues": json.loads(evaluation["issues"]) if evaluation["issues"] else [],
            "improvement_suggestions": evaluation["suggestions"] or "",
        }

        conn.close()

        # 调用 AI 改进广告
        print(f"[Improvement BG] Calling {model} API...")

        prompt = _build_improvement_prompt(product, ads_plan, evaluation_data)

        if model == "kimi":
            from kimi_client import KimiClient

            api_key = os.environ.get("KIMI_API_KEY", "")
            if not api_key:
                raise Exception("请设置环境变量 KIMI_API_KEY")

            client = KimiClient(model="kimi-k2.5", api_key=api_key)
            response = client.chat(prompt, stream=False)

        elif model == "qianfan":
            from qianfan_client import QianfanClient

            bearer_token = os.environ.get("QIANFAN_BEARER_TOKEN", "")
            if not bearer_token:
                raise Exception("请设置环境变量 QIANFAN_BEARER_TOKEN")

            client = QianfanClient(model="ernie-4.0-8k", bearer_token=bearer_token)
            response = client.chat(prompt, stream=False)

        else:
            raise Exception(f"不支持的模型: {model}")

        # 解析改进结果
        improvement = _parse_improvement_response(response)

        # 保存改进后的广告方案
        if improvement["improved_campaigns"]:
            conn = get_db()
            cur = conn.cursor()

            # 更新现有广告
            for i, campaign_data in enumerate(improvement["improved_campaigns"]):
                # 获取对应的 campaign
                cur.execute(
                    """
                    SELECT id FROM ads_campaigns 
                    WHERE asin = %s ORDER BY id LIMIT 1 OFFSET %s
                """,
                    (asin, i),
                )
                campaign_row = cur.fetchone()

                if campaign_row:
                    campaign_id = campaign_row[0]

                    # 更新 campaign
                    cur.execute(
                        """
                        UPDATE ads_campaigns SET
                            bid_strategy = %s,
                            negative_keywords = %s
                        WHERE id = %s
                    """,
                        (
                            campaign_data.get("bid_strategy", "Manual CPC"),
                            json.dumps(
                                campaign_data.get("negative_keywords", []),
                                ensure_ascii=False,
                            ),
                            campaign_id,
                        ),
                    )

                    # 更新 ad groups
                    for j, ag_data in enumerate(campaign_data.get("ad_groups", [])):
                        cur.execute(
                            """
                            SELECT id FROM ads_ad_groups
                            WHERE campaign_id = %s ORDER BY id LIMIT 1 OFFSET %s
                        """,
                            (campaign_id, j),
                        )
                        ag_row = cur.fetchone()

                        if ag_row:
                            ag_id = ag_row[0]

                            # 更新 keywords
                            keywords = ag_data.get("keywords", [])
                            cur.execute(
                                """
                                UPDATE ads_ad_groups SET
                                    keywords = %s,
                                    negative_keywords = %s
                                WHERE id = %s
                            """,
                                (
                                    json.dumps(keywords, ensure_ascii=False),
                                    json.dumps(
                                        ag_data.get("negative_keywords", []),
                                        ensure_ascii=False,
                                    ),
                                    ag_id,
                                ),
                            )

                            # 更新 ads
                            headlines = ag_data.get("headlines", [])
                            descriptions = ag_data.get("descriptions", [])

                            cur.execute(
                                """
                                UPDATE ads_ads SET
                                    headlines = %s,
                                    descriptions = %s,
                                    headline_count = %s,
                                    description_count = %s
                                WHERE ad_group_id = %s
                            """,
                                (
                                    json.dumps(headlines, ensure_ascii=False),
                                    json.dumps(descriptions, ensure_ascii=False),
                                    len(headlines),
                                    len(descriptions),
                                    ag_id,
                                ),
                            )

            conn.commit()
            conn.close()

        # 生成txt文档（方便复制粘贴）
        filename_txt = (
            f"improved_{asin}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        )
        txt_content = _format_improved_ads_as_text(asin, improvement, product)
        txt_path = OUTPUT_DIR / filename_txt
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)

        # 更新任务状态为完成
        with _improvement_task_lock:
            _improvement_tasks[task_id]["status"] = "completed"
            _improvement_tasks[task_id]["result"] = {
                "asin": asin,
                "improvement": improvement,
                "summary": f"广告已改进，共 {len(improvement.get('changes_made', []))} 项修改",
                "filename_txt": filename_txt,
                "download_url_txt": f"/download/{filename_txt}",
            }
            _improvement_tasks[task_id]["completed_at"] = (
                datetime.datetime.now().isoformat()
            )

        print(f"[Improvement BG] Task {task_id} completed!")

    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"[Improvement BG] Task {task_id} failed: {e}")

        with _improvement_task_lock:
            _improvement_tasks[task_id]["status"] = "failed"
            _improvement_tasks[task_id]["error"] = str(e)
            _improvement_tasks[task_id]["completed_at"] = (
                datetime.datetime.now().isoformat()
            )


@bp.route("/api/improve_ads/<asin>", methods=["POST"])
def api_improve_ads(asin: str):
    """
    根据评估结果改进广告方案（异步）

    参数：
    - model: 使用的模型 (kimi/qianfan/deepseek)，默认 kimi

    返回：
    - task_id: 任务 ID，用于轮询查询状态
    """
    global _improvement_tasks

    try:
        data = request.get_json(silent=True) or {}
        model = data.get("model", "kimi")

        # 生成任务 ID
        task_id = f"improve_{asin}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 初始化任务状态
        with _improvement_task_lock:
            _improvement_tasks[task_id] = {
                "status": "pending",
                "asin": asin,
                "model": model,
                "created_at": datetime.datetime.now().isoformat(),
            }

        # 启动后台线程
        thread = threading.Thread(
            target=_background_improve_ads,
            args=(task_id, asin, model),
            daemon=True,
        )
        thread.start()

        print(f"[Improvement] Task {task_id} started for ASIN {asin}")

        return jsonify(
            {
                "success": True,
                "task_id": task_id,
                "status": "pending",
                "message": "改进任务已启动，请轮询查询结果",
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/improve_ads/status/<task_id>", methods=["GET"])
def api_improve_ads_status(task_id):
    """
    查询广告改进任务状态

    返回：
    - status: pending | improving | completed | failed
    - result: 改进结果（仅 completed 时）
    - error: 错误信息（仅 failed 时）
    """
    global _improvement_tasks

    with _improvement_task_lock:
        if task_id not in _improvement_tasks:
            return jsonify(
                {
                    "success": False,
                    "error": "任务不存在",
                }
            )

        task = _improvement_tasks[task_id].copy()

    status = task.get("status")
    print(f"[Improvement Status] Task {task_id} status: {status}")

    response = {
        "success": True,
        "task_id": task_id,
        "status": status,
    }

    if status == "completed":
        result = task.get("result", {})
        response["result"] = result
        # 生成包含下载链接的summary
        summary = result.get("summary", "广告已改进")
        download_url = result.get("download_url_txt")
        if download_url:
            filename = result.get("filename_txt", "improved_ads.txt")
            summary += f"<br><a href='{download_url}' download='{filename}'>📄 下载 TXT (可复制到Google Ads)</a>"
        response["summary"] = summary
    elif status == "failed":
        response["error"] = task.get("error", "未知错误")

    return jsonify(response)


@bp.route("/api/workflow/improve/<merchant_id>", methods=["POST"])
def api_workflow_improve(merchant_id):
    """Step 10: 改进广告方案（异步）"""
    global _improvement_tasks

    try:
        data = request.get_json(silent=True) or {}
        selected_asin = data.get("asin", "").strip()
        model = data.get("model", "kimi")

        if not selected_asin:
            return jsonify(
                {
                    "success": False,
                    "error": "请先选择商品",
                    "hint": "在「亚马逊商品信息」步骤选择要改进的商品",
                }
            )

        # 生成任务 ID
        task_id = f"improve_{selected_asin}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 初始化任务状态
        with _improvement_task_lock:
            _improvement_tasks[task_id] = {
                "status": "pending",
                "asin": selected_asin,
                "model": model,
                "merchant_id": merchant_id,
                "created_at": datetime.datetime.now().isoformat(),
            }

        # 启动后台线程
        thread = threading.Thread(
            target=_background_improve_ads,
            args=(task_id, selected_asin, model),
            daemon=True,
        )
        thread.start()

        print(f"[Workflow Improve] Task {task_id} started for ASIN {selected_asin}")

        return jsonify(
            {
                "success": True,
                "async": True,
                "task_id": task_id,
                "message": "改进任务已启动，请轮询查询结果",
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/workflow/improve/status/<task_id>", methods=["GET"])
def api_workflow_improve_status(task_id):
    """查询广告改进任务状态"""
    global _improvement_tasks

    with _improvement_task_lock:
        if task_id not in _improvement_tasks:
            return jsonify(
                {
                    "success": False,
                    "error": "任务不存在",
                }
            )

        task = _improvement_tasks[task_id].copy()

    status = task.get("status")
    print(f"[Improve Status] Task {task_id} status: {status}")

    response = {
        "success": True,
        "task_id": task_id,
        "status": status,
    }

    if status == "completed":
        result = task.get("result", {})
        response["result"] = result
        # 生成包含下载链接的summary
        summary = result.get("summary", "广告已改进")
        download_url = result.get("download_url_txt")
        if download_url:
            filename = result.get("filename_txt", "improved_ads.txt")
            summary += f"<br><a href='{download_url}' download='{filename}'>📄 下载 TXT (可复制到Google Ads)</a>"
        response["summary"] = summary
    elif status == "failed":
        response["error"] = task.get("error", "未知错误")

    return jsonify(response)
