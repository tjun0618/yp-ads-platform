# routes_merchants.py - Amazon采集、商户管理、商户商品
# 从 ads_manager.py 行 2860-4190 提取
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
from db import get_db, _db, _cached_count, _count_cache
from templates_shared import (
    BASE_CSS,
    NAV_HTML,
    _BASE_STYLE_DARK,
    _PAGER_JS_DARK,
    _SCRAPE_TOPNAV,
)

bp = Blueprint("merchants", __name__)

# 全局状态变量 - Amazon采集
scrape_process = None
scrape_running = False
scrape_thread = None

AMAZON_SCRAPE_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Amazon 采集控制台 · YP Affiliate 管理台</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
    .topbar { background: #1a1a2e; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 20px; height: 56px; position:sticky;top:0;z-index:200; }
    .topbar-title { font-size: 1.1rem; font-weight: 700; color: #fff; }
    .topbar-nav { display: flex; align-items: center; gap: 4px; overflow-x: auto; }
    .topbar-nav a { color: #adb5bd; text-decoration: none; font-size: .87rem; padding: 6px 12px; border-radius: 6px; transition: background .15s; }
    .topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }
    .container { max-width: 780px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 1.6rem; color: #fff; margin-bottom: 6px; }
    .subtitle { color: #888; font-size: .9rem; margin-bottom: 32px; }
    .status-card { background: #1a1d24; border-radius: 12px; padding: 24px 28px; margin-bottom: 28px; border: 1px solid #2a2d36; }
    .status-row { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
    .badge { display: inline-block; padding: 4px 14px; border-radius: 20px; font-size: .8rem; font-weight: 600; text-transform: uppercase; }
    .badge-running  { background: #1a4a1f; color: #4caf50; border: 1px solid #4caf50; }
    .badge-stopped  { background: #4a1a1a; color: #f44336; border: 1px solid #f44336; }
    .badge-finished { background: #1a3a4a; color: #2196f3; border: 1px solid #2196f3; }
    .badge-idle     { background: #2a2d36; color: #888;    border: 1px solid #444; }
    .progress-wrap { margin: 4px 0 14px; }
    .progress-bar-bg { background: #2a2d36; border-radius: 8px; height: 10px; width: 100%; overflow: hidden; }
    .progress-bar    { background: linear-gradient(90deg, #4caf50, #81c784); height: 100%; border-radius: 8px; transition: width .5s; }
    .stats { display: flex; gap: 20px; flex-wrap: wrap; }
    .stat-item { flex: 1; min-width: 110px; background: #23262f; border-radius: 8px; padding: 14px 18px; }
    .stat-label { font-size: .75rem; color: #888; margin-bottom: 4px; }
    .stat-value { font-size: 1.5rem; font-weight: 700; color: #fff; }
    .stat-value.green { color: #4caf50; } .stat-value.red { color: #f44336; } .stat-value.blue { color: #64b5f6; }
    .current-asin { margin-top: 16px; font-size: .85rem; color: #888; }
    .current-asin span { color: #fff; font-family: monospace; background: #23262f; padding: 2px 8px; border-radius: 4px; }
    .btn-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 28px; }
    .btn { flex: 1; min-width: 160px; padding: 14px 20px; border: none; border-radius: 10px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: opacity .15s; display: flex; align-items: center; justify-content: center; gap: 8px; }
    .btn:disabled { opacity: .4; cursor: not-allowed; }
    .btn-start { background: #2e7d32; color: #fff; } .btn-start:hover:not(:disabled) { background: #388e3c; }
    .btn-stop  { background: #c62828; color: #fff; } .btn-stop:hover:not(:disabled)  { background: #d32f2f; }
    .log-card { background: #1a1d24; border-radius: 12px; padding: 20px 24px; border: 1px solid #2a2d36; }
    .log-title { font-size: .85rem; color: #888; margin-bottom: 10px; text-transform: uppercase; }
    .log-box { background: #0f1117; border-radius: 8px; padding: 14px; font-family: monospace; font-size: .82rem; color: #ccc; line-height: 1.6; min-height: 60px; max-height: 180px; overflow-y: auto; white-space: pre-wrap; }
    .tip-box { background: #1a2d1a; border: 1px solid #2e5e2e; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; font-size: .82rem; color: #a5d6a7; line-height: 1.7; }
    .updated-at { text-align: right; font-size: .75rem; color: #555; margin-top: 10px; }
  </style>
</head>
<body>
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_sync">🌐 全量同步</a>
    <a href="/yp_collect">⬇ YP采集</a>
    <a href="/amazon_scrape" class="active">🔄 Amazon采集</a>
    <a href="/merchants">🏬 商户管理</a>
    <a href="/">📦 商品列表</a>
    <a href="/plans">📋 广告方案</a>
    <a href="/qs_dashboard">⭐ 质量评分</a>
    <a href="/competitor_ads">🔍 竞品参考</a>
    <a href="/optimize" style="color:#ffa726">📈 投放优化</a>
  </nav>
</div>
<div class="container">
  <h1>Amazon 采集控制台</h1>
  <p class="subtitle">亚马逊商品详情采集任务控制 · 安全停止后下次开机可继续</p>
  <div class="tip-box">
    关机前：先点「停止采集」，等状态变为 STOPPED 后再关机。<br>
    下次开机：重新点「开始采集」，自动从上次停止位置继续（已完成的 ASIN 不会重复采集）。
  </div>
  <div class="btn-row">
    <button class="btn btn-start" id="btnStart" onclick="doStart()">&#9654; 开始采集</button>
    <button class="btn btn-stop"  id="btnStop"  onclick="doStop()">&#9646;&#9646; 停止采集</button>
  </div>
  <div class="status-card">
    <div class="status-row">
      <span style="font-size:1rem;color:#aaa;">当前状态</span>
      <span class="badge badge-idle" id="statusBadge">IDLE</span>
    </div>
    <div class="progress-wrap">
      <div style="display:flex;justify-content:space-between;font-size:.8rem;color:#888;margin-bottom:6px;">
        <span>采集进度</span><span id="progressText">0 / 0</span>
      </div>
      <div class="progress-bar-bg"><div class="progress-bar" id="progressBar" style="width:0%"></div></div>
    </div>
    <div class="stats">
      <div class="stat-item"><div class="stat-label">已处理</div><div class="stat-value blue" id="statIdx">0</div></div>
      <div class="stat-item"><div class="stat-label">成功</div><div class="stat-value green" id="statSuccess">0</div></div>
      <div class="stat-item"><div class="stat-label">失败/跳过</div><div class="stat-value red" id="statFail">0</div></div>
      <div class="stat-item"><div class="stat-label">剩余</div><div class="stat-value" id="statLeft">-</div></div>
    </div>
    <div class="current-asin" id="currentAsin" style="display:none">
      当前 ASIN：<span id="currentAsinVal"></span>
    </div>
  </div>
  <div class="log-card">
    <div class="log-title">操作日志</div>
    <div class="log-box" id="logBox">等待操作...</div>
  </div>
  <div class="updated-at" id="updatedAt"></div>
</div>
<script>
  function log(msg) {
    const box = document.getElementById('logBox');
    const ts = new Date().toLocaleTimeString('zh-CN');
    box.textContent = '[' + ts + '] ' + msg + '\n' + box.textContent;
  }
  function doStart() {
    document.getElementById('btnStart').disabled = true;
    fetch('/api/start', {method:'POST'}).then(r=>r.json()).then(d=>{log(d.msg);}).catch(()=>{log('启动请求失败');}).finally(()=>{document.getElementById('btnStart').disabled=false;});
  }
  function doStop() {
    document.getElementById('btnStop').disabled = true;
    fetch('/api/stop', {method:'POST'}).then(r=>r.json()).then(d=>{log(d.msg);}).catch(()=>{log('停止请求失败');}).finally(()=>{document.getElementById('btnStop').disabled=false;});
  }
  function refreshProgress() {
    fetch('/api/progress').then(r=>r.json()).then(d=>{
      const idx=d.idx||0, total=d.total||0, success=d.success||0, fail=d.fail||0;
      const status=d.status||'idle', asin=d.current_asin||'', updated=d.updated_at||'';
      const pct = total>0?Math.round(idx/total*100):0;
      document.getElementById('progressBar').style.width=pct+'%';
      document.getElementById('progressText').textContent=idx.toLocaleString()+' / '+total.toLocaleString()+'  ('+pct+'%)';
      document.getElementById('statIdx').textContent=idx.toLocaleString();
      document.getElementById('statSuccess').textContent=success.toLocaleString();
      document.getElementById('statFail').textContent=fail.toLocaleString();
      document.getElementById('statLeft').textContent=total>0?(total-idx).toLocaleString():'-';
      if(asin){document.getElementById('currentAsin').style.display='';document.getElementById('currentAsinVal').textContent=asin;}
      const badge=document.getElementById('statusBadge');
      const map={'running':['badge-running','RUNNING'],'stopped':['badge-stopped','STOPPED'],'finished':['badge-finished','FINISHED'],'idle':['badge-idle','IDLE']};
      badge.className='badge '+(map[status]?map[status][0]:'badge-idle');
      badge.textContent=map[status]?map[status][1]:status.toUpperCase();
      if(updated) document.getElementById('updatedAt').textContent='最近更新: '+updated;
    }).catch(()=>{});
  }
  refreshProgress();
  setInterval(refreshProgress, 3000);
</script>
</body>
</html>
"""


@bp.route("/amazon_scrape")
def page_amazon_scrape():
    from flask import Response

    return Response(AMAZON_SCRAPE_HTML, mimetype="text/html")


@bp.route("/api/start", methods=["POST"])
def api_start():
    """在新 CMD 窗口启动 scrape_amazon_details.py"""
    if STOP_FILE.exists():
        try:
            STOP_FILE.unlink()
        except Exception:
            pass
    try:
        import wmi

        c = wmi.WMI()
        running = [
            p
            for p in c.Win32_Process()
            if "scrape_amazon_details" in (p.CommandLine or "")
        ]
        if running:
            return jsonify(
                {
                    "ok": False,
                    "msg": f"采集进程已在运行（PID: {', '.join(str(p.ProcessId) for p in running)}），请勿重复启动",
                }
            )
    except Exception:
        pass
    bat_file = BASE_DIR / "_launch_scraper.bat"
    bat_content = (
        f'@echo off\r\ncd /d "{BASE_DIR}"\r\ntitle Amazon Scraper\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{SCRAPER_SCRIPT}"\r\necho.\r\necho 采集已结束，按任意键关闭窗口\r\npause > nul\r\n'
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
            {"ok": True, "msg": "采集任务已在新窗口启动，进度每 3 秒自动刷新"}
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"启动失败: {e}"})


@bp.route("/api/stop", methods=["POST"])
def api_stop():
    """写入停止信号文件"""
    try:
        STOP_FILE.write_text("stop", encoding="utf-8")
        proc_running = False
        try:
            import wmi as _wmi

            for p in _wmi.WMI().Win32_Process():
                if "scrape_amazon_details" in (p.CommandLine or ""):
                    proc_running = True
                    break
        except Exception:
            pass
        if not proc_running and PROGRESS_FILE.exists():
            try:
                pf = json.loads(PROGRESS_FILE.read_text(encoding="utf-8-sig"))
                if pf.get("status") in ("finished", "idle", "running"):
                    pf["status"] = "stopped"
                    from datetime import datetime as _dt

                    pf["updated_at"] = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
                    tmp = str(PROGRESS_FILE) + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(pf, f, ensure_ascii=False)
                    os.replace(tmp, str(PROGRESS_FILE))
            except Exception:
                pass
        return jsonify(
            {"ok": True, "msg": "停止信号已发送，采集脚本处理完当前 ASIN 后会安全退出"}
        )
    except Exception as e:
        return jsonify({"ok": False, "msg": f"发送停止信号失败: {e}"})


@bp.route("/api/progress")
def api_progress():
    if PROGRESS_FILE.exists():
        try:
            return jsonify(json.loads(PROGRESS_FILE.read_text(encoding="utf-8-sig")))
        except Exception as e:
            return jsonify(
                {
                    "idx": 0,
                    "total": 0,
                    "success": 0,
                    "fail": 0,
                    "current_asin": "",
                    "status": "error",
                    "updated_at": "",
                    "error": str(e),
                }
            )
    return jsonify(
        {
            "idx": 0,
            "total": 0,
            "success": 0,
            "fail": 0,
            "current_asin": "",
            "status": "idle",
            "updated_at": "",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════
# 采集模块 — 商户管理（读 JSON 文件）
# ═══════════════════════════════════════════════════════════════════════════


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


def _load_merchants_data():
    result = {"approved": [], "unapplied": [], "summary": {}}
    try:
        import mysql.connector

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        # 查询所有商户，按 status 分组
        cur.execute(
            "SELECT merchant_id, merchant_name, avg_payout, payout_unit, "
            "cookie_days, website, country, country_code, online_status, "
            "status, logo FROM yp_merchants ORDER BY id DESC"
        )
        all_merchants = cur.fetchall()

        # 查询哪些商户已有商品（即已下载）
        cur.execute("SELECT DISTINCT merchant_id FROM yp_products")
        downloaded_mids = set(str(r["merchant_id"]) for r in cur.fetchall())

        cur.close()

        approved = []
        unapplied = []
        for m in all_merchants:
            mid = str(m["merchant_id"])
            # Decimal → float 兼容
            if m.get("avg_payout") is not None:
                m["avg_payout"] = float(m["avg_payout"])
            if m.get("cookie_days") is not None:
                m["cookie_days"] = int(m["cookie_days"])
            m["download_status"] = (
                "downloaded" if mid in downloaded_mids else "not_started"
            )
            if (m.get("status") or "").upper() in ("APPROVED", "ONLINE", "ACTIVE"):
                approved.append(m)
            else:
                unapplied.append(m)

        result["approved"] = approved
        result["unapplied"] = unapplied
        result["summary"] = {
            "approved_total": len(approved),
            "unapplied_total": len(unapplied),
            "download_done": sum(
                1 for m in approved if m["download_status"] == "downloaded"
            ),
            "download_failed": 0,
            "download_pending": sum(
                1 for m in approved if m["download_status"] == "not_started"
            ),
        }
    except Exception as e:
        result["error"] = str(e)
    return result


@bp.route("/api/merchants")
def api_merchants():
    data = _load_merchants_data()
    tab = request.args.get("tab", "approved")
    q = request.args.get("q", "").strip().lower()
    dl = request.args.get("dl", "")
    page = max(1, int(request.args.get("page", 1)))
    size = min(200, max(10, int(request.args.get("size", 50))))
    items = data.get(tab, [])
    if q:
        items = [
            m
            for m in items
            if q in m.get("merchant_name", "").lower()
            or q in str(m.get("merchant_id", ""))
        ]
    if dl and tab == "approved":
        items = [m for m in items if m.get("download_status") == dl]
    total = len(items)
    items = items[(page - 1) * size : page * size]
    return jsonify(
        {
            "tab": tab,
            "total": total,
            "page": page,
            "size": size,
            "pages": (total + size - 1) // size,
            "summary": data.get("summary", {}),
            "items": items,
        }
    )


MERCHANTS_UNIFIED_HTML = (
    "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'>\n"
    "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
    "<title>商户管理 · YP Affiliate 管理台</title>\n"
    + _BASE_STYLE_DARK
    + """
<style>
.summary-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 28px; }
.sum-card { flex: 1; min-width: 140px; background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 16px 20px; }
.sum-label { font-size: .75rem; color: #888; margin-bottom: 6px; text-transform: uppercase; }
.sum-value { font-size: 1.6rem; font-weight: 700; }
.sum-value.green { color: #4caf50; } .sum-value.red { color: #f44336; }
.sum-value.blue { color: #64b5f6; } .sum-value.orange { color: #ffa726; } .sum-value.white { color: #fff; }
.tab-bar { display: flex; gap: 4px; margin-bottom: 20px; }
.tab-btn { padding: 8px 22px; border-radius: 8px; border: none; background: #1a1d24; color: #888; font-size: .9rem; cursor: pointer; transition: background .15s; }
.tab-btn.active { background: #2196f3; color: #fff; }
.tab-btn:hover:not(.active) { background: #23262f; color: #fff; }
.scrape-ctrl { display: flex; gap: 14px; align-items: center; background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 10px 18px; margin-bottom: 20px; flex-wrap: wrap; }
.sc-label { font-size: .82rem; color: #888; white-space: nowrap; }
.sc-progress { flex: 1; min-width: 120px; }
.sc-bar-bg { background: #2a2d36; border-radius: 4px; height: 6px; }
.sc-bar { background: #4caf50; height: 6px; border-radius: 4px; transition: width .5s; }
.sc-text { font-size: .75rem; color: #888; margin-top: 4px; }
.sc-btns { display: flex; gap: 8px; }
.sc-btn { padding: 7px 18px; border: none; border-radius: 7px; font-size: .84rem; font-weight: 600; cursor: pointer; }
.sc-btn:disabled { opacity: .4; cursor: not-allowed; }
.sc-btn-start { background: #2e7d32; color: #fff; } .sc-btn-start:hover:not(:disabled) { background: #388e3c; }
.sc-btn-stop  { background: #c62828; color: #fff; } .sc-btn-stop:hover:not(:disabled) { background: #d32f2f; }
</style>
</head>
<body>
"""
    + _SCRAPE_TOPNAV
    + """
<div class="page">
  <div class="summary-row" id="summaryRow">
    <div class="sum-card"><div class="sum-label">已申请通过</div><div class="sum-value blue" id="smApproved">-</div></div>
    <div class="sum-card"><div class="sum-label">产品已下载</div><div class="sum-value green" id="smDlDone">-</div></div>
    <div class="sum-card"><div class="sum-label">下载失败</div><div class="sum-value red" id="smDlFailed">-</div></div>
    <div class="sum-card"><div class="sum-label">未开始下载</div><div class="sum-value orange" id="smDlPending">-</div></div>
    <div class="sum-card"><div class="sum-label">未申请商户</div><div class="sum-value white" id="smUnapplied">-</div></div>
  </div>
  <div class="scrape-ctrl">
    <span class="sc-label">Amazon 采集</span>
    <span class="badge badge-idle" id="scStatus">IDLE</span>
    <div class="sc-progress">
      <div class="sc-bar-bg"><div class="sc-bar" id="scBar" style="width:0%"></div></div>
      <div class="sc-text" id="scText">0 / 0</div>
    </div>
    <div class="sc-btns">
      <button class="sc-btn sc-btn-start" id="scBtnStart" onclick="doStart()">▶ 开始采集</button>
      <button class="sc-btn sc-btn-stop"  id="scBtnStop"  onclick="doStop()">⏸ 暂停采集</button>
    </div>
    <span class="sc-text" id="scUpdated" style="margin-left:8px;"></span>
  </div>
  <div class="tab-bar">
    <button class="tab-btn active" id="tabApproved" onclick="switchTab('approved')">✅ 申请通过</button>
    <button class="tab-btn" id="tabUnapplied" onclick="switchTab('unapplied')">⏳ 未申请</button>
  </div>
  <div class="toolbar">
    <input type="text" class="search-box" id="searchInput" placeholder="搜索商户名称 / ID..." oninput="onSearch()">
    <select class="filter-select" id="dlFilter" onchange="onFilter()">
      <option value="">全部下载状态</option>
      <option value="downloaded">已下载</option>
      <option value="not_started">未下载</option>
      <option value="failed">下载失败</option>
    </select>
    <span style="font-size:.8rem;color:#888;" id="totalCount">-</span>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead id="tblHead"></thead>
      <tbody id="tblBody"><tr><td colspan="8" class="loading">加载中...</td></tr></tbody>
    </table>
  </div>
  <div class="pager" id="pager"></div>
</div>
<script>
"""
    + _PAGER_JS_DARK
    + """
let curTab='approved', curPage=1, curSearch='', curDl='', curTotal=0, curPages=1;
const PAGE_SIZE=50;
function switchTab(tab) {
  curTab=tab; curPage=1; curSearch=''; curDl='';
  document.getElementById('searchInput').value='';
  document.getElementById('dlFilter').value='';
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab'+tab.charAt(0).toUpperCase()+tab.slice(1)).classList.add('active');
  document.getElementById('dlFilter').style.display=tab==='approved'?'':'none';
  loadTable();
}
let searchTimer;
function onSearch() { clearTimeout(searchTimer); searchTimer=setTimeout(()=>{ curSearch=document.getElementById('searchInput').value.trim(); curPage=1; loadTable(); },300); }
function onFilter() { curDl=document.getElementById('dlFilter').value; curPage=1; loadTable(); }
function loadTable() {
  document.getElementById('tblBody').innerHTML='<tr><td colspan="9" class="loading">加载中...</td></tr>';
  let url='/api/merchants?tab='+curTab+'&page='+curPage+'&size='+PAGE_SIZE;
  if(curSearch) url+='&q='+encodeURIComponent(curSearch);
  if(curDl) url+='&dl='+encodeURIComponent(curDl);
  fetch(url).then(r=>r.json()).then(data=>{
    try{
      const s=data.summary||{};
      document.getElementById('smApproved').textContent=(s.approved_total||0).toLocaleString();
      document.getElementById('smDlDone').textContent=(s.download_done||0).toLocaleString();
      document.getElementById('smDlFailed').textContent=(s.download_failed||0).toLocaleString();
      document.getElementById('smDlPending').textContent=(s.download_pending||0).toLocaleString();
      document.getElementById('smUnapplied').textContent=(s.unapplied_total||0).toLocaleString();
      curTotal=data.total; curPages=data.pages;
      document.getElementById('totalCount').textContent='共 '+data.total.toLocaleString()+' 条';
      renderHead(); renderBody(data.items);
      renderPager('pager', curPage, curPages, curTotal, PAGE_SIZE, 'goPage');
    }catch(e){console.error('renderBody error:',e);document.getElementById('tblBody').innerHTML='<tr><td colspan="9" class="empty">渲染错误: '+e.message+'</td></tr>';}
  }).catch(e=>{document.getElementById('tblBody').innerHTML='<tr><td colspan="9" class="empty">加载失败: '+e+'</td></tr>';});
}
function renderHead() {
  const h=document.getElementById('tblHead');
  if(curTab==='approved'){h.innerHTML='<tr><th>#</th><th>商户名称</th><th>商户ID</th><th>佣金/次</th><th>Cookie天</th><th>网站状态</th><th>国家</th><th>下载状态</th><th>商品</th><th>操作</th></tr>';}
  else{h.innerHTML='<tr><th>#</th><th>商户名称</th><th>商户ID</th><th>佣金/次</th><th>Cookie天</th><th>网站状态</th><th>国家</th><th>商品</th></tr>';}
}
function dlPill(s){if(s==='downloaded')return '<span class="pill pill-green">已下载</span>';if(s==='failed')return '<span class="pill pill-red">下载失败</span>';return '<span class="pill pill-gray">未下载</span>';}
function onlinePill(s){if(!s||s==='OFFLINE')return '<span class="pill pill-red">离线</span>';if(s==='ONLINE')return '<span class="pill pill-green">在线</span>';return '<span class="pill pill-gray">'+s+'</span>';}
function collectProducts(mid, name, btn){
  if(!confirm('即将采集商户「'+name+'」的商品，需要调试 Chrome 已启动，确认继续？')) return;
  btn.disabled=true; btn.textContent='采集中...';
  fetch('/api/yp_collect_merchant', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({merchant_id:mid, merchant_name:name})})
    .then(r=>r.json()).then(d=>{
      if(d.ok){ btn.textContent='✅ 已启动'; btn.style.background='#2e7d32'; }
      else{ btn.disabled=false; btn.textContent='⬇ 采集商品'; alert('启动失败: '+(d.msg||'')); }
    }).catch(e=>{ btn.disabled=false; btn.textContent='⬇ 采集商品'; alert('请求失败: '+e); });
}
function htmlEsc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function renderBody(items){
  const body=document.getElementById('tblBody');
  if(!items||!items.length){body.innerHTML='<tr><td colspan="10" class="empty">暂无数据</td></tr>';return;}
  const offset=(curPage-1)*PAGE_SIZE;
  body.innerHTML=items.map((m,i)=>{
    const payout=m.avg_payout&&parseFloat(m.avg_payout)>0?'$'+parseFloat(m.avg_payout).toFixed(2):'<span style="color:#555">-</span>';
    const cookie=m.cookie_days?m.cookie_days+'d':'-';
    const nameEsc=htmlEsc(m.merchant_name);
    const countryEsc=htmlEsc(m.country||'-');
    const onlineEsc=htmlEsc(m.online_status||'');
    const roomBtn='<a href="/merchant_room/'+m.merchant_id+'" class="link-btn" style="background:#1a2a40;border-color:#2a4a6a;color:#90caf9;">&#x1F3AF; &#20316;&#25112;&#23460;</a>';
    const viewBtn='<a href="/merchant_products?merchant_id='+m.merchant_id+'" class="link-btn" style="margin-left:4px;">&#21830;&#21697; &rarr;</a>';
    // ⚠️ 用 data-* 属性传参，彻底避免商户名含单引号/特殊字符导致 JS 崩溃
    const collectBtn='<button class="link-btn" style="font-size:11px;padding:3px 10px;margin-left:4px;background:#1a3a1a;border-color:#2a5a2a;color:#81c784;" data-mid="'+m.merchant_id+'" data-name="'+nameEsc+'" onclick="collectProducts(this.dataset.mid,this.dataset.name,this)">&#x2B07;</button>';
    const base='<td class="td-id">'+(offset+i+1)+'</td><td class="td-name" title="'+nameEsc+'">'+nameEsc+'</td><td class="td-id">'+m.merchant_id+'</td><td class="td-num">'+payout+'</td><td class="td-num">'+cookie+'</td><td>'+onlinePill(onlineEsc)+'</td><td>'+countryEsc+'</td>';
    if(curTab==='approved') return '<tr>'+base+'<td>'+dlPill(m.download_status)+'</td><td>'+roomBtn+viewBtn+'</td><td>'+collectBtn+'</td></tr>';
    return '<tr>'+base+'<td>'+roomBtn+viewBtn+'</td></tr>';
  }).join('');
}
function goPage(p){curPage=p;loadTable();window.scrollTo(0,0);}
function doStart(){document.getElementById('scBtnStart').disabled=true;fetch('/api/start',{method:'POST'}).then(r=>r.json()).then(d=>{console.log(d.msg);}).finally(()=>{document.getElementById('scBtnStart').disabled=false;});}
function doStop(){document.getElementById('scBtnStop').disabled=true;fetch('/api/stop',{method:'POST'}).then(r=>r.json()).then(d=>{console.log(d.msg);}).finally(()=>{document.getElementById('scBtnStop').disabled=false;});}
function refreshScrapeStatus(){
  fetch('/api/progress').then(r=>r.json()).then(d=>{
    const status=d.status||'idle', idx=d.idx||0, total=d.total||0, updated=d.updated_at||'';
    const pct=total>0?Math.round(idx/total*100):0;
    const sc=document.getElementById('scStatus');
    const map={'running':['badge-running','RUNNING'],'stopped':['badge-stopped','STOPPED'],'finished':['badge-finished','FINISHED'],'idle':['badge-idle','IDLE']};
    sc.className='badge '+(map[status]?map[status][0]:'badge-idle');
    sc.textContent=map[status]?map[status][1]:status.toUpperCase();
    document.getElementById('scBar').style.width=pct+'%';
    document.getElementById('scText').textContent=idx.toLocaleString()+' / '+total.toLocaleString()+' ('+pct+'%)';
    if(updated) document.getElementById('scUpdated').textContent='更新: '+updated;
  }).catch(()=>{});
}
document.getElementById('dlFilter').style.display='';
renderHead(); loadTable(); refreshScrapeStatus();
setInterval(refreshScrapeStatus, 3000);
</script>
</body>
</html>
"""
)


@bp.route("/merchants")
def page_merchants():
    return MERCHANTS_UNIFIED_HTML


# ═══════════════════════════════════════════════════════════════════════════
# 采集模块 — 商户商品 / 商品管理 API
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/api/merchant_products")
def api_merchant_products():
    mid = request.args.get("merchant_id", "").strip()
    q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    size = min(200, max(10, int(request.args.get("size", 50))))
    sort = request.args.get(
        "sort", "id_desc"
    )  # 排序参数：id_desc, earn_desc, earn_asc, price_desc, price_asc, commission_desc, commission_asc

    print(
        f"[DEBUG] api_merchant_products: mid={mid}, q={q}, page={page}, size={size}, sort={sort}"
    )

    if not mid:
        return jsonify({"error": "merchant_id required"}), 400
    try:
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT merchant_id, merchant_name, avg_payout, cookie_days, website, country, online_status, status FROM yp_merchants WHERE merchant_id=%s LIMIT 1",
            (mid,),
        )
        merchant = cur.fetchone() or {}
        # 如果 yp_merchants 中没有，从 JSON 文件回退
        if not merchant:
            merchant = _get_merchant_from_json(mid) or {}
        base_where = "WHERE p.merchant_id=%s"
        params = [mid]
        if q:
            base_where += " AND (p.product_name LIKE %s OR p.asin LIKE %s)"
            params.extend([f"%{q}%", f"%{q}%"])

        # 排序逻辑
        order_map = {
            "id_desc": "p.id DESC",
            "id_asc": "p.id ASC",
            "earn_desc": "(CAST(p.price AS DECIMAL(10,2)) * CAST(REPLACE(REPLACE(p.commission,'%',''),'$','') AS DECIMAL(10,2)) / 100) DESC",
            "earn_asc": "(CAST(p.price AS DECIMAL(10,2)) * CAST(REPLACE(REPLACE(p.commission,'%',''),'$','') AS DECIMAL(10,2)) / 100) ASC",
            "price_desc": "CAST(p.price AS DECIMAL(10,2)) DESC",
            "price_asc": "CAST(p.price AS DECIMAL(10,2)) ASC",
            "commission_desc": "CAST(REPLACE(REPLACE(p.commission,'%',''),'$','') AS DECIMAL(10,2)) DESC",
            "commission_asc": "CAST(REPLACE(REPLACE(p.commission,'%',''),'$','') AS DECIMAL(10,2)) ASC",
            "rating_desc": "CAST(d.rating AS DECIMAL(3,1)) DESC",
            "rating_asc": "CAST(d.rating AS DECIMAL(3,1)) ASC",
        }
        order_by = order_map.get(sort, "p.id DESC")

        print(f"[DEBUG] base_where: {base_where}")
        print(f"[DEBUG] params: {params}")
        print(f"[DEBUG] order_by: {order_by}")

        cur.execute(
            f"""SELECT SQL_CALC_FOUND_ROWS p.id, p.asin, p.product_name, p.price, p.commission,
                               p.tracking_url, p.amazon_url, p.scraped_at,
                               d.title as amz_title, d.rating, d.review_count, d.main_image_url, d.brand, d.availability, d.price as amz_price, d.category_path,
                               pl.plan_status
                        FROM yp_products p LEFT JOIN amazon_product_details d ON p.asin=d.asin
                        LEFT JOIN ads_plans pl ON p.asin=pl.asin
                        {base_where} ORDER BY {order_by} LIMIT %s OFFSET %s""",
            params + [size, (page - 1) * size],
        )

        def _earn(ps, cs):
            try:
                v = float(ps or 0) * float(str(cs or "").rstrip("%")) / 100
                return f"${v:.2f}" if v > 0 else ""
            except:
                return ""

        def _max_bid(ps, cs):
            """最高出价 = 预计佣金 / 30 * 7（人民币）"""
            try:
                earn = float(ps or 0) * float(str(cs or "").rstrip("%")) / 100
                v = earn / 30 * 7
                return f"¥{v:.2f}" if v > 0 else ""
            except:
                return ""

        def _min_bid(ps, cs):
            """最低出价 = 预计佣金 / 50 * 7（人民币）"""
            try:
                earn = float(ps or 0) * float(str(cs or "").rstrip("%")) / 100
                v = earn / 50 * 7
                return f"¥{v:.2f}" if v > 0 else ""
            except:
                return ""

        def _has_plan(status):
            return status == "completed"

        items = []
        for r in cur.fetchall():
            ps = str(r["price"]) if r["price"] else ""
            cs = r["commission"] or ""
            items.append(
                {
                    "id": r["id"],
                    "asin": r["asin"] or "",
                    "product_name": r["product_name"] or "",
                    "yp_price": ps,
                    "commission": cs,
                    "earn": _earn(ps, cs),
                    "max_bid": _max_bid(ps, cs),
                    "min_bid": _min_bid(ps, cs),
                    "tracking_url": r["tracking_url"] or "",
                    "amazon_url": r["amazon_url"] or "",
                    "scraped_at": str(r["scraped_at"]) if r["scraped_at"] else "",
                    "has_amazon": bool(r["amz_title"]),
                    "amz_title": r["amz_title"] or "",
                    "amz_price": r["amz_price"] or "",
                    "rating": r["rating"] or "",
                    "review_count": r["review_count"] or "",
                    "image_url": r["main_image_url"] or "",
                    "brand": r["brand"] or "",
                    "availability": r["availability"] or "",
                    "category_path": r["category_path"] or "",
                    "has_plan": _has_plan(r["plan_status"]),
                }
            )
        cur.execute("SELECT FOUND_ROWS()")
        total = cur.fetchone()["FOUND_ROWS()"]
        conn.close()
        return jsonify(
            {
                "merchant": {
                    k: str(v) if v is not None else "" for k, v in merchant.items()
                },
                "total": total,
                "page": page,
                "size": size,
                "pages": max(1, (total + size - 1) // size),
                "items": items,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/products")
def api_products():
    category = request.args.get("category", "ALL").strip()
    mid = request.args.get("merchant_id", "").strip()
    q = request.args.get("q", "").strip()
    has_amazon = request.args.get("has_amazon", "")
    price_min = request.args.get("price_min", "").strip()
    price_max = request.args.get("price_max", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    size = min(200, max(10, int(request.args.get("size", 50))))
    try:
        conn = _db()
        cur = conn.cursor(dictionary=True)
        _cats_key = "all_categories"
        if _cats_key in _count_cache and _time.time() < _count_cache[_cats_key][1]:
            categories = _count_cache[_cats_key][0]
        else:
            cur.execute(
                "SELECT category_id, category_name FROM yp_categories ORDER BY category_name"
            )
            categories = [
                {"id": r["category_id"], "name": r["category_name"]}
                for r in cur.fetchall()
            ]
            _count_cache[_cats_key] = (categories, _time.time() + 300)
        conditions = ["p.tracking_url IS NOT NULL", "p.tracking_url != ''"]
        params = []
        if category != "ALL":
            conditions.append("d.category_path LIKE %s")
            params.append(f"%{category}%")
        if mid:
            conditions.append("p.merchant_id=%s")
            params.append(mid)
        if q:
            conditions.append(
                "(p.product_name LIKE %s OR p.asin LIKE %s OR p.merchant_name LIKE %s OR d.brand LIKE %s)"
            )
            params += [f"%{q}%"] * 4
        if has_amazon == "1":
            conditions.append("d.asin IS NOT NULL")
        elif has_amazon == "0":
            conditions.append("d.asin IS NULL")
        try:
            if price_min:
                conditions.append("p.price>=%s")
                params.append(float(price_min))
        except ValueError:
            pass
        try:
            if price_max:
                conditions.append("p.price<=%s")
                params.append(float(price_max))
        except ValueError:
            pass
        join_type = "LEFT JOIN" if has_amazon != "1" else "INNER JOIN"
        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
        has_filter = bool(
            category != "ALL" or mid or q or has_amazon or price_min or price_max
        )
        # ─── 总数（避免 2000ms 的 COUNT(*) 全表扫描）────────────────────────
        # 无过滤：用 information_schema 估算（3ms vs 2000ms）
        # 有过滤：用独立 COUNT 查询（去掉 SQL_CALC_FOUND_ROWS，MySQL 8.0 中该特性性能差）
        if has_filter:
            cur.execute(
                f"SELECT COUNT(*) FROM yp_products p {join_type} amazon_product_details d ON p.asin=d.asin {where_sql}",
                params,
            )
            total = cur.fetchone()["COUNT(*)"]
        else:
            cur.execute(
                "SELECT TABLE_ROWS FROM information_schema.tables WHERE table_schema='affiliate_marketing' AND table_name='yp_products'"
            )
            r = cur.fetchone()
            est = r.get("TABLE_ROWS") or r.get("table_rows") if r else None
            total = int(est) if est else 300000
        cur.execute(
            f"""SELECT p.id, p.asin, p.merchant_name, p.merchant_id,
                               p.product_name, p.price as yp_price, p.commission, p.tracking_url, p.amazon_url,
                               d.title as amz_title, d.rating, d.review_count, d.main_image_url, d.brand, d.price as amz_price_val, d.availability, d.category_path,
                               pl.plan_status
                        FROM yp_products p {join_type} amazon_product_details d ON p.asin=d.asin
                        LEFT JOIN ads_plans pl ON p.asin=pl.asin
                        {where_sql} ORDER BY p.id DESC LIMIT %s OFFSET %s""",
            params + [size, (page - 1) * size],
        )

        def _earn(ps, cs):
            try:
                v = float(ps or 0) * float(str(cs or "").rstrip("%")) / 100
                return f"${v:.2f}" if v > 0 else ""
            except:
                return ""

        def _has_plan(status):
            return status == "completed"

        items = []
        for r in cur.fetchall():
            ps = str(r["yp_price"]) if r["yp_price"] else ""
            cs = r["commission"] or ""
            items.append(
                {
                    "id": r["id"],
                    "asin": r["asin"] or "",
                    "merchant_name": r["merchant_name"] or "",
                    "merchant_id": r["merchant_id"] or "",
                    "product_name": r["product_name"] or "",
                    "yp_price": ps,
                    "commission": cs,
                    "earn": _earn(ps, cs),
                    "tracking_url": r["tracking_url"] or "",
                    "amazon_url": r["amazon_url"] or "",
                    "has_amazon": bool(r["amz_title"]),
                    "amz_title": r["amz_title"] or "",
                    "amz_price": r["amz_price_val"] or "",
                    "rating": r["rating"] or "",
                    "review_count": r["review_count"] or "",
                    "image_url": r["main_image_url"] or "",
                    "brand": r["brand"] or "",
                    "availability": r["availability"] or "",
                    "category_path": r["category_path"] or "",
                    "has_plan": _has_plan(r["plan_status"]),
                }
            )
        conn.close()
        conn = None
        return jsonify(
            {
                "total": total,
                "page": page,
                "size": size,
                "pages": max(1, (total + size - 1) // size),
                "categories": categories,
                "items": items,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/product_detail")
def api_product_detail():
    asin = request.args.get("asin", "").strip()
    if not asin:
        return jsonify({"error": "asin required"}), 400
    try:
        conn = _db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM yp_products WHERE asin=%s LIMIT 1", (asin,))
        yp = cur.fetchone()
        cur.execute(
            "SELECT * FROM amazon_product_details WHERE asin=%s LIMIT 1", (asin,)
        )
        amz_raw = cur.fetchone()
        conn.close()

        def _j(v):
            if not v:
                return []
            try:
                return json.loads(v)
            except:
                return str(v)

        amz = None
        if amz_raw:
            amz = {
                "asin": amz_raw["asin"],
                "title": amz_raw["title"] or "",
                "brand": amz_raw["brand"] or "",
                "price": amz_raw["price"] or "",
                "original_price": amz_raw["original_price"] or "",
                "rating": amz_raw["rating"] or "",
                "review_count": amz_raw["review_count"] or "",
                "availability": amz_raw["availability"] or "",
                "bullet_points": _j(amz_raw["bullet_points"]),
                "description": amz_raw["description"] or "",
                "product_details": _j(amz_raw["product_details"]),
                "category_path": amz_raw["category_path"] or "",
                "main_image_url": amz_raw["main_image_url"] or "",
                "image_urls": _j(amz_raw["image_urls"]),
                "top_reviews": _j(amz_raw["top_reviews"]),
                "keywords": amz_raw["keywords"] or "",
                "amazon_url": amz_raw["amazon_url"] or "",
                "scraped_at": str(amz_raw["scraped_at"])
                if amz_raw["scraped_at"]
                else "",
            }
        yp_out = None
        if yp:
            yp_out = {
                "asin": yp["asin"] or "",
                "merchant_name": yp["merchant_name"] or "",
                "merchant_id": yp["merchant_id"] or "",
                "product_name": yp["product_name"] or "",
                "yp_price": str(yp["price"]) if yp["price"] else "",
                "commission": yp["commission"] or "",
                "tracking_url": yp["tracking_url"] or "",
                "amazon_url": yp["amazon_url"] or "",
                "scraped_at": str(yp["scraped_at"]) if yp["scraped_at"] else "",
            }
        return jsonify({"asin": asin, "yp": yp_out, "amazon": amz})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/merchant_products")
def page_merchant_products():
    # 使用 Response 直接返回，避免 Jinja2 把 JS 中 {{...}} 当模板解析导致500
    return Response(MERCHANT_PRODUCTS_UNIFIED_HTML, mimetype="text/html; charset=utf-8")


@bp.route("/products")
def page_products():
    # 商品管理已合并到商品列表主页，保留路由做兼容重定向
    return redirect("/")


# 商户商品页 HTML（深色主题，含统一导航）
MERCHANT_PRODUCTS_UNIFIED_HTML = (
    "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'>\n"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
    "<title>商户商品 · YP Affiliate 管理台</title>\n"
    + _BASE_STYLE_DARK
    + "\n</head>\n<body>\n"
    + _SCRAPE_TOPNAV
    + """
<div class="page">
  <a style="display:inline-flex;align-items:center;gap:6px;color:#888;font-size:.88rem;text-decoration:none;padding:6px 14px;border-radius:7px;background:#1a1d24;border:1px solid #2a2d36;margin-bottom:20px;" href="/merchants">← 返回商户管理</a>
  <div id="pageTitle" style="font-size:1.3rem;font-weight:700;color:#fff;margin-bottom:4px;">商户商品</div>
  <div id="pageSub" style="font-size:.85rem;color:#888;margin-bottom:24px;">加载中...</div>
  <div class="toolbar">
    <input type="text" class="search-box" id="searchInput" placeholder="搜索商品名称 / ASIN..." oninput="onSearch()" style="min-width:240px;">
    <span style="font-size:.8rem;color:#888;" id="totalCount">-</span>
  </div>
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>#</th><th>图片</th><th>ASIN</th><th>商品名称</th><th class="th-sort" onclick="sortBy('price')">YP价格 <span id="sort-price" class="sort-icon"></span></th><th class="th-sort" onclick="sortBy('commission')">佣金率 <span id="sort-commission" class="sort-icon"></span></th><th class="th-sort" onclick="sortBy('earn')">预计佣金 <span id="sort-earn" class="sort-icon"></span></th><th>最高出价</th><th>最低出价</th><th class="th-sort" onclick="sortBy('rating')">评分 <span id="sort-rating" class="sort-icon"></span></th><th>评论数</th><th>Amazon详情</th><th>操作</th></tr></thead>
      <tbody id="tblBody"><tr><td colspan="13" class="loading">加载中...</td></tr></tbody>
    </table>
  </div>
  <div class="pager" id="pager"></div>
</div>
<script>
"""
    + _PAGER_JS_DARK
    + """
const mid = new URLSearchParams(location.search).get('merchant_id') || '';
let curPage=1, curSearch='', curTotal=0, curPages=1, curSort='earn_desc';
const PAGE_SIZE=50;
// 排序相关
const sortMap = {
  'price': {asc: 'price_asc', desc: 'price_desc'},
  'commission': {asc: 'commission_asc', desc: 'commission_desc'},
  'earn': {asc: 'earn_asc', desc: 'earn_desc'},
  'rating': {asc: 'rating_asc', desc: 'rating_desc'}
};
function updateSortIcons(){
  document.querySelectorAll('.sort-icon').forEach(el=>el.textContent='');
  const [field, dir] = curSort.split('_');
  const icon = document.getElementById('sort-'+field);
  if(icon) icon.textContent = dir==='desc'?' ▼':' ▲';
}
function sortBy(field){
  const [curField, curDir] = curSort.split('_');
  if(curField===field){
    curSort = field + '_' + (curDir==='desc'?'asc':'desc');
  }else{
    curSort = field + '_desc';
  }
  curPage=1;
  loadTable();
}
function starsHtml(r){const n=parseFloat(r)||0;const full=Math.floor(n),half=n-full>=.5?1:0;let s='';for(let i=0;i<full;i++)s+='★';if(half)s+='½';return '<span style="color:#ffa726">'+s+'</span> <span style="color:#888;font-size:.8rem">'+( n||'')+'</span>';}
function loadMerchantInfo(data){const m=data.merchant||{};document.getElementById('pageTitle').textContent=m.merchant_name||'商户商品';document.getElementById('pageSub').textContent='商户ID: '+(m.merchant_id||mid)+'  ·  佣金: $'+parseFloat(m.avg_payout||0).toFixed(2)+'/次  ·  Cookie: '+(m.cookie_days||'-')+'天  ·  共 '+data.total.toLocaleString()+' 件商品';}
function htmlEsc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function renderBody(items){
  const body=document.getElementById('tblBody');const offset=(curPage-1)*PAGE_SIZE;
  if(!items||!items.length){body.innerHTML='<tr><td colspan="13" class="empty">暂无商品</td></tr>';return;}
  body.innerHTML=items.map((p,i)=>{
    const img=p.image_url?'<img src="'+htmlEsc(p.image_url)+'" style="width:48px;height:48px;object-fit:contain;background:#23262f;border-radius:4px;" onerror="this.hidden=1">'  :'<span style="color:#555;font-size:.75rem">无图</span>';
    const amzBadge=p.has_amazon?'<span class="pill pill-green">已采集</span>':'<span class="pill pill-gray">未采集</span>';
    const nameEsc=htmlEsc(p.product_name);
    const nameShort=(p.product_name||'').length>60?htmlEsc(p.product_name.slice(0,60))+'…':nameEsc||'-';
    const earnHtml=p.earn?'<span style="color:#69f0ae;font-weight:600">'+p.earn+'</span>':'<span style="color:#555">-</span>';
    const maxBidHtml=p.max_bid?'<span style="color:#ff9800;font-weight:600">'+p.max_bid+'</span>':'<span style="color:#555">-</span>';
    const minBidHtml=p.min_bid?'<span style="color:#90caf9;font-weight:600">'+p.min_bid+'</span>':'<span style="color:#555">-</span>';
    let adBtn='';
    if(p.has_plan){
      adBtn='<button style="background:#2e7d32;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="downloadPlan(this.dataset.asin)">下载方案</button>';
    }else if(p.has_amazon){
      adBtn='<button style="background:#1565c0;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="generateAd(this)">制作广告</button>';
    }else{
      adBtn='<button style="background:#e65100;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="generateAd(this)" title="建议先采集Amazon数据">制作广告</button>';
    }
    return '<tr><td class="td-id">'+(offset+i+1)+'</td><td>'+img+'</td><td class="td-id"><a href="https://www.amazon.com/dp/'+p.asin+'" target="_blank" style="color:#64b5f6">'+p.asin+'</a></td><td class="td-name" title="'+nameEsc+'">'+nameShort+'</td><td class="td-num">'+(p.yp_price?'$'+parseFloat(p.yp_price).toFixed(2):'-')+'</td><td class="td-num">'+(p.commission||'-')+'</td><td class="td-num">'+earnHtml+'</td><td class="td-num">'+maxBidHtml+'</td><td class="td-num">'+minBidHtml+'</td><td>'+starsHtml(p.rating)+'</td><td class="td-num">'+(p.review_count||'-')+'</td><td>'+amzBadge+'</td><td style="white-space:nowrap">'+adBtn+'</td></tr>';
  }).join('');
}
function loadTable(){
  document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="loading">加载中...</td></tr>';
  let url='/api/merchant_products?merchant_id='+encodeURIComponent(mid)+'&page='+curPage+'&size='+PAGE_SIZE+'&sort='+curSort;
  if(curSearch) url+='&q='+encodeURIComponent(curSearch);
  fetch(url).then(r=>r.json()).then(data=>{
    try{
      if(data.error){document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">错误: '+data.error+'</td></tr>';return;}
      loadMerchantInfo(data);curTotal=data.total;curPages=data.pages;
      document.getElementById('totalCount').textContent='共 '+data.total.toLocaleString()+' 件商品';
      renderBody(data.items);renderPager('pager',curPage,curPages,curTotal,PAGE_SIZE,'goPage');
      updateSortIcons();
    }catch(e){console.error('loadTable render error:',e);document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">渲染错误: '+e.message+'</td></tr>';}
  }).catch(e=>{document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">加载失败: '+e+'</td></tr>';});
}
let searchTimer;
function onSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(()=>{curSearch=document.getElementById('searchInput').value.trim();curPage=1;loadTable();},300);}
function goPage(p){curPage=p;loadTable();window.scrollTo(0,0);}
function openDetail(asin){alert('请在商品列表页查看详情（/products）或访问 https://www.amazon.com/dp/'+asin);}
async function generateAd(btn){
  const asin=btn.dataset.asin;
  btn.disabled=true;
  btn.textContent='生成中...';
  try{
    let res=await fetch('/api/generate/'+asin,{method:'POST'});
    let data=await res.json();
    if(data.success){
      alert('广告方案生成成功！共 '+data.campaigns+' 个广告系列');
      location.reload();
    }else if(data.message && data.message.includes('already exists')){
      // 方案已存在，尝试强制重新生成
      btn.textContent='重新生成中...';
      res=await fetch('/api/generate/'+asin+'?force=1',{method:'POST'});
      data=await res.json();
      if(data.success){
        alert('广告方案重新生成成功！共 '+data.campaigns+' 个广告系列');
        location.reload();
      }else{
        alert(data.message||'重新生成失败');
        btn.disabled=false;
        btn.textContent='制作广告';
      }
    }else{
      alert(data.message||'生成失败');
      btn.disabled=false;
      btn.textContent='制作广告';
    }
  }catch(e){
    alert('请求失败: '+e);
    btn.disabled=false;
    btn.textContent='制作广告';
  }
}
function downloadPlan(asin){
  window.open('/api/download_plan/'+asin);
}
loadTable();
</script>
</body>
</html>
"""
)

# 商品管理页 HTML（深色主题）
PRODUCTS_UNIFIED_HTML = (
    "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'>\n"
    "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
    "<title>商品管理 · YP Affiliate 管理台</title>\n"
    + _BASE_STYLE_DARK
    + """
<style>
.cat-sidebar{width:220px;flex-shrink:0;}
.cat-list{background:#1a1d24;border:1px solid #2a2d36;border-radius:10px;overflow:hidden;max-height:calc(100vh - 160px);overflow-y:auto;position:sticky;top:72px;}
.cat-item{padding:9px 16px;font-size:.86rem;cursor:pointer;border-bottom:1px solid #23262f;transition:background .12s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cat-item:hover{background:#23262f;color:#fff;}
.cat-item.active{background:#2196f3;color:#fff;}
.main-area{flex:1;min-width:0;}
.layout{display:flex;gap:20px;align-items:flex-start;}
</style>
</head>
<body>
"""
    + _SCRAPE_TOPNAV
    + """
<div class="page">
  <div class="layout">
    <div class="cat-sidebar">
      <div class="cat-list" id="catList">
        <div class="cat-item active" data-cat="ALL" onclick="selectCatByEl(this)">全部类别</div>
      </div>
    </div>
    <div class="main-area">
      <div class="toolbar">
        <input type="text" class="search-box" id="searchInput" placeholder="搜索商品名称/ASIN/品牌/商户..." oninput="onSearch()" style="min-width:260px;flex:1;">
        <select class="filter-select" id="amzFilter" onchange="onFilter()">
          <option value="">全部商品</option>
          <option value="1">已采集 Amazon 详情</option>
          <option value="0">未采集 Amazon 详情</option>
        </select>
        <div style="display:flex;align-items:center;gap:6px;">
          <span style="font-size:.82rem;color:#888;white-space:nowrap;">价格 $</span>
          <input type="number" class="search-box" id="priceMin" placeholder="最低" oninput="onPriceFilter()" style="width:80px;padding:8px 10px;">
          <span style="color:#555;">–</span>
          <input type="number" class="search-box" id="priceMax" placeholder="最高" oninput="onPriceFilter()" style="width:80px;padding:8px 10px;">
        </div>
        <button onclick="clearFilters()" style="background:#23262f;color:#aaa;border:1px solid #2a2d36;border-radius:7px;padding:7px 14px;font-size:.82rem;cursor:pointer;">清除筛选</button>
        <span style="font-size:.8rem;color:#888;" id="totalCount">-</span>
      </div>
      <div class="tbl-wrap">
        <table>
          <thead><tr><th>#</th><th>图片</th><th>ASIN</th><th>商品名称</th><th>商户</th><th>YP价格</th><th>佣金率</th><th>预计佣金</th><th>评分</th><th>Amazon详情</th><th>操作</th></tr></thead>
          <tbody id="tblBody"><tr><td colspan="11" class="loading">加载中...</td></tr></tbody>
        </table>
      </div>
      <div class="pager" id="pager"></div>
    </div>
  </div>
</div>
<script>
"""
    + _PAGER_JS_DARK
    + """
let curCat='ALL',curPage=1,curSearch='',curAmz='',curTotal=0,curPages=1,curPriceMin='',curPriceMax='';
const PAGE_SIZE=50;
function selectCatByEl(el){curCat=el.getAttribute('data-cat');curPage=1;document.querySelectorAll('.cat-item').forEach(e=>e.classList.remove('active'));el.classList.add('active');loadTable();}
function onFilter(){curAmz=document.getElementById('amzFilter').value;curPage=1;loadTable();}
let searchTimer;
function onSearch(){clearTimeout(searchTimer);searchTimer=setTimeout(()=>{curSearch=document.getElementById('searchInput').value.trim();curPage=1;loadTable();},300);}
let priceTimer;
function onPriceFilter(){clearTimeout(priceTimer);priceTimer=setTimeout(()=>{curPriceMin=document.getElementById('priceMin').value.trim();curPriceMax=document.getElementById('priceMax').value.trim();curPage=1;loadTable();},400);}
function clearFilters(){document.getElementById('searchInput').value='';document.getElementById('amzFilter').value='';document.getElementById('priceMin').value='';document.getElementById('priceMax').value='';curSearch='';curAmz='';curPriceMin='';curPriceMax='';curPage=1;loadTable();}
function goPage(p){curPage=p;loadTable();window.scrollTo(0,0);}
function starsHtml(r){const n=parseFloat(r)||0;const full=Math.floor(n),half=n-full>=.5?1:0;let s='';for(let i=0;i<full;i++)s+='★';if(half)s+='½';return '<span style="color:#ffa726">'+s+'</span><span style="color:#888;font-size:.8rem"> '+(n||'')+'</span>';}
let catsLoaded=false;
function loadCategories(cats){const list=document.getElementById('catList');let html='<div class="cat-item active" data-cat="ALL" onclick="selectCatByEl(this)">全部类别</div>';(cats||[]).forEach(c=>{const safe=c.name.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');html+='<div class="cat-item" data-cat="'+safe+'" onclick="selectCatByEl(this)">'+safe+'</div>';});list.innerHTML=html;}
function htmlEsc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function renderBody(items){
  const body=document.getElementById('tblBody');const offset=(curPage-1)*PAGE_SIZE;
  if(!items||!items.length){body.innerHTML='<tr><td colspan="11" class="empty">暂无商品</td></tr>';return;}
  body.innerHTML=items.map((p,i)=>{
    const img=p.image_url?'<img src="'+htmlEsc(p.image_url)+'" style="width:48px;height:48px;object-fit:contain;background:#23262f;border-radius:4px;" onerror="this.hidden=1">'  :'<span style="color:#555;font-size:.75rem">无图</span>';
    const amzBadge=p.has_amazon?'<span class="pill pill-green">已采集</span>':'<span class="pill pill-gray">未采集</span>';
    const nameEsc=htmlEsc(p.product_name);
    const mnameEsc=htmlEsc(p.merchant_name);
    const nameShort=(p.product_name||'').length>55?htmlEsc(p.product_name.slice(0,55))+'…':nameEsc||'-';
    const mname=(p.merchant_name||'').length>18?htmlEsc(p.merchant_name.slice(0,18))+'…':mnameEsc||'-';
    const earnHtml=p.earn?'<span style="color:#69f0ae;font-weight:600">'+p.earn+'</span>':'<span style="color:#555">-</span>';
    return '<tr><td class="td-id">'+(offset+i+1)+'</td><td>'+img+'</td><td class="td-id"><a href="https://www.amazon.com/dp/'+p.asin+'" target="_blank" style="color:#64b5f6">'+p.asin+'</a></td><td class="td-name" title="'+nameEsc+'">'+nameShort+'</td><td style="font-size:.8rem;color:#aaa" title="'+mnameEsc+'">'+mname+'</td><td class="td-num">'+(p.yp_price?'$'+parseFloat(p.yp_price).toFixed(2):'-')+'</td><td class="td-num">'+(p.commission||'-')+'</td><td class="td-num">'+earnHtml+'</td><td>'+starsHtml(p.rating)+'</td><td>'+amzBadge+'</td><td><a href="https://www.amazon.com/dp/'+p.asin+'" target="_blank" class="link-btn">Amazon</a></td></tr>';
  }).join('');
}
function loadTable(){
  document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="loading">加载中...</td></tr>';
  let url='/api/products?category='+encodeURIComponent(curCat)+'&page='+curPage+'&size='+PAGE_SIZE;
  if(curSearch) url+='&q='+encodeURIComponent(curSearch);
  if(curAmz) url+='&has_amazon='+curAmz;
  if(curPriceMin) url+='&price_min='+encodeURIComponent(curPriceMin);
  if(curPriceMax) url+='&price_max='+encodeURIComponent(curPriceMax);
  fetch(url).then(r=>r.json()).then(data=>{
    try{
      if(data.error){document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">错误: '+data.error+'</td></tr>';return;}
      if(!catsLoaded&&data.categories&&data.categories.length){loadCategories(data.categories);catsLoaded=true;}
      curTotal=data.total;curPages=data.pages;
      document.getElementById('totalCount').textContent='共 '+data.total.toLocaleString()+' 件';
      renderBody(data.items);
      renderPager('pager',curPage,curPages,curTotal,PAGE_SIZE,'goPage');
    }catch(e){console.error('loadTable render error:',e);document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">渲染错误: '+e.message+'</td></tr>';}
  }).catch(e=>{document.getElementById('tblBody').innerHTML='<tr><td colspan="13" class="empty">加载失败: '+e+'</td></tr>';});
}
loadTable();
</script>
</body>
</html>
"""
)


# ═══════════════════════════════════════════════════════════════════════════
# 采集模块 — YP 数据采集
# ═══════════════════════════════════════════════════════════════════════════

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
<div class="page" style="max-width:900px;margin-top:30px;">
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
