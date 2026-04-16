# routes_collect.py - YP采集、作战室、下载方案
# 从 ads_manager.py 行 4191-5889 提取
import json, os, sys, io, csv, uuid, re, time as _time, requests, threading, subprocess, datetime
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
    YP_COLLECT_SCRIPT,
    YP_STOP_FILE,
    PYTHON_EXE,
    YP_SITE_ID,
    YP_API_TOKEN,
    YP_OFFER_BY_ADVERT_URL,
)
from db import (
    get_db,
    _db,
    _cached_count,
    _count_cache,
    _parse_report_column,
    _clean_numeric_value,
)
from templates_shared import (
    BASE_CSS,
    NAV_HTML,
    _BASE_STYLE_DARK,
    _PAGER_JS_DARK,
    _SCRAPE_TOPNAV,
)

bp = Blueprint("collect", __name__)


def _get_merchant_from_json(merchant_id):
    """从 approved_merchants.json / unapplied_merchants.json 查找商户信息（回退方案）"""
    try:
        mid_str = str(merchant_id)
        for fname in ("approved_merchants.json", "unapplied_merchants.json"):
            fp = OUTPUT_DIR / fname
            if not fp.exists():
                continue
            merchants = json.loads(fp.read_text(encoding="utf-8-sig"))
            for m in merchants:
                if str(m.get("merchant_id", "")) == mid_str:
                    return {
                        "merchant_id": m.get("merchant_id"),
                        "merchant_name": m.get("merchant_name", ""),
                        "avg_payout": m.get("avg_payout", None),
                        "cookie_days": m.get("cookie_days", None),
                        "website": m.get("website", ""),
                        "country": m.get("country", "US"),
                        "online_status": m.get("online_status", ""),
                        "status": m.get("status", ""),
                    }
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# YP 数据采集页面
# ═══════════════════════════════════════════════════════════════
YP_COLLECT_UNIFIED_HTML = (
    "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'>\n"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
    "<title>YP数据采集 · YP Affiliate 管理台</title>\n"
    + _BASE_STYLE_DARK
    + """
<style>
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px;margin-bottom:24px;}
.stat-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:18px 20px;}
.stat-card .label{font-size:.78rem;color:#888;margin-bottom:6px;text-transform:uppercase;}
.stat-card .value{font-size:1.8rem;font-weight:700;color:#fff;}
.stat-card .value.green{color:#69f0ae;} .stat-card .value.red{color:#f44336;} .stat-card .value.orange{color:#ffb74d;} .stat-card .value.blue{color:#64b5f6;}
.progress-wrap{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:20px 22px;margin-bottom:24px;}
.progress-label{display:flex;justify-content:space-between;font-size:.83rem;color:#888;margin-bottom:8px;}
.progress-bg{background:#2a2d36;border-radius:8px;height:12px;overflow:hidden;}
.progress-fill{height:100%;border-radius:8px;background:linear-gradient(90deg,#4caf50,#81c784);transition:width .5s;}
.btn-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px;}
.btn-dl{padding:12px 28px;border:none;border-radius:9px;font-size:.95rem;font-weight:600;cursor:pointer;}
.btn-dl:disabled{opacity:.4;cursor:not-allowed;}
.btn-dl-start{background:#2e7d32;color:#fff;} .btn-dl-start:hover:not(:disabled){background:#388e3c;}
.btn-dl-stop{background:#c62828;color:#fff;} .btn-dl-stop:hover:not(:disabled){background:#d32f2f;}
.log-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:18px 20px;}
.log-title{font-size:.82rem;color:#888;text-transform:uppercase;margin-bottom:10px;}
.log-box{background:#0f1117;border-radius:8px;padding:14px;font-family:monospace;font-size:.8rem;color:#ccc;line-height:1.6;min-height:80px;max-height:240px;overflow-y:auto;white-space:pre-wrap;}
.note-card{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;padding:16px 20px;margin-bottom:24px;font-size:.84rem;color:#aaa;line-height:1.7;}
.note-card b{color:#e0e0e0;} .note-card code{background:#23262f;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:.82rem;color:#64b5f6;}
</style>
</head>
<body>
"""
    + _SCRAPE_TOPNAV
    + """
<div class="page" style="max-width:900px;">
  <h2 style="font-size:1.5rem;color:#fff;margin-bottom:6px;">YP 数据采集</h2>
  <p style="color:#888;font-size:.88rem;margin-bottom:22px;">从 YeahPromos 平台下载各商户的商品数据（ASIN / 价格 / 佣金率 / 投放链接），写入 MySQL 供商品列表使用。</p>
  <h2 style="font-size:1.3rem;color:#fff;margin-bottom:6px;">按商户 ID 采集</h2>
  <p style="color:#888;font-size:.85rem;margin-bottom:18px;">输入 YP 平台的 merchant_id（数字），单独采集该商户的商品数据。采集结果写入 yp_products 表。</p>
  <div class="note-card">
    <b>使用前提：</b>调试 Chrome 必须已启动（<code>chrome.exe --remote-debugging-port=9222</code>），且已在 YP 平台登录。<br>
    <b>查找 merchant_id：</b>在上方「商户管理」页面可查看所有商户及其 ID。
  </div>
  <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;flex-wrap:wrap;">
    <input type="text" id="midInput" placeholder="输入 merchant_id，多个用逗号分隔（如 111335,112887）" style="flex:1;min-width:300px;padding:10px 14px;background:#0f1117;border:1px solid #2a2d36;border-radius:8px;color:#fff;font-size:.9rem;outline:none;" onkeydown="if(event.key==='Enter')collectByMid()">
    <button class="btn-dl" id="btnMidCollect" onclick="collectByMid()" style="background:#1565c0;color:#fff;white-space:nowrap;">▶ 开始采集</button>
  </div>
  <div class="log-card">
    <div class="log-title">采集结果</div>
    <div class="log-box" id="midResultBox" style="min-height:50px;">等待操作...</div>
  </div>
</div>
<div class="page" style="max-width:900px;margin-top:30px;">
  <div class="stat-grid" id="statGrid">
    <div class="stat-card"><div class="label">采集进程</div><div class="value" id="stRunning">-</div></div>
    <div class="stat-card"><div class="label">商户总数</div><div class="value blue" id="stTotal">-</div></div>
    <div class="stat-card"><div class="label">已完成</div><div class="value green" id="stDone">-</div></div>
    <div class="stat-card"><div class="label">失败</div><div class="value red" id="stFailed">-</div></div>
    <div class="stat-card"><div class="label">待处理</div><div class="value orange" id="stPending">-</div></div>
  </div>
  <div class="progress-wrap">
    <div class="progress-label"><span>采集进度</span><span id="progressText">-</span></div>
    <div class="progress-bg"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
    <div style="font-size:.78rem;color:#555;margin-top:8px;">最后更新：<span id="lastUpdated">-</span></div>
  </div>
  <div class="note-card">
    <b>使用前提：</b>调试 Chrome 必须已启动（<code>chrome.exe --remote-debugging-port=9222</code>），且已在 YP 平台登录。<br>
    <b>断点续传：</b>中途停止后重新启动，会自动跳过已完成的商户继续采集。
  </div>
  <div class="btn-row">
    <button class="btn-dl btn-dl-start" id="btnStart" onclick="startCollect()">▶ 启动 YP 采集</button>
    <button class="btn-dl btn-dl-stop"  id="btnStop"  onclick="stopCollect()" disabled>■ 停止采集</button>
  </div>
  <div class="log-card">
    <div class="log-title">实时日志（最近 20 行）</div>
    <div class="log-box" id="logBox">等待采集启动...</div>
  </div>
</div>
<script>
let isRunning=false;
function updateBtns(running){isRunning=running;document.getElementById('btnStart').disabled=running;document.getElementById('btnStop').disabled=!running;}
function fetchStatus(){
  fetch('/api/yp_collect_status').then(r=>r.json()).then(data=>{
    if(data.error)return;
    updateBtns(data.running);
    document.getElementById('stRunning').innerHTML=data.running?'<span class="badge badge-running">运行中</span>':'<span class="badge badge-idle">空闲</span>';
    document.getElementById('stTotal').textContent=data.total_merchants??'-';
    document.getElementById('stDone').textContent=data.completed??0;
    document.getElementById('stFailed').textContent=data.failed??0;
    document.getElementById('stPending').textContent=data.pending??0;
    document.getElementById('lastUpdated').textContent=data.last_updated||'-';
    const total=data.total_merchants||0,done=(data.completed||0)+(data.failed||0),pct=total>0?Math.min(100,Math.round(done/total*100)):0;
    document.getElementById('progressFill').style.width=pct+'%';
    document.getElementById('progressText').textContent=total>0?(done+' / '+total+'  ('+pct+'%)'):'-';
    const lines=data.log_lines||[];if(lines.length)document.getElementById('logBox').textContent=lines.join('\\n');
  }).catch(()=>{});
}
function startCollect(){
  document.getElementById('btnStart').disabled=true;
  fetch('/api/yp_collect_start',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.ok){updateBtns(true);document.getElementById('logBox').textContent='['+new Date().toLocaleTimeString()+'] '+d.msg;}
    else{alert(d.msg);document.getElementById('btnStart').disabled=false;}
  });
}
function stopCollect(){
  document.getElementById('btnStop').disabled=true;
  fetch('/api/yp_collect_stop',{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.msg);document.getElementById('btnStop').disabled=false;});
}
function collectByMid(){
  var input=document.getElementById('midInput').value.trim();
  if(!input){alert('请输入 merchant_id');return;}
  var mids=input.split(/[,，\\s]+/).filter(function(s){return s.length>0});
  var resultBox=document.getElementById('midResultBox');
  var btn=document.getElementById('btnMidCollect');
  btn.disabled=true;
  btn.textContent='启动中...';
  resultBox.textContent='正在启动采集进程...';
  fetch('/api/yp_collect_by_mid',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({merchant_ids:mids})}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){
      btn.disabled=false;
      btn.textContent='▶ 开始采集';
      resultBox.textContent='['+new Date().toLocaleTimeString()+'] '+d.msg+'\\n\\n提示：采集需要 Chrome 调试模式已启动并登录 YP。采集日志将实时显示在上方「全量采集」的日志区域。';
    }else{
      btn.disabled=false;
      btn.textContent='▶ 开始采集';
      resultBox.textContent='ERROR: '+(d.msg||'未知错误');
    }
  }).catch(function(e){
    btn.disabled=false;
    btn.textContent='▶ 开始采集';
    resultBox.textContent='请求失败: '+e.message;
  });
}
fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>
"""
)


@bp.route("/yp_collect")
def page_yp_collect():
    return YP_COLLECT_UNIFIED_HTML


@bp.route("/api/yp_collect_status")
def api_yp_collect_status():
    try:
        log_file = OUTPUT_DIR / "download_log.txt"
        last_updated = ""

        # 从 MySQL 读取统计数据
        conn = _db()
        cur = conn.cursor(dictionary=True)

        # 商户总数
        cur.execute("SELECT COUNT(*) AS cnt FROM yp_merchants")
        total_merchants = cur.fetchone()["cnt"]

        # 已完成：yp_products 中有商品的商户数
        cur.execute("SELECT COUNT(DISTINCT merchant_id) AS cnt FROM yp_products")
        completed = cur.fetchone()["cnt"]

        pending = max(0, total_merchants - completed)

        # 商品总数
        cur.execute("SELECT COUNT(*) AS cnt FROM yp_products")
        total_products = cur.fetchone()["cnt"]

        # 最近采集时间
        cur.execute("SELECT MAX(created_at) AS latest FROM yp_products")
        row = cur.fetchone()
        if row and row.get("latest"):
            last_updated = str(row["latest"])

        cur.close()
        conn.close()

        log_lines = []
        if log_file.exists():
            try:
                lines = log_file.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()
                log_lines = lines[-20:]
            except Exception:
                pass
        running = False
        try:
            import wmi as _wmi

            for p in _wmi.WMI().Win32_Process():
                if "download_only" in (p.CommandLine or ""):
                    running = True
                    break
        except Exception:
            pass
        return jsonify(
            {
                "running": running,
                "total_merchants": total_merchants,
                "completed": completed,
                "failed": 0,
                "pending": pending,
                "total_products": total_products,
                "last_updated": last_updated,
                "log_lines": log_lines,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════
# 商户作战室 API
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/api/merchant_room/<merchant_id>")
def api_merchant_room(merchant_id):
    """返回商户作战室所有聚合数据"""
    try:
        conn = _db()
        cur = conn.cursor(dictionary=True)

        # 1. 商户基本信息 - 优先从 yp_merchants 获取，再回退 JSON，最后回退 yp_us_products
        cur.execute(
            """SELECT merchant_id, merchant_name, avg_payout, cookie_days,
                              website, country, online_status, status
                       FROM yp_merchants WHERE merchant_id=%s LIMIT 1""",
            (str(merchant_id),),
        )
        merchant = cur.fetchone()

        # 如果 yp_merchants 中没有，从 JSON 文件回退
        if not merchant:
            merchant = _get_merchant_from_json(merchant_id)

        # 还是没有，从 yp_us_products 获取
        if not merchant:
            cur.execute(
                """SELECT yp_merchant_id AS merchant_id, merchant_name
                        FROM yp_us_products WHERE yp_merchant_id=%s LIMIT 1""",
                (int(merchant_id),),
            )
            merchant = cur.fetchone() or {}
            # 补充默认值
            if merchant:
                merchant.setdefault("avg_payout", None)
                merchant.setdefault("cookie_days", None)
                merchant.setdefault("website", None)
                merchant.setdefault("country", "US")
                merchant.setdefault("online_status", None)
                merchant.setdefault("status", None)

        # 2. 商品统计 - 使用 yp_us_products 表
        _stats_key = f"merchant_stats_{merchant_id}"
        if _stats_key in _count_cache and _time.time() < _count_cache[_stats_key][1]:
            stats = _count_cache[_stats_key][0]
        else:
            cur.execute(
                """SELECT COUNT(*) as total,
                          SUM(tracking_url IS NOT NULL AND tracking_url!='') as with_link
                   FROM yp_us_products
                   WHERE yp_merchant_id=%s""",
                (int(merchant_id),),
            )
            _raw = cur.fetchone() or {}
            # with_amazon 改为估算
            cur.execute(
                "SELECT COUNT(*) cnt FROM amazon_product_details d WHERE EXISTS (SELECT 1 FROM yp_us_products p WHERE p.asin=d.asin AND p.yp_merchant_id=%s)",
                (int(merchant_id),),
            )
            _amz = (cur.fetchone() or {}).get("cnt", 0)
            stats = {
                "total": str(_raw.get("total") or 0),
                "with_link": str(_raw.get("with_link") or 0),
                "with_amazon": str(_amz),
                "max_price": "0",
                "min_price": "0",
            }
            _count_cache[_stats_key] = (stats, _time.time() + 60)

        # 3. Google 关键词
        cur.execute(
            """SELECT keyword, keyword_source FROM ads_merchant_keywords
                       WHERE merchant_id=%s ORDER BY keyword_source, keyword""",
            (str(merchant_id),),
        )
        keywords = [
            {"kw": r["keyword"], "src": r["keyword_source"]} for r in cur.fetchall()
        ]

        # 4. SEMrush 竞品数据
        cur.execute(
            """SELECT domain, monthly_visits, organic_traffic, paid_traffic,
                              authority_score, organic_keywords_count, paid_keywords_count,
                              backlinks, top_organic_keywords, top_paid_keywords, ad_copies, scraped_at
                       FROM semrush_competitor_data
                       WHERE merchant_id=%s ORDER BY scraped_at DESC LIMIT 1""",
            (str(merchant_id),),
        )
        sem_raw = cur.fetchone()
        semrush = None
        if sem_raw:

            def _pj(v):
                if not v:
                    return []
                try:
                    return json.loads(v)
                except:
                    return []

            semrush = {
                "domain": sem_raw["domain"] or "",
                "monthly_visits": sem_raw["monthly_visits"] or "-",
                "organic_traffic": sem_raw["organic_traffic"] or "-",
                "paid_traffic": sem_raw["paid_traffic"] or "-",
                "authority_score": sem_raw["authority_score"] or "-",
                "organic_kw_count": sem_raw["organic_keywords_count"] or "-",
                "paid_kw_count": sem_raw["paid_keywords_count"] or "-",
                "backlinks": sem_raw["backlinks"] or "-",
                "top_organic_keywords": _pj(sem_raw["top_organic_keywords"])[:15],
                "top_paid_keywords": _pj(sem_raw["top_paid_keywords"])[:15],
                "ad_copies": _pj(sem_raw["ad_copies"])[:8],
                "scraped_at": str(sem_raw["scraped_at"])
                if sem_raw["scraped_at"]
                else "",
            }

        # 4.5 如果数据库没有数据，尝试从临时文件读取
        if not semrush:
            semrush_file = BASE_DIR / "temp" / f"semrush_collected_{merchant_id}.json"
            if semrush_file.exists():
                try:
                    file_data = json.loads(semrush_file.read_text(encoding="utf-8"))
                    raw_data = file_data.get("data", {})

                    # 转换数据格式
                    traffic = raw_data.get("traffic", {})
                    organic_kw = raw_data.get("organic_keywords", {})
                    paid_kw = raw_data.get("paid_keywords", {})
                    ad_copies_raw = raw_data.get("ad_copies", [])

                    # 提取 top_keywords
                    top_organic = (
                        organic_kw.get("top_keywords", [])
                        if isinstance(organic_kw, dict)
                        else []
                    )
                    top_paid = (
                        paid_kw.get("top_keywords", [])
                        if isinstance(paid_kw, dict)
                        else []
                    )

                    # 过滤无效广告文案（SEMrush UI 文本）
                    valid_ads = []
                    for ad in ad_copies_raw:
                        headline = ad.get("headline", "")
                        descs = ad.get("descriptions", [])
                        # 检查是否是 SEMrush UI 文本（中文）
                        is_ui_text = any(
                            any(
                                c in d
                                for c in [
                                    "节省用于",
                                    "揭示和分析",
                                    "特定国家",
                                    "获取报告",
                                    "Semrush 平台",
                                ]
                            )
                            for d in descs
                            if isinstance(d, str)
                        )
                        if not is_ui_text and headline:
                            valid_ads.append(ad)

                    semrush = {
                        "domain": raw_data.get("domain", ""),
                        "monthly_visits": "-",
                        "organic_traffic": traffic.get("organic", "-"),
                        "paid_traffic": traffic.get("paid", "-"),
                        "authority_score": str(traffic.get("authority_score", "-")),
                        "organic_kw_count": organic_kw.get("total", "-")
                        if isinstance(organic_kw, dict)
                        else "-",
                        "paid_kw_count": paid_kw.get("total", "-")
                        if isinstance(paid_kw, dict)
                        else "-",
                        "backlinks": str(traffic.get("backlinks", "-")),
                        "top_organic_keywords": top_organic[:15],
                        "top_paid_keywords": top_paid[:15],
                        "ad_copies": valid_ads[:8],
                        "scraped_at": file_data.get("collected_at", ""),
                    }
                    print(f"[DEBUG] 从临时文件加载 SEMrush 数据: {semrush_file}")
                except Exception as e:
                    print(f"[DEBUG] 读取临时文件失败: {e}")

        # 5. 最新商品（带 Amazon 数据）- 使用 yp_us_products 表
        # 支持搜索参数
        search_q = request.args.get("q", "").strip()
        if search_q:
            # 搜索模式：返回所有匹配的商品（不限数量）
            cur.execute(
                """SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                              d.title as amz_title, d.rating, d.review_count, d.main_image_url,
                              d.brand, d.price as amz_price, d.bullet_points, d.top_reviews,
                              d.availability, d.category_path, d.description, d.keywords,
                              pl.plan_status
                       FROM yp_us_products p
                       LEFT JOIN amazon_product_details d ON p.asin=d.asin
                       LEFT JOIN ads_plans pl ON p.asin=pl.asin
                       WHERE p.yp_merchant_id=%s AND p.tracking_url IS NOT NULL AND p.tracking_url!=''
                       AND (p.product_name LIKE %s OR p.asin LIKE %s)
                       ORDER BY p.id DESC LIMIT 200""",
                (int(merchant_id), f"%{search_q}%", f"%{search_q}%"),
            )
        else:
            # 默认模式：返回最新的 50 个
            cur.execute(
                """SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                              d.title as amz_title, d.rating, d.review_count, d.main_image_url,
                              d.brand, d.price as amz_price, d.bullet_points, d.top_reviews,
                              d.availability, d.category_path, d.description, d.keywords,
                              pl.plan_status
                       FROM yp_us_products p
                       LEFT JOIN amazon_product_details d ON p.asin=d.asin
                       LEFT JOIN ads_plans pl ON p.asin=pl.asin
                       WHERE p.yp_merchant_id=%s AND p.tracking_url IS NOT NULL AND p.tracking_url!=''
                       ORDER BY p.id DESC LIMIT 50""",
                (int(merchant_id),),
            )

        def _earn(ps, cs):
            try:
                v = float(ps or 0) * float(str(cs or "").rstrip("%")) / 100
                return f"${v:.2f}" if v > 0 else ""
            except:
                return ""

        def _pj(v):
            if not v:
                return []
            try:
                return json.loads(v)
            except:
                return []

        def _has_plan(status):
            return status == "completed"

        products = []
        for r in cur.fetchall():
            ps = str(r["price"]) if r["price"] else ""
            products.append(
                {
                    "asin": r["asin"] or "",
                    "product_name": r["product_name"] or "",
                    "yp_price": ps,
                    "commission": r["commission"] or "",
                    "earn": _earn(ps, r["commission"]),
                    "tracking_url": r["tracking_url"] or "",
                    "amazon_url": "",  # yp_us_products 没有此字段
                    "has_amazon": bool(r["amz_title"]),
                    "amz_title": r["amz_title"] or "",
                    "amz_price": str(r["amz_price"]) if r["amz_price"] else "",
                    "rating": str(r["rating"]) if r["rating"] else "",
                    "review_count": str(r["review_count"]) if r["review_count"] else "",
                    "image_url": r["main_image_url"] or "",
                    "brand": r["brand"] or "",
                    "availability": r["availability"] or "",
                    "category_path": r["category_path"] or "",
                    "bullet_points": _pj(r["bullet_points"]),
                    "top_reviews": _pj(r["top_reviews"]),
                    "description": (r["description"] or "")[:600],
                    "keywords": r["keywords"] or "",
                    "has_plan": _has_plan(r["plan_status"]),
                }
            )

        # 6. 已有广告方案数 - 使用 yp_us_products 表
        cur.execute(
            """SELECT COUNT(*) as cnt FROM ads_plans ap
                       JOIN yp_us_products p ON ap.asin=p.asin
                       WHERE p.yp_merchant_id=%s AND ap.plan_status='completed'""",
            (int(merchant_id),),
        )
        plan_count = (cur.fetchone() or {}).get("cnt", 0)

        conn.close()
        return jsonify(
            {
                "merchant": {
                    k: str(v) if v is not None else "" for k, v in merchant.items()
                },
                "stats": {
                    k: (str(v) if v is not None else "0") for k, v in stats.items()
                },
                "keywords": keywords,
                "semrush": semrush,
                "products": products,
                "plan_count": plan_count,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/merchant_room/<merchant_id>")
def page_merchant_room(merchant_id):
    # 强制不使用缓存，每次重新渲染
    html = MERCHANT_ROOM_HTML.replace(
        "<body>",
        '<body><div id="DEBUG_TEST" style="position:fixed;top:0;left:0;background:red;color:white;padding:10px;z-index:99999;">TEST V3</div>',
    )
    html = html.replace(
        "{% raw %}", '{% raw %}\nconsole.log("[INIT] JavaScript 开始加载 v3");'
    )
    return render_template_string(html, merchant_id=merchant_id)


# ── 商户作战室 HTML ──────────────────────────────────────────────────────────
MERCHANT_ROOM_HTML = (
    """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>商户作战室 · YP Affiliate</title>
"""
    + _BASE_STYLE_DARK
    + """
<style>
.room-layout { display: flex; gap: 18px; align-items: flex-start; padding: 22px 24px; }
.room-left  { width: 380px; flex-shrink: 0; display: flex; flex-direction: column; gap: 14px; }
.room-right { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.panel { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px; overflow: hidden; }
.panel-head { padding: 12px 16px; background: #15181f; border-bottom: 1px solid #2a2d36;
              display: flex; align-items: center; justify-content: space-between; }
.panel-head h3 { font-size: .88rem; font-weight: 700; color: #e0e0e0; margin: 0; }
.panel-body { padding: 14px 16px; }
.kw-panel-body { padding: 12px 16px; }
.stat-row { display: flex; gap: 10px; flex-wrap: wrap; }
.stat-box { flex: 1; min-width: 80px; background: #15181f; border-radius: 8px;
            padding: 10px 12px; text-align: center; }
.stat-box .num { font-size: 1.5rem; font-weight: 700; color: #64b5f6; }
.stat-box .lbl { font-size: .72rem; color: #888; margin-top: 2px; }
.kw-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.kw-tag { background: #0a2040; color: #64b5f6; border: 1px solid #1a4060;
          padding: 3px 10px; border-radius: 20px; font-size: .78rem; cursor: pointer; transition: all .15s; }
.kw-tag:hover { background: #1565c0; color: #fff; }
.kw-tag.related { background: #1a2a0a; color: #a5d6a7; border-color: #2a4a1a; }
.sem-row { display: flex; justify-content: space-between; padding: 4px 0;
           border-bottom: 1px solid #23262f; font-size: .84rem; }
.sem-row:last-child { border-bottom: none; }
.sem-key { color: #888; flex-shrink: 0; margin-right: 8px; }
.sem-val { color: #e0e0e0; font-weight: 600; font-family: monospace; text-align: right; }
.sem-kw-item { padding: 5px 8px; border-radius: 6px; background: #15181f;
               margin-bottom: 5px; font-size: .8rem; }
.sem-kw-item .kw-text { color: #90caf9; font-weight: 600; }
.sem-kw-item .kw-meta { color: #888; font-size: .74rem; margin-top: 2px; }
.ad-copy-card { background: #15181f; border-radius: 8px; padding: 10px 12px;
                margin-bottom: 8px; border-left: 3px solid #1565c0; }
.ad-copy-card .ad-title { color: #64b5f6; font-weight: 700; font-size: .87rem; margin-bottom: 4px; }
.ad-copy-card .ad-desc  { color: #ccc; font-size: .82rem; line-height: 1.5; }
.prod-card { background: #15181f; border-radius: 10px; padding: 14px;
             display: flex; gap: 12px; cursor: pointer; transition: all .15s;
             border: 1px solid #2a2d36; margin-bottom: 8px; }
.prod-card:hover { border-color: #2196f3; background: #1a2030; }
.prod-card.selected { border-color: #2196f3; background: #0d1929; }
.prod-img { width: 72px; height: 72px; border-radius: 8px; object-fit: cover;
            background: #23262f; flex-shrink: 0; }
.prod-img-placeholder { width: 72px; height: 72px; border-radius: 8px;
                        background: #23262f; display: flex; align-items: center;
                        justify-content: center; color: #555; font-size: 1.5rem; flex-shrink: 0; }
.prod-info { flex: 1; min-width: 0; }
.prod-name { font-size: .85rem; font-weight: 600; color: #e0e0e0;
             overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.prod-meta { display: flex; gap: 8px; align-items: center; margin-top: 4px; flex-wrap: wrap; }
.prod-price { color: #ffa726; font-weight: 700; font-size: .9rem; }
.prod-comm  { color: #66bb6a; font-size: .78rem; }
.prod-earn  { color: #ce93d8; font-size: .78rem; font-weight: 700; }
.prod-asin  { color: #888; font-size: .74rem; font-family: monospace; }
.star-row { display: flex; align-items: center; gap: 4px; margin-top: 3px; }
.stars { color: #ffa726; font-size: .85rem; }
.review-cnt { color: #888; font-size: .76rem; }
.prod-actions { display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap; }
.detail-panel { background: #15181f; border-radius: 12px; padding: 18px;
                border: 1px solid #2a2d36; }
.detail-section { margin-bottom: 18px; }
.detail-section h4 { font-size: .82rem; color: #888; font-weight: 600;
                     text-transform: uppercase; letter-spacing: .5px; margin-bottom: 10px;
                     padding-bottom: 6px; border-bottom: 1px solid #2a2d36; }
.bullet-item { padding: 6px 0 6px 16px; border-bottom: 1px solid #23262f;
               font-size: .84rem; color: #e0e0e0; line-height: 1.5;
               position: relative; }
.bullet-item::before { content: "•"; position: absolute; left: 2px; color: #2196f3; }
.bullet-item:last-child { border-bottom: none; }
.review-card { background: #1a1d24; border-radius: 8px; padding: 12px;
               margin-bottom: 8px; border: 1px solid #2a2d36; }
.review-stars { color: #ffa726; font-size: .85rem; margin-bottom: 4px; }
.review-title { font-weight: 700; font-size: .85rem; color: #e0e0e0; margin-bottom: 6px; }
.review-body  { font-size: .82rem; color: #ccc; line-height: 1.6; }
.copy-btn { background: #23262f; border: 1px solid #2a2d36; border-radius: 5px;
            padding: 2px 8px; font-size: .72rem; color: #adb5bd; cursor: pointer;
            transition: all .12s; white-space: nowrap; }
.copy-btn:hover { background: #2196f3; color: #fff; border-color: #2196f3; }
.link-url { font-family: monospace; font-size: .75rem; color: #888; word-break: break-all; }
.tab-bar { display: flex; gap: 2px; border-bottom: 1px solid #2a2d36; padding: 0 16px; }
.tab-btn { padding: 9px 14px; font-size: .82rem; color: #888; cursor: pointer;
           border: none; background: none; border-bottom: 2px solid transparent;
           transition: all .15s; font-weight: 600; }
.tab-btn.active { color: #2196f3; border-bottom-color: #2196f3; }
.tab-btn:hover:not(.active) { color: #e0e0e0; }
.tab-content { display: none; padding: 16px; }
.tab-content.active { display: block; }
.empty-hint { text-align: center; padding: 30px 20px; color: #555; font-size: .85rem; }
.room-header { padding: 12px 24px; border-bottom: 1px solid #2a2d36;
               display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.merchant-title { font-size: 1.3rem; font-weight: 700; color: #fff; }
.merchant-domain { font-size: .85rem; color: #888; }
.sem-status-badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
                    font-size: .74rem; font-weight: 600; }
.sem-ok   { background: #1a3d1a; color: #66bb6a; }
.sem-none { background: #2a2d36; color: #888; }
.scrape-semrush-btn { background: #1565c0; color: #fff; border: none; border-radius: 7px;
                       padding: 5px 14px; font-size: .8rem; font-weight: 600;
                       cursor: pointer; transition: background .15s; }
.scrape-semrush-btn:hover { background: #1976d2; }
.scrape-semrush-btn:disabled { opacity: .5; cursor: not-allowed; }
#roomWrap { min-height: 100vh; }
</style>
</head>
<body>
"""
    + _SCRAPE_TOPNAV
    + """
<div id="roomWrap">
  <div class="room-header" id="roomHeader">
    <a href="/merchants" style="color:#888;text-decoration:none;font-size:.85rem;">← 商户管理</a>
    <div>
      <div class="merchant-title" id="merchantTitle">加载中...</div>
      <div class="merchant-domain" id="merchantDomain"></div>
    </div>
    <div id="merchantBadges" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;"></div>
  </div>

  <div class="room-layout">
    <!-- ── 左栏：商户信息 + 关键词 + SEMrush ── -->
    <div class="room-left">

      <!-- 商户基本信息 -->
      <div class="panel">
        <div class="panel-head"><h3>商户信息</h3></div>
        <div class="panel-body" id="merchantInfo"><div class="empty-hint">加载中...</div></div>
      </div>

      <!-- Google Suggest 关键词 -->
      <div class="panel">
        <div class="panel-head">
          <h3>🔍 品牌关键词</h3>
          <button class="copy-btn" id="fetchKwBtn" onclick="fetchKeywords()">采集关键词</button>
        </div>
        <div class="kw-panel-body" id="kwPanel"><div class="empty-hint">暂无关键词，点击「采集关键词」</div></div>
      </div>

      <!-- SEMrush 竞品数据 -->
      <div class="panel">
        <div class="panel-head">
          <h3>📊 SEMrush 竞品</h3>
          <button class="scrape-semrush-btn" id="scrapeSemBtn" onclick="showCollectMethodModal()">采集竞品数据</button>
        </div>
        <div id="semrushPanel" class="sem-panel-body">
          <div class="tab-bar">
            <button class="tab-btn active" onclick="showSemTab('overview',this)">概览</button>
            <button class="tab-btn" onclick="showSemTab('organic',this)">自然词</button>
            <button class="tab-btn" onclick="showSemTab('paid',this)">付费词</button>
            <button class="tab-btn" onclick="showSemTab('adcopy',this)">广告文案</button>
          </div>
          <div class="tab-content active" id="sem-overview"><div class="empty-hint">暂无数据</div></div>
          <div class="tab-content" id="sem-organic"><div class="empty-hint">暂无数据</div></div>
          <div class="tab-content" id="sem-paid"><div class="empty-hint">暂无数据</div></div>
          <div class="tab-content" id="sem-adcopy"><div class="empty-hint">暂无数据</div></div>
        </div>
      </div>

    </div><!-- /room-left -->

    <!-- ── 右栏：商品列表 + 详情 ── -->
    <div class="room-right">

      <div class="panel">
        <div class="panel-head">
          <h3>📦 商品列表</h3>
          <div style="display:flex;gap:8px;align-items:center;">
            <input type="text" id="prodSearch" class="search-box" style="width:200px;font-size:.8rem;padding:5px 10px;"
                   placeholder="搜索商品..." oninput="filterProducts()">
            <span id="prodCount" style="color:#888;font-size:.78rem;"></span>
          </div>
        </div>
        <div class="panel-body" style="padding:10px;">
          <div id="prodList"><div class="empty-hint">加载中...</div></div>
        </div>
      </div>

    </div><!-- /room-right -->
  </div><!-- /room-layout -->
</div>

<!-- 商品详情侧抽屉 -->
<div id="detailDrawer" style="display:none;position:fixed;right:0;top:0;bottom:0;width:480px;
     background:#1a1d24;border-left:1px solid #2a2d36;z-index:500;overflow-y:auto;
     box-shadow:-4px 0 20px rgba(0,0,0,.5);">
  <div style="padding:14px 18px;background:#15181f;border-bottom:1px solid #2a2d36;
              display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10;">
    <span style="font-weight:700;font-size:.95rem;color:#fff;" id="drawerAsin"></span>
    <button onclick="closeDrawer()" style="background:none;border:none;color:#888;font-size:1.3rem;cursor:pointer;">✕</button>
  </div>
  <div id="drawerContent" style="padding:16px;"></div>
</div>
<div id="drawerOverlay" onclick="closeDrawer()" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.4);z-index:499;"></div>

<div class="toast-container" id="toast-container"></div>

<!-- 采集方式选择弹窗 -->
<div id="collectMethodModal" style="display:none;position:fixed;inset:0;z-index:900;background:rgba(0,0,0,.6);align-items:center;justify-content:center;">
  <div style="background:#1a1d24;border:1px solid #2a2d36;border-radius:16px;padding:28px;width:480px;max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,.5);">
    <div style="color:#e0e0e0;font-size:18px;font-weight:bold;margin-bottom:8px;text-align:center;">选择采集方式</div>
    <div style="color:#888;font-size:13px;margin-bottom:24px;text-align:center;">选择如何获取 SEMrush 竞品数据</div>
    
    <div style="display:flex;flex-direction:column;gap:12px;">
      <div onclick="startAutoCollect()" style="background:#252830;border:2px solid #3a3d46;border-radius:12px;padding:18px;cursor:pointer;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="font-size:28px;">🤖</div>
          <div>
            <div style="color:#e0e0e0;font-size:15px;font-weight:600;">自动采集</div>
            <div style="color:#888;font-size:12px;margin-top:4px;">打开外贸侠，自动采集 SEMrush 数据</div>
          </div>
        </div>
      </div>
      
      <div onclick="showScreenshotModal()" style="background:#252830;border:2px solid #4caf50;border-radius:12px;padding:18px;cursor:pointer;position:relative;">
        <div style="position:absolute;top:8px;right:8px;background:#4caf50;color:#fff;font-size:10px;padding:2px 8px;border-radius:4px;">推荐</div>
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="font-size:28px;">📸</div>
          <div>
            <div style="color:#e0e0e0;font-size:15px;font-weight:600;">上传截图</div>
            <div style="color:#888;font-size:12px;margin-top:4px;">手动截图后上传，AI 自动解析数据</div>
          </div>
        </div>
      </div>
    </div>
    
    <div style="text-align:center;margin-top:20px;">
      <button onclick="closeCollectMethodModal()" style="padding:8px 24px;border:1px solid #3a3d46;border-radius:8px;background:transparent;color:#888;cursor:pointer;font-size:14px;">取消</button>
    </div>
  </div>
</div>

<!-- 域名输入弹窗（替代 prompt()） -->
<div id="domainModal" style="display:none;position:fixed;inset:0;z-index:900;background:rgba(0,0,0,.6);align-items:center;justify-content:center;">
  <div style="background:#1e1e2e;border:1px solid #444;border-radius:12px;padding:24px;width:420px;max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,.5);">
    <div style="color:#e0e0e0;font-size:16px;font-weight:bold;margin-bottom:12px;">输入官网域名</div>
    <div style="color:#aaa;font-size:13px;margin-bottom:16px;">商户没有 website 字段，请输入官网域名用于 SEMrush 竞品分析：</div>
    <input id="domainInput" type="text" placeholder="例如: beautybyearth.com" style="width:100%;padding:10px 14px;border:1px solid #555;border-radius:6px;background:#2a2a3e;color:#e0e0e0;font-size:14px;box-sizing:border-box;outline:none;" onfocus="this.style.borderColor='#6c8aff'" onblur="this.style.borderColor='#555'" onkeydown="if(event.key==='Enter'){document.getElementById('domainConfirmBtn').click();}">
    <div style="display:flex;gap:10px;margin-top:16px;justify-content:flex-end;">
      <button id="domainCancelBtn" style="padding:8px 20px;border:1px solid #555;border-radius:6px;background:transparent;color:#aaa;cursor:pointer;font-size:14px;" onclick="closeDomainModal()">取消</button>
      <button id="domainConfirmBtn" style="padding:8px 20px;border:none;border-radius:6px;background:#6c8aff;color:#fff;cursor:pointer;font-size:14px;font-weight:bold;" onclick="confirmDomain()">确认采集</button>
    </div>
  </div>
</div>

<!-- 截图上传弹窗 -->
<div id="screenshotModal" style="display:none;position:fixed;inset:0;z-index:900;background:rgba(0,0,0,.7);align-items:center;justify-content:center;overflow-y:auto;padding:20px;">
  <div style="background:#1a1d24;border:1px solid #2a2d36;border-radius:16px;padding:24px;width:800px;max-width:95vw;max-height:90vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,.6);">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;border-bottom:1px solid #2a2d36;padding-bottom:16px;">
      <div>
        <div style="color:#e0e0e0;font-size:18px;font-weight:bold;">📸 上传 SEMrush 截图</div>
        <div style="color:#888;font-size:13px;margin-top:4px;">上传截图后自动解析数据，未上传的部分将为空</div>
      </div>
      <button onclick="closeScreenshotModal()" style="background:none;border:none;color:#888;font-size:24px;cursor:pointer;">&times;</button>
    </div>
    
    <!-- 域名输入 -->
    <div style="margin-bottom:20px;">
      <label style="color:#adb5bd;font-size:13px;display:block;margin-bottom:6px;">官网域名 <span style="color:#f44336;">*</span></label>
      <input id="screenshotDomain" type="text" placeholder="例如: beautybyearth.com" style="width:100%;padding:10px 14px;border:1px solid #3a3d46;border-radius:8px;background:#252830;color:#e0e0e0;font-size:14px;box-sizing:border-box;">
    </div>
    
    <!-- 截图上传区域 -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px;">
      <!-- 概览截图 -->
      <div class="upload-zone" id="uploadOverview" onclick="triggerUpload('overview')" style="border:2px dashed #3a3d46;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:all .2s;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:32px;margin-bottom:8px;">📊</div>
        <div style="color:#adb5bd;font-size:14px;font-weight:600;">概览截图</div>
        <div style="color:#666;font-size:12px;margin-top:4px;">流量、权威分数、关键词数量</div>
        <div id="uploadOverviewStatus" style="color:#4caf50;font-size:12px;margin-top:8px;display:none;">✓ 已上传</div>
        <input type="file" id="fileOverview" accept="image/*" style="display:none;" onchange="handleFileSelect(this, 'overview')">
      </div>
      
      <!-- 自然关键词截图 -->
      <div class="upload-zone" id="uploadOrganic" onclick="triggerUpload('organic')" style="border:2px dashed #3a3d46;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:all .2s;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:32px;margin-bottom:8px;">🔍</div>
        <div style="color:#adb5bd;font-size:14px;font-weight:600;">自然关键词截图</div>
        <div style="color:#666;font-size:12px;margin-top:4px;">自然搜索关键词列表</div>
        <div id="uploadOrganicStatus" style="color:#4caf50;font-size:12px;margin-top:8px;display:none;">✓ 已上传</div>
        <input type="file" id="fileOrganic" accept="image/*" style="display:none;" onchange="handleFileSelect(this, 'organic')">
      </div>
      
      <!-- 付费关键词截图 -->
      <div class="upload-zone" id="uploadPaid" onclick="triggerUpload('paid')" style="border:2px dashed #3a3d46;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:all .2s;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:32px;margin-bottom:8px;">💰</div>
        <div style="color:#adb5bd;font-size:14px;font-weight:600;">付费关键词截图</div>
        <div style="color:#666;font-size:12px;margin-top:4px;">付费搜索关键词列表</div>
        <div id="uploadPaidStatus" style="color:#4caf50;font-size:12px;margin-top:8px;display:none;">✓ 已上传</div>
        <input type="file" id="filePaid" accept="image/*" style="display:none;" onchange="handleFileSelect(this, 'paid')">
      </div>
      
      <!-- 广告文案截图 -->
      <div class="upload-zone" id="uploadAdcopy" onclick="triggerUpload('adcopy')" style="border:2px dashed #3a3d46;border-radius:12px;padding:20px;text-align:center;cursor:pointer;transition:all .2s;min-height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;">
        <div style="font-size:32px;margin-bottom:8px;">📝</div>
        <div style="color:#adb5bd;font-size:14px;font-weight:600;">广告文案截图</div>
        <div style="color:#666;font-size:12px;margin-top:4px;">广告标题和描述</div>
        <div id="uploadAdcopyStatus" style="color:#4caf50;font-size:12px;margin-top:8px;display:none;">✓ 已上传</div>
        <input type="file" id="fileAdcopy" accept="image/*" style="display:none;" onchange="handleFileSelect(this, 'adcopy')">
      </div>
    </div>
    
    <!-- 解析结果预览 -->
    <div id="parseResult" style="display:none;background:#252830;border-radius:12px;padding:16px;margin-bottom:20px;">
      <div style="color:#4fc3f7;font-size:14px;font-weight:600;margin-bottom:12px;">📋 解析结果预览</div>
      <div id="parseResultContent" style="color:#adb5bd;font-size:13px;line-height:1.6;max-height:200px;overflow-y:auto;"></div>
    </div>
    
    <!-- 操作按钮 -->
    <div style="display:flex;gap:12px;justify-content:flex-end;border-top:1px solid #2a2d36;padding-top:16px;">
      <button onclick="closeScreenshotModal()" style="padding:10px 24px;border:1px solid #3a3d46;border-radius:8px;background:transparent;color:#adb5bd;cursor:pointer;font-size:14px;">取消</button>
      <button id="parseBtn" onclick="console.log('[TEST] Button clicked'); if(typeof parseScreenshots === 'function') { parseScreenshots(); } else { console.error('[TEST] parseScreenshots is not defined!'); alert('parseScreenshots函数未定义，请刷新页面'); }" style="padding:10px 24px;border:none;border-radius:8px;background:#6b5b95;color:#fff;cursor:pointer;font-size:14px;font-weight:600;">🔍 解析截图</button>
      <button id="saveBtn" onclick="saveScreenshotsData()" style="padding:10px 24px;border:none;border-radius:8px;background:#4caf50;color:#fff;cursor:pointer;font-size:14px;font-weight:600;display:none;">💾 保存数据</button>
    </div>
  </div>
</div>

<style>
.upload-zone:hover { border-color:#6c8aff !important; background:#252830; }
.upload-zone.dragover { border-color:#4caf50 !important; background:#1a3a1a; }
</style>

<script>
var MID = '{{ merchant_id }}';
{% raw %}
console.log('[INIT] JavaScript 开始加载');
var allProducts = [];
var filteredProducts = [];
var semData = null;

// 立即测试函数定义
function testInit() {
  console.log('[INIT] testInit 被调用');
}
testInit();

function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(function() {
    toast('已复制到剪贴板', 'success');
  }).catch(function() {
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta);
    ta.select(); document.execCommand('copy'); ta.remove();
    toast('已复制', 'success');
  });
}

function starsHtml(rating) {
  var n = parseFloat(rating) || 0;
  var full = Math.floor(n); var half = (n - full) >= 0.3 ? 1 : 0;
  var s = '';
  for (var i=0;i<full;i++) s += '★';
  if (half) s += '½';
  while (s.replace('½','x').length < 5) s += '☆';
  return '<span class="stars">' + s + '</span> <span style="color:#ffa726;font-size:.82rem;">' + n.toFixed(1) + '</span>';
}

function showSemTab(name, btn) {
  document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('.tab-content').forEach(function(c) { c.classList.remove('active'); });
  btn.classList.add('active');
  document.getElementById('sem-' + name).classList.add('active');
}

// ── 加载作战室数据 ──────────────────────────────────────────────────────────
function loadRoom() {
  console.log('[DEBUG] loadRoom called, MID:', MID);
  try {
    fetch('/api/merchant_room/' + MID)
      .then(function(r) { 
        console.log('[DEBUG] fetch response:', r.status);
        return r.json(); 
      })
      .then(function(d) {
        console.log('[DEBUG] data received:', d);
        try {
          if (d.error) { toast('加载失败: ' + d.error, 'error'); return; }
          renderMerchantInfo(d.merchant, d.stats, d.plan_count);
          renderKeywords(d.keywords);
          renderSemrush(d.semrush);
          allProducts = d.products || [];
          filteredProducts = allProducts;
          renderProducts(allProducts);
        } catch(e) {
          console.error('renderRoom error:', e);
          toast('渲染失败: ' + e.message, 'error');
        }
      })
      .catch(function(e) { 
        console.error('[DEBUG] fetch error:', e);
        toast('网络错误: ' + e, 'error'); 
      });
  } catch(err) {
    console.error('[DEBUG] loadRoom error:', err);
    alert('loadRoom error: ' + err.message);
  }
}

// ── 商户信息 ────────────────────────────────────────────────────────────────
function renderMerchantInfo(m, stats, planCount) {
  document.getElementById('merchantTitle').textContent = m.merchant_name || ('商户 ' + MID);
  if (m.website) document.getElementById('merchantDomain').textContent = m.website;

  var badges = document.getElementById('merchantBadges');
  var onlineStatus = (m.online_status || '').toUpperCase();
  var online = onlineStatus === 'ONLINE';
  badges.innerHTML =
    '<span class="sem-status-badge ' + (online ? 'sem-ok' : 'sem-none') + '">' + htmlEscRoom(m.online_status || '未知') + '</span>' +
    '<span class="pill pill-blue">' + htmlEscRoom(m.country || '-') + '</span>' +
    (m.avg_payout ? '<span class="pill pill-orange">$' + parseFloat(m.avg_payout).toFixed(2) + '/转化</span>' : '') +
    (m.cookie_days ? '<span class="pill pill-gray">' + htmlEscRoom(m.cookie_days) + 'd Cookie</span>' : '') +
    '<span class="pill pill-purple">' + planCount + ' 个广告方案</span>';

  var info = document.getElementById('merchantInfo');
  var rows = [
    ['商户ID', htmlEscRoom(m.merchant_id)],
    ['佣金/次', m.avg_payout ? '$' + parseFloat(m.avg_payout).toFixed(2) : '-'],
    ['Cookie天数', htmlEscRoom((m.cookie_days || '-') + (m.cookie_days ? 'd' : ''))],
    ['网站', m.website ? '<a href="https://' + htmlEscRoom(m.website) + '" target="_blank" style="color:#64b5f6;">' + htmlEscRoom(m.website) + '</a>' : '-'],
    ['状态', htmlEscRoom(m.status || '-')],
    ['商品总数', parseInt(stats.total || 0).toLocaleString()],
    ['有推广链接', parseInt(stats.with_link || 0).toLocaleString()],
    ['已采集Amazon', parseInt(stats.with_amazon || 0).toLocaleString()],
    ['价格区间', stats.min_price && stats.max_price && parseFloat(stats.min_price)>0 ? '$' + parseFloat(stats.min_price).toFixed(2) + ' ~ $' + parseFloat(stats.max_price).toFixed(2) : '-'],
    ['广告方案', planCount + ' 个'],
  ];
  info.innerHTML = rows.map(function(r) {
    return '<div class="sem-row"><span class="sem-key">' + r[0] + '</span><span class="sem-val">' + r[1] + '</span></div>';
  }).join('');
}

// ── 关键词 ───────────────────────────────────────────────────────────────────
function htmlEscRoom(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function renderKeywords(kws) {
  var panel = document.getElementById('kwPanel');
  if (!kws || !kws.length) {
    panel.innerHTML = '<div class="empty-hint">暂无关键词，点击「采集关键词」</div>'; return;
  }
  var auto = kws.filter(function(k) { return k.src === 'autocomplete'; });
  var rel  = kws.filter(function(k) { return k.src === 'related'; });
  var html = '';
  if (auto.length) {
    html += '<div style="font-size:.74rem;color:#888;margin-bottom:6px;font-weight:600;">自动补全 (' + auto.length + ')</div>';
    html += '<div class="kw-grid">' + auto.map(function(k) {
      return '<span class="kw-tag" data-kw="'+htmlEscRoom(k.kw)+'" onclick="copyText(this.dataset.kw)" title="点击复制">' + htmlEscRoom(k.kw) + '</span>';
    }).join('') + '</div>';
  }
  if (rel.length) {
    html += '<div style="font-size:.74rem;color:#888;margin-top:12px;margin-bottom:6px;font-weight:600;">相关搜索 (' + rel.length + ')</div>';
    html += '<div class="kw-grid">' + rel.map(function(k) {
      return '<span class="kw-tag related" data-kw="'+htmlEscRoom(k.kw)+'" onclick="copyText(this.dataset.kw)" title="点击复制">' + htmlEscRoom(k.kw) + '</span>';
    }).join('') + '</div>';
  }
  panel.innerHTML = html;
}

function fetchKeywords() {
  var btn = document.getElementById('fetchKwBtn');
  btn.textContent = '采集中...'; btn.disabled = true;
  fetch('/api/fetch_suggest/' + MID, {method:'POST'})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      btn.disabled = false; btn.textContent = '采集关键词';
      if (d.success) {
        toast('采集成功，共 ' + d.keyword_count + ' 个关键词', 'success');
        renderKeywords((d.keywords||[]).map(function(k) { return {kw:k, src:'autocomplete'}; }));
        loadRoom();
      } else {
        toast('采集失败: ' + (d.message || '未知错误'), 'error');
      }
    })
    .catch(function(e) { btn.disabled=false; btn.textContent='采集关键词'; toast('请求失败: '+e,'error'); });
}

// ── SEMrush ──────────────────────────────────────────────────────────────────
function renderSemrush(sem) {
  semData = sem;
  if (!sem) {
    document.getElementById('sem-overview').innerHTML = '<div class="empty-hint">暂无竞品数据，点击「采集竞品数据」</div>';
    return;
  }
  // 概览
  var ov = '<div style="padding:8px 0;">';
  var ovRows = [
    ['域名', sem.domain],
    ['月均流量', sem.monthly_visits],
    ['自然流量', sem.organic_traffic],
    ['付费流量', sem.paid_traffic],
    ['权威评分', sem.authority_score],
    ['自然关键词', sem.organic_kw_count],
    ['付费关键词', sem.paid_kw_count],
    ['外链数', sem.backlinks],
    ['采集时间', sem.scraped_at ? sem.scraped_at.substring(0,16) : '-'],
  ];
  ov += ovRows.map(function(r) {
    return '<div class="sem-row"><span class="sem-key">' + r[0] + '</span><span class="sem-val">' + (r[1]||'-') + '</span></div>';
  }).join('');
  ov += '</div>';
  document.getElementById('sem-overview').innerHTML = ov;

  // 自然词
  var org = sem.top_organic_keywords || [];
  if (org.length) {
    document.getElementById('sem-organic').innerHTML = org.map(function(k) {
      var kw = typeof k === 'string' ? k : (k.keyword || k.kw || JSON.stringify(k));
      var vol = typeof k === 'object' ? (k.volume || k.search_volume || '') : '';
      var pos = typeof k === 'object' ? (k.position || k.pos || '') : '';
      return '<div class="sem-kw-item"><div class="kw-text">' + kw + '</div>' +
             (vol||pos ? '<div class="kw-meta">' + (pos?'位置:'+pos+' ':'') + (vol?'搜索量:'+vol:'') + '</div>' : '') +
             '</div>';
    }).join('');
  } else {
    document.getElementById('sem-organic').innerHTML = '<div class="empty-hint">暂无自然搜索词</div>';
  }

  // 付费词
  var paid = sem.top_paid_keywords || [];
  if (paid.length) {
    document.getElementById('sem-paid').innerHTML = paid.map(function(k) {
      var kw = typeof k === 'string' ? k : (k.keyword || k.kw || JSON.stringify(k));
      var cpc = typeof k === 'object' ? (k.cpc || k.cost || '') : '';
      var vol = typeof k === 'object' ? (k.volume || k.search_volume || '') : '';
      return '<div class="sem-kw-item"><div class="kw-text">' + kw + '</div>' +
             (cpc||vol ? '<div class="kw-meta">' + (cpc?'CPC:$'+cpc+' ':'') + (vol?'搜索量:'+vol:'') + '</div>' : '') +
             '</div>';
    }).join('');
  } else {
    document.getElementById('sem-paid').innerHTML = '<div class="empty-hint">暂无付费关键词</div>';
  }

  // 广告文案
  var ads = sem.ad_copies || [];
  if (ads.length) {
    document.getElementById('sem-adcopy').innerHTML = ads.map(function(a) {
      var title = typeof a === 'string' ? a : (a.title || a.headline || a.ad_title || '');
      var desc  = typeof a === 'object' ? (a.description || a.desc || a.body || '') : '';
      if (!title && typeof a === 'object') title = JSON.stringify(a).substring(0,80);
      return '<div class="ad-copy-card">' +
             '<div class="ad-title">' + title + '</div>' +
             (desc ? '<div class="ad-desc">' + desc + '</div>' : '') +
             '</div>';
    }).join('');
  } else {
    document.getElementById('sem-adcopy').innerHTML = '<div class="empty-hint">暂无广告文案样本</div>';
  }
}

// ── 截图上传相关函数 ──────────────────────────
var uploadedFiles = {};
var parsedData = null;

function htmlEsc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// 采集方式选择弹窗
function showCollectMethodModal() {
  document.getElementById('collectMethodModal').style.display = 'flex';
}

function closeCollectMethodModal() {
  document.getElementById('collectMethodModal').style.display = 'none';
}

function startAutoCollect() {
  closeCollectMethodModal();
  scrapeSemrush();  // 调用原有的自动采集函数
}

function showScreenshotModal() {
  var modal = document.getElementById('screenshotModal');
  modal.style.display = 'flex';
  
  // 重置状态
  uploadedFiles = {};
  parsedData = null;
  document.getElementById('screenshotDomain').value = '';
  document.getElementById('parseResult').style.display = 'none';
  document.getElementById('saveBtn').style.display = 'none';
  
  // 重置上传状态
  ['overview', 'organic', 'paid', 'adcopy'].forEach(function(type) {
    document.getElementById('upload' + type.charAt(0).toUpperCase() + type.slice(1) + 'Status').style.display = 'none';
    document.getElementById('file' + type.charAt(0).toUpperCase() + type.slice(1)).value = '';
  });
  
  // 自动填充域名
  var domainField = document.getElementById('domainInput');
  if (domainField && domainField.value) {
    document.getElementById('screenshotDomain').value = domainField.value;
  }
}

function closeScreenshotModal() {
  document.getElementById('screenshotModal').style.display = 'none';
}

function triggerUpload(type) {
  document.getElementById('file' + type.charAt(0).toUpperCase() + type.slice(1)).click();
}

function handleFileSelect(input, type) {
  if (input.files && input.files[0]) {
    uploadedFiles[type] = input.files[0];
    document.getElementById('upload' + type.charAt(0).toUpperCase() + type.slice(1) + 'Status').style.display = 'block';
    document.getElementById('upload' + type.charAt(0).toUpperCase() + type.slice(1) + 'Status').textContent = '✓ 已上传: ' + input.files[0].name.substring(0, 20);
    toast('已选择 ' + type + ' 截图', 'success');
  }
}

function parseScreenshots() {
  console.log('[DEBUG] parseScreenshots 被调用');
  var domain = document.getElementById('screenshotDomain').value.trim();
  console.log('[DEBUG] domain:', domain);
  if (!domain) {
    toast('请输入官网域名', 'error');
    return;
  }
  
  console.log('[DEBUG] uploadedFiles:', Object.keys(uploadedFiles));
  if (Object.keys(uploadedFiles).length === 0) {
    toast('请至少上传一张截图', 'error');
    return;
  }
  
  var btn = document.getElementById('parseBtn');
  btn.textContent = '解析中...';
  btn.disabled = true;
  
  // 构建 FormData
  var formData = new FormData();
  formData.append('domain', domain);
  formData.append('merchant_id', MID);
  
  for (var type in uploadedFiles) {
    formData.append('screenshot_' + type, uploadedFiles[type]);
    console.log('[DEBUG] 添加文件:', type, uploadedFiles[type].name);
  }
  
  console.log('[DEBUG] 发送请求到 /api/parse_semrush_screenshots');
  fetch('/api/parse_semrush_screenshots', {
    method: 'POST',
    body: formData
  })
  .then(function(r) { 
    console.log('[DEBUG] 响应状态:', r.status);
    return r.json(); 
  })
  .then(function(d) {
    console.log('[DEBUG] 响应数据:', d);
    btn.textContent = '🔍 解析截图';
    btn.disabled = false;
    
    if (d.success) {
      parsedData = d.data;
      
      // 显示解析结果
      var resultDiv = document.getElementById('parseResult');
      var contentDiv = document.getElementById('parseResultContent');
      resultDiv.style.display = 'block';
      
      var html = '';
      if (d.data.traffic) {
        html += '<div style="margin-bottom:10px;"><b>流量概览:</b> 自然流量 ' + (d.data.traffic.organic || '-') + 
                ' | 付费流量 ' + (d.data.traffic.paid || '-') + 
                ' | 权威分数 ' + (d.data.traffic.authority_score || '-') + '</div>';
      }
      if (d.data.organic_keywords && d.data.organic_keywords.length > 0) {
        html += '<div style="margin-bottom:10px;"><b>自然关键词:</b> ' + d.data.organic_keywords.length + ' 条</div>';
      }
      if (d.data.paid_keywords && d.data.paid_keywords.length > 0) {
        html += '<div style="margin-bottom:10px;"><b>付费关键词:</b> ' + d.data.paid_keywords.length + ' 条</div>';
      }
      if (d.data.ad_copies && d.data.ad_copies.length > 0) {
        html += '<div style="margin-bottom:10px;"><b>广告文案:</b> ' + d.data.ad_copies.length + ' 条</div>';
      }
      
      // 显示OCR原始文本用于调试
      if (d.data._debug_ocr) {
        html += '<div style="margin-top:15px;border-top:1px solid #3a3d46;padding-top:10px;">';
        html += '<b style="color:#ffb74d;">OCR原始文本 (调试):</b>';
        for (var ocrType in d.data._debug_ocr) {
          html += '<div style="margin-top:8px;padding:8px;background:#1a1d24;border-radius:4px;font-size:12px;color:#888;max-height:150px;overflow:auto;">';
          html += '<b>' + ocrType + ':</b> ' + htmlEsc(d.data._debug_ocr[ocrType].substring(0, 500));
          html += '</div>';
        }
        html += '</div>';
      }
      
      contentDiv.innerHTML = html || '<div style="color:#888;">解析完成，但未提取到有效数据</div>';
      
      // 显示保存按钮
      document.getElementById('saveBtn').style.display = 'inline-block';
      toast('解析完成！', 'success');
    } else {
      toast('解析失败: ' + (d.error || '未知错误'), 'error');
    }
  })
  .catch(function(e) {
    btn.textContent = '🔍 解析截图';
    btn.disabled = false;
    toast('请求失败: ' + e.message, 'error');
  });
}

function saveScreenshotsData() {
  if (!parsedData) {
    toast('请先解析截图', 'error');
    return;
  }
  
  var btn = document.getElementById('saveBtn');
  btn.textContent = '保存中...';
  btn.disabled = true;
  
  var domain = document.getElementById('screenshotDomain').value.trim();
  console.log('[DEBUG] 保存数据:', {merchant_id: MID, domain: domain, data: parsedData});
  
  var payload;
  try {
    payload = JSON.stringify({
      merchant_id: MID,
      domain: domain,
      data: parsedData
    });
  } catch(e) {
    console.error('[DEBUG] JSON序列化失败:', e);
    toast('数据格式错误: ' + e.message, 'error');
    btn.textContent = '💾 保存数据';
    btn.disabled = false;
    return;
  }
  
  fetch('/api/save_semrush_data', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: payload
  })
  .then(function(r) { 
    console.log('[DEBUG] 响应状态:', r.status);
    return r.json(); 
  })
  .then(function(d) {
    console.log('[DEBUG] 响应数据:', d);
    btn.textContent = '💾 保存数据';
    btn.disabled = false;
    
    if (d.success) {
      toast('数据保存成功！', 'success');
      closeScreenshotModal();
      setTimeout(function() { location.reload(); }, 1000);
    } else {
      toast('保存失败: ' + (d.error || '未知错误'), 'error');
    }
  })
  .catch(function(e) {
    console.error('[DEBUG] 请求失败:', e);
    btn.textContent = '💾 保存数据';
    btn.disabled = false;
    toast('请求失败: ' + e.message, 'error');
  });
}

function scrapeSemrush(manualDomain) {
  var btn = document.getElementById('scrapeSemBtn');
  btn.textContent = '采集中...'; btn.disabled = true;
  
  // 构建请求体
  var payloadObj = { use_waimaoxia: true };
  if (manualDomain) {
    payloadObj.domain = manualDomain;
  }
  var payload = JSON.stringify(payloadObj);
  
  fetch('/api/scrape_semrush/' + MID, {
    method:'POST',
    headers: {'Content-Type': 'application/json'},
    body: payload
  })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      btn.disabled = false; btn.textContent = '采集竞品数据';
      if (d.ok) {
        var modeText = d.mode === 'waimaoxia' ? '外贸侠模式' : '传统模式';
        toast('SEMrush 采集任务已启动 (' + modeText + ')，请在新窗口中完成登录', 'success');
        // 启动状态轮询
        startStatusPolling(MID);
      } else if (d.need_domain) {
        // 需要手动输入域名 - 用自定义弹窗替代 prompt()
        showDomainModal();
      } else {
        toast('启动失败: ' + (d.msg || ''), 'error');
      }
    })
    .catch(function(e) { btn.disabled=false; btn.textContent='采集竞品数据'; toast('请求失败: '+e,'error'); });
}

// ── 域名输入弹窗（替代 prompt()）──────────────────
function showDomainModal() {
  var modal = document.getElementById('domainModal');
  var input = document.getElementById('domainInput');
  modal.style.display = 'flex';
  input.value = '';
  setTimeout(function() { input.focus(); }, 100);
}

function closeDomainModal() {
  document.getElementById('domainModal').style.display = 'none';
}

function confirmDomain() {
  var input = document.getElementById('domainInput').value.trim();
  if (!input) {
    document.getElementById('domainInput').style.borderColor = '#ff5555';
    return;
  }
  closeDomainModal();
  scrapeSemrush(input);
}

// 轮询采集状态
var statusPollingInterval = null;
function startStatusPolling(merchantId) {
  if (statusPollingInterval) {
    clearInterval(statusPollingInterval);
  }
  
  var pollCount = 0;
  var maxPolls = 60; // 最多轮询60次（10分钟）
  
  statusPollingInterval = setInterval(function() {
    pollCount++;
    if (pollCount > maxPolls) {
      clearInterval(statusPollingInterval);
      toast('状态轮询超时，请手动刷新查看结果', 'warning');
      return;
    }
    
    fetch('/api/scrape_semrush_status/' + merchantId)
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok && d.status === 'completed') {
          clearInterval(statusPollingInterval);
          toast('SEMrush 数据采集完成！', 'success');
          // 刷新页面显示新数据
          setTimeout(function() { location.reload(); }, 1500);
        }
      })
      .catch(function(e) { /* 忽略轮询错误 */ });
  }, 10000); // 每10秒轮询一次
}

// ── 商品列表 ─────────────────────────────────────────────────────────────────
function filterProducts() {
  var q = document.getElementById('prodSearch').value.trim();
  
  // 如果搜索词为空，使用本地过滤
  if (!q) {
    filteredProducts = allProducts;
    renderProducts(filteredProducts);
    return;
  }
  
  // 如果搜索词长度 >= 2，调用后端 API 搜索
  if (q.length >= 2) {
    fetch('/api/merchant_room/' + MID + '?q=' + encodeURIComponent(q))
      .then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.products) {
          filteredProducts = d.products;
          renderProducts(filteredProducts);
        }
      })
      .catch(function(e) {
        // 后端搜索失败，使用本地过滤
        filteredProducts = allProducts.filter(function(p) {
          return p.product_name.toLowerCase().includes(q.toLowerCase()) || p.asin.toLowerCase().includes(q.toLowerCase());
        });
        renderProducts(filteredProducts);
      });
  } else {
    // 搜索词太短，使用本地过滤
    filteredProducts = allProducts.filter(function(p) {
      return p.product_name.toLowerCase().includes(q.toLowerCase()) || p.asin.toLowerCase().includes(q.toLowerCase());
    });
    renderProducts(filteredProducts);
  }
}

function renderProducts(prods) {
  var el = document.getElementById('prodList');
  document.getElementById('prodCount').textContent = prods.length + ' / ' + allProducts.length + ' 件';
  if (!prods.length) { el.innerHTML = '<div class="empty-hint">暂无商品数据</div>'; return; }
  el.innerHTML = prods.map(function(p, i) {
    var imgSrc = htmlEscRoom(p.image_url);
    var img = p.image_url
      ? '<img class="prod-img" src="' + imgSrc + '" loading="lazy" onerror="this.hidden=1">'
      : '<div class="prod-img-placeholder">&#x1F4E6;</div>';
    var stars = p.rating ? starsHtml(p.rating) : '';
    var revCnt = p.review_count ? '<span class="review-cnt">(' + parseInt(p.review_count||0).toLocaleString() + ' reviews)</span>' : '';
    var amzBadge = p.has_amazon ? '<span class="pill pill-green" style="font-size:.7rem;padding:1px 6px;">Amazon&#10003;</span>' : '<span class="pill pill-gray" style="font-size:.7rem;padding:1px 6px;">&#26410;&#37319;&#38598;</span>';
    var displayName = htmlEscRoom(p.amz_title || p.product_name);
    return '<div class="prod-card" id="pcard_' + i + '" data-idx="' + i + '" onclick="selectProduct(parseInt(this.dataset.idx))">' +
           img +
           '<div class="prod-info">' +
           '<div class="prod-name">' + displayName + '</div>' +
           '<div class="prod-meta">' +
           '<span class="prod-asin">' + htmlEscRoom(p.asin) + '</span>' + amzBadge +
           '</div>' +
           '<div class="prod-meta">' +
           (p.yp_price ? '<span class="prod-price">$' + parseFloat(p.yp_price||0).toFixed(2) + '</span>' : '') +
           (p.commission ? '<span class="prod-comm">&#20139;&#37329; ' + htmlEscRoom(p.commission) + '</span>' : '') +
           (p.earn ? '<span class="prod-earn">&#39044;&#20272; ' + htmlEscRoom(p.earn) + '</span>' : '') +
           '</div>' +
           (stars ? '<div class="star-row">' + stars + revCnt + '</div>' : '') +
           '</div>' +
           '</div>';
  }).join('');
}

function selectProduct(idx) {
  document.querySelectorAll('.prod-card').forEach(function(c) { c.classList.remove('selected'); });
  var card = document.getElementById('pcard_' + idx);
  if (card) card.classList.add('selected');
  openDrawer(filteredProducts[idx]);
}

// ── 详情抽屉 ─────────────────────────────────────────────────────────────────
function openDrawer(p) {
  document.getElementById('drawerAsin').textContent = p.asin;
  document.getElementById('drawerContent').innerHTML = buildDetailHTML(p);
  document.getElementById('detailDrawer').style.display = 'block';
  document.getElementById('drawerOverlay').style.display = 'block';
}
function closeDrawer() {
  document.getElementById('detailDrawer').style.display = 'none';
  document.getElementById('drawerOverlay').style.display = 'none';
}

function buildDetailHTML(p) {
  var html = '';
  // ── 商品标题 + 图片 ──
  if (p.image_url) {
    html += '<img src="' + p.image_url + '" style="width:100%;max-height:260px;object-fit:contain;border-radius:10px;background:#15181f;margin-bottom:14px;">';
  }
  html += '<h2 style="font-size:.95rem;font-weight:700;color:#fff;margin-bottom:12px;line-height:1.5;">' + (p.amz_title || p.product_name) + '</h2>';

  // ── 价格 + 评分 ──
  html += '<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px;">';
  if (p.amz_price) html += '<span style="font-size:1.3rem;font-weight:700;color:#ffa726;">$' + parseFloat(p.amz_price||0).toFixed(2) + '</span>';
  if (p.rating) html += starsHtml(p.rating);
  if (p.review_count) html += '<span style="color:#888;font-size:.8rem;">(' + parseInt(p.review_count||0).toLocaleString() + ')</span>';
  if (p.availability) html += '<span class="pill pill-' + (p.availability.toLowerCase().includes('stock')?'green':'gray') + '" style="font-size:.74rem;">' + p.availability + '</span>';
  html += '</div>';

  // ── 推广链接操作区 ──
  html += '<div class="detail-section">';
  html += '<h4>推广链接 &amp; 商品操作</h4>';
  html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">';
  if (p.tracking_url) {
    html += '<button class="btn btn-primary btn-sm" data-url="' + htmlEscRoom(p.tracking_url) + '" onclick="copyText(this.dataset.url)">&#x1F4CB; &#22797;&#21046;&#25512;&#24191;&#38142;&#25509;</button>';
    html += '<a href="' + htmlEscRoom(p.tracking_url) + '" target="_blank" class="btn btn-success btn-sm">&#x1F6D2; &#25171;&#24320;&#20140;&#39532;&#36819;</a>';
  }
  if (p.amazon_url) {
    html += '<a href="' + htmlEscRoom(p.amazon_url) + '" target="_blank" class="btn btn-secondary btn-sm">&#x1F517; Amazon&#30452;&#38142;</a>';
  }
  if (p.has_plan) {
    html += '<button class="btn btn-sm" style="background:#2e7d32;color:#fff;" data-asin="' + htmlEscRoom(p.asin) + '" onclick="downloadPlan(this.dataset.asin)">&#x1F4E5; &#19979;&#36733;&#24191;&#21578;&#26041;&#26696;</button>';
    html += ' <button class="btn btn-info btn-sm" data-asin="' + htmlEscRoom(p.asin) + '" onclick="polishAds(this)">&#x2728; &#28070;&#33394;</button>';
    html += ' <button class="btn btn-secondary btn-sm" data-asin="' + htmlEscRoom(p.asin) + '" data-force="1" onclick="generateAdAI(this)">&#x1F916; AI&#37325;&#26032;&#29983;&#25104;</button>';
    html += ' <button class="btn btn-sm" style="background:#6b5b95;color:#fff;" data-asin="' + htmlEscRoom(p.asin) + '" onclick="generateAdAgent(this)">&#x1F9BE; Agent</button>';
  } else {
    html += '<button class="btn btn-warning btn-sm" data-asin="' + htmlEscRoom(p.asin) + '" onclick="generateAd(this)">&#x26A1; &#21046;&#20316;&#24191;&#21578;</button>';
    html += ' <button class="btn btn-secondary btn-sm" data-asin="' + htmlEscRoom(p.asin) + '" onclick="generateAdAI(this)">&#x1F916; AI&#29983;&#25104;</button>';
    html += ' <button class="btn btn-sm" style="background:#6b5b95;color:#fff;" data-asin="' + htmlEscRoom(p.asin) + '" onclick="generateAdAgent(this)">&#x1F9BE; Agent</button>';
  }
  if (!p.has_amazon) {
    html += '<button class="btn btn-secondary btn-sm" data-asin="' + htmlEscRoom(p.asin) + '" onclick="fetchAmazon(this)">&#x1F504; &#37319;&#38598;Amazon&#25968;&#25454;</button>';
  }
  // 下载商品报告按钮
  html += '<a href="/api/generate_product_report/' + p.asin + '" class="btn btn-secondary btn-sm" target="_blank">&#x1F4C4; &#19979;&#36733;&#25253;&#21578;</a>';
  html += '</div>';
  if (p.tracking_url) {
    html += '<div class="link-url">' + htmlEscRoom(p.tracking_url) + '</div>';
  }
  html += '</div>';

  // ── 佣金信息 ──
  html += '<div class="detail-section">';
  html += '<h4>佣金信息</h4>';
  var commRows = [
    ['YP价格', p.yp_price ? '$' + parseFloat(p.yp_price||0).toFixed(2) : '-'],
    ['佣金率', p.commission || '-'],
    ['预估佣金', p.earn || '-'],
    ['品牌', p.brand || '-'],
    ['类别', p.category_path || '-'],
  ];
  html += commRows.map(function(r) {
    return '<div class="sem-row"><span class="sem-key">' + r[0] + '</span><span class="sem-val">' + r[1] + '</span></div>';
  }).join('');
  html += '</div>';

  // ── Bullet Points ──
  if (p.bullet_points && p.bullet_points.length) {
    html += '<div class="detail-section">';
    html += '<h4>🎯 商品卖点 (' + p.bullet_points.length + '条)</h4>';
    html += p.bullet_points.map(function(b) {
      return '<div class="bullet-item">' + b + '</div>';
    }).join('');
    html += '</div>';
  }

  // ── 商品描述 ──
  if (p.description && p.description.trim()) {
    html += '<div class="detail-section">';
    html += '<h4>商品描述</h4>';
    html += '<div style="font-size:.82rem;color:#ccc;line-height:1.7;padding:8px 0;">' + p.description.substring(0,500) + (p.description.length>500?'...':'') + '</div>';
    html += '</div>';
  }

  // ── 关键词 ──
  if (p.keywords && p.keywords.trim()) {
    html += '<div class="detail-section">';
    html += '<h4>🔑 关键词</h4>';
    html += '<div style="font-size:.8rem;color:#90caf9;line-height:1.8;">' + p.keywords + '</div>';
    html += '</div>';
  }

  // ── 用户评论（金矿！）──
  if (p.top_reviews && p.top_reviews.length) {
    html += '<div class="detail-section">';
    html += '<h4>💬 用户评论 (' + p.top_reviews.length + '条) — 痛点/卖点金矿</h4>';
    html += p.top_reviews.map(function(rv) {
      var stars = '';
      if (rv.rating) {
        var n = parseFloat(rv.rating) || 0;
        for (var i=0;i<Math.round(n);i++) stars += '★';
        while (stars.length < 5) stars += '☆';
        stars = '<span style="color:#ffa726;">' + stars + '</span> ' + n.toFixed(1);
      }
      return '<div class="review-card">' +
             (stars ? '<div class="review-stars">' + stars + '</div>' : '') +
             (rv.title ? '<div class="review-title">' + rv.title + '</div>' : '') +
             (rv.body  ? '<div class="review-body">'  + rv.body  + '</div>' : '') +
             '</div>';
    }).join('');
    html += '</div>';
  }

  return html;
}

function downloadPlan(asin) {
  window.open('/api/download_plan/' + asin);
}

function generateAd(asinOrBtn) {
  var asin = (typeof asinOrBtn === 'string') ? asinOrBtn : asinOrBtn.dataset.asin;
  // 调用统一的广告生成函数
  if (typeof asinOrBtn === 'object' && asinOrBtn.dataset) {
    // 从按钮对象调用 - 使用 fetch API
    asinOrBtn.disabled = true;
    asinOrBtn.innerHTML = '生成中...';
    fetch('/api/generate/' + asin, {method: 'POST'})
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success) {
          toast('广告方案生成成功！共 ' + data.campaigns + ' 个广告系列', 'success');
          setTimeout(function() { location.reload(); }, 1500);
        } else {
          // 检测 already exists 错误，自动用 force=1 重试
          if (data.message && data.message.indexOf('already exists') >= 0) {
            toast('检测到已有方案，正在强制重新生成...', 'info');
            fetch('/api/generate/' + asin + '?force=1', {method: 'POST'})
              .then(function(r2) { return r2.json(); })
              .then(function(data2) {
                if (data2.success) {
                  toast('广告方案生成成功！共 ' + data2.campaigns + ' 个广告系列', 'success');
                  setTimeout(function() { location.reload(); }, 1500);
                } else {
                  toast(data2.message || '生成失败', 'error');
                  asinOrBtn.disabled = false;
                  asinOrBtn.innerHTML = '制作广告';
                }
              })
              .catch(function(e2) {
                toast('重试请求失败: ' + e2.message, 'error');
                asinOrBtn.disabled = false;
                asinOrBtn.innerHTML = '制作广告';
              });
          } else {
            toast(data.message || '生成失败', 'error');
            asinOrBtn.disabled = false;
            asinOrBtn.innerHTML = '制作广告';
          }
        }
      })
      .catch(function(e) {
        toast('请求失败: ' + e.message, 'error');
        asinOrBtn.disabled = false;
        asinOrBtn.innerHTML = '制作广告';
      });
  } else {
    // 直接传入 ASIN - 简单提示
    toast('请从商品列表点击制作广告按钮', 'info');
  }
}

// AI 生成广告（使用百度千帆 + Google Ads 技能）
async function generateAdAI(btn) {
  var asin = btn.dataset.asin;
  var force = btn.dataset.force === '1' ? '&force=1' : '';
  var generatedContent = '';
  var tokenCount = 0;
  var startTime = Date.now();
  var lastChunkTime = startTime;
  var spinnerTimer = null;

  // 动态注入 CSS（避免 Jinja2 吃掉 CSS 花括号）
  if (!document.getElementById('ai-progress-css')) {
    var st = document.createElement('style');
    st.id = 'ai-progress-css';
    st.textContent = '@keyframes aiPulse{0%,100%{opacity:1}50%{opacity:.3}}.ai-spin-dot{display:inline-block;animation:aiPulse 1s infinite;margin-right:2px}'.replace(/aiPulse/g, 'aiPulse'+Date.now());
    document.head.appendChild(st);
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="ai-spin-dot"></span> AI生成中...';

  // 创建遮罩层 + 弹窗
  var overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9998;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';
  var progressDiv = document.createElement('div');
  progressDiv.style.cssText = 'background:#1a1d24;border:1px solid #30363d;border-radius:16px;padding:0;width:600px;max-width:92vw;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 8px 32px rgba(0,0,0,0.6);overflow:hidden;';
  progressDiv.innerHTML =
    '<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid #30363d;">' +
      '<h3 style="margin:0;color:#e6edf3;font-size:16px;">&#x1F916; AI 广告生成</h3>' +
      '<div style="display:flex;align-items:center;gap:12px;">' +
        '<span id="ai-elapsed-' + asin + '" style="color:#8b949e;font-size:12px;">0s</span>' +
        '<span id="ai-tokens-' + asin + '" style="color:#8b949e;font-size:12px;"></span>' +
        '<button id="ai-close-' + asin + '" style="background:none;border:none;color:#8b949e;font-size:18px;cursor:pointer;padding:0 4px;line-height:1;">&#x2715;</button>' +
      '</div>' +
    '</div>' +
    '<div id="ai-log-' + asin + '" style="flex:1;overflow-y:auto;padding:16px 20px;font-size:13px;line-height:1.8;color:#adb5bd;min-height:200px;"></div>' +
    '<div id="ai-stream-' + asin + '" style="display:none;padding:12px 20px;border-top:1px solid #30363d;background:#161b22;max-height:180px;overflow-y:auto;">' +
      '<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">' +
        '<span id="ai-stream-dot-' + asin + '" style="width:8px;height:8px;border-radius:50%;background:#4fc3f7;animation:aiPulse 1s infinite;"></span>' +
        '<span style="color:#4fc3f7;font-size:11px;font-weight:600;">AI 正在输出...</span>' +
      '</div>' +
      '<pre id="ai-stream-content-' + asin + '" style="margin:0;font-size:12px;color:#c9d1d9;white-space:pre-wrap;word-break:break-all;line-height:1.6;font-family:Menlo,Consolas,monospace;max-height:120px;overflow-y:auto;"></pre>' +
    '</div>';
  overlay.appendChild(progressDiv);
  document.body.appendChild(overlay);

  // 关闭按钮
  document.getElementById('ai-close-' + asin).onclick = function() {
    if (confirm('确定要取消 AI 生成吗？')) {
      overlay.remove();
      btn.disabled = false;
      btn.innerHTML = '&#x1F916; AI生成';
    }
  };

  var logDiv = document.getElementById('ai-log-' + asin);
  var elapsedSpan = document.getElementById('ai-elapsed-' + asin);
  var tokensSpan = document.getElementById('ai-tokens-' + asin);
  var streamDiv = document.getElementById('ai-stream-' + asin);
  var streamContent = document.getElementById('ai-stream-content-' + asin);
  var elapsed = 0;

  // 每秒更新计时
  var timer = setInterval(function() {
    elapsed = Math.floor((Date.now() - startTime) / 1000);
    var m = Math.floor(elapsed / 60);
    var s = elapsed % 60;
    elapsedSpan.textContent = m > 0 ? m + 'm ' + s + 's' : s + 's';
    // 如果超过10秒没收到新chunk，显示等待提示
    if (tokenCount > 0 && Date.now() - lastChunkTime > 8000) {
      logDiv.innerHTML += '<div style="color:#ffa726;font-size:11px;">&#x23F3; AI 仍在思考中，请耐心等待...</div>';
      logDiv.scrollTop = logDiv.scrollHeight;
      lastChunkTime = Date.now();
    }
  }, 1000);

  function htmlEscA(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  try {
    var response = await fetch('/api/generate_ai/' + asin + '?llm=kimi' + force);
    if (!response.ok) {
      var errText = await response.text();
      throw new Error('HTTP ' + response.status + ': ' + errText.substring(0, 200));
    }
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    while (true) {
      var result = await reader.read();
      if (result.done) break;
      var value = result.value;

      buffer += decoder.decode(value, {stream: true});
      var lines = buffer.split('\\n\\n');
      buffer = lines.pop();

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.startsWith('data: ')) {
          try {
            var data = JSON.parse(line.substring(6));

            if (data.type === 'progress') {
              var icon = data.text.substring(0, 2);
              logDiv.innerHTML += '<div style="color:#4fc3f7;margin:2px 0;">' + htmlEscA(data.text) + '</div>';
              logDiv.scrollTop = logDiv.scrollHeight;
            } else if (data.type === 'thinking') {
              if (data.text) {
                streamDiv.style.display = 'block';
                tokenCount += data.text.length;
                generatedContent += data.text;
                lastChunkTime = Date.now();
                // 实时显示 AI 输出内容（保留最后 2000 字符）
                streamContent.textContent = generatedContent.slice(-2000);
                streamContent.scrollTop = streamContent.scrollHeight;
                // 更新 token 计数
                tokensSpan.textContent = tokenCount + ' chars';
              }
            } else if (data.type === 'token_count') {
              tokensSpan.textContent = (data.count || 0) + ' tokens';
            } else if (data.type === 'done') {
              clearInterval(timer);
              var r = data.result || {};
              // 完成动画
              var dot = document.getElementById('ai-stream-dot-' + asin);
              if (dot) { dot.style.background = '#4caf50'; dot.style.animation = 'none'; }
              var streamLabel = streamDiv.querySelector('span[style*="color:#4fc3f7"]');
              if (streamLabel) { streamLabel.style.color = '#4caf50'; streamLabel.textContent = 'AI 输出完成'; }

              logDiv.innerHTML += '<div style="color:#4caf50;font-weight:600;margin-top:12px;">&#x2705; 广告方案生成完成！</div>';
              logDiv.innerHTML += '<div style="margin-top:8px;color:#c9d1d9;">广告系列: <b style="color:#58a6ff;">' + (r.campaigns || 0) + '</b> 个 &nbsp;|&nbsp; 广告组: <b style="color:#58a6ff;">' + (r.ad_groups || 0) + '</b> 个 &nbsp;|&nbsp; 广告: <b style="color:#58a6ff;">' + (r.ads || 0) + '</b> 个</div>';
              logDiv.innerHTML += '<div style="margin-top:4px;color:#8b949e;font-size:12px;">耗时 ' + elapsedSpan.textContent + ' | ' + tokenCount + ' chars</div>';
              logDiv.innerHTML += '<div style="margin-top:12px;color:#8b949e;font-size:12px;">页面将在 <b>5秒</b> 后自动刷新...</div>';
              logDiv.scrollTop = logDiv.scrollHeight;
              btn.innerHTML = '&#x2705; AI生成完成';
              setTimeout(function() { overlay.remove(); location.reload(); }, 5000);
            } else if (data.type === 'error') {
              clearInterval(timer);
              logDiv.innerHTML += '<div style="color:#f44336;margin-top:12px;">&#x274C; ' + htmlEscA(data.message) + '</div>';
              btn.disabled = false;
              btn.innerHTML = '&#x1F916; AI生成';
              // 不自动关闭弹窗，让用户看到错误
            }
          } catch (e) {
            console.error('SSE parse error:', e, line);
          }
        }
      }
    }
  } catch (e) {
    clearInterval(timer);
    logDiv.innerHTML += '<div style="color:#f44336;margin-top:12px;">&#x274C; 请求失败: ' + htmlEscA(e.message) + '</div>';
    btn.disabled = false;
    btn.innerHTML = '&#x1F916; AI生成';
  }
}

// AI 润色广告文案
async function polishAds(btn) {
  var asin = btn.dataset.asin;
  
  btn.disabled = true;
  btn.innerHTML = '✨ 润色中...';
  
  // 创建进度显示
  var progressDiv = document.createElement('div');
  progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #17a2b8;border-radius:12px;padding:20px;max-width:500px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(23,162,184,0.5);';
  progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">✨ AI 广告润色</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="polish-log-' + asin + '" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
  document.body.appendChild(progressDiv);
  
  var logDiv = document.getElementById('polish-log-' + asin);
  logDiv.innerHTML = '<div style="color:#17a2b8;">🎨 正在读取广告方案...</div>';
  
  try {
    var response = await fetch('/api/polish_ads/' + asin, {method: 'POST'});
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';
    
    while (true) {
      var {done, value} = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, {stream: true});
      var lines = buffer.split('\\n\\n');
      buffer = lines.pop();
      
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.startsWith('data: ')) {
          try {
            var data = JSON.parse(line.substring(6));
            
            if (data.type === 'progress') {
              logDiv.innerHTML += '<div style="color:#4fc3f7;">' + data.text + '</div>';
              progressDiv.scrollTop = progressDiv.scrollHeight;
            } else if (data.type === 'done') {
              logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ 润色完成！</div>';
              logDiv.innerHTML += '<div style="margin-top:10px;">已润色: ' + (data.result?.polished_count || 0) + ' 条广告</div>';
              btn.innerHTML = '✅ 已润色';
              setTimeout(function() { progressDiv.remove(); location.reload(); }, 2000);
            } else if (data.type === 'error') {
              logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + data.message + '</div>';
              btn.disabled = false;
              btn.innerHTML = '✨ 润色';
            }
          } catch (e) {
            console.error('Parse error:', e, line);
          }
        }
      }
    }
  } catch (e) {
    logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + e.message + '</div>';
    btn.disabled = false;
    btn.innerHTML = '✨ 润色';
  }
}

// Agent 生成广告（使用 OpenClaw sessions_spawn）
async function generateAdAgent(btn) {
  var asin = btn.dataset.asin;
  
  btn.disabled = true;
  btn.innerHTML = '🦾 Agent运行中...';
  
  // 创建进度显示
  var progressDiv = document.createElement('div');
  progressDiv.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#1a1d24;border:1px solid #6b5b95;border-radius:12px;padding:20px;max-width:500px;max-height:400px;overflow-y:auto;z-index:9999;box-shadow:0 4px 20px rgba(107,91,149,0.5);';
  progressDiv.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;"><h3 style="margin:0;color:#fff;">🦾 OpenClaw Agent 生成</h3><button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;color:#888;font-size:20px;cursor:pointer;">&times;</button></div><div id="agent-log-' + asin + '" style="font-size:13px;line-height:1.8;color:#adb5bd;"></div>';
  document.body.appendChild(progressDiv);
  
  var logDiv = document.getElementById('agent-log-' + asin);
  logDiv.innerHTML = '<div style="color:#6b5b95;">🚀 正在创建 ad_creator Agent...</div>';
  
  try {
    var response = await fetch('/api/generate_agent/' + asin, {method: 'POST'});
    var data = await response.json();
    
    if (data.success) {
      logDiv.innerHTML += '<div style="color:#4caf50;margin-top:10px;">✅ Agent 任务已提交！</div>';
      logDiv.innerHTML += '<div style="margin-top:10px;">Run ID: ' + (data.run_id || 'N/A') + '</div>';
      logDiv.innerHTML += '<div>Session: ' + (data.session_key || 'N/A') + '</div>';
      logDiv.innerHTML += '<div style="margin-top:10px;color:#888;">Agent 正在后台执行，请稍后刷新查看结果...</div>';
      btn.innerHTML = '✅ Agent已启动';
      setTimeout(function() { progressDiv.remove(); }, 3000);
    } else {
      logDiv.innerHTML += '<div style="color:#f44336;margin-top:10px;">❌ ' + (data.error || 'Agent 创建失败') + '</div>';
      btn.disabled = false;
      btn.innerHTML = '🦾 Agent';
    }
  } catch (e) {
    logDiv.innerHTML += '<div style="color:#f44336;">❌ 请求失败: ' + e.message + '</div>';
    btn.disabled = false;
    btn.innerHTML = '🦾 Agent';
  }
}

function htmlEscRoom(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function showKeyDialogRoom(callback) {
  var key = prompt('请输入 DeepSeek API Key（仅本次会话保存）：');
  if (!key || !key.trim()) { callback(null); return; }
  fetch('/api/set_deepseek_key', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({api_key: key.trim()})
  }).then(function(r) { return r.json(); })
    .then(function(d) { callback(d.ok ? key : null); })
    .catch(function() { callback(null); });
}

function openStrategistPanelRoom(asin, force) {
  fetch('/api/get_deepseek_key_status')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.configured) {
        showKeyDialogRoom(function(k) { if (k) startStrategistRoom(asin, force); });
      } else {
        startStrategistRoom(asin, force);
      }
    })
    .catch(function() { startStrategistRoom(asin, force); });
}

function startStrategistRoom(asin, force) {
  var overlay = document.getElementById('strat-overlay-room');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'strat-overlay-room';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.82);z-index:9999;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = '<div style="background:#0d1117;border:1px solid #30363d;border-radius:12px;width:min(860px,96vw);max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 8px 48px rgba(0,0,0,0.7);">'
      + '<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #21262d;background:#161b22;">'
      + '<div style="display:flex;align-items:center;gap:10px;"><span style="font-size:22px;">🤖</span>'
      + '<div><div style="font-size:15px;font-weight:600;color:#e6edf3;">AI 广告策略师</div>'
      + '<div style="font-size:12px;color:#8b949e;" id="sr-asin-label"></div></div></div>'
      + '<button onclick="closeStratRoom()" style="background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer;padding:4px 8px;">✕</button></div>'
      + '<div id="sr-log" style="flex:1;overflow-y:auto;padding:16px 20px;font-family:Consolas,monospace;font-size:13px;line-height:1.7;color:#c9d1d9;min-height:320px;max-height:52vh;"></div>'
      + '<div id="sr-result" style="display:none;padding:16px 20px;border-top:1px solid #21262d;background:#0d1117;max-height:200px;overflow-y:auto;"></div>'
      + '<div style="padding:12px 20px;border-top:1px solid #21262d;background:#161b22;display:flex;justify-content:flex-end;gap:10px;">'
      + '<button id="sr-view-btn" style="display:none;" class="btn btn-success btn-sm" data-url="" onclick="window.open(this.dataset.url)">📋 查看广告方案</button>'
      + '<button onclick="closeStratRoom()" class="btn btn-secondary btn-sm">关闭</button>'
      + '</div></div>';
    document.body.appendChild(overlay);
  }

  var logEl = document.getElementById('sr-log');
  var resultEl = document.getElementById('sr-result');
  var viewBtn = document.getElementById('sr-view-btn');
  logEl.innerHTML = ''; resultEl.style.display = 'none'; resultEl.innerHTML = ''; viewBtn.style.display = 'none';
  document.getElementById('sr-asin-label').textContent = 'ASIN: ' + asin;
  window.sr_asin = asin;
  overlay.style.display = 'flex'; document.body.style.overflow = 'hidden';

  function appendLog(html) { logEl.insertAdjacentHTML('beforeend', html); logEl.scrollTop = logEl.scrollHeight; }
  appendLog('<div style="color:#58a6ff;margin-bottom:8px;">🚀 启动 AI 广告策略师分析...</div>');

  var url = '/api/generate_ai/' + asin + '?llm=kimi' + (force ? '&force=1' : '');
  var es = new EventSource(url);
  window.sr_es = es;

  es.onmessage = function(e) {
    try {
      var msg = JSON.parse(e.data);
      if (msg.type === 'start') {
        appendLog('<div style="color:#79c0ff;">' + htmlEscRoom(msg.text) + '</div>');
      } else if (msg.type === 'progress') {
        appendLog('<div style="color:#3fb950;margin:4px 0;">' + htmlEscRoom(msg.text) + '</div>');
      } else if (msg.type === 'thinking') {
        var last = logEl.querySelector('.sr-thinking:last-child');
        if (!last) {
          var sp = document.createElement('span');
          sp.className = 'sr-thinking';
          sp.style.cssText = 'display:block;color:#e6edf3;white-space:pre-wrap;word-break:break-all;margin:2px 0;';
          logEl.appendChild(sp);
          last = sp;
        }
        last.textContent += msg.text;
        logEl.scrollTop = logEl.scrollHeight;
      } else if (msg.type === 'done') {
        var r = msg.result || {};
        var sa = r.strategy_analysis || {};
        var bs = r.budget_summary || {};
        appendLog('<div style="color:#3fb950;font-weight:bold;margin-top:12px;">✅ 广告方案生成完成！</div>');
        var h = '<div style="background:#161b22;border-radius:8px;padding:12px;">'
          + '<div style="color:#58a6ff;font-weight:bold;margin-bottom:8px;">📊 策略摘要</div>';
        if (sa.product_strengths) h += '<div style="margin-bottom:5px;"><span style="color:#8b949e;">产品优势: </span><span style="color:#c9d1d9;">' + htmlEscRoom(sa.product_strengths) + '</span></div>';
        if (sa.target_audience) h += '<div style="margin-bottom:5px;"><span style="color:#8b949e;">目标受众: </span><span style="color:#c9d1d9;">' + htmlEscRoom(sa.target_audience) + '</span></div>';
        if ((sa.key_messaging_angles || []).length) h += '<div style="margin-bottom:5px;"><span style="color:#8b949e;">核心卖点: </span><span style="color:#c9d1d9;">' + (sa.key_messaging_angles || []).map(htmlEscRoom).join(' · ') + '</span></div>';
        h += '<div style="margin-top:8px;padding-top:8px;border-top:1px solid #21262d;display:flex;gap:16px;">'
          + '<span style="color:#8b949e;">广告系列: <span style="color:#f0883e;">' + (r.campaigns || 0) + '</span></span>'
          + '<span style="color:#8b949e;">广告组: <span style="color:#f0883e;">' + (r.ad_groups || 0) + '</span></span>'
          + '<span style="color:#8b949e;">广告: <span style="color:#f0883e;">' + (r.ads || 0) + '</span></span>';
        if (bs.total_daily_budget_usd) h += '<span style="color:#8b949e;">日预算: <span style="color:#3fb950;">$' + (+bs.total_daily_budget_usd).toFixed(2) + '</span></span>';
        h += '</div></div>';
        resultEl.innerHTML = h; resultEl.style.display = 'block'; viewBtn.style.display = 'inline-flex';
        es.close();
        // 重载作战室广告部分
        setTimeout(loadRoom, 1200);
      } else if (msg.type === 'error') {
        appendLog('<div style="color:#f85149;margin-top:8px;">❌ ' + htmlEscRoom(msg.message) + '</div>');
        es.close();
      }
    } catch(ex) {}
  };
  es.onerror = function() { appendLog('<div style="color:#f85149;">⚠ SSE 连接断开</div>'); es.close(); };
}

function closeStratRoom() {
  var o = document.getElementById('strat-overlay-room');
  if (o) o.style.display = 'none';
  document.body.style.overflow = '';
  if (window.sr_es) { window.sr_es.close(); window.sr_es = null; }
}



function fetchAmazon(asinOrBtn) {
  var btn = (typeof asinOrBtn === 'string') ? null : asinOrBtn;
  var asin = btn ? btn.dataset.asin : asinOrBtn;
  if (btn) { btn.disabled = true; btn.textContent = '采集中...'; }
  toast('正在采集 Amazon 数据，请稍候（最多90秒）...', 'info');
  fetch('/api/fetch_amazon/' + asin, {method:'POST'})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (btn) { btn.disabled = false; btn.innerHTML = '&#x1F504; 采集Amazon数据'; }
      if (d.success) {
        toast('Amazon 数据采集完成: ' + asin, 'success');
        setTimeout(loadRoom, 1500);
      } else {
        toast('采集失败: ' + (d.message || '未知错误'), 'error');
      }
    })
    .catch(function(e) {
      if (btn) { btn.disabled = false; btn.innerHTML = '&#x1F504; 采集Amazon数据'; }
      toast('请求失败: '+e, 'error');
    });
}

loadRoom();

// 页面加载完成后检查 parseScreenshots 是否存在
setTimeout(function() {
  console.log('[INIT] parseScreenshots 类型:', typeof parseScreenshots);
  if (typeof parseScreenshots === 'function') {
    console.log('[INIT] parseScreenshots 函数定义:', parseScreenshots.toString().substring(0, 100));
  }
}, 1000);

{% endraw %}
</script>
</body>
</html>
"""
)


@bp.route("/api/scrape_semrush/<merchant_id>", methods=["POST"])
def api_scrape_semrush(merchant_id):
    """触发单商户 SEMrush 竞品数据采集（通过外贸侠网站）"""
    try:
        data = request.get_json(silent=True) or {}
        manual_domain = (data.get("domain") or "").strip()
        use_waimaoxia = data.get("use_waimaoxia", True)  # 默认使用外贸侠流程

        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT merchant_name, website FROM yp_merchants WHERE merchant_id=%s LIMIT 1",
            (merchant_id,),
        )
        m = cur.fetchone() or {}
        conn.close()

        # 优先使用手动输入的域名，其次使用数据库中的 website
        domain = manual_domain or (m.get("website") or "").strip()
        name = m.get("merchant_name") or merchant_id

        if not domain:
            return jsonify(
                {
                    "ok": False,
                    "msg": f"商户「{name}」没有 website 字段，无法采集 SEMrush 数据",
                    "need_domain": True,
                }
            )

        # 根据模式选择脚本
        if use_waimaoxia:
            sem_script = BASE_DIR / "semrush_via_wmx.py"
            script_name = "semrush_via_wmx.py"
        else:
            sem_script = BASE_DIR / "scrape_semrush.py"
            script_name = "scrape_semrush.py"

        if not sem_script.exists():
            return jsonify({"ok": False, "msg": f"{script_name} 不存在"})

        # 创建启动脚本
        bat_file = BASE_DIR / f"_launch_semrush_{merchant_id}.bat"

        if use_waimaoxia:
            # 外贸侠模式：脚本内置Chrome自动检测和启动，无需手动操作
            bat_content = (
                f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle SEMrush采集 - {name}\r\n'
                f"echo ========================================\r\n"
                f"echo  SEMrush 数据采集 - 外贸侠模式\r\n"
                f"echo  商户: {name}\r\n"
                f"echo  域名: {domain}\r\n"
                f"echo ========================================\r\n"
                f"echo.\r\n"
                f'"{PYTHON_EXE}" -X utf8 "{sem_script}" "{merchant_id}" "{domain}"\r\n'
                f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
            )
        else:
            # 传统模式
            domain_arg = f' --domain "{domain}"' if manual_domain else ""
            bat_content = (
                f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle SEMrush {name}\r\n'
                f'"{PYTHON_EXE}" -X utf8 "{sem_script}" --merchant-id {merchant_id}{domain_arg}\r\n'
                f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
            )

        bat_file.write_text(bat_content, encoding="gbk")

        # 启动新窗口
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",
                "cmd.exe",
                "/k",
                str(bat_file),
            ],
            cwd=str(BASE_DIR),
            shell=False,
        )

        mode_text = "外贸侠模式" if use_waimaoxia else "传统模式"
        return jsonify(
            {
                "ok": True,
                "msg": f"SEMrush 采集任务已启动 ({mode_text}, 域名: {domain})",
                "mode": "waimaoxia" if use_waimaoxia else "traditional",
                "domain": domain,
                "merchant_id": merchant_id,
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@bp.route("/api/scrape_semrush_status/<merchant_id>", methods=["GET"])
def api_scrape_semrush_status(merchant_id):
    """查询 SEMrush 采集状态和结果"""
    try:
        import json

        # 查找采集结果文件
        result_file = BASE_DIR / "temp" / f"semrush_collected_{merchant_id}.json"

        if not result_file.exists():
            return jsonify(
                {
                    "ok": True,
                    "status": "pending",
                    "msg": "采集结果尚未生成",
                    "has_data": False,
                }
            )

        # 读取结果
        try:
            data = json.loads(result_file.read_text(encoding="utf-8"))
            return jsonify(
                {
                    "ok": True,
                    "status": "completed",
                    "msg": "采集已完成",
                    "has_data": True,
                    "data": data,
                    "collected_at": data.get("collected_at"),
                    "domain": data.get("domain"),
                }
            )
        except Exception as e:
            return jsonify(
                {
                    "ok": False,
                    "status": "error",
                    "msg": f"读取结果文件失败: {e}",
                }
            )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


@bp.route("/api/parse_semrush_screenshots", methods=["POST"])
def api_parse_semrush_screenshots():
    """解析上传的 SEMrush 截图，使用 Kimi Vision API"""
    import os
    import tempfile
    import base64
    import requests

    try:
        # 获取表单数据
        domain = request.form.get("domain", "").strip()
        merchant_id = request.form.get("merchant_id", "")

        if not domain:
            return jsonify({"success": False, "error": "请输入域名"})

        # 收集上传的截图
        screenshots = {}
        for type_name in ["overview", "organic", "paid", "adcopy"]:
            file_key = f"screenshot_{type_name}"
            if file_key in request.files:
                file = request.files[file_key]
                if file and file.filename:
                    screenshots[type_name] = file

        if not screenshots:
            return jsonify({"success": False, "error": "请至少上传一张截图"})

        # 初始化结果
        result = {
            "domain": domain,
            "traffic": {},
            "organic_keywords": [],
            "paid_keywords": [],
            "ad_copies": [],
            "_debug_ocr": {},
        }

        # Kimi API 配置
        api_key = os.environ.get(
            "KIMI_API_KEY", "sk-Id6uRyPXBuYMKc901g35NzREkAOhWBBDeDNR07bj7YalIwWy"
        )

        def _parse_with_kimi_vision(image_path, screenshot_type):
            """使用 Kimi Vision API 解析截图"""

            # 读取图片并转为 base64
            with open(image_path, "rb") as f:
                image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode("utf-8")

            # 根据截图类型构建不同的 prompt
            if screenshot_type == "overview":
                prompt = """分析这张 SEMrush 网站概览截图，提取以下数据并以 JSON 格式返回：

{
  "traffic": {
    "organic": "自然流量数值（如 34K）",
    "paid": "付费流量数值（如 2K）",
    "authority_score": "权威分数（0-100的数字）"
  }
}

只返回 JSON，不要其他解释。如果某个字段看不到，设为 null。"""

            elif screenshot_type in ["organic", "paid"]:
                prompt = """分析这张 SEMrush 关键词截图，提取关键词列表并以 JSON 格式返回：

{
  "keywords": [
    {"keyword": "关键词文本", "volume": "搜索量", "position": "排名"},
    ...
  ]
}

提取前15个关键词。只返回 JSON，不要其他解释。"""

            elif screenshot_type == "adcopy":
                prompt = """分析这张 SEMrush 广告文案截图，提取 Google Ads 广告并以 JSON 格式返回：

{
  "ad_copies": [
    {
      "headline": "广告标题",
      "descriptions": ["描述1", "描述2"]
    },
    ...
  ]
}

注意：只提取真实的广告文案，忽略 SEMrush 平台的 UI 文本（如"节省用于摘要分析的时间"等中文提示）。
只返回 JSON，不要其他解释。"""

            else:
                prompt = "提取这张截图中的所有文字和数据，以 JSON 格式返回。"

            # 调用 Kimi Vision API
            try:
                resp = requests.post(
                    "https://api.moonshot.cn/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "moonshot-v1-8k-vision-preview",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{image_base64}"
                                        },
                                    },
                                    {"type": "text", "text": prompt},
                                ],
                            }
                        ],
                        "temperature": 0.1,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                print(
                    f"[DEBUG] Kimi Vision 响应 ({screenshot_type}): {content[:500]}..."
                )
                return content
            except Exception as e:
                print(f"[DEBUG] Kimi Vision API 调用失败: {e}")
                return None

        def _extract_json(text):
            """从文本中提取 JSON"""
            import re

            if not text:
                return None
            # 尝试找到 JSON 块
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            return None

        # 处理每张截图
        for type_name, file in screenshots.items():
            try:
                # 保存临时文件
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    file.save(tmp.name)
                    tmp_path = tmp.name

                print(f"[DEBUG] 开始解析截图: {type_name}, 文件: {tmp_path}")

                # 使用 Kimi Vision 解析
                kimi_response = _parse_with_kimi_vision(tmp_path, type_name)

                # 删除临时文件
                try:
                    os.unlink(tmp_path)
                except:
                    pass

                if not kimi_response:
                    print(f"[DEBUG] Kimi Vision 返回空，跳过 {type_name}")
                    continue

                # 存储原始响应用于调试
                result["_debug_ocr"][type_name] = kimi_response[:2000]

                # 解析 JSON
                parsed = _extract_json(kimi_response)
                if not parsed:
                    print(f"[DEBUG] 无法从 Kimi 响应中提取 JSON: {type_name}")
                    continue

                # 根据类型合并数据
                if type_name == "overview":
                    if "traffic" in parsed:
                        result["traffic"] = parsed["traffic"]
                    print(f"[DEBUG] 解析后的流量数据: {result['traffic']}")

                elif type_name == "organic":
                    keywords = parsed.get("keywords", [])
                    result["organic_keywords"] = keywords
                    print(f"[DEBUG] 解析出 {len(keywords)} 个自然关键词")

                elif type_name == "paid":
                    keywords = parsed.get("keywords", [])
                    result["paid_keywords"] = keywords
                    print(f"[DEBUG] 解析出 {len(keywords)} 个付费关键词")

                elif type_name == "adcopy":
                    ads = parsed.get("ad_copies", [])
                    result["ad_copies"] = ads
                    print(f"[DEBUG] 解析出 {len(ads)} 条广告文案")

            except Exception as e:
                print(f"处理截图 {type_name} 失败: {e}")
                import traceback

                traceback.print_exc()
                continue

        result["_ocr_engine"] = "kimi-vision"
        return jsonify({"success": True, "data": result})

    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


def _parse_overview_ocr(ocr_text):
    """从概览截图 OCR 文本中解析流量数据（支持 SEMrush 英文界面）"""
    import re

    traffic = {}
    print(f"[DEBUG] _parse_overview_ocr 原始文本:\n{ocr_text[:1000]}")

    # SEMrush 英文界面标签模式
    patterns = {
        # Authority Score: 数字 (0-100)
        "authority_score": [
            r"Authority\s*Score[:\s]*([0-9]+)",
            r"Auth(?:ority)?\s*Score[:\s]*([0-9]+)",
        ],
        # Organic Search Traffic
        "organic": [
            r"Organic\s*(?:Search\s*)?Traffic[:\s]*([0-9][0-9.,KMB]*)",
            r"Organic[:\s]+([0-9][0-9.,KMB]+)",
            # 数字后跟 K/M/B 的独立行（SEMrush 常见格式）
        ],
        # Paid Search Traffic
        "paid": [
            r"Paid\s*(?:Search\s*)?Traffic[:\s]*([0-9][0-9.,KMB]*)",
            r"Paid[:\s]+([0-9][0-9.,KMB]+)",
        ],
        # Backlinks
        "backlinks": [
            r"Backlinks?[:\s]*([0-9][0-9.,KMB]*)",
        ],
        # Referring Domains
        "referring_domains": [
            r"Referring\s*Domains?[:\s]*([0-9][0-9.,KMB]*)",
        ],
    }

    for key, pats in patterns.items():
        for pat in pats:
            match = re.search(pat, ocr_text, re.IGNORECASE)
            if match:
                traffic[key] = match.group(1).strip()
                break

    # 如果上面没匹配到，尝试从 OCR 文本中找数字+单位的组合
    # SEMrush 概览页通常有明显的大数字（如 250.2K, 1.2M）
    if not traffic.get("organic"):
        # 找所有形如 数字K/M/B 的字符串
        big_nums = re.findall(r"\b([0-9]+\.?[0-9]*\s*[KMB])\b", ocr_text, re.IGNORECASE)
        if big_nums:
            print(f"[DEBUG] 找到大数字: {big_nums}")
            # 第一个通常是 organic traffic
            if len(big_nums) >= 1:
                traffic["organic"] = big_nums[0].replace(" ", "")
            if len(big_nums) >= 2:
                traffic["paid"] = big_nums[1].replace(" ", "")

    return traffic


def _parse_keywords_ocr(ocr_text):
    """从关键词截图 OCR 文本中解析关键词列表（SEMrush 关键词格式）

    SEMrush 关键词页面通常是表格格式：
    关键词 | 排名 | 搜索量 | CPC | 流量百分比
    OCR 识别后可能是乱码+数字的混合

    策略：优先提取纯英文关键词，尽量从OCR乱码中还原
    """
    import re

    keywords = []
    lines = ocr_text.split("\n")
    print(f"[DEBUG] _parse_keywords_ocr 原始文本:\n{ocr_text[:800]}")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过表头和无关行
        skip_patterns = [
            r"^(keyword|volume|search|cpc|position|rank|traffic)",
            r"^(sortable|export|filter|view|results|serp|feature)",
            r"^(https?://|www\.)",
        ]
        if any(re.match(p, line, re.IGNORECASE) for p in skip_patterns):
            continue

        # === 策略1: 标准格式 "keyword volume" 如 "true classic 32360" ===
        # 清理 OCR 噪音字符
        cleaned = line
        # 替换 OCR 常见错误字符
        cleaned = re.sub(r"[&}\]\[()©®]", " ", cleaned)
        # 替换 OCR 识别出的特殊符号
        cleaned = cleaned.replace("= ", "=").replace(" =", "=")
        # 压缩空格
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # 尝试匹配：英文关键词 + 数字（搜索量）
        # 格式: "keyword text 123,456" 或 "keyword text 250.2K"
        match = re.match(
            r"^([a-zA-Z][a-zA-Z\s]{1,40}[a-zA-Z])\s+([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)",
            cleaned,
        )
        if match:
            kw_text = match.group(1).strip()
            volume = match.group(2).replace(",", "")
            if len(kw_text) >= 3:
                keywords.append({"keyword": kw_text, "volume": volume, "raw": line})
                print(f"[DEBUG] 策略1 提取: '{kw_text}' vol={volume}")
                continue

        # === 策略2: OCR乱码中提取英文单词组合 ===
        # 如 "true classic &} N 1" → "true classic"
        # 如 "true classictees) (©) N 1" → "true classictees"
        # 提取连续的英文单词（允许连字符和撇号）
        word_groups = re.findall(
            r"([a-zA-Z]+(?:[\-\'][a-zA-Z]+)*(?:\s+[a-zA-Z]+(?:[\-\'][a-zA-Z]+)*)+)",
            cleaned,
        )
        for group in word_groups:
            group = group.strip()
            # 跳过太短或看起来像乱码的
            if len(group) < 4:
                continue
            # 跳过纯大写短词（通常是OCR乱码）
            if group.isupper() and len(group) <= 5:
                continue
            # 跳过单个常见短词误识别
            if group.lower() in (
                "true",
                "fresh",
                "only",
                "with",
                "from",
                "that",
                "this",
                "they",
                "have",
                "been",
                "were",
            ):
                continue

            # 尝试从剩余部分提取数字作为volume
            remainder = cleaned.replace(group, "", 1).strip()
            vol_match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?[KMB]?)", remainder)
            volume = vol_match.group(1).replace(",", "") if vol_match else ""

            keywords.append({"keyword": group, "volume": volume, "raw": line})
            print(f"[DEBUG] 策略2 提取: '{group}' vol={volume}")
            break  # 每行只取第一个有效关键词组

        if len(keywords) >= 30:
            break

    # 去重（基于关键词文本）
    seen = set()
    unique_keywords = []
    for kw in keywords:
        key = kw["keyword"].lower()
        if key not in seen:
            seen.add(key)
            unique_keywords.append(kw)

    print(f"[DEBUG] 共提取 {len(unique_keywords)} 个唯一关键词")
    return unique_keywords[:20]


def _parse_adcopy_ocr(ocr_text, domain):
    """从广告文案截图 OCR 文本中解析 Google Ads 广告

    SEMrush 广告研究页面的 OCR 文本特点：
    - 多个广告并排显示，OCR 会把同一行的多列广告文字合并
    - 标题通常是短句（如 "Comfort You Can Feel"）
    - 描述是较长文本（如 "Better Fitting T-Shirts..."）
    - URL 包含域名
    - 关键词如 "Save Up to 65%", "Premium Quality" 等是广告特征

    策略：按行分析，识别标题行和描述行，通过广告关键词和长度特征区分
    """
    import re

    ads = []
    print(f"[DEBUG] _parse_adcopy_ocr 原始文本:\n{ocr_text[:1500]}")

    # 清理 OCR 文本
    text = ocr_text.strip()
    lines = text.split("\n")

    # SEMrush 广告特征关键词（英文广告常用）
    headline_keywords = [
        "save up",
        "save big",
        "shop now",
        "shop today",
        "discover",
        "unlock",
        "upgrade to",
        "feel the",
        "best t-shirt",
        "perfect t-shirt",
        "premium quality",
        "hate shirts",
        "president",
        "sale",
        "off everything",
        "trusted by",
        "elevate your",
        "first and only",
        "crack the code",
    ]

    # 收集所有看起来像广告标题的短句
    headlines = []
    descriptions = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 跳过纯数字/乱码行
        if re.match(r"^[0-9A-Z]{2,8}$", line):
            continue
        # 跳过URL行（包含 https://）
        if "https://" in line and len(line) < 120:
            continue
        # 跳过纯域名行
        if re.match(r"^[a-z]+\.[a-z]+", line) and len(line) < 30:
            continue

        # 清理 OCR 噪音
        cleaned = re.sub(r"\[?\d?\]?$", "", line).strip()  # 去掉末尾的 [7 [4 等
        cleaned = re.sub(r">\s*\[", "", cleaned).strip()  # 去掉 > [
        cleaned = re.sub(r"\s+", " ", cleaned)

        # 尝试把混合在一起的多个广告文案分开
        # 特征：一个短句后面跟 " - " 分隔符再跟另一个短句
        # 如 "Comfort You Can Feel - Better Fitting T" → 两个标题
        # 如 "Fresh Tees - The Best T-Shirts - Other" → 多个标题

        # 分割策略：用 " - " 作为广告分隔符
        parts = re.split(r"\s+-\s+", cleaned)

        for part in parts:
            part = part.strip()
            if not part or len(part) < 5:
                continue

            # 判断是标题还是描述
            # 标题特征：较短（<60字符），大写开头，包含广告关键词
            # 描述特征：较长（>60字符），包含更多细节

            is_headline = False
            if len(part) < 60 and re.match(r"^[A-Z]", part):
                if any(kw in part.lower() for kw in headline_keywords):
                    is_headline = True
                elif len(part) < 40 and part.count(" ") <= 6:
                    is_headline = True

            if is_headline:
                headlines.append(part)
            elif len(part) > 25:
                descriptions.append(part)

    # 将标题和描述组合成广告
    # 策略：每个标题配最接近的1-2条描述
    print(f"[DEBUG] 识别出 {len(headlines)} 个标题, {len(descriptions)} 条描述")

    for i, headline in enumerate(headlines):
        ad = {"headline": headline, "descriptions": [], "url": domain}
        # 尝试匹配描述（同一索引位置的描述最可能属于该标题）
        if i < len(descriptions):
            ad["descriptions"].append(descriptions[i])
        # 额外匹配下一条描述
        if i + 1 < len(descriptions):
            desc = descriptions[i + 1]
            # 避免重复
            if desc not in ad["descriptions"]:
                ad["descriptions"].append(desc)

        ads.append(ad)
        print(
            f"[DEBUG] 广告 {i + 1}: 标题='{headline[:50]}' 描述数={len(ad['descriptions'])}"
        )

    # 如果没有找到标题，但有描述，把描述作为独立广告
    if not ads and descriptions:
        for desc in descriptions[:5]:
            # 从描述中提取可能的标题（第一句）
            sentences = re.split(r"[.!]", desc)
            headline = sentences[0][:30] if sentences else desc[:30]
            ads.append({"headline": headline, "descriptions": [desc], "url": domain})

    # 过滤无效广告
    valid_ads = []
    ui_markers = [
        "全面了解域名",
        "分析域名随时间",
        "节省用于摘要分析",
        "获取免费一对一",
        "men's> basics",
        "men s>asits",
    ]
    for ad in ads:
        full_text = ad["headline"] + " " + " ".join(ad.get("descriptions", []))
        if any(marker in full_text for marker in ui_markers):
            continue
        valid_ads.append(ad)

    print(f"[DEBUG] 共提取 {len(valid_ads)} 个有效广告")
    return valid_ads[:10]


@bp.route("/api/save_semrush_data", methods=["POST"])
def api_save_semrush_data():
    """保存解析后的 SEMrush 数据到数据库"""
    import json
    import traceback

    try:
        data = request.get_json()
        print(f"[DEBUG] 收到保存请求: {data.keys() if data else 'None'}")

        if not data:
            return jsonify({"success": False, "error": "请求数据为空"})

        merchant_id = data.get("merchant_id")
        domain = data.get("domain", "").strip()
        sem_data = data.get("data", {})

        print(
            f"[DEBUG] 参数: merchant_id={merchant_id}, domain={domain}, data_keys={sem_data.keys() if sem_data else 'None'}"
        )

        if not merchant_id or not domain:
            return jsonify({"success": False, "error": "缺少必要参数"})

        conn = _db()
        cur = conn.cursor()

        # 检查是否已存在记录
        cur.execute(
            "SELECT id FROM semrush_competitor_data WHERE merchant_id = %s AND domain = %s",
            (merchant_id, domain),
        )
        existing = cur.fetchone()

        # 准备数据
        traffic = sem_data.get("traffic", {})

        # organic_keywords 可能是字典（新格式）或列表（旧格式）
        organic_keywords_raw = sem_data.get("organic_keywords", {})
        if isinstance(organic_keywords_raw, dict):
            organic_keywords_total = organic_keywords_raw.get("total", "")
            organic_keywords_list = organic_keywords_raw.get("top_keywords", [])
        else:
            organic_keywords_total = (
                str(len(organic_keywords_raw)) if organic_keywords_raw else ""
            )
            organic_keywords_list = (
                organic_keywords_raw if isinstance(organic_keywords_raw, list) else []
            )

        # paid_keywords 可能是字典（新格式）或列表（旧格式）
        paid_keywords_raw = sem_data.get("paid_keywords", {})
        if isinstance(paid_keywords_raw, dict):
            paid_keywords_total = paid_keywords_raw.get("total", "")
            paid_keywords_list = paid_keywords_raw.get("top_keywords", [])
        else:
            paid_keywords_total = (
                str(len(paid_keywords_raw)) if paid_keywords_raw else ""
            )
            paid_keywords_list = (
                paid_keywords_raw if isinstance(paid_keywords_raw, list) else []
            )

        ad_copies = sem_data.get("ad_copies", [])

        # 新增字段
        competitors = sem_data.get("competitors", [])
        referring_sources = sem_data.get("referring_sources", [])
        serp_distribution = sem_data.get("serp_distribution", {})
        country_traffic = sem_data.get("country_traffic", [])

        if existing:
            cur.execute(
                """
                UPDATE semrush_competitor_data 
                SET organic_traffic = %s, paid_traffic = %s, authority_score = %s,
                    organic_keywords_count = %s, paid_keywords_count = %s,
                    top_organic_keywords = %s, top_paid_keywords = %s, ad_copies = %s,
                    competitors = %s, referring_sources = %s, serp_distribution = %s, country_traffic = %s,
                    scraped_at = NOW(), status = 'completed'
                WHERE merchant_id = %s AND domain = %s
            """,
                (
                    traffic.get("organic", ""),
                    traffic.get("paid", ""),
                    traffic.get("authority_score", ""),
                    str(organic_keywords_total) or str(len(organic_keywords_list)),
                    str(paid_keywords_total) or str(len(paid_keywords_list)),
                    json.dumps(organic_keywords_list, ensure_ascii=False),
                    json.dumps(paid_keywords_list, ensure_ascii=False),
                    json.dumps(ad_copies, ensure_ascii=False),
                    json.dumps(competitors, ensure_ascii=False),
                    json.dumps(referring_sources, ensure_ascii=False),
                    json.dumps(serp_distribution, ensure_ascii=False),
                    json.dumps(country_traffic, ensure_ascii=False),
                    merchant_id,
                    domain,
                ),
            )
        else:
            cur.execute(
                """
                INSERT INTO semrush_competitor_data 
                (merchant_id, domain, organic_traffic, paid_traffic, authority_score,
                 organic_keywords_count, paid_keywords_count, top_organic_keywords, 
                 top_paid_keywords, ad_copies, competitors, referring_sources, 
                 serp_distribution, country_traffic, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed')
            """,
                (
                    merchant_id,
                    domain,
                    traffic.get("organic", ""),
                    traffic.get("paid", ""),
                    traffic.get("authority_score", ""),
                    str(organic_keywords_total) or str(len(organic_keywords_list)),
                    str(paid_keywords_total) or str(len(paid_keywords_list)),
                    json.dumps(organic_keywords_list, ensure_ascii=False),
                    json.dumps(paid_keywords_list, ensure_ascii=False),
                    json.dumps(ad_copies, ensure_ascii=False),
                    json.dumps(competitors, ensure_ascii=False),
                    json.dumps(referring_sources, ensure_ascii=False),
                    json.dumps(serp_distribution, ensure_ascii=False),
                    json.dumps(country_traffic, ensure_ascii=False),
                ),
            )

        conn.commit()
        conn.close()
        print(f"[DEBUG] 数据保存成功: merchant_id={merchant_id}, domain={domain}")
        return jsonify({"success": True, "message": "数据保存成功"})

    except Exception as e:
        print(f"[DEBUG] 保存异常: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


@bp.route("/api/yp_collect_merchant", methods=["POST"])
def api_yp_collect_merchant():
    """手动触发单个商户的商品采集，在新 cmd 窗口运行 download_only.py --single <mid>"""
    data = request.get_json(silent=True) or {}
    mid = str(data.get("merchant_id", "")).strip()
    name = str(data.get("merchant_name", mid)).strip()
    if not mid:
        return jsonify({"ok": False, "msg": "merchant_id 必填"})
    if YP_STOP_FILE.exists():
        try:
            YP_STOP_FILE.unlink()
        except Exception:
            pass
    bat_file = BASE_DIR / f"_launch_yp_single_{mid}.bat"
    bat_content = (
        f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle 采集商品 {name}\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{YP_COLLECT_SCRIPT}" --single {mid}\r\n'
        f"echo.\r\necho 采集结束，按任意键关闭\r\npause > nul\r\n"
    )
    try:
        bat_file.write_text(bat_content, encoding="gbk")
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "cmd.exe", "/k", str(bat_file)],
            cwd=str(BASE_DIR),
            shell=False,
        )
        return jsonify(
            {"ok": True, "msg": f"商户 {name}（{mid}）采集任务已在新窗口启动"}
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})


def _ensure_chrome_debug():
    """检测 Chrome 调试模式（localhost:9222），未启动则自动拉起。
    返回 (ok: bool, msg: str)
    """
    import socket, time as _t, glob

    def _cdp_alive():
        try:
            s = socket.create_connection(("127.0.0.1", 9222), timeout=1)
            s.close()
            return True
        except Exception:
            return False

    # 已经在跑，直接返回
    if _cdp_alive():
        return True, "Chrome 调试模式已就绪"

    # 找 Chrome 可执行文件路径（按优先级）
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Users\wuhj\AppData\Local\Google\Chrome\Application\chrome.exe",
    ]
    # 再试 360 极速浏览器等（兜底）
    candidates += glob.glob(
        r"C:\Users\wuhj\AppData\Local\**\chrome.exe", recursive=True
    )[:3]

    chrome_exe = None
    for c in candidates:
        if os.path.isfile(c):
            chrome_exe = c
            break

    if not chrome_exe:
        return (
            False,
            "未找到 Chrome，请手动启动调试模式：chrome.exe --remote-debugging-port=9222",
        )

    user_data_dir = r"C:\Users\wuhj\Chrome_Debug"
    try:
        subprocess.Popen(
            [
                chrome_exe,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
    except Exception as e:
        return False, f"启动 Chrome 失败: {e}"

    # 等待最多 8 秒确认启动
    for i in range(16):
        _t.sleep(0.5)
        if _cdp_alive():
            return True, f"Chrome 调试模式已自动启动（{user_data_dir}）"

    return False, "Chrome 已拉起但 9222 端口仍未就绪，请稍候再试"


@bp.route("/api/yp_collect_start", methods=["POST"])
def api_yp_collect_start():
    if YP_STOP_FILE.exists():
        try:
            YP_STOP_FILE.unlink()
        except Exception:
            pass

    # 自动确保 Chrome 调试模式已启动
    chrome_ok, chrome_msg = _ensure_chrome_debug()
    if not chrome_ok:
        return jsonify({"ok": False, "msg": f"Chrome 启动失败：{chrome_msg}"})

    try:
        import wmi as _wmi

        running = [
            p
            for p in _wmi.WMI().Win32_Process()
            if "download_only" in (p.CommandLine or "")
        ]
        if running:
            return jsonify(
                {
                    "ok": False,
                    "msg": f"YP 采集进程已在运行（PID: {', '.join(str(p.ProcessId) for p in running)}），请勿重复启动",
                }
            )
    except Exception:
        pass
    bat_file = BASE_DIR / "_launch_yp_collect.bat"
    bat_content = (
        f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle YP Collect\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{YP_COLLECT_SCRIPT}"\r\necho.\r\necho YP 采集已结束，按任意键关闭窗口\r\npause > nul\r\n'
    )
    try:
        bat_file.write_text(bat_content, encoding="gbk")
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", "cmd.exe", "/k", str(bat_file)],
            cwd=str(BASE_DIR),
            shell=False,
        )
        return jsonify(
            {
                "ok": True,
                "msg": f"【{chrome_msg}】YP 采集任务已在新窗口启动，进度每 5 秒自动刷新",
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"启动失败: {e}"})


@bp.route("/api/yp_collect_stop", methods=["POST"])
def api_yp_collect_stop():
    try:
        YP_STOP_FILE.write_text("stop", encoding="utf-8")
        return jsonify(
            {"ok": True, "msg": "停止信号已发送，采集脚本处理完当前商户后会安全退出"}
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"发送停止信号失败: {e}"})


@bp.route("/api/yp_collect_by_mid", methods=["POST"])
def api_yp_collect_by_mid():
    """按 merchant_id 列表，调用 download_only.py --single 采集指定商户商品"""
    data = request.get_json(silent=True) or {}
    merchant_ids = data.get("merchant_ids", [])
    if not merchant_ids:
        return jsonify({"ok": False, "msg": "请提供 merchant_id"})

    # 清除旧的停止信号
    if YP_STOP_FILE.exists():
        try:
            YP_STOP_FILE.unlink()
        except Exception:
            pass

    # 自动确保 Chrome 调试模式已启动
    chrome_ok, chrome_msg = _ensure_chrome_debug()
    if not chrome_ok:
        return jsonify({"ok": False, "msg": f"Chrome 启动失败：{chrome_msg}"})

    script = str(YP_COLLECT_SCRIPT)
    if not os.path.exists(script):
        return jsonify({"ok": False, "msg": f"采集脚本不存在: {script}"})

    # 多个 merchant_id 用空格拼接
    mid_args = []
    for mid in merchant_ids:
        mid = str(mid).strip()
        if mid:
            mid_args.extend(["--single", mid])

    if not mid_args:
        return jsonify({"ok": False, "msg": "无效的 merchant_id"})

    # 在新 cmd 窗口启动，方便查看日志
    mid_str = " ".join(str(m) for m in merchant_ids)
    bat_file = BASE_DIR / f"_launch_yp_mid_{merchant_ids[0]}.bat"
    bat_content = (
        f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle YP采集 {mid_str}\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{script}" {" ".join(mid_args)}\r\n'
        f"echo.\r\necho 采集已结束，按任意键关闭\r\npause > nul\r\n"
    )
    try:
        bat_file.write_text(bat_content, encoding="gbk")
        subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "start",
                "",
                "cmd.exe",
                "/k",
                str(bat_file),
            ],
            cwd=str(BASE_DIR),
            shell=False,
        )
        return jsonify(
            {
                "ok": True,
                "msg": f"【{chrome_msg}】已在新窗口启动采集：{mid_str}",
            }
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"启动失败: {e}"})


# ─── 广告方案下载 API ─────────────────────────────────────────────────────────


@bp.route("/api/download_plan/<asin>")
def api_download_plan(asin):
    """下载指定 ASIN 的广告方案为 TXT 文件"""
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 1. 检查广告方案是否存在
        cur.execute(
            """
            SELECT id, asin, merchant_id, merchant_name, product_name, product_price,
                   commission_pct, target_cpa, campaign_count, ad_group_count, ad_count,
                   brand_keywords_used, plan_status, generated_at
            FROM ads_plans WHERE asin=%s AND plan_status='completed' LIMIT 1
        """,
            (asin,),
        )
        plan = cur.fetchone()

        if not plan:
            return jsonify(
                {
                    "ok": False,
                    "error": "NOT_FOUND",
                    "msg": f"ASIN {asin} 的广告方案不存在或未完成",
                }
            ), 404

        plan_id = plan["id"]

        # 2. 查询广告系列数据
        cur.execute(
            """
            SELECT id, campaign_name, journey_stage, budget_pct, daily_budget_usd,
                   product_price, commission_pct, commission_usd, target_cpa,
                   negative_keywords, bid_strategy, status, created_at
            FROM ads_campaigns WHERE asin=%s ORDER BY id
        """,
            (asin,),
        )
        campaigns = cur.fetchall()

        # 3. 查询广告组数据
        campaign_ids = [c["id"] for c in campaigns]
        ad_groups = []
        if campaign_ids:
            placeholders = ",".join(["%s"] * len(campaign_ids))
            cur.execute(
                f"""
                SELECT id, campaign_id, ad_group_name, theme, user_intent,
                       keywords, negative_keywords, keyword_count, cpc_bid_usd, status
                FROM ads_ad_groups WHERE campaign_id IN ({placeholders}) ORDER BY campaign_id, id
            """,
                tuple(campaign_ids),
            )
            ad_groups = cur.fetchall()

        # 4. 查询广告数据
        ad_group_ids = [g["id"] for g in ad_groups]
        ads = []
        if ad_group_ids:
            placeholders = ",".join(["%s"] * len(ad_group_ids))
            cur.execute(
                f"""
                SELECT id, ad_group_id, campaign_id, asin, variant,
                       headlines, descriptions, sitelinks, callouts, structured_snippet,
                       final_url, display_url, headline_count, description_count,
                       all_chars_valid, quality_notes, bidding_phases, status
                FROM ads_ads WHERE ad_group_id IN ({placeholders}) ORDER BY ad_group_id, id
            """,
                tuple(ad_group_ids),
            )
            ads = cur.fetchall()

        cur.close()
        conn.close()

        # 5. 构建 TXT 文本内容
        lines = []

        # 顶部：商品信息
        lines.append("=" * 60)
        lines.append("广告方案")
        lines.append("=" * 60)
        lines.append(f"ASIN: {plan['asin']}")
        lines.append(f"商品名称: {plan['product_name'] or ''}")
        lines.append(f"商户名称: {plan['merchant_name'] or ''}")
        lines.append(f"商户ID: {plan['merchant_id'] or ''}")
        lines.append(
            f"商品价格: ${plan['product_price']}"
            if plan["product_price"]
            else "商品价格: "
        )
        lines.append(
            f"佣金率: {plan['commission_pct']}%"
            if plan["commission_pct"]
            else "佣金率: "
        )
        lines.append(
            f"目标CPA: ${plan['target_cpa']}" if plan["target_cpa"] else "目标CPA: "
        )
        lines.append(f"广告系列数: {plan['campaign_count'] or 0}")
        lines.append(f"广告组数: {plan['ad_group_count'] or 0}")
        lines.append(f"广告数: {plan['ad_count'] or 0}")
        lines.append(
            f"生成时间: {str(plan['generated_at']) if plan['generated_at'] else ''}"
        )
        lines.append("")
        lines.append("")

        # 按广告系列分组广告组
        campaign_ad_groups = {}
        for grp in ad_groups:
            cid = grp["campaign_id"]
            if cid not in campaign_ad_groups:
                campaign_ad_groups[cid] = []
            campaign_ad_groups[cid].append(grp)

        # 按广告组分组广告
        ad_group_ads = {}
        for ad in ads:
            gid = ad["ad_group_id"]
            if gid not in ad_group_ads:
                ad_group_ads[gid] = []
            ad_group_ads[gid].append(ad)

        # 遍历每个广告系列
        for camp in campaigns:
            cid = camp["id"]
            lines.append(camp["campaign_name"])

            # 广告系列级否定关键词
            camp_negs = []
            try:
                if camp["negative_keywords"]:
                    camp_negs = json.loads(camp["negative_keywords"])
            except:
                pass
            if camp_negs:
                lines.append(f"  否定关键词: {', '.join(camp_negs)}")

            # 遍历该系列下的广告组
            groups = campaign_ad_groups.get(cid, [])
            for grp in groups:
                gid = grp["id"]
                lines.append(f"  {grp['ad_group_name']}")

                # 关键词
                keywords = []
                try:
                    if grp["keywords"]:
                        keywords = json.loads(grp["keywords"])
                except:
                    pass
                if keywords:
                    kw_list = [kw.get("kw", "") for kw in keywords]
                    lines.append(f"    关键词: {', '.join(kw_list)}")

                # 广告组级否定关键词
                grp_negs = []
                try:
                    if grp["negative_keywords"]:
                        grp_negs = json.loads(grp["negative_keywords"])
                except:
                    pass
                if grp_negs:
                    lines.append(f"    否定关键词: {', '.join(grp_negs)}")

                # 遍历该广告组下的广告
                group_ads = ad_group_ads.get(gid, [])
                for ad in group_ads:
                    # 广告标题
                    headlines = []
                    try:
                        if ad["headlines"]:
                            headlines = json.loads(ad["headlines"])
                    except:
                        pass
                    if headlines:
                        lines.append(f"    广告标题({len(headlines)}个):")
                        for idx, hl in enumerate(headlines, 1):
                            lines.append(f"      {idx}. {hl.get('text', '')}")

                    # 广告描述
                    descriptions = []
                    try:
                        if ad["descriptions"]:
                            descriptions = json.loads(ad["descriptions"])
                    except:
                        pass
                    if descriptions:
                        lines.append(f"    广告描述:")
                        for idx, desc in enumerate(descriptions, 1):
                            lines.append(f"      {idx}. {desc.get('text', '')}")

            # 广告系列之间空两行
            lines.append("")
            lines.append("")

        # 生成 TXT 内容，添加 BOM 头以便 Windows 记事本正确显示中文
        txt_content = "\ufeff" + "\n".join(lines)

        # 生成文件名
        from datetime import datetime

        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"广告方案_{asin}_{date_str}.txt"

        # RFC 5987 编码文件名，支持中文
        encoded_filename = quote(filename)

        return Response(
            txt_content,
            mimetype="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            },
        )

    except Exception as e:
        import traceback

        print(f"[download_plan] ERROR for {asin}: {e}")
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "SERVER_ERROR", "msg": str(e)}), 500


@bp.route("/api/generate_product_report/<asin>")
def api_generate_product_report(asin):
    """生成商品报告文档（Markdown格式）"""
    import json
    from urllib.parse import quote

    try:
        conn = _db()
        cur = conn.cursor(dictionary=True)

        # 1. 获取商品信息
        cur.execute(
            """
            SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url, 
                   p.merchant_name, p.yp_merchant_id,
                   a.title as amz_title, a.brand, a.rating, a.review_count, 
                   a.bullet_points, a.description, a.category_path, a.availability,
                   a.top_reviews
            FROM yp_us_products p
            LEFT JOIN amazon_product_details a ON p.asin = a.asin
            WHERE p.asin = %s
            LIMIT 1
        """,
            (asin,),
        )
        product = cur.fetchone()

        if not product:
            conn.close()
            return jsonify({"ok": False, "error": "商品不存在"}), 404

        merchant_id = product.get("yp_merchant_id")
        merchant_name = product.get("merchant_name", "")

        # 2. 获取商户信息
        cur.execute(
            """
            SELECT merchant_id, merchant_name, website, country, avg_payout, tracking_url
            FROM yp_merchants 
            WHERE merchant_id = %s
            LIMIT 1
        """,
            (merchant_id,),
        )
        merchant = cur.fetchone()

        # 3. 获取品牌关键词
        cur.execute(
            """
            SELECT keyword 
            FROM ads_merchant_keywords 
            WHERE merchant_id = %s OR merchant_name = %s
            LIMIT 30
        """,
            (str(merchant_id) if merchant_id else "", merchant_name),
        )
        brand_keywords = [r["keyword"] for r in cur.fetchall()]

        # 4. 获取 SEMrush 数据
        semrush_data = None
        if merchant_id:
            cur.execute(
                """
                SELECT domain, organic_traffic, paid_traffic, authority_score,
                       organic_keywords_count, paid_keywords_count,
                       top_organic_keywords, top_paid_keywords, ad_copies,
                       competitors, referring_sources, serp_distribution, country_traffic
                FROM semrush_competitor_data 
                WHERE merchant_id = %s
                ORDER BY scraped_at DESC LIMIT 1
            """,
                (merchant_id,),
            )
            semrush_row = cur.fetchone()
            if semrush_row:
                semrush_data = {
                    "domain": semrush_row.get("domain", ""),
                    "organic_traffic": semrush_row.get("organic_traffic", ""),
                    "paid_traffic": semrush_row.get("paid_traffic", ""),
                    "authority_score": semrush_row.get("authority_score", ""),
                    "organic_keywords_count": semrush_row.get(
                        "organic_keywords_count", ""
                    ),
                    "paid_keywords_count": semrush_row.get("paid_keywords_count", ""),
                    "top_organic_keywords": [],
                    "top_paid_keywords": [],
                    "ad_copies": [],
                    "competitors": [],
                    "referring_sources": [],
                    "serp_distribution": {},
                    "country_traffic": [],
                }
                # 解析 JSON 字段
                for field in [
                    "top_organic_keywords",
                    "top_paid_keywords",
                    "ad_copies",
                    "competitors",
                    "referring_sources",
                    "serp_distribution",
                    "country_traffic",
                ]:
                    try:
                        if semrush_row.get(field):
                            semrush_data[field] = json.loads(semrush_row[field])
                    except:
                        pass

        # 5. 尝试从文件读取 SEMrush 数据（如果数据库没有）
        if not semrush_data and merchant_id:
            semrush_file = BASE_DIR / "temp" / f"semrush_collected_{merchant_id}.json"
            if semrush_file.exists():
                try:
                    file_data = json.loads(semrush_file.read_text(encoding="utf-8"))
                    raw_data = file_data.get("data", {})
                    if raw_data:
                        # 转换数据格式以匹配报告生成期望的格式
                        traffic = raw_data.get("traffic", {})
                        organic_kw = raw_data.get("organic_keywords", {})
                        paid_kw = raw_data.get("paid_keywords", {})

                        # 处理 organic_keywords（可能是字典或列表）
                        if isinstance(organic_kw, dict):
                            organic_total = organic_kw.get("total", "")
                            organic_list = organic_kw.get("top_keywords", [])
                        else:
                            organic_total = str(len(organic_kw)) if organic_kw else ""
                            organic_list = (
                                organic_kw if isinstance(organic_kw, list) else []
                            )

                        # 处理 paid_keywords（可能是字典或列表）
                        if isinstance(paid_kw, dict):
                            paid_total = paid_kw.get("total", "")
                            paid_list = paid_kw.get("top_keywords", [])
                        else:
                            paid_total = str(len(paid_kw)) if paid_kw else ""
                            paid_list = paid_kw if isinstance(paid_kw, list) else []

                        semrush_data = {
                            "domain": raw_data.get("domain", ""),
                            "organic_traffic": traffic.get("organic", ""),
                            "paid_traffic": traffic.get("paid", ""),
                            "authority_score": traffic.get("authority_score", ""),
                            "organic_keywords_count": organic_total,
                            "paid_keywords_count": paid_total,
                            "top_organic_keywords": organic_list,
                            "top_paid_keywords": paid_list,
                            "ad_copies": raw_data.get("ad_copies", []),
                            "competitors": raw_data.get("competitors", []),
                            "referring_sources": raw_data.get("referring_sources", []),
                            "serp_distribution": raw_data.get("serp_distribution", {}),
                            "country_traffic": raw_data.get("country_traffic", []),
                        }
                except:
                    pass

        conn.close()

        # 6. 生成 Markdown 文档
        doc_lines = []

        # 品牌信息
        brand_name = merchant.get("merchant_name", "") if merchant else merchant_name
        website = merchant.get("website", "") if merchant else ""
        if not website and semrush_data:
            website = f"https://{semrush_data.get('domain', '')}"

        doc_lines.append(f"#品牌")
        doc_lines.append(brand_name)
        doc_lines.append("")
        doc_lines.append(f"#MID: {merchant_id or 'N/A'}")
        doc_lines.append("")
        doc_lines.append(f"#国家")
        country = merchant.get("country", "US") if merchant else "US"
        doc_lines.append(country.split(" - ")[0] if " - " in country else country)
        doc_lines.append("")
        doc_lines.append(f"#官网")
        doc_lines.append(website or "暂无")
        doc_lines.append("")
        doc_lines.append(f"#介绍")
        # 从产品描述生成介绍
        description = product.get("description", "") or product.get("bullet_points", "")
        if description:
            doc_lines.append(
                description[:500] + ("..." if len(description) > 500 else "")
            )
        else:
            doc_lines.append(f"{brand_name} 是美国知名品牌，专注于优质产品。")
        doc_lines.append("")

        # 谷歌联想词（使用品牌关键词）
        doc_lines.append(f"#谷歌联想词")
        for kw in brand_keywords[:5]:
            doc_lines.append(f"- {kw}")
        doc_lines.append("")

        # 品牌的关键字（自然搜索）
        doc_lines.append(f"#品牌的关键字")
        if semrush_data and semrush_data.get("top_organic_keywords"):
            organic_kws = semrush_data["top_organic_keywords"][:10]
            doc_lines.append("| 关键词 | 排名 | 月搜索量 | CPC | 流量 |")
            doc_lines.append("|-------|-----|---------|-----|------|")
            for kw in organic_kws:
                keyword = kw.get("keyword", "")
                position = kw.get("position", "-")
                volume = kw.get("volume", "-")
                cpc = kw.get("cpc", "-")
                traffic = kw.get("traffic", "-")
                doc_lines.append(
                    f"| {keyword} | {position} | {volume} | ${cpc} | {traffic} |"
                )
        else:
            doc_lines.append("暂无自然关键词数据")
        doc_lines.append("")

        # 付费关键字
        doc_lines.append(f"#付费关键字")
        if semrush_data and semrush_data.get("top_paid_keywords"):
            paid_kws = semrush_data["top_paid_keywords"][:10]
            for kw in paid_kws:
                doc_lines.append(
                    f"- {kw.get('keyword', kw) if isinstance(kw, dict) else kw}"
                )
        elif semrush_data and semrush_data.get("paid_keywords_count"):
            doc_lines.append(f"总数：{semrush_data['paid_keywords_count']} 个")
        else:
            doc_lines.append("暂无付费关键词数据")
        doc_lines.append("")

        # 文字广告样本
        doc_lines.append(f"#文字广告样本")
        if semrush_data and semrush_data.get("ad_copies"):
            for ad in semrush_data["ad_copies"][:3]:
                headline = ad.get("headline", "")
                descriptions = ad.get("descriptions", [])
                doc_lines.append(f"- **{headline}**")
                for desc in descriptions[:2]:
                    doc_lines.append(f"  - {desc}")
                doc_lines.append("")
        else:
            doc_lines.append("暂无广告文案样本")
        doc_lines.append("")

        # 分隔线
        doc_lines.append("————————————————————————")
        doc_lines.append("")

        # 商品信息
        product_title = product.get("amz_title") or product.get("product_name", "")
        doc_lines.append(f"#商品名称")
        doc_lines.append(product_title)
        doc_lines.append("")

        # 商品关键词（基于产品名称生成）
        doc_lines.append(f"#关键词")
        brand_lower = brand_name.lower() if brand_name else ""
        product_words = product_title.lower().split()[:5]

        # 品牌词
        if brand_name:
            doc_lines.append(
                f"- 品牌词：{brand_name} {product_words[2] if len(product_words) > 2 else ''}"
            )

        # 功能词
        if product_words:
            func_words = " ".join(product_words[:3])
            doc_lines.append(f"- 功能词：{func_words}")

        # 特点词
        if product.get("bullet_points"):
            bp = product.get("bullet_points", "")
            if isinstance(bp, str):
                bp_words = bp.split()[:5]
                doc_lines.append(f"- 特点词：{' '.join(bp_words)}")

        doc_lines.append("")

        # 价格
        price = product.get("price", "")
        doc_lines.append(f"#价格：USD {price or 'N/A'}")
        doc_lines.append("")

        # 佣金
        commission = product.get("commission", "")
        doc_lines.append(f"#佣金：{commission or 'N/A'}")
        doc_lines.append("")

        # 商品详情
        doc_lines.append(f"商品详情：")
        doc_lines.append(f"- ASIN: {asin}")
        if product.get("brand"):
            doc_lines.append(f"- 品牌: {product.get('brand')}")
        if product.get("category_path"):
            doc_lines.append(f"- 类目: {product.get('category_path')}")
        if product.get("rating"):
            doc_lines.append(
                f"- 评分: {product.get('rating')} ({product.get('review_count', 0)} 评论)"
            )
        if product.get("availability"):
            doc_lines.append(f"- 库存: {product.get('availability')}")
        doc_lines.append("")

        # 评论
        doc_lines.append(f"#评论")
        if product.get("review_count"):
            doc_lines.append(
                f"共 {product.get('review_count')} 条评论，平均评分 {product.get('rating', 'N/A')}"
            )

            # 解析并显示前5条评论
            top_reviews_raw = product.get("top_reviews", "")
            if top_reviews_raw:
                try:
                    if isinstance(top_reviews_raw, str):
                        top_reviews = json.loads(top_reviews_raw)
                    else:
                        top_reviews = top_reviews_raw

                    if top_reviews and len(top_reviews) > 0:
                        doc_lines.append("")
                        doc_lines.append("**精选评论：**")
                        for i, review in enumerate(top_reviews[:5], 1):
                            rating = review.get("rating", "")
                            title = review.get("title", "")
                            body = review.get("body", "")

                            # 评论标题
                            if title:
                                doc_lines.append(f"\n{i}. **{title}** ({rating})")
                            else:
                                doc_lines.append(f"\n{i}. ({rating})")

                            # 评论内容（完整显示）
                            if body:
                                doc_lines.append(f"   {body}")
                except Exception as e:
                    doc_lines.append(f"   解析评论失败: {str(e)}")
        else:
            doc_lines.append("暂无评论数据")
        doc_lines.append("")

        # 原始链接
        tracking_url = product.get("tracking_url", "")
        doc_lines.append(f"#原始链接")
        doc_lines.append(tracking_url or "暂无")
        doc_lines.append("")

        # 最终链接（通过请求 tracking_url 获取跳转后的真实链接）
        doc_lines.append(f"#最终链接")
        final_url = f"https://www.amazon.com/dp/{asin}"  # 默认值

        if tracking_url:
            try:
                import requests as _requests
                import re as _re

                resp = _requests.get(tracking_url, allow_redirects=False, timeout=10)
                # 从 refresh 头提取跳转 URL
                refresh = resp.headers.get("refresh", "") or resp.headers.get(
                    "Refresh", ""
                )
                if refresh:
                    m = _re.search(r"url=(.+)", refresh, _re.IGNORECASE)
                    if m:
                        final_url = m.group(1).strip()
            except Exception:
                pass  # 使用默认值

        doc_lines.append(final_url)
        doc_lines.append("")

        # 流量概览
        if semrush_data:
            doc_lines.append("————————————————————————")
            doc_lines.append("")
            doc_lines.append(f"#流量概览")
            doc_lines.append(
                f"- 自然流量: {semrush_data.get('organic_traffic', 'N/A')}"
            )
            doc_lines.append(f"- 付费流量: {semrush_data.get('paid_traffic', 'N/A')}")
            doc_lines.append(
                f"- 权威分数: {semrush_data.get('authority_score', 'N/A')}"
            )
            doc_lines.append(
                f"- 自然关键词数: {semrush_data.get('organic_keywords_count', 'N/A')}"
            )
            doc_lines.append(
                f"- 付费关键词数: {semrush_data.get('paid_keywords_count', 'N/A')}"
            )
            doc_lines.append("")

            # 竞品数据
            competitors = semrush_data.get("competitors", [])
            if competitors:
                doc_lines.append(f"#SEO竞品")
                for c in competitors[:5]:
                    comp_domain = c.get("domain", c) if isinstance(c, dict) else c
                    comp_type = c.get("type", "") if isinstance(c, dict) else ""
                    doc_lines.append(
                        f"- {comp_domain}" + (f" ({comp_type})" if comp_type else "")
                    )
                doc_lines.append("")

            # 引用来源
            referring_sources = semrush_data.get("referring_sources", [])
            if referring_sources:
                doc_lines.append(f"#主要引用来源")
                for r in referring_sources[:5]:
                    ref_domain = r.get("domain", r) if isinstance(r, dict) else r
                    mentions = r.get("mentions", "") if isinstance(r, dict) else ""
                    doc_lines.append(
                        f"- {ref_domain}"
                        + (f" ({mentions} 次提及)" if mentions else "")
                    )
                doc_lines.append("")

            # SERP 分布
            serp_dist = semrush_data.get("serp_distribution", {})
            if serp_dist:
                doc_lines.append(f"#SERP分布")
                organic_pct = serp_dist.get("organic", 0)
                ai_pct = serp_dist.get("ai_overviews", 0)
                other_pct = serp_dist.get("other_serp", 0)
                doc_lines.append(f"- 自然搜索: {organic_pct}%")
                doc_lines.append(f"- AI 概览: {ai_pct}%")
                doc_lines.append(f"- 其他 SERP: {other_pct}%")
                doc_lines.append("")

            # 国家/地区流量
            country_traffic = semrush_data.get("country_traffic", [])
            if country_traffic:
                doc_lines.append(f"#国家/地区分布")
                doc_lines.append("| 国家/地区 | 可见度 | 提及数 |")
                doc_lines.append("|----------|-------|--------|")
                for ct in country_traffic[:5]:
                    ct_country = ct.get("country", "")
                    ct_visibility = ct.get("visibility", "-")
                    ct_mentions = ct.get("mentions", "-")
                    doc_lines.append(
                        f"| {ct_country} | {ct_visibility} | {ct_mentions} |"
                    )
                doc_lines.append("")

        # 生成文档内容
        doc_content = "\n".join(doc_lines)

        # 生成文件名
        brand_safe = "".join(
            c if c.isalnum() or c in " -_" else "" for c in brand_name
        )[:30]
        filename = f"{brand_safe}_{asin}_报告.md"

        # 返回文件下载
        encoded_filename = quote(filename)

        return Response(
            doc_content,
            mimetype="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            },
        )

    except Exception as e:
        import traceback

        print(f"[generate_product_report] ERROR: {e}")
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": str(e)}), 500


# ─── 广告优化模块（T-002: 文件上传 + CSV/Excel解析）──────────────────────────────
