"""
Google Ads 广告生成引擎 v1.0
=====================================
按 ASIN 按需生成完整 Google Ads 广告方案，并写入数据库。

遵循 google-ads-creation Skill v4.0 规范：
- Campaign 双层级结构（5-6 个 Campaign）
- 15 个标题（≤30字符）+ 5 个描述（≤90字符）
- 否定关键词三级架构
- 广告扩展（Sitelink / Callout / Structured Snippet）
- 出价策略三阶段演进

用法:
    python -X utf8 generate_ads.py --asin B09G1Z83GM
    python -X utf8 generate_ads.py --asin B09G1Z83GM --force   # 覆盖已有方案
"""
import argparse
import json
import math
import re
import sys
import mysql.connector
from datetime import datetime

DB = dict(host='localhost', port=3306, user='root', password='admin',
          database='affiliate_marketing', charset='utf8mb4')

# ─── 账户级通用否定关键词（所有 Campaign 共享） ───────────────────────────────
ACCOUNT_NEGATIVES = [
    "-setup", "-installation", "-manual", "-instructions", "-\"how to\"",
    "-tutorial", "-guide", "-settings", "-configure",
    "-troubleshooting", "-repair", "-fix", "-broken", "-\"not working\"",
    "-problem", "-issue", "-error",
    "-warranty", "-service", "-support", "-help",
    "-\"replacement parts\"", "-\"spare parts\"",
    "-return", "-refund", "-exchange", "-complaint",
    "-contact", "-\"phone number\"", "-\"customer service\"",
    "-free", "-diy", "-\"do it yourself\"", "-homemade",
    "-\"make your own\"", "-used", "-\"second hand\"", "-rental",
    "-login", "-\"sign in\"", "-\"sign up\"", "-account", "-password",
    "-review", "-reviews", "-\"near me\"", "-website", "-app",
    "-ingredients", "-nutrition", "-\"side effects\"", "-recall",
]


def get_db():
    return mysql.connector.connect(**DB)


def get_product_info(conn, asin: str) -> dict | None:
    """从 yp_products + yp_merchants + amazon_product_details 拉取商品完整信息
    
    注意：使用 LEFT JOIN 连接 yp_merchants，因为某些商品的 merchant_id 在商户表中可能不存在
    """
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT
            p.asin, p.product_name, p.price, p.commission, p.tracking_url, p.amazon_url,
            p.merchant_id, 
            COALESCE(m.merchant_name, p.merchant_name) AS merchant_name,
            m.website, m.avg_payout, m.cookie_days,
            m.country,
            a.title          AS amz_title,
            a.brand          AS amz_brand,
            a.price          AS amz_price,
            a.rating,
            a.review_count,
            a.bullet_points  AS bullets,
            a.description    AS amz_desc,
            a.main_image_url AS image_url,
            a.keywords       AS amz_keywords
        FROM yp_products p
        LEFT JOIN yp_merchants m ON CONVERT(p.merchant_id USING utf8mb4) = CONVERT(m.merchant_id USING utf8mb4)
        LEFT JOIN amazon_product_details a ON CONVERT(p.asin USING utf8mb4) = CONVERT(a.asin USING utf8mb4)
        WHERE CONVERT(p.asin USING utf8mb4) = %s
        LIMIT 1
    """, (asin,))
    row = cur.fetchone()
    cur.close()
    return row


def get_brand_keywords(conn, merchant_id: str) -> list[str]:
    """获取商户品牌关键词"""
    cur = conn.cursor()
    cur.execute("""
        SELECT keyword, keyword_source FROM ads_merchant_keywords
        WHERE CONVERT(merchant_id USING utf8mb4) = %s
        ORDER BY keyword_source, keyword
    """, (str(merchant_id),))
    rows = cur.fetchall()
    cur.close()
    # 优先 autocomplete，其次 related
    auto = [r[0] for r in rows if r[1] == 'autocomplete']
    related = [r[0] for r in rows if r[1] == 'related']
    return auto + related


def to_float(val) -> float:
    """安全转换为 float，支持带 $ 前缀的字符串"""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace('$', '').replace(',', '').strip())
    except Exception:
        return 0.0


def calc_target_cpa(price, commission_pct) -> float:
    """目标CPA = 商品价格 × 佣金率 × 0.7"""
    try:
        p = to_float(price)
        c = to_float(commission_pct) / 100
        return round(p * c * 0.7, 2)
    except Exception:
        return 0.0


def clean_headline(text: str, max_len=30) -> str:
    """确保标题不超过30字符"""
    text = text.strip()
    if len(text) <= max_len:
        return text
    # 截断到最后一个空格
    return text[:max_len].rsplit(' ', 1)[0].strip()


def clean_description(text: str, max_len=90) -> str:
    """确保描述不超过90字符"""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0].strip()


def fmt_price(p):
    """格式化价格"""
    try:
        return f"${to_float(p):.2f}"
    except Exception:
        return "$--"


def fmt_commission(c):
    """格式化佣金"""
    try:
        return f"{to_float(str(c).replace('%','').strip()):.1f}%"
    except Exception:
        return "--%"


def parse_bullets(bullets_raw) -> list[str]:
    """解析 bullet_points（可能是 JSON 字符串或换行分隔文本）"""
    if not bullets_raw:
        return []
    try:
        data = json.loads(bullets_raw)
        if isinstance(data, list):
            return [str(b).strip() for b in data if b]
    except Exception:
        pass
    # 换行分隔
    lines = [l.strip().strip('•·-').strip() for l in str(bullets_raw).split('\n') if l.strip()]
    return [l for l in lines if len(l) > 5][:8]


def build_campaigns(prod: dict, brand_kws: list[str], target_cpa: float) -> list[dict]:
    """构建 Campaign 列表（符合 google-ads-creation v4.0 规范）"""
    brand = (prod.get('amz_brand') or prod.get('merchant_name') or '').strip()
    product_name = (prod.get('amz_title') or prod.get('product_name') or '').strip()
    asin = prod['asin']
    price = prod.get('amz_price') or prod.get('price')
    commission = prod.get('commission')
    rating = prod.get('rating') or '4.5'
    review_count = prod.get('review_count') or '100+'
    bullets = parse_bullets(prod.get('bullets'))

    # 清理品牌名（用于 Campaign 命名）
    brand_slug = re.sub(r'[^A-Za-z0-9 ]', '', brand).strip().replace(' ', '-')[:20]

    # 提取简短产品描述（用于 Campaign 命名）
    # 取商品名称前几个词
    pname_words = re.sub(r'[^A-Za-z0-9 ]', ' ', product_name).split()
    product_slug = '-'.join(pname_words[:3]) if pname_words else 'Product'

    campaigns = []

    # ── Campaign 1: Brand ──────────────────────────────────────────────────────
    brand_kws_lower = [k.lower() for k in brand_kws]
    brand_headlines = _gen_brand_headlines(brand, product_name, price, rating, review_count)
    brand_descriptions = _gen_brand_descriptions(brand, product_name, price, commission, bullets)

    campaigns.append({
        'campaign_name': f"{brand_slug}-Brand",
        'journey_stage': 'Brand',
        'budget_pct': 12,
        'daily_budget_usd': _suggest_budget(target_cpa, 0.12),
        'negative_keywords': ACCOUNT_NEGATIVES,
        'bid_strategy': 'Manual CPC → Max Conversions → Target CPA',
        'ad_groups': [
            {
                'ad_group_name': 'Brand-Exact',
                'theme': f'{brand} brand exact match',
                'user_intent': f'User searching for {brand} brand directly',
                'keywords': _build_brand_keywords(brand, brand_kws[:5], 'exact'),
                'negative_keywords': [],
                'cpc_bid_usd': 1.2,
                'ads': [_build_ad(brand_headlines, brand_descriptions, prod, 'A')]
            },
            {
                'ad_group_name': 'Brand-Product',
                'theme': f'{brand} + product terms',
                'user_intent': f'User looking for {brand} specific product',
                'keywords': _build_brand_keywords(brand, brand_kws[5:10], 'phrase'),
                'negative_keywords': [],
                'cpc_bid_usd': 1.0,
                'ads': [_build_ad(brand_headlines, brand_descriptions, prod, 'B')]
            },
        ]
    })

    # ── Campaign 2: Problem Awareness ─────────────────────────────────────────
    prob_headlines, prob_descriptions = _gen_problem_awareness(brand, product_name, price, bullets, rating)
    campaigns.append({
        'campaign_name': f"{brand_slug}-{product_slug}-Problem-Awareness",
        'journey_stage': 'Problem-Awareness',
        'budget_pct': 20,
        'daily_budget_usd': _suggest_budget(target_cpa, 0.20),
        'negative_keywords': ACCOUNT_NEGATIVES,
        'bid_strategy': 'Manual CPC',
        'ad_groups': [
            {
                'ad_group_name': 'Problem-Discovery',
                'theme': 'User discovers they have a problem this product solves',
                'user_intent': 'Searching for solutions to problems this product addresses',
                'keywords': _gen_problem_keywords(product_name, bullets),
                'negative_keywords': ['-buy', '-purchase', '-order', f'-{brand.lower()}'],
                'cpc_bid_usd': 0.8,
                'ads': [_build_ad(prob_headlines, prob_descriptions, prod, 'A')]
            },
        ]
    })

    # ── Campaign 3: Solution Evaluation ───────────────────────────────────────
    sol_headlines, sol_descriptions = _gen_solution_eval(brand, product_name, price, rating, review_count, bullets)
    campaigns.append({
        'campaign_name': f"{brand_slug}-{product_slug}-Solution-Evaluation",
        'journey_stage': 'Solution-Evaluation',
        'budget_pct': 18,
        'daily_budget_usd': _suggest_budget(target_cpa, 0.18),
        'negative_keywords': ACCOUNT_NEGATIVES,
        'bid_strategy': 'Manual CPC',
        'ad_groups': [
            {
                'ad_group_name': 'Comparison-Best',
                'theme': 'Best / Top / Review comparison searches',
                'user_intent': 'Comparing products before buying',
                'keywords': _gen_comparison_keywords(product_name, brand),
                'negative_keywords': ['-setup', '-install', '-how to use'],
                'cpc_bid_usd': 1.0,
                'ads': [_build_ad(sol_headlines, sol_descriptions, prod, 'A')]
            },
        ]
    })

    # ── Campaign 4: Feature Exploration ───────────────────────────────────────
    feat_headlines, feat_descriptions = _gen_feature_exploration(brand, product_name, price, bullets, rating, review_count)
    campaigns.append({
        'campaign_name': f"{brand_slug}-{product_slug}-Feature-Exploration",
        'journey_stage': 'Feature-Exploration',
        'budget_pct': 22,
        'daily_budget_usd': _suggest_budget(target_cpa, 0.22),
        'negative_keywords': ACCOUNT_NEGATIVES,
        'bid_strategy': 'Manual CPC',
        'ad_groups': [
            {
                'ad_group_name': 'Feature-Specific',
                'theme': 'Specific product features and capabilities',
                'user_intent': 'Searching for specific features in this product category',
                'keywords': _gen_feature_keywords(product_name, bullets),
                'negative_keywords': [],
                'cpc_bid_usd': 0.9,
                'ads': [_build_ad(feat_headlines, feat_descriptions, prod, 'A')]
            },
        ]
    })

    # ── Campaign 5: Purchase Decision ─────────────────────────────────────────
    purch_headlines, purch_descriptions = _gen_purchase_decision(brand, product_name, price, commission, rating, review_count)
    campaigns.append({
        'campaign_name': f"{brand_slug}-{product_slug}-Purchase-Decision",
        'journey_stage': 'Purchase-Decision',
        'budget_pct': 28,
        'daily_budget_usd': _suggest_budget(target_cpa, 0.28),
        'negative_keywords': ACCOUNT_NEGATIVES,
        'bid_strategy': 'Manual CPC → Max Conversions → Target CPA',
        'ad_groups': [
            {
                'ad_group_name': 'Buy-Now',
                'theme': 'High purchase intent – buy / order / shop',
                'user_intent': 'Ready to purchase, looking for the best deal',
                'keywords': _gen_buy_keywords(product_name, brand),
                'negative_keywords': ['-used', '-second hand', '-rental', '-diy'],
                'cpc_bid_usd': 1.8,
                'ads': [_build_ad(purch_headlines, purch_descriptions, prod, 'A'),
                        _build_ad(purch_headlines, purch_descriptions, prod, 'B')]
            },
        ]
    })

    return campaigns


# ─── 标题/描述生成器 ─────────────────────────────────────────────────────────

def _hl(text: str) -> dict:
    """标题条目，自动截断并标注字符数"""
    t = clean_headline(text)
    return {'text': t, 'chars': len(t)}


def _desc(text: str) -> dict:
    """描述条目，自动截断并标注字符数"""
    t = clean_description(text)
    return {'text': t, 'chars': len(t)}


def _gen_brand_headlines(brand, product_name, price, rating, review_count) -> list:
    """品牌广告系列 15 个标题"""
    b = brand[:15] if brand else 'Brand'
    p_short = ' '.join(product_name.split()[:3])[:20] if product_name else 'Product'
    price_str = fmt_price(price)
    rv = str(review_count).replace('(', '').replace(')', '') if review_count else '100+'

    headlines = [
        # 品牌+产品核心 (2)
        _hl(f"{b} Official Store"),
        _hl(f"{b} {p_short}"),
        # 社会证明 (2)
        _hl(f"{rv} Reviews – Shop {b}"),
        _hl(f"Rated {rating}/5 – {b}"),
        # 价格/促销 (2)
        _hl(f"{b} – From {price_str}"),
        _hl(f"Best Price on {b}"),
        # 行动号召 (2)
        _hl(f"Shop {b} on Amazon"),
        _hl(f"Buy {b} – Ships Free"),
        # 问题解决 (3)
        _hl(f"Top-Rated {p_short}"),
        _hl(f"{b} – #1 Choice"),
        _hl(f"Trusted {b} Products"),
        # 功能特点 (3)
        _hl(f"Premium {p_short}"),
        _hl(f"{b} – Quality Gear"),
        _hl(f"Authentic {b} Brand"),
        # 差异化 (1)
        _hl(f"Ships via Amazon Prime"),
    ]
    return headlines[:15]


def _gen_brand_descriptions(brand, product_name, price, commission, bullets) -> list:
    b = brand or 'This brand'
    price_str = fmt_price(price)
    feature = bullets[0][:40] if bullets else 'premium quality product'

    descs = [
        _desc(f"Shop official {b} products on Amazon. {feature}. {price_str}. Free Prime shipping."),
        _desc(f"Looking for {b}? Find the best selection on Amazon. Easy returns, secure checkout."),
        _desc(f"{b} delivers top-rated products w/ thousands of verified reviews. Shop now on Amazon."),
        _desc(f"Get {b} today – {feature}. Prime shipping available. Trusted by thousands of buyers."),
        _desc(f"{b} products starting at {price_str}. 30-day easy returns. Secure Amazon checkout."),
    ]
    return descs[:5]


def _gen_problem_awareness(brand, product_name, price, bullets, rating) -> tuple:
    pname = ' '.join(product_name.split()[:4]) if product_name else 'this product'
    b1 = bullets[0][:35] if bullets else 'solves your problem'
    b2 = bullets[1][:35] if len(bullets) > 1 else 'proven results'

    headlines = [
        _hl(f"Struggling w/ {pname[:20]}?"),
        _hl(f"Finally – {pname[:22]}"),
        _hl(f"Fix It With {brand[:18]}"),
        _hl(f"Solve It Now – {brand[:15]}"),
        _hl(f"Rated {rating}/5 Stars"),
        _hl(f"Thousands Trust {brand[:13]}"),
        _hl(f"Works. Proven. Delivered."),
        _hl(f"See Results – Shop Now"),
        _hl(f"Top Solution Available"),
        _hl(f"Amazon's Top Pick"),
        _hl(f"{brand[:20]} – It Works"),
        _hl(f"Real Results, Real People"),
        _hl(f"Don't Settle – Get {brand[:11]}"),
        _hl(f"Trusted by 10K+ Buyers"),
        _hl(f"Shop {brand[:23]} Today"),
    ]

    descriptions = [
        _desc(f"Tired of the same problem? {b1}. Try {brand} – rated {rating}/5 by real customers."),
        _desc(f"{b1}. {brand} delivers results where others fail. Buy on Amazon w/ free returns."),
        _desc(f"Thousands solved this problem with {brand}. See why on Amazon. {fmt_price(None)} starts here."),
        _desc(f"{b2}. {brand} – the proven solution. Ships free with Prime. Easy 30-day returns."),
        _desc(f"Stop dealing with it. {brand} works. Rated {rating}/5. Buy on Amazon today."),
    ]
    return headlines[:15], descriptions[:5]


def _gen_solution_eval(brand, product_name, price, rating, review_count, bullets) -> tuple:
    pname = ' '.join(product_name.split()[:3]) if product_name else 'this product'
    rv = str(review_count).replace('(', '').replace(')', '') if review_count else '500+'
    price_str = fmt_price(price)

    headlines = [
        _hl(f"Best {pname[:22]} 2025"),
        _hl(f"Top-Rated {pname[:20]}"),
        _hl(f"{brand[:20]} vs Others"),
        _hl(f"Why {brand[:20]} Wins"),
        _hl(f"{rv} Reviews Agree"),
        _hl(f"Rated {rating}/5 Stars"),
        _hl(f"Amazon's Choice – {brand[:11]}"),
        _hl(f"#1 Best Seller Option"),
        _hl(f"Compare & Save on {brand[:11]}"),
        _hl(f"Experts Recommend {brand[:11]}"),
        _hl(f"See Full Comparison"),
        _hl(f"Side-by-Side Reviews"),
        _hl(f"Quality You Can Trust"),
        _hl(f"{price_str} – Beat Competitors"),
        _hl(f"Shop Smarter – {brand[:14]}"),
    ]

    descriptions = [
        _desc(f"Looking for the best {pname}? {brand} leads with {rating}/5 stars & {rv} reviews. Buy on Amazon."),
        _desc(f"{brand} vs the rest: better quality, real results, {rv} verified reviews. Compare now."),
        _desc(f"Why choose {brand}? {rating}-star rated, {rv}+ reviews, ships free. Start comparing today."),
        _desc(f"Don't overpay. {brand} delivers premium {pname} at {price_str}. Free returns on Amazon."),
        _desc(f"Customers say {brand} beats competitors. See {rv} reviews on Amazon. Order today."),
    ]
    return headlines[:15], descriptions[:5]


def _gen_feature_exploration(brand, product_name, price, bullets, rating, review_count) -> tuple:
    b1 = bullets[0][:35] if bullets else 'premium feature'
    b2 = bullets[1][:35] if len(bullets) > 1 else 'advanced design'
    b3 = bullets[2][:35] if len(bullets) > 2 else 'easy to use'
    pname = ' '.join(product_name.split()[:3]) if product_name else 'product'
    price_str = fmt_price(price)

    headlines = [
        _hl(f"{pname[:28]} Features"),
        _hl(f"Advanced {pname[:20]}"),
        _hl(f"{brand[:20]} Key Features"),
        _hl(f"Built for Performance"),
        _hl(f"Premium {pname[:21]} Design"),
        _hl(f"See All {brand[:21]} Features"),
        _hl(f"Engineered to Last"),
        _hl(f"Works Right Out of Box"),
        _hl(f"Easy Setup, Big Results"),
        _hl(f"Features Competitors Lack"),
        _hl(f"Rated {rating}/5 for Quality"),
        _hl(f"Get {brand[:22]} Features"),
        _hl(f"{price_str} – Worth It"),
        _hl(f"Shop Full {brand[:20]}"),
        _hl(f"Premium at a Fair Price"),
    ]

    descriptions = [
        _desc(f"{brand}: {b1}. {b2}. See all features on Amazon. {price_str}."),
        _desc(f"What makes {brand} different? {b1}. {b3}. Rated {rating}/5. Shop now."),
        _desc(f"{b1}. {b2}. {brand} – built for real use. Free Prime shipping. Buy on Amazon."),
        _desc(f"Explore {brand} features: {b1}. Easy to use. {price_str}. 30-day returns."),
        _desc(f"Every detail matters. {brand}: {b3}. {price_str}. Thousands of 5-star reviews."),
    ]
    return headlines[:15], descriptions[:5]


def _gen_purchase_decision(brand, product_name, price, commission, rating, review_count) -> tuple:
    pname = ' '.join(product_name.split()[:3]) if product_name else 'product'
    price_str = fmt_price(price)
    rv = str(review_count).replace('(', '').replace(')', '') if review_count else '500+'

    headlines = [
        _hl(f"Buy {pname[:24]} Now"),
        _hl(f"Order {brand[:23]} Today"),
        _hl(f"Shop {brand[:22]} – Amazon"),
        _hl(f"{price_str} – Free Shipping"),
        _hl(f"Ships Free w/ Prime"),
        _hl(f"30-Day Easy Returns"),
        _hl(f"Secure Amazon Checkout"),
        _hl(f"Get It by Tomorrow"),
        _hl(f"Limited Stock – Act Fast"),
        _hl(f"Best Value – {brand[:18]}"),
        _hl(f"{rv} Happy Customers"),
        _hl(f"Rated {rating}/5 – Buy Now"),
        _hl(f"Free Prime Delivery"),
        _hl(f"Shop {brand[:22]} Official"),
        _hl(f"Amazon's Choice Product"),
    ]

    descriptions = [
        _desc(f"Buy {brand} on Amazon. {price_str}. Free Prime shipping. {rv} reviews, {rating}/5 stars. Order now."),
        _desc(f"Ready to buy {brand}? {price_str}. Secure Amazon checkout. Free returns. Ships fast."),
        _desc(f"{rv} customers chose {brand}. {price_str}. Amazon's Choice. Free shipping. Buy today."),
        _desc(f"Get {brand} delivered tomorrow. {price_str}. 30-day returns. Trusted by thousands."),
        _desc(f"Don't wait – {brand} at {price_str}. Free Prime delivery. Easy returns. Shop now."),
    ]
    return headlines[:15], descriptions[:5]


def _build_ad(headlines: list, descriptions: list, prod: dict, variant: str) -> dict:
    """构建一个广告（含扩展）"""
    brand = prod.get('amz_brand') or prod.get('merchant_name') or ''
    product_name = prod.get('amz_title') or prod.get('product_name') or ''
    price_str = fmt_price(prod.get('amz_price') or prod.get('price'))

    # 广告扩展
    sitelinks = [
        {'text': 'Read All Reviews', 'desc1': 'Verified buyer reviews', 'desc2': 'See what people say'},
        {'text': 'Free Shipping Info', 'desc1': 'Prime shipping available', 'desc2': 'Fast delivery options'},
        {'text': '30-Day Returns', 'desc1': 'Easy hassle-free returns', 'desc2': 'Shop with confidence'},
        {'text': 'Compare Models', 'desc1': 'Find your best match', 'desc2': 'Side-by-side guide'},
        {'text': 'Best Sellers', 'desc1': f'Top {brand} products', 'desc2': 'Curated for you'},
        {'text': 'Product Details', 'desc1': 'Full specs and features', 'desc2': 'All the info you need'},
    ]

    callouts = [
        'Free Prime Shipping',
        '30-Day Free Returns',
        'Secure Amazon Checkout',
        'Fast 2-Day Delivery',
        'Trusted Brand',
        'Verified Reviews',
    ]

    # Structured Snippet – 从 bullet points 提取
    bullets = parse_bullets(prod.get('bullets'))
    snippet_vals = []
    for b in bullets[:6]:
        # 取前几个词
        words = b.split()[:4]
        val = ' '.join(words)[:25]
        if val:
            snippet_vals.append(val)
    if not snippet_vals:
        snippet_vals = ['Premium Quality', 'Easy to Use', 'Fast Delivery']

    structured_snippet = {
        'header': 'Features',
        'values': snippet_vals[:10]
    }

    # 出价策略三阶段
    bidding_phases = [
        {'phase': 1, 'weeks': '1-2', 'strategy': 'Manual CPC', 'note': 'High intent $1.5-3.0, mid $0.8-1.5, low $0.4-0.8'},
        {'phase': 2, 'weeks': '2-4', 'strategy': 'Max Conversions', 'note': 'Switch after 15+ conversions'},
        {'phase': 3, 'weeks': '4+', 'strategy': 'Target CPA', 'note': 'Switch after 30+ conversions'},
    ]

    # A 变体：功能主导；B 变体：情感主导（重排顺序，突出不同角度）
    if variant == 'B':
        # B 变体调换部分标题顺序，突出情感/社会证明
        hl_reordered = headlines[2:5] + headlines[0:2] + headlines[5:]
    else:
        hl_reordered = headlines

    # 质检
    bad_headlines = [h for h in hl_reordered if h['chars'] > 30]
    bad_descs = [d for d in descriptions if d['chars'] > 90]
    all_valid = len(bad_headlines) == 0 and len(bad_descs) == 0

    notes = []
    if bad_headlines:
        notes.append(f"{len(bad_headlines)} headlines exceed 30 chars")
    if bad_descs:
        notes.append(f"{len(bad_descs)} descriptions exceed 90 chars")

    return {
        'variant': variant,
        'headlines': hl_reordered[:15],
        'descriptions': descriptions[:5],
        'sitelinks': sitelinks,
        'callouts': callouts,
        'structured_snippet': structured_snippet,
        'final_url': prod.get('tracking_url') or prod.get('amazon_url') or '',
        'display_url': f"amazon.com/{brand.replace(' ','-')[:20]}/{' '.join((prod.get('amz_title') or '').split()[:2]).replace(' ','-')[:20]}",
        'headline_count': len(hl_reordered[:15]),
        'description_count': len(descriptions[:5]),
        'all_chars_valid': 1 if all_valid else 0,
        'quality_notes': '; '.join(notes) if notes else 'All checks passed',
        'bidding_phases': bidding_phases,
    }


# ─── 关键词生成器 ────────────────────────────────────────────────────────────

def _build_brand_keywords(brand: str, extra_kws: list, match_type: str = 'exact') -> list:
    """品牌关键词组"""
    b = brand.lower().strip()
    mt = {'exact': 'E', 'phrase': 'P', 'broad': 'B'}.get(match_type, 'E')
    kws = [{'type': mt, 'kw': b}]
    # 加上 Google Suggest 采集的品牌词
    for kw in extra_kws[:8]:
        k = kw.lower().strip()
        if k and k != b:
            kws.append({'type': 'P', 'kw': k})
    return kws[:12]


def _gen_problem_keywords(product_name: str, bullets: list) -> list:
    """问题意识阶段关键词（8-12个）"""
    pname = product_name.lower()
    words = re.sub(r'[^a-z0-9 ]', ' ', pname).split()
    core = ' '.join(words[:3]) if words else 'product'

    base = [
        {'type': 'B', 'kw': f'best {core}'},
        {'type': 'P', 'kw': f'"{core} for home"'},
        {'type': 'P', 'kw': f'"{core} that works"'},
        {'type': 'B', 'kw': f'{core} solution'},
        {'type': 'B', 'kw': f'top {core}'},
        {'type': 'P', 'kw': f'"need a {core}"'},
        {'type': 'B', 'kw': f'{core} help'},
        {'type': 'B', 'kw': f'fix {core} problem'},
    ]
    return base[:12]


def _gen_comparison_keywords(product_name: str, brand: str) -> list:
    """比较评估阶段关键词"""
    pname_clean = re.sub(r'[^a-z0-9 ]', ' ', product_name.lower())
    core = ' '.join(pname_clean.split()[:3])
    b = brand.lower()

    return [
        {'type': 'P', 'kw': f'"best {core} review"'},
        {'type': 'P', 'kw': f'"top {core} 2025"'},
        {'type': 'B', 'kw': f'{core} vs'},
        {'type': 'P', 'kw': f'"{core} comparison"'},
        {'type': 'P', 'kw': f'"is {b} worth it"'},
        {'type': 'B', 'kw': f'{b} review'},
        {'type': 'P', 'kw': f'"{b} vs"'},
        {'type': 'B', 'kw': f'best {b} products'},
        {'type': 'P', 'kw': f'"rated {core}"'},
        {'type': 'B', 'kw': f'{core} recommendations'},
    ][:12]


def _gen_feature_keywords(product_name: str, bullets: list) -> list:
    """功能探索阶段关键词"""
    pname_clean = re.sub(r'[^a-z0-9 ]', ' ', product_name.lower())
    core = ' '.join(pname_clean.split()[:3])

    # 从 bullets 里提取功能词
    feat_kws = []
    for b in bullets[:3]:
        words = b.lower().split()[:4]
        feat_kw = ' '.join(words)
        feat_kws.append({'type': 'B', 'kw': f'{core} {feat_kw}'[:80]})

    base = [
        {'type': 'P', 'kw': f'"{core} features"'},
        {'type': 'B', 'kw': f'{core} how it works'},
        {'type': 'P', 'kw': f'"{core} specifications"'},
        {'type': 'B', 'kw': f'premium {core}'},
    ]
    return (feat_kws + base)[:12]


def _gen_buy_keywords(product_name: str, brand: str) -> list:
    """购买决策阶段关键词（高意图）"""
    pname_clean = re.sub(r'[^a-z0-9 ]', ' ', product_name.lower())
    core = ' '.join(pname_clean.split()[:3])
    b = brand.lower()

    return [
        {'type': 'E', 'kw': f'buy {core}'},
        {'type': 'E', 'kw': f'order {b}'},
        {'type': 'P', 'kw': f'"{core} amazon"'},
        {'type': 'P', 'kw': f'"buy {b} online"'},
        {'type': 'E', 'kw': f'{b} price'},
        {'type': 'P', 'kw': f'"{b} where to buy"'},
        {'type': 'P', 'kw': f'"{core} free shipping"'},
        {'type': 'B', 'kw': f'{core} best deal'},
        {'type': 'P', 'kw': f'"shop {b}"'},
        {'type': 'B', 'kw': f'{b} discount'},
    ][:12]


def _suggest_budget(target_cpa: float, pct: float) -> float:
    """基于 CPA 推算每日预算"""
    if not target_cpa or target_cpa <= 0:
        return round(5.0 * pct * 10, 2)
    # 假设每天至少能产生 1 次转化：daily_budget = target_cpa × 3 × pct_share
    return round(target_cpa * 3 * pct * 10, 2)


# ─── 写入数据库 ───────────────────────────────────────────────────────────────

def save_plan_to_db(conn, prod: dict, campaigns: list, brand_kws: list, target_cpa: float):
    """将广告方案写入 ads_plans / ads_campaigns / ads_ad_groups / ads_ads"""
    cur = conn.cursor()
    asin = prod['asin']
    mid = str(prod.get('merchant_id', ''))
    price = prod.get('amz_price') or prod.get('price')
    commission = prod.get('commission')

    # 1. 删除旧方案（如果 --force）
    cur.execute("SELECT id FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
    existing = cur.fetchone()
    if existing:
        plan_id = existing[0]
        # 级联删除（外键 ON DELETE CASCADE 已设置）
        cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))
        cur.execute("DELETE FROM ads_plans WHERE asin=%s", (asin,))
        conn.commit()

    # 2. 写 ads_plans（汇总行）
    cur.execute("""
        INSERT INTO ads_plans
            (asin, merchant_id, merchant_name, product_name, product_price,
             commission_pct, target_cpa, brand_keywords_used,
             has_amazon_data, plan_status, generated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed',NOW())
    """, (
        asin, mid,
        prod.get('merchant_name'),
        prod.get('amz_title') or prod.get('product_name'),
        to_float(price) or None,
        to_float(str(commission).replace('%','')) or None,
        target_cpa,
        json.dumps(brand_kws[:20], ensure_ascii=False),
        1 if prod.get('amz_title') else 0,
    ))
    conn.commit()
    plan_id = cur.lastrowid

    total_campaigns = total_groups = total_ads = 0

    for camp in campaigns:
        # 3. 写 ads_campaigns
        cur.execute("""
            INSERT INTO ads_campaigns
                (asin, merchant_id, merchant_name,
                 campaign_name, journey_stage, budget_pct, daily_budget_usd,
                 product_price, commission_pct, commission_usd, target_cpa,
                 negative_keywords, bid_strategy, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft')
        """, (
            asin, mid, prod.get('merchant_name'),
            camp['campaign_name'], camp['journey_stage'],
            camp.get('budget_pct'), camp.get('daily_budget_usd'),
            float(to_float(price)) if price else None,
            float(str(commission).replace('%','').strip()) if commission else None,
            round(to_float(price) * to_float(str(commission).replace('%','')) / 100, 4),
            target_cpa,
            json.dumps(camp.get('negative_keywords', []), ensure_ascii=False),
            camp.get('bid_strategy'),
        ))
        conn.commit()
        campaign_id = cur.lastrowid
        total_campaigns += 1

        for grp in camp.get('ad_groups', []):
            # 4. 写 ads_ad_groups
            kws = grp.get('keywords', [])
            cur.execute("""
                INSERT INTO ads_ad_groups
                    (campaign_id, ad_group_name, theme, user_intent,
                     keywords, negative_keywords, keyword_count, cpc_bid_usd, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')
            """, (
                campaign_id,
                grp['ad_group_name'],
                grp.get('theme', ''),
                grp.get('user_intent', ''),
                json.dumps(kws, ensure_ascii=False),
                json.dumps(grp.get('negative_keywords', []), ensure_ascii=False),
                len(kws),
                grp.get('cpc_bid_usd'),
            ))
            conn.commit()
            ad_group_id = cur.lastrowid
            total_groups += 1

            for ad in grp.get('ads', []):
                # 5. 写 ads_ads
                cur.execute("""
                    INSERT INTO ads_ads
                        (ad_group_id, campaign_id, asin, variant,
                         headlines, descriptions,
                         sitelinks, callouts, structured_snippet,
                         final_url, display_url,
                         headline_count, description_count, all_chars_valid, quality_notes,
                         bidding_phases, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft')
                """, (
                    ad_group_id, campaign_id, asin, ad['variant'],
                    json.dumps(ad['headlines'], ensure_ascii=False),
                    json.dumps(ad['descriptions'], ensure_ascii=False),
                    json.dumps(ad.get('sitelinks', []), ensure_ascii=False),
                    json.dumps(ad.get('callouts', []), ensure_ascii=False),
                    json.dumps(ad.get('structured_snippet', {}), ensure_ascii=False),
                    ad.get('final_url', ''),
                    ad.get('display_url', ''),
                    ad.get('headline_count', 15),
                    ad.get('description_count', 5),
                    ad.get('all_chars_valid', 0),
                    ad.get('quality_notes', ''),
                    json.dumps(ad.get('bidding_phases', []), ensure_ascii=False),
                ))
                total_ads += 1

    conn.commit()

    # 更新 ads_plans 统计
    cur.execute("""
        UPDATE ads_plans
        SET campaign_count=%s, ad_group_count=%s, ad_count=%s
        WHERE asin=%s
    """, (total_campaigns, total_groups, total_ads, asin))
    conn.commit()
    cur.close()

    return plan_id, total_campaigns, total_groups, total_ads


# ─── 主函数 ──────────────────────────────────────────────────────────────────

def generate_ads_for_asin(asin: str, force: bool = False) -> dict:
    """为指定 ASIN 生成完整广告方案，返回结果摘要"""
    conn = get_db()

    # 检查是否已有方案
    cur = conn.cursor()
    cur.execute("SELECT id, plan_status, generated_at FROM ads_plans WHERE asin=%s LIMIT 1", (asin,))
    existing = cur.fetchone()
    cur.close()

    # plan_status=None 或 'generating' 表示上次失败/未完成，自动允许重新生成
    existing_status = existing[1] if existing else None
    if existing and existing_status == 'completed' and not force:
        return {
            'success': False,
            'message': f"Plan already exists (id={existing[0]}, status={existing[1]}, generated={existing[2]}). Use --force to regenerate.",
            'asin': asin,
        }

    # 获取商品信息
    prod = get_product_info(conn, asin)
    if not prod:
        conn.close()
        return {'success': False, 'message': f'ASIN {asin} not found in yp_products', 'asin': asin}

    has_amazon_data = bool(prod.get('amz_title'))
    brand = prod.get('amz_brand') or prod.get('merchant_name') or 'Brand'
    price = prod.get('amz_price') or prod.get('price')
    commission = prod.get('commission')

    # 获取品牌关键词
    mid = str(prod.get('merchant_id', ''))
    brand_kws = get_brand_keywords(conn, mid)

    # 计算目标 CPA（清洗价格和佣金率后再算）
    price_num = to_float(price)
    commission_num = to_float(str(commission or '').replace('%', ''))
    target_cpa = round(price_num * commission_num / 100 * 0.7, 2)

    print(f"\n{'='*60}")
    print(f"ASIN:         {asin}")
    print(f"Product:      {str(prod.get('amz_title') or prod.get('product_name'))[:50]}")
    print(f"Brand:        {brand}")
    print(f"Price:        {fmt_price(price)}")
    print(f"Commission:   {fmt_commission(commission)}")
    print(f"Target CPA:   ${target_cpa:.2f}")
    print(f"Brand KWs:    {len(brand_kws)} keywords available")
    print(f"Amazon Data:  {'YES' if has_amazon_data else 'NO (limited data)'}")
    print(f"{'='*60}")

    if not has_amazon_data:
        print("  [WARN] No Amazon product details found.")
        print("  Generating basic ads without Amazon data...")
        print("  Tip: Run scrape_amazon_details.py to fetch Amazon data for this ASIN.")

    # 生成广告方案
    print("\nGenerating campaigns...")
    campaigns = build_campaigns(prod, brand_kws, target_cpa)

    # 写入数据库
    print("Saving to database...")
    plan_id, n_campaigns, n_groups, n_ads = save_plan_to_db(conn, prod, campaigns, brand_kws, target_cpa)
    conn.close()

    print(f"\n[OK] Plan saved:")
    print(f"  plan_id:    {plan_id}")
    print(f"  campaigns:  {n_campaigns}")
    print(f"  ad groups:  {n_groups}")
    print(f"  ads:        {n_ads}")

    return {
        'success': True,
        'asin': asin,
        'plan_id': plan_id,
        'campaigns': n_campaigns,
        'ad_groups': n_groups,
        'ads': n_ads,
        'brand': brand,
        'target_cpa': target_cpa,
        'has_amazon_data': has_amazon_data,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate Google Ads for an ASIN')
    parser.add_argument('--asin', required=True, help='Amazon ASIN')
    parser.add_argument('--force', action='store_true', help='Regenerate even if plan exists')
    args = parser.parse_args()

    result = generate_ads_for_asin(args.asin, force=args.force)
    if not result['success']:
        print(f"\n[ERROR] {result['message']}")
        sys.exit(1)
