"""
Google Ads 广告生成引擎 v2.0
=====================================
v5.0 规范：产品品类智能分析 → 动态账户结构 → 关键词引擎重写 → 文案去模板化 → 后置QA检查

用法:
    python -X utf8 generate_ads_v2.py --asin B0CH88XS35
    python -X utf8 generate_ads_v2.py --asin B0CH88XS35 --force
"""
import argparse, json, re, sys, math
import mysql.connector

DB = dict(host='localhost', port=3306, user='root', password='admin',
          database='affiliate_marketing', charset='utf8mb4')

# ── 品类词库 ──
CATEGORY_KEYWORDS = {
    'jewelry': {
        'core': ['travel jewelry case','jewelry box','jewelry organizer','jewelry holder',
                 'travel jewelry organizer','portable jewelry box','small jewelry box',
                 'jewelry roll','necklace case','earring organizer','compact jewelry case'],
        'scenes': ['graduation gifts for her','birthday gifts for women under $10',
                   'stocking stuffers for women','bridesmaid gift ideas',
                   'gift for bestie under $10','travel jewelry case gift',
                   'small gift for girlfriend','gifts for mom under $20',
                   'anniversary gift for her','christmas gifts for women'],
        'features': ['compact','portable','small','velvet','personalized',
                     'lightweight','tangle free','zippered','gift box included'],
        'audience': ['for women','for her','for girls','for mom','for girlfriend'],
    },
    'pet': {
        'core': ['automatic pet feeder','dog stain remover','pet water fountain','dog crate','pet bed'],
        'scenes': ['for travel','for multi-cat','for large dogs','for puppies','for indoor cats'],
        'features': ['automatic','wifi','app control','large capacity','quiet','waterproof'],
        'audience': ['for dogs','for cats','for puppies'],
    },
    'electronics': {
        'core': ['wireless earbuds','phone charger','portable power bank','bluetooth speaker'],
        'scenes': ['for travel','for office','for gaming','for car'],
        'features': ['noise cancelling','waterproof','fast charging','compact','long battery'],
        'audience': ['for iphone','for android'],
    },
    'health': {
        'core': ['probiotic for dogs','joint supplement','face moisturizer','vitamin d drops'],
        'scenes': ['for sensitive stomach','for senior dogs','for dry skin','for anti aging'],
        'features': ['natural ingredients','vet recommended','organic','non gmo','made in usa'],
        'audience': ['for dogs','for cats','for men','for women'],
    },
}
CATEGORY_DETECT = {
    'jewelry': ['jewelry','necklace','earring','ring','bracelet','pendant','jewel case','jewel box','jewel organizer'],
    'pet': ['pet','dog','cat','puppy','kitten','feeder','litter','crate','leash','flea','grooming'],
    'electronics': ['earbuds','headphone','charger','cable','speaker','power bank','battery','bluetooth','wireless'],
    'health': ['supplement','probiotic','vitamin','protein','moisturizer','cream','serum','collagen','omega','skincare'],
}

# ── 工具函数 ──
def get_db(): return mysql.connector.connect(**DB)

def to_float(val):
    if val is None: return 0.0
    try: return float(str(val).replace('$','').replace(',','').strip())
    except: return 0.0

def fmt_price(p):
    v = to_float(p)
    return f"${v:.2f}" if v > 0 else "$--"

def fmt_commission(c):
    try: return f"{to_float(str(c).replace('%','').strip()):.1f}%"
    except: return "--%"

def parse_bullets(raw):
    if not raw: return []
    try:
        d = json.loads(raw)
        if isinstance(d, list): return [str(b).strip() for b in d if b]
    except: pass
    return [l.strip().lstrip('•').lstrip('-').strip() for l in str(raw).split('\n') if l.strip() and len(l.strip())>5][:8]

def clean_hl(t, mx=30):
    t = t.strip()
    return t[:mx].rsplit(' ',1)[0].strip() if len(t)>mx else t

def clean_desc(t, mx=90):
    t = t.strip()
    return t[:mx].rsplit(' ',1)[0].strip() if len(t)>mx else t

def hl(text): return {'text': clean_hl(text), 'chars': len(clean_hl(text))}
def desc(text): return {'text': clean_desc(text), 'chars': len(clean_desc(text))}

# ── 数据读取 ──
def get_product_info(conn, asin):
    cur = conn.cursor(dictionary=True)
    cur.execute("""SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url, p.amazon_url,
        p.merchant_id, COALESCE(m.merchant_name,p.merchant_name) AS merchant_name,
        m.country, a.title AS amz_title, a.brand AS amz_brand, a.price AS amz_price,
        a.rating, a.review_count, a.bullet_points AS bullets, a.description AS amz_desc,
        a.main_image_url AS image_url
        FROM yp_products p
        LEFT JOIN yp_merchants m ON CONVERT(p.merchant_id USING utf8mb4)=CONVERT(m.merchant_id USING utf8mb4)
        LEFT JOIN amazon_product_details a ON CONVERT(p.asin USING utf8mb4)=CONVERT(a.asin USING utf8mb4)
        WHERE CONVERT(p.asin USING utf8mb4)=%s LIMIT 1""", (asin,))
    row = cur.fetchone(); cur.close(); return row

def get_brand_keywords(conn, mid):
    cur = conn.cursor()
    cur.execute("""SELECT keyword FROM ads_merchant_keywords
        WHERE CONVERT(merchant_id USING utf8mb4)=%s ORDER BY keyword_source,keyword""", (str(mid),))
    rows = cur.fetchall(); cur.close()
    return [r[0] for r in rows]

# ── Step 1: 产品分析 ──
def _detect_category(title):
    t = title.lower()
    scores = {cat: sum(1 for kw in kws if kw in t) for cat,kws in CATEGORY_DETECT.items()}
    best = max(scores, key=scores.get) if scores else 'general'
    return best if scores[best]>0 else 'general'

def _detect_type(title):
    t = title.lower()
    gift_s = sum(1 for s in ['gift','birthday','graduation','holiday','present','christmas','valentine','stocking','bridesmaid','anniversary'] if s in t)
    pain_s = sum(1 for s in ['stain remover','cleaner','odor','protector','repair','waterproof','leak'] if s in t)
    effect_s = sum(1 for s in ['probiotic','whitening','anti-aging','supplement','collagen','serum'] if s in t)
    if gift_s>=2 or (gift_s>=1 and gift_s>pain_s and gift_s>effect_s): return 'gift'
    if pain_s>=2: return 'pain_point'
    if effect_s>=1: return 'effect'
    return 'mixed'

def _extract_kws(title, brand):
    tc = title.lower()
    bl = brand.lower()
    for attempt in [bl, bl.split()[0]]:
        if attempt and tc.startswith(attempt): tc = tc[len(attempt):].strip()
    words = re.sub(r'[^a-z0-9 ]',' ',tc).split()
    cat = _detect_category(title)
    cd = CATEGORY_KEYWORDS.get(cat,{})
    core = [kw for kw in cd.get('core',[]) if kw in tc] or [' '.join(words[:3])]
    scenes = [kw for kw in cd.get('scenes',[]) if kw in tc]
    features = [kw for kw in cd.get('features',[]) if kw in tc]
    audience = [kw for kw in cd.get('audience',[]) if kw in tc]
    return {'category':cat,'core':core,'scenes':scenes,'features':features,'audience':audience}

def analyze_product(prod):
    brand = (prod.get('amz_brand') or prod.get('merchant_name') or '').strip()
    title = (prod.get('amz_title') or prod.get('product_name') or '').strip()
    price = to_float(prod.get('amz_price') or prod.get('price'))
    comm_pct = to_float(str(prod.get('commission') or '0').replace('%',''))
    rating = prod.get('rating')
    review_count = prod.get('review_count')
    bullets = parse_bullets(prod.get('bullets'))
    comm_usd = round(price * comm_pct / 100, 3)
    target_cpa = round(comm_usd * 0.7, 2)
    cat = _detect_category(title)
    ptype = _detect_type(title)
    kw_ext = _extract_kws(title, brand)
    if comm_usd < 1.5: profit='low'; ncamp=2
    elif comm_usd < 5: profit='medium'; ncamp=3
    else: profit='high'; ncamp=5
    rc = to_float(review_count) if review_count else 0
    brand_aw = 'known' if rc>500 else 'unknown'
    if target_cpa < 1.0: feas = 'high_risk'
    elif target_cpa < 3.0: feas = 'medium_risk'
    else: feas = 'good'
    max_cpc = round(target_cpa / 20, 2)
    # Social proof
    r_val = to_float(rating)
    rv_int = int(rc) if rc else 0
    if r_val and rv_int>0: sp=f"{r_val}★ with {rv_int}+ reviews"; sp_s=f"{rv_int}+ reviews"
    elif r_val: sp=f"{r_val}-star rated"; sp_s=f"{r_val}★ rated"
    elif rv_int>0: sp=f"{rv_int}+ verified reviews"; sp_s=f"{rv_int}+ reviews"
    else: sp=''; sp_s=''
    brand_slug = re.sub(r'[^A-Za-z0-9 ]','',brand).strip().replace(' ','-')[:20] if brand else 'Brand'
    return dict(brand=brand, brand_slug=brand_slug, title=title, price=price,
        price_str=fmt_price(price), commission_pct=comm_pct, commission_str=fmt_commission(comm_pct),
        commission_usd=comm_usd, rating=rating, review_count=review_count, bullets=bullets,
        target_cpa=target_cpa, category=cat, product_type=ptype, keywords=kw_ext,
        profit_level=profit, recommended_campaigns=ncamp, brand_awareness=brand_aw,
        feasibility=feas, suggested_max_cpc=max_cpc, asin=prod['asin'],
        tracking_url=prod.get('tracking_url') or prod.get('amazon_url') or '',
        social_proof=sp, social_proof_short=sp_s)

# ── Step 3: Campaign 结构 ──
def _build_campaign_structure(a):
    bs = a['brand_slug']; ptype = a['product_type']; profit = a['profit_level']
    if ptype == 'gift':
        c = [
            {'name':f"{bs}-Gift-Scenario",'stage':'Gift-Scenario','budget_pct':55 if profit=='low' else 45,'bid':'Manual CPC','groups':['Gift-Occasions','Gift-Under-Price']},
            {'name':f"{bs}-Brand-Direct",'stage':'Brand','budget_pct':25 if profit=='low' else 20,'bid':'Manual CPC','groups':['Brand-Exact']},
            {'name':f"{bs}-Category-Core",'stage':'Category','budget_pct':20 if profit=='low' else 25,'bid':'Manual CPC','groups':['Category-Main']},
        ]
        if profit != 'low':
            c.append({'name':f"{bs}-Buy-Now",'stage':'Purchase','budget_pct':10,'bid':'Manual CPC → Max Conversions → Target CPA','groups':['Buy-Now']})
    elif ptype == 'pain_point':
        c = [
            {'name':f"{bs}-Pain-Point-Solution",'stage':'Problem-Solution','budget_pct':35,'bid':'Manual CPC','groups':['Core-Problem','Specific-Scenario']},
            {'name':f"{bs}-Category-Comparison",'stage':'Comparison','budget_pct':30,'bid':'Manual CPC','groups':['Best-Top-Review']},
            {'name':f"{bs}-Buy-Now",'stage':'Purchase','budget_pct':25,'bid':'Manual CPC → Max Conversions → Target CPA','groups':['Buy-Now']},
            {'name':f"{bs}-Brand",'stage':'Brand','budget_pct':10,'bid':'Manual CPC','groups':['Brand-Exact']},
        ]
    elif ptype == 'effect':
        c = [
            {'name':f"{bs}-Category-Core",'stage':'Category','budget_pct':30,'bid':'Manual CPC','groups':['Category-Main','Ingredient-Feature']},
            {'name':f"{bs}-Effect-Proof",'stage':'Effect','budget_pct':25,'bid':'Manual CPC','groups':['Results-Data','Expert-Trust']},
            {'name':f"{bs}-Comparison-Review",'stage':'Comparison','budget_pct':20,'bid':'Manual CPC','groups':['Best-Top-Review']},
            {'name':f"{bs}-Buy-Now",'stage':'Purchase','budget_pct':20,'bid':'Manual CPC → Max Conversions → Target CPA','groups':['Buy-Now']},
            {'name':f"{bs}-Brand",'stage':'Brand','budget_pct':5,'bid':'Manual CPC','groups':['Brand-Exact']},
        ]
    else:
        c = [
            {'name':f"{bs}-Brand-Direct",'stage':'Brand','budget_pct':20,'bid':'Manual CPC','groups':['Brand-Exact']},
            {'name':f"{bs}-Feature-Category",'stage':'Feature','budget_pct':45,'bid':'Manual CPC','groups':['Feature-Main','Category-Search']},
            {'name':f"{bs}-Buy-Now",'stage':'Purchase','budget_pct':35,'bid':'Manual CPC → Max Conversions → Target CPA','groups':['Buy-Now']},
        ]
    if profit=='low' and len(c)>3:
        c = c[:3]
        total = sum(x['budget_pct'] for x in c)
        for x in c: x['budget_pct'] = round(x['budget_pct']/total*100)
    return c

# ── Step 4: 否定关键词 ──
def get_account_negatives(a):
    negs = ["-free","-diy","-homemade",'-"do it yourself"',"-used",'-"second hand"',"-rental","-wholesale","-bulk","-manufacturer","-supplier",
            "-setup","-installation","-manual","-instructions","-tutorial","-troubleshooting","-repair","-broken",'-"not working"',
            "-warranty","-service","-support","-help",'-"replacement parts"',"-return","-refund","-exchange","-complaint",
            "-login",'-"sign in"',"-account","-password","-website","-app",'-"near me"']
    ptype = a['product_type']; cat = a['category']
    if ptype=='gift':
        negs = [n for n in negs if n not in ['-review','-reviews','-problem','-issue']]
    if ptype=='pain_point':
        negs = [n for n in negs if n not in (['-"how to"','-guide','-fix','-problem','-issue'])]
    if cat=='electronics':
        negs = [n for n in negs if n not in ['-app','-setup']]
    if cat=='jewelry':
        negs.extend(["-watch box","-watch case","-ring display","-earring stand","-necklace stand",
                     "-jewelry armoire","-makeup bag","-makeup case","-coin purse"])
        tl = a['title'].lower()
        for mat in ['diamond','gold','silver','platinum']:
            if mat not in tl: negs.append(f"-{mat}")
    elif cat=='pet':
        negs.extend(["-pet insurance","-vet clinic","-pet adoption","-pet boarding"])
        if not any(w in a['title'].lower() for w in ['food','treat','snack']):
            negs.extend(["-cat food","-dog food","-pet food"])
    elif cat=='health':
        negs.extend(["-recipe","-cooking","-dosage","-prescription","-doctor","-recall"])
    return negs

def _group_negatives(a, camp_name, grp_name):
    negs = []
    if 'Gift' in camp_name or 'Scenario' in camp_name:
        negs.extend(['-for men','-for dad','-for boyfriend','-for him','-corporate','-business'])
    if 'Buy' in camp_name or 'Purchase' in camp_name:
        negs.extend(['-review','-vs','-compare','-alternative','-used','-second hand','-rental'])
    if 'Brand' in camp_name:
        negs.extend(['-cheap','-discount','-budget','-alternative','-vs'])
    if grp_name == 'Category-Main' and a['category']=='jewelry':
        negs.extend(['-large','-big','-oversized','-wooden','-leather'])
    return negs

# ── Step 5: 关键词生成 ──
def _gen_keywords(a, grp, brand_kws):
    brand = a['brand'].lower()
    kd = a['keywords']; cat = a['category']
    cd = CATEGORY_KEYWORDS.get(cat,{})
    core = kd.get('core',[]); scenes = kd.get('scenes',[]); feats = kd.get('features',[]); aud = kd.get('audience',[])
    kws = []
    if grp == 'Brand-Exact':
        if a['brand_awareness']=='unknown':
            for kw in brand_kws[:4]:
                k = kw.lower().strip()
                if k and brand in k: kws.append({'type':'E','kw':k})
            for c in core[:2]:
                if c: kws.append({'type':'E','kw':f"{brand} {c}"})
        else:
            for kw in brand_kws[:8]:
                k = kw.lower().strip()
                if k: kws.append({'type':'E' if brand in k else 'P','kw':k})
    elif grp == 'Gift-Occasions':
        ss = scenes if scenes else cd.get('scenes',[])[:8]
        for s in ss[:7]: kws.append({'type':'P','kw':s})
        for c in core[:2]: kws.append({'type':'P','kw':f"{c} gift"})
        if aud: kws.append({'type':'B','kw':f"gifts {aud[0]}"})
    elif grp == 'Gift-Under-Price':
        p = a['price']
        if p > 0:
            for c in core[:3]:
                kws.append({'type':'P','kw':f"{c} under ${int(p)}"})
                kws.append({'type':'E','kw':f"buy {c}"})
        if p<=10:
            kws.extend([{'type':'P','kw':'gifts under $10 for women'},{'type':'P','kw':'cheap gifts for her'}])
        elif p<=20:
            kws.extend([{'type':'P','kw':'gifts under $20 for women'},{'type':'P','kw':'affordable gifts for her'}])
    elif grp in ('Category-Main','Category-Search','Feature-Main'):
        ac = core if core else cd.get('core',[])[:10]
        for i,c in enumerate(ac[:7]):
            kws.append({'type':'E' if i<2 else 'P','kw':c})
        for f in feats[:2]:
            if ac: kws.append({'type':'P','kw':f"{f} {ac[0]}"})
    elif grp == 'Buy-Now':
        for c in core[:3]:
            kws.append({'type':'E','kw':f"buy {c}"})
            kws.append({'type':'P','kw':f"{c} on amazon"})
        if a['price']>0:
            pt = f"under ${int(a['price'])}"
            for c in core[:2]: kws.append({'type':'P','kw':f"{c} {pt}"})
    elif grp in ('Core-Problem','Specific-Scenario'):
        ac = core if core else cd.get('core',[])[:8]
        for c in ac[:4]: kws.append({'type':'P','kw':f"best {c}"})
        for s in scenes[:4]: kws.append({'type':'P','kw':s})
    elif grp == 'Best-Top-Review':
        ac = core if core else cd.get('core',[])[:5]
        for c in ac[:4]:
            kws.append({'type':'P','kw':f"best {c}"})
            kws.append({'type':'P','kw':f"top rated {c}"})
    elif grp in ('Results-Data','Ingredient-Feature','Expert-Trust'):
        ac = core if core else cd.get('core',[])[:5]
        for c in ac[:3]: kws.append({'type':'P','kw':f"{c} reviews"})
        for f in feats[:3]:
            if ac: kws.append({'type':'P','kw':f"{f} {ac[0]}"})
            else: kws.append({'type':'P','kw':f})
    else:
        ac = core if core else ['product']
        for c in ac[:5]: kws.append({'type':'P','kw':c})
    # Dedup + limit
    seen = set(); unique = []
    for kw in kws:
        key = kw['kw'].lower()
        if key not in seen and len(key.split())<=6:
            seen.add(key); unique.append(kw)
    return unique[:12]

# ── Step 6: 标题生成 ──
def _gen_headlines(a, grp):
    brand = a['brand']; ps = a['price_str']
    kc = a['keywords'].get('core',['product'])
    core = kc[0] if kc else 'product'
    feats = a['keywords'].get('features',[])
    sp = a.get('social_proof_short','')
    # Pre-compute to avoid nested calls
    f0 = feats[0] if feats else 'quality'
    f1 = feats[1] if len(feats)>1 else 'premium'
    f2 = feats[2] if len(feats)>2 else 'portable'
    f3 = feats[3] if len(feats)>3 else 'compact'
    sp_val = sp if sp else 'Top Rated'
    b = brand[:20]
    pi = int(a['price']) if a['price']>0 else 10

    if grp == 'Brand-Exact':
        raw = [f"{b} Official Store", f"{b} on Amazon", f"{brand[:15]} {core[:12]}",
               f"Shop {b}", f"Buy {b}", f"{ps} — {brand[:16]}", "Free Prime Shipping",
               "30-Day Easy Returns", f"{b} — Trusted Brand", f"Authentic {brand[:17]}",
               "Secure Amazon Checkout", f"{b} Best Seller", "Fast Amazon Delivery",
               f"{b} Official", f"Shop {b} Today"]
    elif grp == 'Gift-Occasions':
        raw = ["Graduation Gift for Her", "Birthday Gift for Women",
               f"{core[:18]} — Perfect Gift", "Gift for Bestie", f"Gift for Mom {ps}",
               "Stocking Stuffers Women", "Bridesmaid Gift Ideas",
               f"{core[:22]} Under ${pi}", "Small Gift for Her",
               f"{core[:20]} Gift Box", "Anniversary Gift Idea",
               f"{core[:16]} — Ships Free", f"Gift {core[:20]} Prime",
               f"Shop {core[:22]} Gift", sp_val]
    elif grp == 'Gift-Under-Price':
        raw = [f"Gifts Under ${pi}", f"{core[:20]} {ps}", f"Buy {core[:22]}",
               f"Affordable {core[:18]}", f"Under ${pi} Gift Her", f"Best {core[:20]} Deal",
               f"{core[:18]} on Amazon", f"{core[:16]} Free Shipping",
               f"{ps} {core[:20]}", sp_val, f"Prime {core[:22]}",
               "30-Day Returns", f"Order {core[:22]} Today", "Secure Checkout", "Fast Delivery"]
    elif grp in ('Category-Main','Category-Search','Feature-Main'):
        raw = [core[:28], f"Best {core[:24]}", f"Top Rated {core[:20]}", f0[:28],
               f1[:28], f"Buy {core[:24]}", f"{core[:18]} on Amazon",
               f"{core[:20]} {ps}", f"Free Shipping {core[:14]}", f"{core[:20]} Prime",
               sp_val, f2[:28], "30-Day Easy Returns", "Secure Checkout", f"{core[:20]} Reviews"]
    elif grp == 'Buy-Now':
        raw = [f"Buy {core[:24]}", f"Order {core[:24]}", f"{core[:20]} on Amazon",
               f"{ps} Free Shipping", "Ships Free w/ Prime", "30-Day Easy Returns",
               "Secure Checkout", "Get It by Tomorrow", f"Best {core[:20]} Deal",
               sp_val, f"Shop {core[:22]} — {ps}", f"Order {core[:24]} Now",
               "Amazon's Choice", "Prime Delivery", f"{ps} — Order Now"]
    elif grp in ('Core-Problem','Specific-Scenario'):
        raw = [f"Best {core[:24]}", f"Top {core[:26]} 2025", f"{f0[:28]}",
               f"{f1[:28]}", f"Buy {core[:24]}", f"Rated {core[:22]}",
               f"{core[:18]} on Amazon", sp_val, "30-Day Easy Returns",
               "Free Prime Shipping", f"{core[:16]} Reviews", "Secure Amazon Checkout",
               f"{f2[:28]}", f"Shop {core[:22]} Now", "Order Today"]
    elif grp == 'Best-Top-Review':
        raw = [f"Best {core[:24]} 2025", f"Top Rated {core[:20]}",
               f"{core[:28]} Review", f"Why {brand[:18]} {core[:8]}" if brand else f"Best {core[:24]}",
               sp_val, f"{ps} — Best Deal", f"{core[:18]} on Amazon",
               f"Compare {core[:22]}", f"Top Pick {core[:20]}", f"Buy {core[:24]}",
               "Free Prime Shipping", "30-Day Returns", "Expert Recommended",
               "Shop Amazon", "Order Now"]
    elif grp in ('Results-Data','Ingredient-Feature','Expert-Trust'):
        raw = [f"{core[:28]} Results", f"Best {core[:24]} Reviews", f"{f0[:28]}",
               f"{f1[:28]}", sp_val, f"{core[:18]} — Buy Now", f"Buy {core[:24]}",
               f"{ps} {core[:20]}", "Free Shipping", "30-Day Returns",
               f"{f2[:28]}", "Secure Checkout", "Prime Delivery",
               f"Order {core[:24]} Today", "Fast Delivery"]
    else:
        raw = [core[:28], f"Best {core[:24]}", f"Buy {core[:24]}",
               f"{core[:20]} {ps}", f"{core[:18]} on Amazon", "Free Prime Shipping",
               "30-Day Easy Returns", "Secure Checkout", sp_val,
               f"Order {core[:24]}", "Fast Delivery", "Prime Delivery",
               f"Shop {core[:22]}", "Buy Now", f"Get {core[:22]} Today"]
    return [hl(t) for t in raw[:15]]

# ── Step 6: 描述生成 ──
def _gen_descriptions(a, grp):
    brand = a['brand']; ps = a['price_str']
    kc = a['keywords'].get('core',['product'])
    core = kc[0] if kc else 'product'
    feats = a['keywords'].get('features',[])
    sp = a.get('social_proof','')
    bl = a['bullets']
    b1 = bl[0][:45] if bl else core
    b2 = bl[1][:45] if len(bl)>1 else ''
    # Pre-compute
    sp_line = f" {sp}." if sp else ''
    f0 = feats[0] if feats else ''

    if grp == 'Brand-Exact':
        raw = [f"Shop {brand} on Amazon. {b1}. {ps}. Free Prime shipping.",
               f"Looking for {brand}? Find the best on Amazon. Easy returns.",
               f"{b1}. {b2}.{sp_line} Buy on Amazon.",
               f"{brand} from {ps}. 30-day returns. Amazon checkout.",
               f"Order {brand} today. {b1}. Prime shipping. Shop now."]
    elif grp.startswith('Gift'):
        raw = [f"{core.capitalize()}. {b1}. Perfect gift - {ps}. Ships free.",
               f"Looking for a gift? {b1}. Compact, gift-ready. Free returns.",
               f"{b2}. {b1}.{sp_line} Amazon." if sp and b2 else f"{b1}. Great gift. Buy on Amazon.",
               f"{ps} - affordable gift. Prime shipping. 30-day returns.",
               f"Order now - ships fast. {b1}. Easy returns."]
    elif grp in ('Category-Main','Category-Search','Feature-Main'):
        raw = [f"{b1}. {b2 or f0 or core}. {ps}. Free shipping.",
               f"{core}? {b1}. {f0}. Buy now." if f0 else f"{core}? {b1}. Buy now.",
               f"{b2 or b1}. {f0}.{sp_line}" if f0 else f"{b1}.{sp_line}",
               f"{ps}. Free Prime. 30-day returns. Secure checkout.",
               f"Order {core} today. Ships fast. {b1}."]
    elif grp == 'Buy-Now':
        raw = [f"Buy {core} on Amazon. {ps}. Free Prime shipping.",
               f"Ready? {core}. {ps}. Secure checkout. Free returns.",
               f"{sp}. {ps}. Ships free." if sp else f"{core}. {ps}. Free shipping.",
               f"Get {core} fast. {ps}. 30-day returns.",
               f"Don't wait - {core} at {ps}. Free Prime. Shop now."]
    elif grp in ('Core-Problem','Specific-Scenario'):
        raw = [f"Best {core}. {b1}. {ps}. Buy Amazon.",
               f"{b1}. Try {brand}{sp_line}" if sp else f"{b1}. Try it now.",
               f"{b2 or b1}. {f0}. {ps}. Free shipping.",
               f"{ps}. Free Prime. 30-day returns. Secure checkout.",
               f"Order today - {b1}. Ships fast. Easy returns."]
    elif grp == 'Best-Top-Review':
        raw = [f"Best {core}? {brand}: {b1}.{sp_line}" if sp else f"Best {core}? {b1}. Buy Amazon.",
               f"{brand}: {b1}. {b2}. Compare now." if b2 else f"{brand}: {b1}. Compare now.",
               f"Why {brand}? {b1}. {ps}.",
               f"{ps}. Free returns. Prime shipping.",
               f"{core} at {ps}. Free shipping. Order today."]
    else:
        raw = [f"{b1}. {ps}. Free Prime. Buy Amazon.",
               f"{core}. {b2 or ''}. Shop now.",
               f"{b1}. {f0}.{sp_line}" if f0 else f"{b1}.{sp_line}",
               f"{ps}. 30-day returns. Free Prime.",
               f"Order today - {b1}. Ships fast."]
    return [desc(t) for t in raw[:5]]

# ── Step 7: 扩展生成 ──
def _gen_extensions(a):
    brand = a['brand']
    kc = a['keywords'].get('core',['product'])
    core = kc[0] if kc else 'product'
    feats = a['keywords'].get('features',[])
    sp = a.get('social_proof_short','')
    bl = a['bullets']
    sitelinks = [
        {'text':'View Product Details','desc1':f'{core[:20]} full info','desc2':'See all features'},
        {'text':'Customer Reviews','desc1':'Verified Amazon reviews','desc2':'See real photos'},
        {'text':'Free Shipping','desc1':'Prime eligible','desc2':'Fast delivery'},
        {'text':'30-Day Returns','desc1':'Easy hassle-free','desc2':'Shop with confidence'},
        {'text':'Shop on Amazon','desc1':f'{brand} official','desc2':'Secure checkout'},
    ]
    callouts = [feats[0][:24] if feats else 'Quality Product',
                feats[1][:24] if len(feats)>1 else 'Easy to Use',
                'Free Prime Shipping','30-Day Easy Returns','Secure Amazon Checkout',
                sp if sp else 'Trusted Brand']
    sv = []
    for b in bl[:5]:
        v = ' '.join(b.split()[:4])[:25]
        if v and v not in sv: sv.append(v)
    for f in feats[:3]:
        if f not in sv: sv.append(f)
    if not sv: sv = ['Quality','Free Shipping','Easy Returns']
    return {'sitelinks':sitelinks,'callouts':callouts,'structured_snippet':{'header':'Features','values':sv[:10]}}

# ── Ad 变体构建 ──
def _build_ad(hls, descs, ext, prod, variant):
    brand = prod.get('amz_brand') or prod.get('merchant_name') or ''
    title = prod.get('amz_title') or prod.get('product_name') or ''
    dp = f"amazon.com/{brand.replace(' ','-')[:20]}/{'-'.join(title.split()[:2])[:20]}"
    if variant=='B' and len(hls)>=5: h = hls[3:6]+hls[0:3]+hls[6:]
    else: h = hls
    hf = h[:15]; df = descs[:5]
    bp = [{'phase':1,'weeks':'1-2','strategy':'Manual CPC','note':'Start conservative'},
          {'phase':2,'weeks':'2-4','strategy':'Max Conversions','note':'After 15+ conversions'},
          {'phase':3,'weeks':'4+','strategy':'Target CPA','note':'After 30+ conversions'}]
    bh = [x for x in hf if x['chars']>30]; bd = [x for x in df if x['chars']>90]
    notes = []
    if bh: notes.append(f"{len(bh)} headlines exceed 30 chars")
    if bd: notes.append(f"{len(bd)} descriptions exceed 90 chars")
    return {'variant':variant,'headlines':hf,'descriptions':df,'sitelinks':ext['sitelinks'],
            'callouts':ext['callouts'],'structured_snippet':ext['structured_snippet'],
            'final_url':prod.get('tracking_url') or prod.get('amazon_url') or '',
            'display_url':dp,'headline_count':len(hf),'description_count':len(df),
            'all_chars_valid':1 if not(bh or bd) else 0,
            'quality_notes':'; '.join(notes) if notes else 'All checks passed','bidding_phases':bp}

# ── Step 8: QA 检查 ──
def qa_check(campaigns, a):
    issues = []
    if a['price']<=0: issues.append({'qa':1,'sev':'fatal','msg':'Price $0 or missing'})
    # Duplication
    all_h = []
    for c in campaigns:
        for g in c.get('ad_groups',[]):
            for ad in g.get('ads',[]): all_h.append(set(h['text'] for h in ad.get('headlines',[])))
    for i in range(len(all_h)):
        for j in range(i+1,len(all_h)):
            if all_h[i] and all_h[j]:
                ov=len(all_h[i]&all_h[j]); tt=len(all_h[i]|all_h[j])
                if tt>0 and ov/tt>0.5: issues.append({'qa':2,'sev':'high','msg':f'Groups {i},{j}: {ov}/{tt} overlap'})
    # Keyword authenticity
    fake=['that works','need a ','how it works']
    for c in campaigns:
        for g in c.get('ad_groups',[]):
            for kw in g.get('keywords',[]):
                t=kw['kw'].lower()
                for p in fake:
                    if p in t: issues.append({'qa':3,'sev':'high','msg':f"Suspicious KW: '{t}'"})
                if len(t.split())>6: issues.append({'qa':3,'sev':'medium','msg':f"Long KW: '{t}'"})
    # Template residual
    tmpls=['solves your problem','premium feature','advanced design','built for performance','works. proven.','premium quality product']
    for c in campaigns:
        for g in c.get('ad_groups',[]):
            for ad in g.get('ads',[]):
                for h in ad.get('headlines',[]):
                    if any(p in h['text'].lower() for p in tmpls): issues.append({'qa':4,'sev':'fatal','msg':f"Template HL: '{h['text']}'"})
                for d in ad.get('descriptions',[]):
                    if any(p in d['text'].lower() for p in tmpls): issues.append({'qa':4,'sev':'fatal','msg':f"Template DESC: '{d['text']}'"})
    # Negative KW
    cat=a['category']; ptype=a['product_type']
    for c in campaigns:
        for neg in c.get('negative_keywords',[]):
            nl=neg.lower()
            if cat=='jewelry' and any(x in nl for x in ['-ingredients','-nutrition']): issues.append({'qa':5,'sev':'medium','msg':f"Cat mismatch: '{neg}'"})
            if ptype=='gift' and '-review' in nl: issues.append({'qa':5,'sev':'high','msg':f"Blocks traffic: '{neg}'"})
    # Char limits
    for c in campaigns:
        for g in c.get('ad_groups',[]):
            for ad in g.get('ads',[]):
                for h in ad.get('headlines',[]):
                    if h['chars']>30: issues.append({'qa':6,'sev':'fatal','msg':f"HL {h['chars']}c: '{h['text']}'"})
                for d in ad.get('descriptions',[]):
                    if d['chars']>90: issues.append({'qa':6,'sev':'fatal','msg':f"DESC {d['chars']}c: '{d['text']}'"})
    fatal=[i for i in issues if i['sev']=='fatal']; high=[i for i in issues if i['sev']=='high']; med=[i for i in issues if i['sev']=='medium']
    rl=["="*60,"  QA Report v5.0","="*60,
        f"  QA-1 Price:        {'PASS' if not any(i['qa']==1 for i in issues) else 'FAIL'}",
        f"  QA-2 Duplicates:   {'PASS' if not any(i['qa']==2 for i in issues) else 'FAIL'}",
        f"  QA-3 Keywords:     {'PASS' if not any(i['qa']==3 for i in issues) else 'WARN'}",
        f"  QA-4 Template:     {'PASS' if not any(i['qa']==4 for i in issues) else 'FAIL'}",
        f"  QA-5 Neg KW:       {'PASS' if not any(i['qa']==5 for i in issues) else 'WARN'}",
        f"  QA-6 Chars:        {'PASS' if not any(i['qa']==6 for i in issues) else 'FAIL'}",
        "="*60,f"  Fatal: {len(fatal)} | High: {len(high)} | Medium: {len(med)}",
        f"  Result: {'ALL PASS' if not fatal else 'BLOCKED'}","="*60]
    if issues:
        rl.append("  Issues:")
        for iss in issues: rl.append(f"    [{iss['sev'].upper()}] QA-{iss['qa']}: {iss['msg']}")
    return {'passed':len(fatal)==0,'issues':issues,'report':chr(10).join(rl),'fatal_count':len(fatal),'high_count':len(high)}

# ── 汇总构建 ──
def build_campaigns(a, brand_kws):
    anegs = get_account_negatives(a)
    cs = _build_campaign_structure(a)
    campaigns = []
    for cd in cs:
        camp = {'campaign_name':cd['name'],'journey_stage':cd['stage'],'budget_pct':cd['budget_pct'],
                'daily_budget_usd':round(a['target_cpa']*3*cd['budget_pct']/100*10,2) if a['target_cpa']>0 else round(50*cd['budget_pct']/100,2),
                'negative_keywords':anegs[:],'bid_strategy':cd['bid'],'ad_groups':[]}
        for gn in cd['groups']:
            kws=_gen_keywords(a,gn,brand_kws); gnegs=_group_negatives(a,cd['name'],gn)
            hls=_gen_headlines(a,gn); descs=_gen_descriptions(a,gn); ext=_gen_extensions(a)
            variants=['A','B'] if 'Buy' in gn else ['A']
            ads=[_build_ad(hls,descs,ext,{'amz_brand':a['brand'],'merchant_name':a['brand'],
                 'amz_title':a['title'],'product_name':a['title'],'tracking_url':a['tracking_url'],
                 'amazon_url':a.get('tracking_url','')},v) for v in variants]
            camp['ad_groups'].append({'ad_group_name':gn,'theme':f"{cd['stage']} - {gn}",
                'user_intent':f"User searching for {gn.replace('-',' ')}",'keywords':kws,
                'negative_keywords':gnegs,
                'cpc_bid_usd':round(a['suggested_max_cpc']*1.5,2) if a['suggested_max_cpc']>0 else 0.50,
                'ads':ads})
        campaigns.append(camp)
    return campaigns

# ── DB写入 ──
def save_plan(conn, prod, campaigns, brand_kws, tcpa, analysis=None, qa=None):
    cur=conn.cursor(); asin=prod['asin']; mid=str(prod.get('merchant_id',''))
    price=prod.get('amz_price') or prod.get('price'); comm=prod.get('commission')
    cur.execute("SELECT id FROM ads_plans WHERE asin=%s LIMIT 1",(asin,))
    if cur.fetchone():
        cur.execute("DELETE FROM ads_campaigns WHERE asin=%s",(asin,))
        cur.execute("DELETE FROM ads_plans WHERE asin=%s",(asin,)); conn.commit()
    cur.execute("INSERT INTO ads_plans (asin,merchant_id,merchant_name,product_name,product_price,"
        "commission_pct,target_cpa,brand_keywords_used,has_amazon_data,plan_status,generated_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'completed',NOW())",
        (asin,mid,prod.get('merchant_name'),prod.get('amz_title') or prod.get('product_name'),
         to_float(price) or None,to_float(str(comm).replace('%','')) or None,
         tcpa,json.dumps(brand_kws[:20],ensure_ascii=False),1 if prod.get('amz_title') else 0))
    conn.commit(); pid=cur.lastrowid; tc=tg=ta=0
    for camp in campaigns:
        cur.execute("INSERT INTO ads_campaigns (asin,merchant_id,merchant_name,campaign_name,"
            "journey_stage,budget_pct,daily_budget_usd,product_price,commission_pct,commission_usd,"
            "target_cpa,negative_keywords,bid_strategy,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft')",
            (asin,mid,prod.get('merchant_name'),camp['campaign_name'],camp['journey_stage'],
             camp.get('budget_pct'),camp.get('daily_budget_usd'),
             float(to_float(price)) if price else None,
             float(str(comm).replace('%','').strip()) if comm else None,
             round(to_float(price)*to_float(str(comm).replace('%',''))/100,4),
             tcpa,json.dumps(camp.get('negative_keywords',[]),ensure_ascii=False),camp.get('bid_strategy')))
        conn.commit(); cid=cur.lastrowid; tc+=1
        for grp in camp.get('ad_groups',[]):
            kws=grp.get('keywords',[])
            cur.execute("INSERT INTO ads_ad_groups (campaign_id,ad_group_name,theme,user_intent,"
                "keywords,negative_keywords,keyword_count,cpc_bid_usd,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')",
                (cid,grp['ad_group_name'],grp.get('theme',''),grp.get('user_intent',''),
                 json.dumps(kws,ensure_ascii=False),json.dumps(grp.get('negative_keywords',[]),ensure_ascii=False),
                 len(kws),grp.get('cpc_bid_usd')))
            conn.commit(); gid=cur.lastrowid; tg+=1
            for ad in grp.get('ads',[]):
                cur.execute("INSERT INTO ads_ads (ad_group_id,campaign_id,asin,variant,headlines,descriptions,"
                    "sitelinks,callouts,structured_snippet,final_url,display_url,headline_count,description_count,"
                    "all_chars_valid,quality_notes,bidding_phases,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'draft')",
                    (gid,cid,asin,ad['variant'],json.dumps(ad['headlines'],ensure_ascii=False),
                     json.dumps(ad['descriptions'],ensure_ascii=False),json.dumps(ad.get('sitelinks',[]),ensure_ascii=False),
                     json.dumps(ad.get('callouts',[]),ensure_ascii=False),json.dumps(ad.get('structured_snippet',{}),ensure_ascii=False),
                     ad.get('final_url',''),ad.get('display_url',''),ad.get('headline_count',15),ad.get('description_count',5),
                     ad.get('all_chars_valid',0),ad.get('quality_notes',''),json.dumps(ad.get('bidding_phases',[]),ensure_ascii=False)))
                ta+=1
    conn.commit()
    cur.execute("UPDATE ads_plans SET campaign_count=%s,ad_group_count=%s,ad_count=%s WHERE asin=%s",(tc,tg,ta,asin))
    conn.commit(); cur.close()
    return pid,tc,tg,ta

# ── 主函数 ──
def generate_ads_for_asin(asin, force=False):
    conn=get_db()
    cur=conn.cursor(); cur.execute("SELECT id,plan_status,generated_at FROM ads_plans WHERE asin=%s LIMIT 1",(asin,))
    existing=cur.fetchone(); cur.close()
    if existing and existing[1]=='completed' and not force:
        return {'success':False,'message':f"Plan exists (id={existing[0]}). Use --force.",'asin':asin}
    prod=get_product_info(conn,asin)
    if not prod: conn.close(); return {'success':False,'message':f'ASIN {asin} not found','asin':asin}
    has_amz=bool(prod.get('amz_title'))
    if not has_amz: print("  [WARN] No Amazon data found.")
    brand_kws=get_brand_keywords(conn,str(prod.get('merchant_id','')))
    print("\nStep 1: Analyzing product...")
    a=analyze_product(prod)
    print(f"\n{'='*60}")
    print(f"  Product Analysis v5.0")
    print(f"{'='*60}")
    print(f"  ASIN:         {asin}")
    print(f"  Brand:        {a['brand']}")
    print(f"  Category:     {a['category']}")
    print(f"  Type:         {a['product_type']}")
    print(f"  Price:        {a['price_str']}")
    print(f"  Commission:   {a['commission_str']} (${a['commission_usd']:.2f})")
    print(f"  Target CPA:   ${a['target_cpa']:.2f}")
    print(f"  Profit:       {a['profit_level']}")
    print(f"  Feasibility:  {a['feasibility']}")
    print(f"  Brand:        {a['brand_awareness']}")
    print(f"  Max CPC:      ${a['suggested_max_cpc']:.2f}")
    print(f"  Campaigns:    {a['recommended_campaigns']}")
    print(f"  Brand KWs:    {len(brand_kws)}")
    print(f"  Amazon Data:  {'YES' if has_amz else 'NO'}")
    print(f"  Social Proof: {a.get('social_proof') or 'N/A'}")
    if a['feasibility']=='high_risk':
        print(f"  🔴 HIGH RISK: commission ${a['commission_usd']:.2f}, target CPA ${a['target_cpa']:.2f}")
        if a['suggested_max_cpc']<0.15: print(f"  🔴 Suggested max CPC < $0.15 — consider social media")
        if a['brand_awareness']=='unknown': print(f"  🟡 Unknown brand — brand campaign may have low volume")
    print(f"{'='*60}")
    print("\nStep 2: Building campaigns...")
    campaigns=build_campaigns(a,brand_kws)
    print("Step 3: Running QA checks...")
    qa=qa_check(campaigns,a)
    print(qa['report'])
    print("Step 4: Saving to database...")
    pid,nc,ng,na=save_plan(conn,prod,campaigns,brand_kws,a['target_cpa'],a,qa)
    conn.close()
    print(f"\n[OK] Plan saved: plan_id={pid}, campaigns={nc}, groups={ng}, ads={na}")
    return {'success':True,'asin':asin,'plan_id':pid,'campaigns':nc,'ad_groups':ng,'ads':na,
            'brand':a['brand'],'target_cpa':a['target_cpa'],'has_amazon_data':has_amz,
            'qa_passed':qa['passed'],'qa_fatal':qa['fatal_count'],'product_type':a['product_type']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Generate Google Ads v5.0')
    parser.add_argument('--asin',required=True)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    result=generate_ads_for_asin(args.asin,force=args.force)
    if not result['success']:
        print(f"\n[ERROR] {result['message']}"); sys.exit(1)
