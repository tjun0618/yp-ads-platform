# -*- coding: utf-8 -*-
"""
scrape_control.py
=================
Amazon 采集任务控制台（Web UI）

功能：
  - 浏览器访问 http://localhost:5050 打开控制界面
  - /merchants  → 商户管理页面
  - 点击「开始采集」→ 在新 CMD 窗口启动 scrape_amazon_details.py
  - 点击「停止采集」→ 创建 .scrape_stop 信号文件，采集脚本安全退出
  - 页面每 3 秒自动刷新进度（已处理 / 成功 / 失败 / 当前 ASIN）

用法：
  python scrape_control.py
  # 然后浏览器访问 http://localhost:5050
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

BASE_DIR       = Path(os.path.abspath(__file__)).parent
STOP_FILE      = BASE_DIR / '.scrape_stop'
PROGRESS_FILE  = BASE_DIR / '.scrape_progress'
SCRAPER_SCRIPT = BASE_DIR / 'scrape_amazon_details.py'
PYTHON_EXE     = sys.executable

app = Flask(__name__)

# ─── HTML 模板 ─────────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Amazon 采集控制台</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
    .topbar { background: #15181f; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 20px; height: 56px; }
    .topbar-title { font-size: 1.1rem; font-weight: 700; color: #fff; }
    .topbar-nav a { color: #888; text-decoration: none; font-size: .88rem; padding: 6px 12px; border-radius: 6px; transition: background .15s; }
    .topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }
    .container { max-width: 780px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 1.6rem; color: #fff; margin-bottom: 6px; letter-spacing: .5px; }
    .subtitle { color: #888; font-size: .9rem; margin-bottom: 32px; }

    .status-card {
      background: #1a1d24; border-radius: 12px; padding: 24px 28px;
      margin-bottom: 28px; border: 1px solid #2a2d36;
    }
    .status-row { display: flex; align-items: center; gap: 12px; margin-bottom: 18px; }
    .badge {
      display: inline-block; padding: 4px 14px; border-radius: 20px;
      font-size: .8rem; font-weight: 600; text-transform: uppercase; letter-spacing: .5px;
    }
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
    .stat-value.green { color: #4caf50; }
    .stat-value.red   { color: #f44336; }
    .stat-value.blue  { color: #64b5f6; }

    .current-asin { margin-top: 16px; font-size: .85rem; color: #888; word-break: break-all; }
    .current-asin span { color: #fff; font-family: monospace; background: #23262f; padding: 2px 8px; border-radius: 4px; }

    .btn-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 28px; }
    .btn {
      flex: 1; min-width: 160px; padding: 14px 20px; border: none; border-radius: 10px;
      font-size: 1rem; font-weight: 600; cursor: pointer; transition: opacity .15s, transform .1s;
      display: flex; align-items: center; justify-content: center; gap: 8px;
    }
    .btn:active  { transform: scale(.97); }
    .btn:disabled { opacity: .4; cursor: not-allowed; }
    .btn-start { background: #2e7d32; color: #fff; }
    .btn-start:hover:not(:disabled) { background: #388e3c; }
    .btn-stop  { background: #c62828; color: #fff; }
    .btn-stop:hover:not(:disabled)  { background: #d32f2f; }

    .log-card { background: #1a1d24; border-radius: 12px; padding: 20px 24px; border: 1px solid #2a2d36; }
    .log-title { font-size: .85rem; color: #888; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .5px; }
    .log-box { background: #0f1117; border-radius: 8px; padding: 14px; font-family: monospace; font-size: .82rem; color: #ccc; line-height: 1.6; min-height: 60px; max-height: 180px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }

    .tip-box { background: #1a2d1a; border: 1px solid #2e5e2e; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; font-size: .82rem; color: #a5d6a7; line-height: 1.7; }
    .updated-at { text-align: right; font-size: .75rem; color: #555; margin-top: 10px; }
  </style>
</head>
<body>
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_collect">YP采集</a>
    <a href="/" class="active">采集控制台</a>
    <a href="/merchants">商户管理</a>
    <a href="/products">商品管理</a>
  </nav>
</div>
<div class="container">
  <h1>Amazon 采集控制台</h1>
  <p class="subtitle">亚马逊商品详情采集任务控制 &nbsp;·&nbsp; 安全停止后下次开机可继续</p>

  <div class="tip-box">
    关机前：先点「停止采集」，等状态变为 STOPPED 后再关机。<br>
    下次开机：重新点「开始采集」，自动从上次停止位置继续（已完成的 ASIN 不会重复采集）。
  </div>

  <!-- 按钮 -->
  <div class="btn-row">
    <button class="btn btn-start" id="btnStart" onclick="doStart()">
      &#9654; 开始采集
    </button>
    <button class="btn btn-stop" id="btnStop" onclick="doStop()">
      &#9646;&#9646; 停止采集
    </button>
  </div>

  <!-- 状态卡片 -->
  <div class="status-card">
    <div class="status-row">
      <span style="font-size:1rem; color:#aaa;">当前状态</span>
      <span class="badge badge-idle" id="statusBadge">IDLE</span>
    </div>

    <div class="progress-wrap">
      <div style="display:flex; justify-content:space-between; font-size:.8rem; color:#888; margin-bottom:6px;">
        <span>采集进度</span>
        <span id="progressText">0 / 0</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar" id="progressBar" style="width:0%"></div>
      </div>
    </div>

    <div class="stats">
      <div class="stat-item">
        <div class="stat-label">已处理</div>
        <div class="stat-value blue"  id="statIdx">0</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">成功</div>
        <div class="stat-value green" id="statSuccess">0</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">失败/跳过</div>
        <div class="stat-value red"   id="statFail">0</div>
      </div>
      <div class="stat-item">
        <div class="stat-label">剩余</div>
        <div class="stat-value"       id="statLeft">-</div>
      </div>
    </div>

    <div class="current-asin" id="currentAsin" style="display:none">
      当前 ASIN：<span id="currentAsinVal"></span>
    </div>
  </div>

  <!-- 操作日志 -->
  <div class="log-card">
    <div class="log-title">操作日志</div>
    <div class="log-box" id="logBox">等待操作...</div>
  </div>
  <div class="updated-at" id="updatedAt"></div>
</div><!-- /container -->

<script>
  function log(msg) {
    const box = document.getElementById('logBox');
    const ts  = new Date().toLocaleTimeString('zh-CN');
    box.textContent = '[' + ts + '] ' + msg + '\n' + box.textContent;
  }

  function doStart() {
    document.getElementById('btnStart').disabled = true;
    fetch('/api/start', {method:'POST'})
      .then(r => r.json())
      .then(d => { log(d.msg); })
      .catch(() => { log('启动请求失败，请检查控制台窗口'); })
      .finally(() => { document.getElementById('btnStart').disabled = false; });
  }

  function doStop() {
    document.getElementById('btnStop').disabled = true;
    fetch('/api/stop', {method:'POST'})
      .then(r => r.json())
      .then(d => { log(d.msg); })
      .catch(() => { log('停止请求失败'); })
      .finally(() => { document.getElementById('btnStop').disabled = false; });
  }

  function refreshProgress() {
    fetch('/api/progress')
      .then(r => r.json())
      .then(d => {
        const idx     = d.idx     || 0;
        const total   = d.total   || 0;
        const success = d.success || 0;
        const fail    = d.fail    || 0;
        const status  = d.status  || 'idle';
        const asin    = d.current_asin || '';
        const updated = d.updated_at   || '';

        const pct = total > 0 ? Math.round(idx / total * 100) : 0;
        document.getElementById('progressBar').style.width = pct + '%';
        document.getElementById('progressText').textContent =
          idx.toLocaleString() + ' / ' + total.toLocaleString() + '  (' + pct + '%)';

        document.getElementById('statIdx').textContent     = idx.toLocaleString();
        document.getElementById('statSuccess').textContent = success.toLocaleString();
        document.getElementById('statFail').textContent    = fail.toLocaleString();
        document.getElementById('statLeft').textContent    = total > 0 ? (total - idx).toLocaleString() : '-';

        if (asin) {
          document.getElementById('currentAsin').style.display = '';
          document.getElementById('currentAsinVal').textContent = asin;
        }

        const badge = document.getElementById('statusBadge');
        const map = {
          'running':  ['badge-running',  'RUNNING'],
          'stopped':  ['badge-stopped',  'STOPPED'],
          'finished': ['badge-finished', 'FINISHED'],
          'idle':     ['badge-idle',     'IDLE'],
        };
        badge.className = 'badge ' + (map[status] ? map[status][0] : 'badge-idle');
        badge.textContent = map[status] ? map[status][1] : status.toUpperCase();

        if (updated) document.getElementById('updatedAt').textContent = '最近更新: ' + updated;
      })
      .catch(() => {});
  }

  refreshProgress();
  setInterval(refreshProgress, 3000);
</script>
</body>
</html>
"""

# ─── API 路由 ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/api/start', methods=['POST'])
def api_start():
    """在新的 CMD 窗口中启动采集脚本"""
    # 清理旧停止信号
    if STOP_FILE.exists():
        try:
            STOP_FILE.unlink()
        except Exception:
            pass

    # ── 防止重复启动：检查是否已有采集进程 ──────────────────────────
    try:
        import wmi
        c = wmi.WMI()
        running = [p for p in c.Win32_Process()
                   if 'scrape_amazon_details' in (p.CommandLine or '')]
        if running:
            return jsonify({'ok': False,
                            'msg': f'采集进程已在运行（PID: {", ".join(str(p.ProcessId) for p in running)}），请勿重复启动'})
    except Exception:
        pass  # wmi 不可用时跳过检查

    # ── 通过临时 bat 文件启动，彻底避免路径引号/转义问题 ────────────
    bat_file = BASE_DIR / '_launch_scraper.bat'
    bat_content = (
        f'@echo off\r\n'
        f'cd /d "{BASE_DIR}"\r\n'
        f'title Amazon Scraper\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{SCRAPER_SCRIPT}"\r\n'
        f'echo.\r\n'
        f'echo 采集已结束，按任意键关闭窗口\r\n'
        f'pause > nul\r\n'
    )
    try:
        bat_file.write_text(bat_content, encoding='gbk')  # cmd 窗口使用 GBK
        bat_str = str(bat_file)
        # 用 cmd.exe /c start 开新窗口：start 的第一个带引号参数是窗口标题，
        # 第二个才是命令，两对引号分开不会互相干扰
        subprocess.Popen(
            ['cmd.exe', '/c', 'start', 'Amazon Scraper', 'cmd.exe', '/k', bat_str],
            cwd=str(BASE_DIR),
            shell=False   # 不用 shell=True，完全规避转义
        )
        return jsonify({'ok': True,
                        'msg': '采集任务已在新窗口启动，进度每 3 秒自动刷新'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'启动失败: {e}'})


@app.route('/api/stop', methods=['POST'])
def api_stop():
    """写入停止信号文件，并兜底处理无进程时的状态更新"""
    try:
        STOP_FILE.write_text('stop', encoding='utf-8')

        # ── 兜底：若当前没有采集进程（finished / idle），直接把进度文件改为 stopped ──
        # 这样页面轮询到的下一帧就会显示 STOPPED，不需要等采集脚本响应
        proc_running = False
        try:
            import wmi as _wmi
            for p in _wmi.WMI().Win32_Process():
                if 'scrape_amazon_details' in (p.CommandLine or ''):
                    proc_running = True
                    break
        except Exception:
            pass  # wmi 不可用时跳过检测，由采集脚本自己写

        if not proc_running and PROGRESS_FILE.exists():
            try:
                pf = json.loads(PROGRESS_FILE.read_text(encoding='utf-8-sig'))
                if pf.get('status') in ('finished', 'idle', 'running'):
                    pf['status'] = 'stopped'
                    from datetime import datetime as _dt
                    pf['updated_at'] = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
                    tmp = str(PROGRESS_FILE) + '.tmp'
                    import json as _json
                    with open(tmp, 'w', encoding='utf-8') as f:
                        _json.dump(pf, f, ensure_ascii=False)
                    os.replace(tmp, str(PROGRESS_FILE))
            except Exception:
                pass

        return jsonify({'ok': True,
                        'msg': '停止信号已发送，采集脚本处理完当前 ASIN 后会安全退出（通常几秒内）'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'发送停止信号失败: {e}'})


@app.route('/api/progress')
def api_progress():
    """返回当前进度 JSON"""
    if PROGRESS_FILE.exists():
        try:
            # utf-8-sig 自动跳过 BOM（Windows PowerShell Set-Content 会写 BOM）
            return jsonify(json.loads(PROGRESS_FILE.read_text(encoding='utf-8-sig')))
        except Exception as e:
            # 解析失败时返回原始内容供调试，而不是静默返回 idle
            return jsonify({
                'idx': 0, 'total': 0, 'success': 0, 'fail': 0,
                'current_asin': '', 'status': 'error',
                'updated_at': '', 'error': str(e),
            })
    return jsonify({
        'idx': 0, 'total': 0, 'success': 0, 'fail': 0,
        'current_asin': '', 'status': 'idle', 'updated_at': '',
    })



# ─── 商户管理 API ───────────────────────────────────────────────────────────────

OUTPUT_DIR = BASE_DIR / 'output'

def _load_merchants_data():
    """从预生成的 JSON 文件加载商户数据（含下载状态），实时读取"""
    result = {'approved': [], 'unapplied': [], 'summary': {}}
    try:
        approved_file = OUTPUT_DIR / 'approved_merchants.json'
        unapplied_file = OUTPUT_DIR / 'unapplied_merchants.json'
        download_state_file = OUTPUT_DIR / 'download_state.json'

        # 读取下载状态
        completed_mids, failed_mids = set(), set()
        if download_state_file.exists():
            ds = json.loads(download_state_file.read_text(encoding='utf-8-sig'))
            completed_mids = set(str(m) for m in ds.get('completed_mids', []))
            failed_mids    = set(str(m) for m in ds.get('failed_mids', []))

        # 读取 APPROVED
        if approved_file.exists():
            merchants = json.loads(approved_file.read_text(encoding='utf-8-sig'))
            for m in merchants:
                mid = str(m.get('merchant_id', ''))
                m['download_status'] = (
                    'downloaded' if mid in completed_mids else
                    ('failed'    if mid in failed_mids    else 'not_started')
                )
            result['approved'] = merchants

        # 读取 UNAPPLIED
        if unapplied_file.exists():
            result['unapplied'] = json.loads(unapplied_file.read_text(encoding='utf-8-sig'))

        # 汇总统计
        approved = result['approved']
        dl_done    = sum(1 for m in approved if m['download_status'] == 'downloaded')
        dl_failed  = sum(1 for m in approved if m['download_status'] == 'failed')
        dl_pending = sum(1 for m in approved if m['download_status'] == 'not_started')
        result['summary'] = {
            'approved_total'  : len(approved),
            'unapplied_total' : len(result['unapplied']),
            'download_done'   : dl_done,
            'download_failed' : dl_failed,
            'download_pending': dl_pending,
        }
    except Exception as e:
        result['error'] = str(e)
    return result


@app.route('/api/merchants')
def api_merchants():
    """返回商户列表（支持 ?tab=approved|unapplied&q=搜索词&dl=downloaded|failed|not_started&page=N&size=50）"""
    data = _load_merchants_data()
    tab  = request.args.get('tab', 'approved')
    q    = request.args.get('q', '').strip().lower()
    dl   = request.args.get('dl', '')    # 下载状态过滤（approved 专用）
    page = max(1, int(request.args.get('page', 1)))
    size = min(200, max(10, int(request.args.get('size', 50))))

    items = data.get(tab, [])

    # 过滤
    if q:
        items = [m for m in items if q in m.get('merchant_name', '').lower()
                 or q in str(m.get('merchant_id', ''))]
    if dl and tab == 'approved':
        items = [m for m in items if m.get('download_status') == dl]

    total = len(items)
    start = (page - 1) * size
    items = items[start: start + size]

    return jsonify({
        'tab'    : tab,
        'total'  : total,
        'page'   : page,
        'size'   : size,
        'pages'  : (total + size - 1) // size,
        'summary': data.get('summary', {}),
        'items'  : items,
    })


@app.route('/merchants')
def page_merchants():
    """商户管理页面"""
    return render_template_string(MERCHANTS_HTML)


# ─── 商户管理页面 HTML ──────────────────────────────────────────────────────────
MERCHANTS_HTML = r"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>商户管理 · YP Affiliate</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }

    /* ── top bar ── */
    .topbar { background: #15181f; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 20px; height: 56px; position: sticky; top: 0; z-index: 100; }
    .topbar-title { font-size: 1.1rem; font-weight: 700; color: #fff; white-space: nowrap; }
    .topbar-nav a { color: #888; text-decoration: none; font-size: .88rem; padding: 6px 12px; border-radius: 6px; transition: background .15s; }
    .topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }
    .topbar-spacer { flex: 1; }

    /* ── layout ── */
    .page { max-width: 1400px; margin: 0 auto; padding: 28px 20px; }

    /* ── summary cards ── */
    .summary-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 28px; }
    .sum-card { flex: 1; min-width: 140px; background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 16px 20px; }
    .sum-label { font-size: .75rem; color: #888; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .4px; }
    .sum-value { font-size: 1.6rem; font-weight: 700; }
    .sum-value.green { color: #4caf50; } .sum-value.red { color: #f44336; }
    .sum-value.blue  { color: #64b5f6; } .sum-value.orange { color: #ffa726; }
    .sum-value.white { color: #fff; }

    /* ── tabs ── */
    .tab-bar { display: flex; gap: 4px; margin-bottom: 20px; }
    .tab-btn { padding: 8px 22px; border-radius: 8px; border: none; background: #1a1d24; color: #888;
               font-size: .9rem; font-weight: 500; cursor: pointer; transition: background .15s, color .15s; }
    .tab-btn.active { background: #2196f3; color: #fff; }
    .tab-btn:hover:not(.active) { background: #23262f; color: #fff; }

    /* ── toolbar ── */
    .toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 18px; }
    .search-box { flex: 1; min-width: 200px; max-width: 360px; background: #1a1d24; border: 1px solid #2a2d36;
                  border-radius: 8px; padding: 8px 14px; color: #e0e0e0; font-size: .88rem; outline: none; }
    .search-box::placeholder { color: #555; }
    .search-box:focus { border-color: #2196f3; }
    .filter-select { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 8px; padding: 8px 12px;
                     color: #e0e0e0; font-size: .88rem; outline: none; cursor: pointer; }
    .filter-select:focus { border-color: #2196f3; }
    .toolbar-right { display: flex; gap: 10px; align-items: center; margin-left: auto; }

    /* ── scrape control mini ── */
    .scrape-ctrl { display: flex; gap: 10px; align-items: center; background: #1a1d24; border: 1px solid #2a2d36;
                   border-radius: 10px; padding: 10px 18px; margin-bottom: 20px; flex-wrap: wrap; gap: 14px; }
    .sc-label { font-size: .82rem; color: #888; white-space: nowrap; }
    .sc-badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600; text-transform: uppercase; }
    .badge-running  { background: #1a4a1f; color: #4caf50; border: 1px solid #4caf50; }
    .badge-stopped  { background: #4a1a1a; color: #f44336; border: 1px solid #f44336; }
    .badge-finished { background: #1a3a4a; color: #2196f3; border: 1px solid #2196f3; }
    .badge-idle     { background: #2a2d36; color: #888;    border: 1px solid #444; }
    .sc-progress { flex: 1; min-width: 120px; }
    .sc-bar-bg { background: #2a2d36; border-radius: 4px; height: 6px; }
    .sc-bar    { background: #4caf50; height: 6px; border-radius: 4px; transition: width .5s; }
    .sc-text   { font-size: .75rem; color: #888; margin-top: 4px; }
    .sc-btns   { display: flex; gap: 8px; }
    .sc-btn    { padding: 7px 18px; border: none; border-radius: 7px; font-size: .84rem; font-weight: 600;
                 cursor: pointer; transition: opacity .15s; }
    .sc-btn:disabled { opacity: .4; cursor: not-allowed; }
    .sc-btn-start { background: #2e7d32; color: #fff; }
    .sc-btn-start:hover:not(:disabled) { background: #388e3c; }
    .sc-btn-stop  { background: #c62828; color: #fff; }
    .sc-btn-stop:hover:not(:disabled)  { background: #d32f2f; }

    /* ── table ── */
    .tbl-wrap { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; overflow: hidden; }
    table { width: 100%; border-collapse: collapse; font-size: .85rem; }
    thead th { background: #15181f; color: #888; font-weight: 600; padding: 12px 14px; text-align: left;
               font-size: .78rem; text-transform: uppercase; letter-spacing: .4px; white-space: nowrap; }
    tbody tr { border-top: 1px solid #23262f; }
    tbody tr:hover { background: #1e2129; }
    td { padding: 10px 14px; vertical-align: middle; }
    .td-name { font-weight: 500; color: #fff; max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .td-id   { color: #888; font-family: monospace; font-size: .8rem; }
    .td-num  { text-align: right; font-family: monospace; }

    /* ── status badges ── */
    .pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
    .pill-green  { background: #1a3d1a; color: #66bb6a; }
    .pill-red    { background: #3d1a1a; color: #ef5350; }
    .pill-gray   { background: #23262f; color: #888; }
    .pill-orange { background: #3d2a0a; color: #ffa726; }
    .pill-blue   { background: #0a2040; color: #64b5f6; }
    .pill-online { background: #1a3d2a; color: #26a69a; }
    .link-btn { display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: .78rem; font-weight: 600; text-decoration: none; background: #1a3a4a; color: #64b5f6; border: 1px solid #2a5a6a; transition: background .15s; }
    .link-btn:hover { background: #2196f3; color: #fff; border-color: #2196f3; }

    /* ── pagination ── */
    .pager { display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
    .pager-btn { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 6px; padding: 6px 14px;
                 color: #e0e0e0; font-size: .84rem; cursor: pointer; transition: background .15s; }
    .pager-btn:hover:not(:disabled) { background: #2196f3; color: #fff; border-color: #2196f3; }
    .pager-btn.cur { background: #2196f3; color: #fff; border-color: #2196f3; }
    .pager-btn:disabled { opacity: .4; cursor: not-allowed; }
    .pager-info { font-size: .8rem; color: #888; margin-left: auto; }

    .loading { text-align: center; padding: 40px; color: #888; font-size: .9rem; }
    .empty   { text-align: center; padding: 40px; color: #555; font-size: .9rem; }
  </style>
</head>
<body>

<!-- Top Nav -->
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_collect">YP采集</a>
    <a href="/">采集控制台</a>
    <a href="/merchants" class="active">商户管理</a>
    <a href="/products">商品管理</a>
  </nav>
</div>


<div class="page">

  <!-- Summary Cards -->
  <div class="summary-row" id="summaryRow">
    <div class="sum-card"><div class="sum-label">已申请通过</div><div class="sum-value blue" id="smApproved">-</div></div>
    <div class="sum-card"><div class="sum-label">产品已下载</div><div class="sum-value green" id="smDlDone">-</div></div>
    <div class="sum-card"><div class="sum-label">下载失败</div><div class="sum-value red" id="smDlFailed">-</div></div>
    <div class="sum-card"><div class="sum-label">未开始下载</div><div class="sum-value orange" id="smDlPending">-</div></div>
    <div class="sum-card"><div class="sum-label">未申请商户</div><div class="sum-value white" id="smUnapplied">-</div></div>
  </div>

  <!-- Scrape Control Bar -->
  <div class="scrape-ctrl">
    <span class="sc-label">Amazon 采集</span>
    <span class="sc-badge badge-idle" id="scStatus">IDLE</span>
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

  <!-- Tabs -->
  <div class="tab-bar">
    <button class="tab-btn active" id="tabApproved" onclick="switchTab('approved')">✅ 申请通过</button>
    <button class="tab-btn"        id="tabUnapplied" onclick="switchTab('unapplied')">⏳ 未申请</button>
  </div>

  <!-- Toolbar -->
  <div class="toolbar">
    <input type="text" class="search-box" id="searchInput" placeholder="搜索商户名称 / ID..." oninput="onSearch()">
    <select class="filter-select" id="dlFilter" onchange="onFilter()" style="display:none">
      <option value="">全部下载状态</option>
      <option value="downloaded">已下载</option>
      <option value="not_started">未下载</option>
      <option value="failed">下载失败</option>
    </select>
    <div class="toolbar-right">
      <span style="font-size:.8rem;color:#888;" id="totalCount">-</span>
    </div>
  </div>

  <!-- Table -->
  <div class="tbl-wrap">
    <table>
      <thead id="tblHead"></thead>
      <tbody id="tblBody"><tr><td colspan="8" class="loading">加载中...</td></tr></tbody>
    </table>
  </div>

  <!-- Pagination -->
  <div class="pager" id="pager"></div>

</div><!-- /page -->

<script>
// ── state ──
let curTab    = 'approved';
let curPage   = 1;
let curSearch = '';
let curDl     = '';
let curTotal  = 0;
let curPages  = 1;
const PAGE_SIZE = 50;

// ── tab switch ──
function switchTab(tab) {
  curTab = tab; curPage = 1; curSearch = ''; curDl = '';
  document.getElementById('searchInput').value = '';
  document.getElementById('dlFilter').value = '';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1)).classList.add('active');
  document.getElementById('dlFilter').style.display = tab === 'approved' ? '' : 'none';
  loadTable();
}

// ── search / filter ──
let searchTimer;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { curSearch = document.getElementById('searchInput').value.trim(); curPage = 1; loadTable(); }, 300);
}
function onFilter() { curDl = document.getElementById('dlFilter').value; curPage = 1; loadTable(); }

// ── load table ──
function loadTable() {
  const body = document.getElementById('tblBody');
  body.innerHTML = '<tr><td colspan="9" class="loading">加载中...</td></tr>';

  let url = `/api/merchants?tab=${curTab}&page=${curPage}&size=${PAGE_SIZE}`;
  if (curSearch) url += '&q=' + encodeURIComponent(curSearch);
  if (curDl)     url += '&dl=' + encodeURIComponent(curDl);

  fetch(url).then(r => r.json()).then(data => {
    // update summary
    const s = data.summary || {};
    document.getElementById('smApproved').textContent  = (s.approved_total   || 0).toLocaleString();
    document.getElementById('smDlDone').textContent    = (s.download_done    || 0).toLocaleString();
    document.getElementById('smDlFailed').textContent  = (s.download_failed  || 0).toLocaleString();
    document.getElementById('smDlPending').textContent = (s.download_pending || 0).toLocaleString();
    document.getElementById('smUnapplied').textContent = (s.unapplied_total  || 0).toLocaleString();

    curTotal = data.total; curPages = data.pages;
    document.getElementById('totalCount').textContent = `共 ${data.total.toLocaleString()} 条`;

    renderHead();
    renderBody(data.items);
    renderPager();
  }).catch(e => {
    body.innerHTML = `<tr><td colspan="9" class="empty">加载失败: ${e}</td></tr>`;
  });
}

// ── render head ──
function renderHead() {
  const h = document.getElementById('tblHead');
  if (curTab === 'approved') {
    h.innerHTML = `<tr>
      <th>#</th><th>商户名称</th><th>商户ID</th>
      <th>佣金/次</th><th>Cookie天</th>
      <th>网站状态</th><th>国家</th>
      <th>产品下载状态</th><th>商品</th>
    </tr>`;
  } else {
    h.innerHTML = `<tr>
      <th>#</th><th>商户名称</th><th>商户ID</th>
      <th>佣金/次</th><th>Cookie天</th>
      <th>网站状态</th><th>国家</th><th>商品</th>
    </tr>`;
  }
}

// ── render body ──
function dlPill(s) {
  if (s === 'downloaded') return '<span class="pill pill-green">已下载</span>';
  if (s === 'failed')     return '<span class="pill pill-red">下载失败</span>';
  return '<span class="pill pill-gray">未下载</span>';
}
function onlinePill(s) {
  if (!s || s === 'OFFLINE') return '<span class="pill pill-red">离线</span>';
  if (s === 'ONLINE')        return '<span class="pill pill-green">在线</span>';
  return `<span class="pill pill-gray">${s}</span>`;
}
function renderBody(items) {
  const body = document.getElementById('tblBody');
  if (!items || items.length === 0) {
    body.innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>'; return;
  }
  const offset = (curPage - 1) * PAGE_SIZE;
  body.innerHTML = items.map((m, i) => {
    const payout = m.avg_payout && parseFloat(m.avg_payout) > 0
      ? '$' + parseFloat(m.avg_payout).toFixed(2)
      : '<span style="color:#555">-</span>';
    const cookie = m.cookie_days ? m.cookie_days + 'd' : '-';
    const country = m.country || '-';
    const viewBtn = `<a href="/merchant_products?merchant_id=${m.merchant_id}" class="link-btn" style="white-space:nowrap">查看商品 →</a>`;
    const base = `
      <td class="td-id">${offset + i + 1}</td>
      <td class="td-name" title="${m.merchant_name}">${m.merchant_name || '-'}</td>
      <td class="td-id">${m.merchant_id}</td>
      <td class="td-num">${payout}</td>
      <td class="td-num">${cookie}</td>
      <td>${onlinePill(m.online_status)}</td>
      <td>${country}</td>
    `;
    if (curTab === 'approved') {
      return `<tr>${base}<td>${dlPill(m.download_status)}</td><td>${viewBtn}</td></tr>`;
    }
    return `<tr>${base}<td>${viewBtn}</td></tr>`;
  }).join('');
}

// ── pagination ──
function renderPager() {
  const pager = document.getElementById('pager');
  if (curPages <= 1) { pager.innerHTML = ''; return; }
  let html = '';
  html += `<button class="pager-btn" ${curPage<=1?'disabled':''} onclick="goPage(${curPage-1})">‹ 上一页</button>`;
  const start = Math.max(1, curPage - 3), end = Math.min(curPages, curPage + 3);
  if (start > 1) html += `<button class="pager-btn" onclick="goPage(1)">1</button><span style="color:#555">…</span>`;
  for (let p = start; p <= end; p++) {
    html += `<button class="pager-btn ${p===curPage?'cur':''}" onclick="goPage(${p})">${p}</button>`;
  }
  if (end < curPages) html += `<span style="color:#555">…</span><button class="pager-btn" onclick="goPage(${curPages})">${curPages}</button>`;
  html += `<button class="pager-btn" ${curPage>=curPages?'disabled':''} onclick="goPage(${curPage+1})">下一页 ›</button>`;
  html += `<span class="pager-info">第 ${curPage} / ${curPages} 页，共 ${curTotal.toLocaleString()} 条</span>`;
  pager.innerHTML = html;
}
function goPage(p) { curPage = p; loadTable(); window.scrollTo(0,0); }

// ── scrape control ──
function doStart() {
  document.getElementById('scBtnStart').disabled = true;
  fetch('/api/start', {method:'POST'})
    .then(r => r.json())
    .then(d => { console.log(d.msg); })
    .finally(() => { document.getElementById('scBtnStart').disabled = false; });
}
function doStop() {
  document.getElementById('scBtnStop').disabled = true;
  fetch('/api/stop', {method:'POST'})
    .then(r => r.json())
    .then(d => { console.log(d.msg); })
    .finally(() => { document.getElementById('scBtnStop').disabled = false; });
}
function refreshScrapeStatus() {
  fetch('/api/progress').then(r => r.json()).then(d => {
    const status  = d.status  || 'idle';
    const idx     = d.idx     || 0;
    const total   = d.total   || 0;
    const updated = d.updated_at || '';
    const pct     = total > 0 ? Math.round(idx / total * 100) : 0;

    const scStatus = document.getElementById('scStatus');
    const map = {
      'running' : ['badge-running',  'RUNNING'],
      'stopped' : ['badge-stopped',  'STOPPED'],
      'finished': ['badge-finished', 'FINISHED'],
      'idle'    : ['badge-idle',     'IDLE'],
    };
    scStatus.className = 'sc-badge ' + (map[status] ? map[status][0] : 'badge-idle');
    scStatus.textContent = map[status] ? map[status][1] : status.toUpperCase();

    document.getElementById('scBar').style.width  = pct + '%';
    document.getElementById('scText').textContent = `${idx.toLocaleString()} / ${total.toLocaleString()} (${pct}%)`;
    if (updated) document.getElementById('scUpdated').textContent = '更新: ' + updated;
  }).catch(() => {});
}

// ── init ──
document.getElementById('dlFilter').style.display = '';
renderHead();
loadTable();
refreshScrapeStatus();
setInterval(refreshScrapeStatus, 3000);
</script>
</body>
</html>
"""



# ─── DB helper（连接池）────────────────────────────────────────────────────────
import mysql.connector as _mc
import mysql.connector.pooling as _pool
import time as _time
_DB_CFG = dict(host='localhost', port=3306, user='root', password='admin',
               database='affiliate_marketing', charset='utf8mb4')

_db_pool = _pool.MySQLConnectionPool(
    pool_name='scrape_pool',
    pool_size=5,
    **_DB_CFG
)

def _db():
    """从连接池取一个连接（带 dictionary=True cursor 支持）"""
    conn = _db_pool.get_connection()
    return conn

# ─── COUNT 缓存（避免全表 COUNT 扫描，60 秒 TTL）────────────────────────────────
_count_cache = {}   # key -> (value, expire_ts)
_COUNT_TTL = 60     # 秒

def _cached_count(key, sql, params=()):
    """带 TTL 缓存的 COUNT 查询；key 相同则复用结果，TTL 到期后重新查"""
    now = _time.time()
    if key in _count_cache:
        val, exp = _count_cache[key]
        if now < exp:
            return val
    conn = _db()
    cur = conn.cursor()
    cur.execute(sql, params)
    val = cur.fetchone()[0]
    conn.close()
    _count_cache[key] = (val, now + _COUNT_TTL)
    return val


# ─── 商户商品 API ───────────────────────────────────────────────────────────────

@app.route('/api/merchant_products')
def api_merchant_products():
    """
    GET /api/merchant_products?merchant_id=XXX&page=1&size=50&q=关键词
    返回指定商户的所有商品（含 Amazon 采集状态）
    """
    mid   = request.args.get('merchant_id', '').strip()
    q     = request.args.get('q', '').strip()
    page  = max(1, int(request.args.get('page', 1)))
    size  = min(200, max(10, int(request.args.get('size', 50))))
    if not mid:
        return jsonify({'error': 'merchant_id required'}), 400
    try:
        conn = _db()
        cur  = conn.cursor(dictionary=True)
        # 商户基本信息
        cur.execute(
            "SELECT merchant_id, merchant_name, avg_payout, cookie_days, website, country, online_status, status "
            "FROM yp_merchants WHERE merchant_id = %s LIMIT 1", (mid,)
        )
        merchant = cur.fetchone() or {}

        # 构建商品查询
        base_where = "WHERE p.merchant_id = %s"
        params = [mid]
        if q:
            base_where += " AND p.product_name LIKE %s"
            params.append(f'%{q}%')

        offset = (page - 1) * size
        params_p = params + [size, offset]
        # SQL_CALC_FOUND_ROWS 一次性获取 total 和分页数据，省掉单独的 COUNT 查询
        cur.execute(
            f"""SELECT SQL_CALC_FOUND_ROWS
                       p.id, p.asin, p.product_name, p.price, p.commission,
                       p.tracking_url, p.amazon_url, p.scraped_at,
                       d.title as amz_title, d.rating, d.review_count,
                       d.main_image_url, d.brand, d.availability,
                       d.price as amz_price, d.category_path
                FROM yp_products p
                LEFT JOIN amazon_product_details d ON p.asin = d.asin
                {base_where}
                ORDER BY p.id DESC
                LIMIT %s OFFSET %s""",
            params_p
        )
        def _calc_earn(price_str, commission_str):
            try:
                price = float(price_str) if price_str else 0
                rate  = float(str(commission_str).rstrip('%')) / 100 if commission_str else 0
                val   = price * rate
                return f'${val:.2f}' if val > 0 else ''
            except Exception:
                return ''

        items = []
        for r in cur.fetchall():
            price_s = str(r['price']) if r['price'] else ''
            comm_s  = r['commission'] or ''
            items.append({
                'id'          : r['id'],
                'asin'        : r['asin'] or '',
                'product_name': r['product_name'] or '',
                'yp_price'    : price_s,
                'commission'  : comm_s,
                'earn'        : _calc_earn(price_s, comm_s),
                'tracking_url': r['tracking_url'] or '',
                'amazon_url'  : r['amazon_url'] or '',
                'scraped_at'  : str(r['scraped_at']) if r['scraped_at'] else '',
                'has_amazon'  : bool(r['amz_title']),
                'amz_title'   : r['amz_title'] or '',
                'amz_price'   : r['amz_price'] or '',
                'rating'      : r['rating'] or '',
                'review_count': r['review_count'] or '',
                'image_url'   : r['main_image_url'] or '',
                'brand'       : r['brand'] or '',
                'availability': r['availability'] or '',
                'category_path': r['category_path'] or '',
            })
        cur.execute("SELECT FOUND_ROWS()")
        total = cur.fetchone()['FOUND_ROWS()']
        conn.close()
        return jsonify({
            'merchant': {k: str(v) if v is not None else '' for k, v in merchant.items()},
            'total'   : total,
            'page'    : page,
            'size'    : size,
            'pages'   : max(1, (total + size - 1) // size),
            'items'   : items,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── 商品列表 API ───────────────────────────────────────────────────────────────

@app.route('/api/products')
def api_products():
    """
    GET /api/products?category=ALL&merchant_id=&q=&has_amazon=0|1
                      &price_min=&price_max=&page=1&size=50
    支持按 amazon_product_details.category_path 筛选（ALL = 全部）
    q 同时搜 product_name / asin / merchant_name / brand
    price_min / price_max 按 yp_products.price 过滤（USD）
    """
    category   = request.args.get('category', 'ALL').strip()
    mid        = request.args.get('merchant_id', '').strip()
    q          = request.args.get('q', '').strip()
    has_amazon = request.args.get('has_amazon', '')
    price_min  = request.args.get('price_min', '').strip()
    price_max  = request.args.get('price_max', '').strip()
    page       = max(1, int(request.args.get('page', 1)))
    size       = min(200, max(10, int(request.args.get('size', 50))))

    try:
        conn = _db()
        cur  = conn.cursor(dictionary=True)

        # 全量类别（来自 yp_categories）—— 用长缓存（300s TTL）
        _cats_cache_key = 'all_categories'
        if _cats_cache_key in _count_cache and _time.time() < _count_cache[_cats_cache_key][1]:
            categories = _count_cache[_cats_cache_key][0]
        else:
            cur.execute("SELECT category_id, category_name FROM yp_categories ORDER BY category_name")
            categories = [{'id': r['category_id'], 'name': r['category_name']} for r in cur.fetchall()]
            _count_cache[_cats_cache_key] = (categories, _time.time() + 300)


        # 构建 WHERE
        conditions = ["p.tracking_url IS NOT NULL", "p.tracking_url != ''"]
        params = []
        if category != 'ALL':
            conditions.append("d.category_path LIKE %s")
            params.append(f'%{category}%')
        if mid:
            conditions.append("p.merchant_id = %s")
            params.append(mid)
        if q:
            conditions.append("(p.product_name LIKE %s OR p.asin LIKE %s OR p.merchant_name LIKE %s OR d.brand LIKE %s)")
            params += [f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%']
        if has_amazon == '1':
            conditions.append("d.asin IS NOT NULL")
        elif has_amazon == '0':
            conditions.append("d.asin IS NULL")
        # 价格区间（基于 yp_products.price，忽略非数字输入）
        try:
            if price_min:
                conditions.append("CAST(p.price AS DECIMAL(10,2)) >= %s")
                params.append(float(price_min))
        except ValueError:
            pass
        try:
            if price_max:
                conditions.append("CAST(p.price AS DECIMAL(10,2)) <= %s")
                params.append(float(price_max))
        except ValueError:
            pass

        join_type = "LEFT JOIN" if has_amazon != '1' else "INNER JOIN"
        where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

        # ── total 计算策略 ──────────────────────────────────────────────────────
        # 无任何过滤条件时：用缓存，避免每次全表扫描（60s TTL）
        # 有过滤条件时：需精确计数，用 SQL_CALC_FOUND_ROWS 在 SELECT 中顺带获取
        has_filter = bool(category != 'ALL' or mid or q or has_amazon or price_min or price_max)
        use_calc   = has_filter  # 有过滤时在 SELECT 中嵌入 CALC

        offset = (page - 1) * size
        select_prefix = "SQL_CALC_FOUND_ROWS" if use_calc else ""
        cur.execute(
            f"""SELECT {select_prefix}
                       p.id, p.asin, p.merchant_name, p.merchant_id,
                       p.product_name, p.price as yp_price, p.commission,
                       p.tracking_url, p.amazon_url,
                       d.title as amz_title, d.rating, d.review_count,
                       d.main_image_url, d.brand,
                       d.price as amz_price_val, d.availability, d.category_path
                FROM yp_products p
                {join_type} amazon_product_details d ON p.asin = d.asin
                {where_sql}
                ORDER BY p.id DESC
                LIMIT %s OFFSET %s""",
            params + [size, offset]
        )
        def _calc_earn(price_str, commission_str):
            """计算预计佣金：price * commission%，返回格式化字符串或空串"""
            try:
                price = float(price_str) if price_str else 0
                rate  = float(str(commission_str).rstrip('%')) / 100 if commission_str else 0
                val   = price * rate
                return f'${val:.2f}' if val > 0 else ''
            except Exception:
                return ''

        items = []
        for r in cur.fetchall():
            price_s = str(r['yp_price']) if r['yp_price'] else ''
            comm_s  = r['commission'] or ''
            items.append({
                'id'          : r['id'],
                'asin'        : r['asin'] or '',
                'merchant_name': r['merchant_name'] or '',
                'merchant_id' : r['merchant_id'] or '',
                'product_name': r['product_name'] or '',
                'yp_price'    : price_s,
                'commission'  : comm_s,
                'earn'        : _calc_earn(price_s, comm_s),
                'tracking_url': r['tracking_url'] or '',
                'amazon_url'  : r['amazon_url'] or '',
                'has_amazon'  : bool(r['amz_title']),
                'amz_title'   : r['amz_title'] or '',
                'amz_price'   : r['amz_price_val'] or '',
                'rating'      : r['rating'] or '',
                'review_count': r['review_count'] or '',
                'image_url'   : r['main_image_url'] or '',
                'brand'       : r['brand'] or '',
                'availability': r['availability'] or '',
                'category_path': r['category_path'] or '',
            })

        if use_calc:
            cur.execute("SELECT FOUND_ROWS()")
            total = cur.fetchone()['FOUND_ROWS()']
        else:
            # 无过滤条件：用缓存 COUNT，key 固定
            conn.close()
            conn = None
            total = _cached_count(
                'products_all',
                "SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''"
            )

        if conn:
            conn.close()
        return jsonify({
            'total'     : total,
            'page'      : page,
            'size'      : size,
            'pages'     : max(1, (total + size - 1) // size),
            'categories': categories,
            'items'     : items,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── 单商品详情 API ─────────────────────────────────────────────────────────────

@app.route('/api/product_detail')
def api_product_detail():
    """
    GET /api/product_detail?asin=XXXXX
    返回 YP 商品信息 + Amazon 详情（含 bullet_points、reviews、images 等）
    """
    asin = request.args.get('asin', '').strip()
    if not asin:
        return jsonify({'error': 'asin required'}), 400
    try:
        conn = _db()
        cur  = conn.cursor(dictionary=True)

        cur.execute(
            "SELECT * FROM yp_products WHERE asin = %s LIMIT 1", (asin,)
        )
        yp = cur.fetchone()

        cur.execute(
            "SELECT * FROM amazon_product_details WHERE asin = %s LIMIT 1", (asin,)
        )
        amz_raw = cur.fetchone()
        conn.close()

        # 解析 JSON 字段
        def _j(v):
            if not v:
                return []
            try:
                return json.loads(v)
            except Exception:
                return str(v)

        amz = None
        if amz_raw:
            amz = {
                'asin'           : amz_raw['asin'],
                'title'          : amz_raw['title'] or '',
                'brand'          : amz_raw['brand'] or '',
                'price'          : amz_raw['price'] or '',
                'original_price' : amz_raw['original_price'] or '',
                'rating'         : amz_raw['rating'] or '',
                'review_count'   : amz_raw['review_count'] or '',
                'availability'   : amz_raw['availability'] or '',
                'bullet_points'  : _j(amz_raw['bullet_points']),
                'description'    : amz_raw['description'] or '',
                'product_details': _j(amz_raw['product_details']),
                'category_path'  : amz_raw['category_path'] or '',
                'main_image_url' : amz_raw['main_image_url'] or '',
                'image_urls'     : _j(amz_raw['image_urls']),
                'top_reviews'    : _j(amz_raw['top_reviews']),
                'keywords'       : amz_raw['keywords'] or '',
                'amazon_url'     : amz_raw['amazon_url'] or '',
                'scraped_at'     : str(amz_raw['scraped_at']) if amz_raw['scraped_at'] else '',
            }

        yp_out = None
        if yp:
            yp_out = {
                'asin'        : yp['asin'] or '',
                'merchant_name': yp['merchant_name'] or '',
                'merchant_id' : yp['merchant_id'] or '',
                'product_name': yp['product_name'] or '',
                'yp_price'    : str(yp['price']) if yp['price'] else '',
                'commission'  : yp['commission'] or '',
                'tracking_url': yp['tracking_url'] or '',
                'amazon_url'  : yp['amazon_url'] or '',
                'scraped_at'  : str(yp['scraped_at']) if yp['scraped_at'] else '',
            }

        return jsonify({'asin': asin, 'yp': yp_out, 'amazon': amz})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── 商户商品页面 ────────────────────────────────────────────────────────────────

@app.route('/merchant_products')
def page_merchant_products():
    return render_template_string(MERCHANT_PRODUCTS_HTML)


# ─── 商品页面 ────────────────────────────────────────────────────────────────────

@app.route('/products')
def page_products():
    return render_template_string(PRODUCTS_HTML)


# ─── 公共 CSS / JS 片段（内联）──────────────────────────────────────────────────

_BASE_STYLE = """
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
.topbar { background: #15181f; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 20px; height: 56px; position: sticky; top: 0; z-index: 200; }
.topbar-title { font-size: 1.1rem; font-weight: 700; color: #fff; white-space: nowrap; }
.topbar-nav a { color: #888; text-decoration: none; font-size: .88rem; padding: 6px 12px; border-radius: 6px; transition: background .15s; }
.topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }
.page { max-width: 1440px; margin: 0 auto; padding: 28px 20px; }
input, select, button { font-family: inherit; }
.search-box { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 8px; padding: 8px 14px; color: #e0e0e0; font-size: .88rem; outline: none; }
.search-box:focus { border-color: #2196f3; }
.filter-select { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 8px; padding: 8px 12px; color: #e0e0e0; font-size: .88rem; outline: none; cursor: pointer; }
.toolbar { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 18px; }
.tbl-wrap { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; overflow: hidden; }
table { width: 100%; border-collapse: collapse; font-size: .85rem; }
thead th { background: #15181f; color: #888; font-weight: 600; padding: 12px 14px; text-align: left; font-size: .78rem; text-transform: uppercase; letter-spacing: .4px; white-space: nowrap; }
tbody tr { border-top: 1px solid #23262f; }
tbody tr:hover { background: #1e2129; }
td { padding: 10px 14px; vertical-align: middle; }
.td-name { font-weight: 500; color: #fff; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-id   { color: #888; font-family: monospace; font-size: .8rem; }
.td-num  { text-align: right; font-family: monospace; }
.pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: .75rem; font-weight: 600; }
.pill-green  { background: #1a3d1a; color: #66bb6a; }
.pill-red    { background: #3d1a1a; color: #ef5350; }
.pill-gray   { background: #23262f; color: #888; }
.pill-blue   { background: #0a2040; color: #64b5f6; }
.pill-orange { background: #3d2a0a; color: #ffa726; }
.pager { display: flex; align-items: center; gap: 8px; margin-top: 16px; flex-wrap: wrap; }
.pager-btn { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 6px; padding: 6px 14px; color: #e0e0e0; font-size: .84rem; cursor: pointer; transition: background .15s; }
.pager-btn:hover:not(:disabled) { background: #2196f3; color: #fff; border-color: #2196f3; }
.pager-btn.cur { background: #2196f3; color: #fff; border-color: #2196f3; }
.pager-btn:disabled { opacity: .4; cursor: not-allowed; }
.pager-info { font-size: .8rem; color: #888; margin-left: auto; }
.loading { text-align: center; padding: 40px; color: #888; font-size: .9rem; }
.empty   { text-align: center; padding: 40px; color: #555; font-size: .9rem; }
/* modal */
.modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.75); z-index: 1000; align-items: flex-start; justify-content: center; overflow-y: auto; padding: 40px 16px; }
.modal-overlay.open { display: flex; }
.modal { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 14px; width: 100%; max-width: 860px; position: relative; margin: auto; }
.modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 22px 24px 16px; border-bottom: 1px solid #23262f; }
.modal-title { font-size: 1.05rem; font-weight: 700; color: #fff; flex: 1; margin-right: 16px; }
.modal-close { background: none; border: none; color: #888; font-size: 1.4rem; cursor: pointer; padding: 0 4px; line-height: 1; }
.modal-close:hover { color: #fff; }
.modal-body { padding: 20px 24px 28px; }
.detail-section { margin-bottom: 22px; }
.detail-section h3 { font-size: .78rem; text-transform: uppercase; letter-spacing: .6px; color: #2196f3; margin-bottom: 12px; padding-bottom: 6px; border-bottom: 1px solid #23262f; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 20px; }
.detail-row { display: flex; flex-direction: column; gap: 3px; }
.detail-label { font-size: .72rem; color: #888; text-transform: uppercase; letter-spacing: .3px; }
.detail-value { font-size: .88rem; color: #e0e0e0; word-break: break-all; }
.detail-value a { color: #64b5f6; }
.product-images { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.product-images img { width: 80px; height: 80px; object-fit: contain; background: #fff; border-radius: 6px; border: 1px solid #2a2d36; cursor: pointer; }
.product-images img:hover { border-color: #2196f3; }
.bullets li { font-size: .86rem; color: #c0c0c0; margin-left: 18px; margin-bottom: 6px; line-height: 1.5; }
.review-card { background: #15181f; border: 1px solid #23262f; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px; }
.review-author { font-size: .8rem; color: #888; margin-bottom: 4px; }
.review-title  { font-size: .88rem; font-weight: 600; color: #e0e0e0; margin-bottom: 6px; }
.review-body   { font-size: .83rem; color: #b0b0b0; line-height: 1.55; }
.star-rating   { color: #ffa726; font-size: .9rem; }
.pd-table { width: 100%; border-collapse: collapse; font-size: .83rem; }
.pd-table td { padding: 5px 10px; border-bottom: 1px solid #23262f; }
.pd-table td:first-child { color: #888; width: 36%; white-space: nowrap; }
.pd-table td:last-child  { color: #e0e0e0; word-break: break-all; }
.back-btn { display: inline-flex; align-items: center; gap: 6px; color: #888; font-size: .88rem; text-decoration: none; padding: 6px 14px; border-radius: 7px; background: #1a1d24; border: 1px solid #2a2d36; margin-bottom: 20px; }
.back-btn:hover { background: #23262f; color: #fff; }
.page-title { font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 4px; }
.page-sub   { font-size: .85rem; color: #888; margin-bottom: 24px; }
.amz-badge { background: #ff9900; color: #000; font-weight: 700; font-size: .72rem; padding: 2px 8px; border-radius: 10px; }
.link-btn { display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: .78rem; font-weight: 600; text-decoration: none; background: #1a3a4a; color: #64b5f6; border: 1px solid #2a5a6a; transition: background .15s; }
.link-btn:hover { background: #2196f3; color: #fff; border-color: #2196f3; }
</style>
"""

_TOPNAV = """
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_collect">YP采集</a>
    <a href="/">采集控制台</a>
    <a href="/merchants">商户管理</a>
    <a href="/products">商品管理</a>
  </nav>
</div>
"""

YP_COLLECT_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YP数据采集 · YP Affiliate</title>
""" + _BASE_STYLE + """
<style>
.stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px,1fr)); gap: 14px; margin-bottom: 24px; }
.stat-card { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 18px 20px; }
.stat-card .label { font-size: .78rem; color: #888; margin-bottom: 6px; text-transform: uppercase; letter-spacing: .4px; }
.stat-card .value { font-size: 1.8rem; font-weight: 700; color: #fff; }
.stat-card .value.green  { color: #69f0ae; }
.stat-card .value.red    { color: #f44336; }
.stat-card .value.orange { color: #ffb74d; }
.stat-card .value.blue   { color: #64b5f6; }
.progress-wrap { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 20px 22px; margin-bottom: 24px; }
.progress-label { display: flex; justify-content: space-between; font-size: .83rem; color: #888; margin-bottom: 8px; }
.progress-bg { background: #2a2d36; border-radius: 8px; height: 12px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 8px; background: linear-gradient(90deg, #4caf50, #81c784); transition: width .5s; }
.btn-row { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 24px; }
.btn { padding: 12px 28px; border: none; border-radius: 9px; font-size: .95rem; font-weight: 600; cursor: pointer; transition: opacity .15s; }
.btn:disabled { opacity: .4; cursor: not-allowed; }
.btn-start { background: #2e7d32; color: #fff; }
.btn-start:hover:not(:disabled) { background: #388e3c; }
.btn-stop  { background: #c62828; color: #fff; }
.btn-stop:hover:not(:disabled)  { background: #d32f2f; }
.log-card { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 18px 20px; }
.log-title { font-size: .82rem; color: #888; text-transform: uppercase; letter-spacing: .4px; margin-bottom: 10px; }
.log-box { background: #0f1117; border-radius: 8px; padding: 14px; font-family: monospace; font-size: .8rem; color: #ccc; line-height: 1.6; min-height: 80px; max-height: 240px; overflow-y: auto; white-space: pre-wrap; word-break: break-all; }
.badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600; text-transform: uppercase; }
.badge-running  { background: #1a4a1f; color: #4caf50; border: 1px solid #4caf50; }
.badge-idle     { background: #2a2d36; color: #888; border: 1px solid #444; }
.note-card { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; padding: 16px 20px; margin-bottom: 24px; font-size: .84rem; color: #aaa; line-height: 1.7; }
.note-card b { color: #e0e0e0; }
.note-card code { background: #23262f; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: .82rem; color: #64b5f6; }
</style>
</head>
<body>
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_collect" class="active">YP采集</a>
    <a href="/">采集控制台</a>
    <a href="/merchants">商户管理</a>
    <a href="/products">商品管理</a>
  </nav>
</div>

<div class="page" style="max-width:900px;">
  <h2 style="font-size:1.5rem;color:#fff;margin-bottom:6px;">YP 数据采集</h2>
  <p style="color:#888;font-size:.88rem;margin-bottom:22px;">
    从 YeahPromos 平台下载各商户的商品数据（ASIN / 价格 / 佣金率 / 投放链接），写入 MySQL 供商品管理页使用。
  </p>

  <!-- 状态卡片 -->
  <div class="stat-grid" id="statGrid">
    <div class="stat-card"><div class="label">采集进程</div><div class="value" id="stRunning">-</div></div>
    <div class="stat-card"><div class="label">商户总数</div><div class="value blue" id="stTotal">-</div></div>
    <div class="stat-card"><div class="label">已完成</div><div class="value green" id="stDone">-</div></div>
    <div class="stat-card"><div class="label">失败</div><div class="value red" id="stFailed">-</div></div>
    <div class="stat-card"><div class="label">待处理</div><div class="value orange" id="stPending">-</div></div>
  </div>

  <!-- 进度条 -->
  <div class="progress-wrap">
    <div class="progress-label">
      <span>采集进度</span>
      <span id="progressText">-</span>
    </div>
    <div class="progress-bg"><div class="progress-fill" id="progressFill" style="width:0%"></div></div>
    <div style="font-size:.78rem;color:#555;margin-top:8px;">最后更新：<span id="lastUpdated">-</span></div>
  </div>

  <!-- 说明提示 -->
  <div class="note-card">
    <b>使用前提：</b>调试 Chrome 必须已启动（<code>chrome.exe --remote-debugging-port=9222</code>），且已在 YP 平台登录。<br>
    <b>数据说明：</b>采集内容写入 <code>D:\\workspace\\YP_products.xlsx</code>（Excel），需通过 sync_excel_to_mysql.py 同步到数据库后，商品管理页才会更新。<br>
    <b>断点续传：</b>中途停止后重新启动，会自动跳过已完成的商户继续采集。
  </div>

  <!-- 操作按钮 -->
  <div class="btn-row">
    <button class="btn btn-start" id="btnStart" onclick="startCollect()">▶ 启动 YP 采集</button>
    <button class="btn btn-stop"  id="btnStop"  onclick="stopCollect()" disabled>■ 停止采集</button>
  </div>

  <!-- 实时日志 -->
  <div class="log-card">
    <div class="log-title">实时日志（最近 20 行）</div>
    <div class="log-box" id="logBox">等待采集启动...</div>
  </div>
</div>

<script>
let pollTimer = null;
let isRunning = false;

function updateBtns(running) {
  isRunning = running;
  document.getElementById('btnStart').disabled = running;
  document.getElementById('btnStop').disabled  = !running;
}

function fetchStatus() {
  fetch('/api/yp_collect_status').then(r => r.json()).then(data => {
    if (data.error) return;
    const running = data.running;
    updateBtns(running);
    document.getElementById('stRunning').innerHTML =
      running ? '<span class="badge badge-running">运行中</span>'
              : '<span class="badge badge-idle">空闲</span>';
    document.getElementById('stTotal').textContent   = data.total_merchants ?? '-';
    document.getElementById('stDone').textContent    = data.completed ?? 0;
    document.getElementById('stFailed').textContent  = data.failed ?? 0;
    document.getElementById('stPending').textContent = data.pending ?? 0;
    document.getElementById('lastUpdated').textContent = data.last_updated || '-';
    const total  = data.total_merchants || 0;
    const done   = (data.completed || 0) + (data.failed || 0);
    const pct    = total > 0 ? Math.min(100, Math.round(done / total * 100)) : 0;
    document.getElementById('progressFill').style.width = pct + '%';
    document.getElementById('progressText').textContent =
      total > 0 ? (done + ' / ' + total + '  (' + pct + '%)') : '-';
    const lines = data.log_lines || [];
    if (lines.length) {
      document.getElementById('logBox').textContent = lines.join('\\n');
    }
  }).catch(() => {});
}

function startCollect() {
  document.getElementById('btnStart').disabled = true;
  fetch('/api/yp_collect_start', {method:'POST'}).then(r => r.json()).then(d => {
    if (d.ok) {
      updateBtns(true);
      document.getElementById('logBox').textContent = '[' + new Date().toLocaleTimeString() + '] ' + d.msg;
    } else {
      alert(d.msg);
      document.getElementById('btnStart').disabled = false;
    }
  });
}

function stopCollect() {
  document.getElementById('btnStop').disabled = true;
  fetch('/api/yp_collect_stop', {method:'POST'}).then(r => r.json()).then(d => {
    alert(d.msg);
    document.getElementById('btnStop').disabled = false;
  });
}

// 每 5 秒轮询
fetchStatus();
setInterval(fetchStatus, 5000);
</script>
</body>
</html>
"""

_PAGER_JS = """
function renderPager(pager_id, curPage, curPages, curTotal, pageSize, onGoPage) {
  const pager = document.getElementById(pager_id);
  if (curPages <= 1) { pager.innerHTML = ''; return; }
  let html = '';
  html += '<button class="pager-btn" '+(curPage<=1?'disabled':'')+' onclick="'+onGoPage+'('+(curPage-1)+')">&#8249; 上一页</button>';
  const start = Math.max(1, curPage-3), end = Math.min(curPages, curPage+3);
  if (start>1) html += '<button class="pager-btn" onclick="'+onGoPage+'(1)">1</button><span style="color:#555">…</span>';
  for (let p=start;p<=end;p++) html += '<button class="pager-btn '+(p===curPage?'cur':'')+'" onclick="'+onGoPage+'('+p+')">'+p+'</button>';
  if (end<curPages) html += '<span style="color:#555">…</span><button class="pager-btn" onclick="'+onGoPage+'('+curPages+')">'+curPages+'</button>';
  html += '<button class="pager-btn" '+(curPage>=curPages?'disabled':'')+' onclick="'+onGoPage+'('+(curPage+1)+')">下一页 &#8250;</button>';
  html += '<span class="pager-info">第 '+curPage+' / '+curPages+' 页，共 '+curTotal.toLocaleString()+' 条</span>';
  pager.innerHTML = html;
}
"""

_PRODUCT_DETAIL_JS = """
function renderModal(data) {
  var yp  = data.yp    || {};
  var amz = data.amazon || null;
  document.getElementById('modalTitle').textContent = (amz&&amz.title) ? amz.title : (yp.product_name || data.asin);

  var html = '';

  // ── 商品图片 ──
  var imgs = [];
  if (amz && amz.main_image_url) imgs.push(amz.main_image_url);
  if (amz && Array.isArray(amz.image_urls)) {
    amz.image_urls.forEach(function(u){ if(u && u!==amz.main_image_url) imgs.push(u); });
  }
  if (imgs.length) {
    html += '<div class="detail-section">';
    html += '<div class="product-images">';
    imgs.slice(0,8).forEach(function(u){
      html += '<img src="'+u+'" data-src="'+u+'" class="detail-img-clickable" title="click to enlarge">';
    });
    html += '</div></div>';
  }

  // ── YP 平台信息 ──
  html += '<div class="detail-section">';
  html += '<h3>YP 平台信息</h3>';
  html += '<div class="detail-grid">';
  html += '<div class="detail-row"><span class="detail-label">ASIN</span><span class="detail-value">'+data.asin+'</span></div>';
  html += '<div class="detail-row"><span class="detail-label">商户</span><span class="detail-value">'+(yp.merchant_name||'-')+'</span></div>';
  html += '<div class="detail-row"><span class="detail-label">YP 价格</span><span class="detail-value">'+(yp.yp_price?'$'+parseFloat(yp.yp_price).toFixed(2):'-')+'</span></div>';
  html += '<div class="detail-row"><span class="detail-label">佣金率</span><span class="detail-value">'+(yp.commission||'-')+'</span></div>';
  if (yp.tracking_url) {
    html += '<div class="detail-row" style="grid-column:1/-1"><span class="detail-label">推广链接</span><span class="detail-value"><a href="'+yp.tracking_url+'" target="_blank" class="link-btn">打开推广链接</a></span></div>';
  }
  html += '</div></div>';

  // ── Amazon 详情 ──
  if (amz) {
    html += '<div class="detail-section">';
    html += '<h3><span class="amz-badge">amazon</span> 商品详情</h3>';
    html += '<div class="detail-grid">';
    html += '<div class="detail-row"><span class="detail-label">品牌</span><span class="detail-value">'+(amz.brand||'-')+'</span></div>';
    html += '<div class="detail-row"><span class="detail-label">Amazon 价格</span><span class="detail-value">'+(amz.price||'-')+'</span></div>';
    html += '<div class="detail-row"><span class="detail-label">评分</span><span class="detail-value">'+starsHtml(amz.rating)+'</span></div>';
    html += '<div class="detail-row"><span class="detail-label">评论数</span><span class="detail-value">'+(amz.review_count||'-')+'</span></div>';
    html += '<div class="detail-row"><span class="detail-label">库存状态</span><span class="detail-value">'+(amz.availability||'-')+'</span></div>';
    html += '<div class="detail-row"><span class="detail-label">类别路径</span><span class="detail-value" style="font-size:.78rem">'+(amz.category_path||'-')+'</span></div>';
    if (amz.amazon_url) {
      html += '<div class="detail-row" style="grid-column:1/-1"><span class="detail-label">Amazon链接</span><span class="detail-value"><a href="'+amz.amazon_url+'" target="_blank" class="link-btn">在Amazon查看</a></span></div>';
    }
    html += '</div>';

    // Bullet points
    if (amz.bullet_points && amz.bullet_points.length) {
      var bullets = Array.isArray(amz.bullet_points) ? amz.bullet_points : [amz.bullet_points];
      if (bullets.length) {
        html += '<div style="margin-top:14px"><div class="detail-label" style="margin-bottom:8px">商品亮点</div>';
        html += '<ul class="bullets">';
        bullets.forEach(function(b){ if(b) html += '<li>'+b+'</li>'; });
        html += '</ul></div>';
      }
    }

    // Product Details table
    if (amz.product_details) {
      var pd = amz.product_details;
      var rows = [];
      if (Array.isArray(pd)) {
        rows = pd;
      } else if (typeof pd === 'object') {
        Object.keys(pd).forEach(function(k){ rows.push({key:k, value:pd[k]}); });
      }
      if (rows.length) {
        html += '<div style="margin-top:14px"><div class="detail-label" style="margin-bottom:8px">规格参数</div>';
        html += '<table class="pd-table">';
        rows.slice(0,20).forEach(function(r){
          var k=r.key||r[0]||'', v=r.value||r[1]||'';
          html += '<tr><td>'+k+'</td><td>'+v+'</td></tr>';
        });
        html += '</table></div>';
      }
    }

    // Description
    if (amz.description && amz.description.length > 20) {
      html += '<div style="margin-top:14px"><div class="detail-label" style="margin-bottom:8px">商品描述</div>';
      html += '<div style="font-size:.84rem;color:#b0b0b0;line-height:1.6;max-height:120px;overflow:hidden;position:relative" id="descBox">';
      html += amz.description.slice(0,600)+(amz.description.length>600?'…':'');
      html += '</div></div>';
    }

    html += '</div>'; // detail-section

    // Top Reviews
    if (amz.top_reviews && amz.top_reviews.length) {
      html += '<div class="detail-section">';
      html += '<h3>用户评价（TOP ' + Math.min(amz.top_reviews.length, 3) + '）</h3>';
      amz.top_reviews.slice(0,3).forEach(function(rv){
        var title   = rv.title   || rv.review_title || '';
        var body    = rv.body    || rv.review_body  || rv.text || '';
        var author  = rv.author  || rv.reviewer_name || '';
        var rating  = rv.rating  || rv.stars || '';
        var date    = rv.date    || rv.review_date  || '';
        html += '<div class="review-card">';
        html += '<div class="review-author">'+starsHtml(rating)+' &nbsp;'+author+(date?' · '+date:'')+'</div>';
        if(title) html += '<div class="review-title">'+title+'</div>';
        if(body)  html += '<div class="review-body">'+body.slice(0,400)+(body.length>400?'…':'')+'</div>';
        html += '</div>';
      });
      html += '</div>';
    }

  } else {
    html += '<div class="detail-section" style="color:#888;padding:20px 0">暂无 Amazon 详情数据（该商品尚未采集）</div>';
  }

  document.getElementById('modalBody').innerHTML = html;
}
"""


# ═══════════════════════════════════════════════════════════════════
#  商户商品页面 HTML
# ═══════════════════════════════════════════════════════════════════
MERCHANT_PRODUCTS_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>商户商品 · YP Affiliate</title>
""" + _BASE_STYLE + """
</head>
<body>
""" + _TOPNAV + """
<div class="page">

  <a class="back-btn" href="/merchants">← 返回商户管理</a>
  <div id="pageTitle" class="page-title">商户商品</div>
  <div id="pageSub"   class="page-sub">加载中...</div>

  <div class="toolbar">
    <input type="text" class="search-box" id="searchInput" placeholder="搜索商品名称 / ASIN..." oninput="onSearch()" style="min-width:240px;">
    <span style="font-size:.8rem;color:#888;" id="totalCount">-</span>
  </div>

  <div class="tbl-wrap">
    <table>
      <thead><tr>
        <th>#</th><th>图片</th><th>ASIN</th><th>商品名称</th>
        <th>YP价格</th><th>佣金率</th><th>预计佣金</th><th>评分</th><th>评论数</th>
        <th>Amazon详情</th><th>操作</th>
      </tr></thead>
      <tbody id="tblBody"><tr><td colspan="11" class="loading">加载中...</td></tr></tbody>
    </table>
  </div>
  <div class="pager" id="pager"></div>

</div><!-- /page -->

<!-- 详情弹窗 -->
<div class="modal-overlay" id="detailModal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" id="modalTitle">商品详情</div>
      <button class="modal-close" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body" id="modalBody">加载中...</div>
  </div>
</div>

<script>
""" + _PAGER_JS + """
const mid = new URLSearchParams(location.search).get('merchant_id') || '';
let curPage=1, curSearch='', curTotal=0, curPages=1;
const PAGE_SIZE=50;

function loadMerchantInfo(data) {
  const m = data.merchant || {};
  document.getElementById('pageTitle').textContent = m.merchant_name || '商户商品';
  document.getElementById('pageSub').textContent =
    `商户ID: ${m.merchant_id || mid}  ·  佣金: $${parseFloat(m.avg_payout||0).toFixed(2)}/次  ·  Cookie: ${m.cookie_days||'-'}天  ·  共 ${data.total.toLocaleString()} 件商品`;
}

function starsHtml(r) {
  const n = parseFloat(r) || 0;
  const full = Math.floor(n), half = n-full>=.5?1:0;
  let s='';
  for(let i=0;i<full;i++) s+='★';
  if(half) s+='½';
  return `<span class="star-rating">${s}</span> <span style="color:#888;font-size:.8rem">${n||''}</span>`;
}

function renderBody(items) {
  const body = document.getElementById('tblBody');
  const offset = (curPage-1)*PAGE_SIZE;
  if (!items||!items.length) { body.innerHTML='<tr><td colspan="11" class="empty">暂无商品</td></tr>'; return; }
  body.innerHTML = items.map((p,i) => {
    const img = p.image_url
      ? `<img src="${p.image_url}" style="width:48px;height:48px;object-fit:contain;background:#fff;border-radius:4px;" onerror="this.style.display='none'">`
      : '<span style="color:#555;font-size:.75rem">无图</span>';
    const amzBadge = p.has_amazon
      ? '<span class="pill pill-green">已采集</span>'
      : '<span class="pill pill-gray">未采集</span>';
    const nameShort = (p.product_name||'').length>60 ? p.product_name.slice(0,60)+'…' : (p.product_name||'-');
    const earnHtml = p.earn
      ? `<span style="color:#69f0ae;font-weight:600">${p.earn}</span>`
      : '<span style="color:#555">-</span>';
    return `<tr>
      <td class="td-id">${offset+i+1}</td>
      <td>${img}</td>
      <td class="td-id"><a href="https://www.amazon.com/dp/${p.asin}" target="_blank" style="color:#64b5f6">${p.asin}</a></td>
      <td class="td-name" title="${p.product_name}">${nameShort}</td>
      <td class="td-num">${p.yp_price?'$'+parseFloat(p.yp_price).toFixed(2):'-'}</td>
      <td class="td-num">${p.commission||'-'}</td>
      <td class="td-num">${earnHtml}</td>
      <td>${starsHtml(p.rating)}</td>
      <td class="td-num">${p.review_count||'-'}</td>
      <td>${amzBadge}</td>
      <td><button class="link-btn" onclick="openDetail('${p.asin}')">查看详情</button></td>
    </tr>`;
  }).join('');
}

function loadTable() {
  const body = document.getElementById('tblBody');
  body.innerHTML = '<tr><td colspan="11" class="loading">加载中...</td></tr>';
  let url = `/api/merchant_products?merchant_id=${encodeURIComponent(mid)}&page=${curPage}&size=${PAGE_SIZE}`;
  if (curSearch) url += '&q='+encodeURIComponent(curSearch);
  fetch(url).then(r=>r.json()).then(data => {
    if (data.error) { body.innerHTML=`<tr><td colspan="11" class="empty">错误: ${data.error}</td></tr>`; return; }
    loadMerchantInfo(data);
    curTotal=data.total; curPages=data.pages;
    document.getElementById('totalCount').textContent = `共 ${data.total.toLocaleString()} 件商品`;
    renderBody(data.items);
    renderPager('pager', curPage, curPages, curTotal, PAGE_SIZE, 'goPage');
  }).catch(e => { body.innerHTML=`<tr><td colspan="10" class="empty">加载失败: ${e}</td></tr>`; });
}

let searchTimer;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { curSearch=document.getElementById('searchInput').value.trim(); curPage=1; loadTable(); }, 300);
}
function goPage(p) { curPage=p; loadTable(); window.scrollTo(0,0); }

// ─── 详情弹窗 ───
function openDetail(asin) {
  document.getElementById('modalTitle').textContent = asin;
  document.getElementById('modalBody').innerHTML = '<div class="loading">加载中...</div>';
  document.getElementById('detailModal').classList.add('open');
  fetch('/api/product_detail?asin='+encodeURIComponent(asin))
    .then(r=>r.json()).then(renderModal).catch(e => {
      document.getElementById('modalBody').innerHTML = '<div class="empty">加载失败: '+e+'</div>';
    });
}
function closeModal() {
  document.getElementById('detailModal').classList.remove('open');
}
document.getElementById('detailModal').addEventListener('click', function(e) {
  if (e.target===this) closeModal();
});

""" + _PRODUCT_DETAIL_JS + """

loadTable();
</script>
</body>
</html>
"""

# ═══════════════════════════════════════════════════════════════════
#  商品管理页面 HTML
# ═══════════════════════════════════════════════════════════════════
PRODUCTS_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>商品管理 · YP Affiliate</title>
""" + _BASE_STYLE + """
<style>
.cat-sidebar { width: 220px; flex-shrink: 0; }
.cat-list { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px; overflow: hidden; max-height: calc(100vh - 160px); overflow-y: auto; position: sticky; top: 72px; }
.cat-item { padding: 9px 16px; font-size: .86rem; cursor: pointer; border-bottom: 1px solid #23262f; transition: background .12s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-item:hover { background: #23262f; color: #fff; }
.cat-item.active { background: #2196f3; color: #fff; }
.cat-count { float: right; font-size: .75rem; color: #888; }
.cat-item.active .cat-count { color: rgba(255,255,255,.7); }
.main-area { flex: 1; min-width: 0; }
.layout { display: flex; gap: 20px; align-items: flex-start; }
</style>
</head>
<body>
""" + _TOPNAV + """
<div class="page">

  <div class="layout">
    <!-- Category Sidebar -->
    <div class="cat-sidebar">
      <div class="cat-list" id="catList">
        <div class="cat-item active" data-cat="ALL" onclick="selectCat('ALL',this)">全部类别</div>
      </div>
    </div>

    <!-- Main Content -->
    <div class="main-area">
      <div class="toolbar">
        <!-- 第一行：关键字 + Amazon状态 + 统计 -->
        <input type="text" class="search-box" id="searchInput"
               placeholder="搜索商品名称 / ASIN / 品牌 / 商户..."
               oninput="onSearch()" style="min-width:260px;flex:1;">
        <select class="filter-select" id="amzFilter" onchange="onFilter()">
          <option value="">全部商品</option>
          <option value="1">已采集 Amazon 详情</option>
          <option value="0">未采集 Amazon 详情</option>
        </select>
        <!-- 价格区间 -->
        <div style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
          <span style="font-size:.82rem;color:#888;white-space:nowrap;">价格 $</span>
          <input type="number" class="search-box" id="priceMin"
                 placeholder="最低" min="0" step="0.01"
                 oninput="onPriceFilter()"
                 style="width:80px;min-width:0;padding:8px 10px;">
          <span style="color:#555;font-size:.9rem;">–</span>
          <input type="number" class="search-box" id="priceMax"
                 placeholder="最高" min="0" step="0.01"
                 oninput="onPriceFilter()"
                 style="width:80px;min-width:0;padding:8px 10px;">
        </div>
        <button class="btn-sm" onclick="clearFilters()"
                style="background:#23262f;color:#aaa;border:1px solid #2a2d36;border-radius:7px;padding:7px 14px;font-size:.82rem;cursor:pointer;white-space:nowrap;">
          清除筛选
        </button>
        <span style="font-size:.8rem;color:#888;white-space:nowrap;" id="totalCount">-</span>
      </div>

      <div class="tbl-wrap">
        <table>
          <thead><tr>
            <th>#</th><th>图片</th><th>ASIN</th><th>商品名称</th>
            <th>商户</th><th>YP价格</th><th>佣金率</th><th>预计佣金</th>
            <th>评分</th><th>Amazon详情</th><th>操作</th>
          </tr></thead>
          <tbody id="tblBody"><tr><td colspan="11" class="loading">加载中...</td></tr></tbody>
        </table>
      </div>
      <div class="pager" id="pager"></div>
    </div>
  </div>

</div>

<!-- 详情弹窗 -->
<div class="modal-overlay" id="detailModal">
  <div class="modal">
    <div class="modal-header">
      <div class="modal-title" id="modalTitle">商品详情</div>
      <button class="modal-close" onclick="closeModal()">×</button>
    </div>
    <div class="modal-body" id="modalBody">加载中...</div>
  </div>
</div>

<script>
""" + _PAGER_JS + """
let curCat='ALL', curPage=1, curSearch='', curAmz='', curTotal=0, curPages=1;
let curPriceMin='', curPriceMax='';
const PAGE_SIZE=50;

function selectCat(cat, el) {
  curCat=cat; curPage=1;
  document.querySelectorAll('.cat-item').forEach(e=>e.classList.remove('active'));
  el.classList.add('active');
  loadTable();
}
function onFilter() { curAmz=document.getElementById('amzFilter').value; curPage=1; loadTable(); }
let searchTimer;
function onSearch() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { curSearch=document.getElementById('searchInput').value.trim(); curPage=1; loadTable(); }, 300);
}
let priceTimer;
function onPriceFilter() {
  clearTimeout(priceTimer);
  priceTimer = setTimeout(() => {
    curPriceMin = document.getElementById('priceMin').value.trim();
    curPriceMax = document.getElementById('priceMax').value.trim();
    curPage=1; loadTable();
  }, 400);
}
function clearFilters() {
  document.getElementById('searchInput').value='';
  document.getElementById('amzFilter').value='';
  document.getElementById('priceMin').value='';
  document.getElementById('priceMax').value='';
  curSearch=''; curAmz=''; curPriceMin=''; curPriceMax='';
  curPage=1; loadTable();
}
function goPage(p) { curPage=p; loadTable(); window.scrollTo(0,0); }

function loadCategories(cats) {
  const list = document.getElementById('catList');
  let html = '<div class="cat-item active" data-cat="ALL" onclick="selectCatByEl(this)">全部类别</div>';
  (cats||[]).forEach(c => {
    const safe = c.name.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    html += '<div class="cat-item" data-cat="'+safe+'" onclick="selectCatByEl(this)">'+safe+'</div>';
  });
  list.innerHTML = html;
}
function selectCatByEl(el) {
  const cat = el.getAttribute('data-cat');
  curCat = cat; curPage = 1;
  document.querySelectorAll('.cat-item').forEach(e => e.classList.remove('active'));
  el.classList.add('active');
  loadTable();
}

function starsHtml(r) {
  const n = parseFloat(r)||0;
  const full=Math.floor(n), half=n-full>=.5?1:0;
  let s='';
  for(let i=0;i<full;i++) s+='★';
  if(half) s+='½';
  return `<span class="star-rating">${s}</span><span style="color:#888;font-size:.8rem"> ${n||''}</span>`;
}

function renderBody(items) {
  const body=document.getElementById('tblBody');
  const offset=(curPage-1)*PAGE_SIZE;
  if(!items||!items.length){body.innerHTML='<tr><td colspan="11" class="empty">暂无商品</td></tr>';return;}
  body.innerHTML=items.map((p,i)=>{
    const img = p.image_url
      ? `<img src="${p.image_url}" style="width:48px;height:48px;object-fit:contain;background:#fff;border-radius:4px;" onerror="this.style.display='none'">`
      : '<span style="color:#555;font-size:.75rem">无图</span>';
    const amzBadge = p.has_amazon ? '<span class="pill pill-green">已采集</span>' : '<span class="pill pill-gray">未采集</span>';
    const nameShort=(p.product_name||'').length>55?p.product_name.slice(0,55)+'…':(p.product_name||'-');
    const mname=(p.merchant_name||'').length>18?p.merchant_name.slice(0,18)+'…':(p.merchant_name||'-');
    const earnHtml = p.earn
      ? `<span style="color:#69f0ae;font-weight:600">${p.earn}</span>`
      : '<span style="color:#555">-</span>';
    return `<tr>
      <td class="td-id">${offset+i+1}</td>
      <td>${img}</td>
      <td class="td-id"><a href="https://www.amazon.com/dp/${p.asin}" target="_blank" style="color:#64b5f6">${p.asin}</a></td>
      <td class="td-name" title="${p.product_name}">${nameShort}</td>
      <td style="font-size:.8rem;color:#aaa" title="${p.merchant_name}">${mname}</td>
      <td class="td-num">${p.yp_price?'$'+parseFloat(p.yp_price).toFixed(2):'-'}</td>
      <td class="td-num">${p.commission||'-'}</td>
      <td class="td-num">${earnHtml}</td>
      <td>${starsHtml(p.rating)}</td>
      <td>${amzBadge}</td>
      <td><button class="link-btn" onclick="openDetail('${p.asin}')">查看详情</button></td>
    </tr>`;
  }).join('');
}

let catsLoaded=false;
function loadTable() {
  const body=document.getElementById('tblBody');
  body.innerHTML='<tr><td colspan="11" class="loading">加载中...</td></tr>';
  let url=`/api/products?category=${encodeURIComponent(curCat)}&page=${curPage}&size=${PAGE_SIZE}`;
  if(curSearch) url+='&q='+encodeURIComponent(curSearch);
  if(curAmz) url+='&has_amazon='+curAmz;
  if(curPriceMin) url+='&price_min='+encodeURIComponent(curPriceMin);
  if(curPriceMax) url+='&price_max='+encodeURIComponent(curPriceMax);
  fetch(url).then(r=>r.json()).then(data=>{
    if(data.error){body.innerHTML=`<tr><td colspan="11" class="empty">错误: ${data.error}</td></tr>`;return;}
    if(!catsLoaded && data.categories && data.categories.length){ loadCategories(data.categories); catsLoaded=true; }
    curTotal=data.total; curPages=data.pages;
    document.getElementById('totalCount').textContent=`共 ${data.total.toLocaleString()} 件`;
    renderBody(data.items);
    renderPager('pager',curPage,curPages,curTotal,PAGE_SIZE,'goPage');
  }).catch(e=>{body.innerHTML=`<tr><td colspan="10" class="empty">加载失败: ${e}</td></tr>`;});
}

// ─── 详情弹窗 ───
function openDetail(asin) {
  document.getElementById('modalTitle').textContent = asin;
  document.getElementById('modalBody').innerHTML='<div class="loading">加载中...</div>';
  document.getElementById('detailModal').classList.add('open');
  fetch('/api/product_detail?asin='+encodeURIComponent(asin))
    .then(r=>r.json()).then(renderModal).catch(e=>{
      document.getElementById('modalBody').innerHTML='<div class="empty">加载失败: '+e+'</div>';
    });
}
function closeModal() { document.getElementById('detailModal').classList.remove('open'); }
document.getElementById('detailModal').addEventListener('click',function(e){if(e.target===this)closeModal();});

""" + _PRODUCT_DETAIL_JS + """

loadTable();
</script>
</body>
</html>
"""




# ─── YP 采集页面路由 ─────────────────────────────────────────────────────────────

YP_COLLECT_SCRIPT = BASE_DIR / 'download_only.py'
YP_STOP_FILE      = BASE_DIR / '.yp_collect_stop'

@app.route('/yp_collect')
def page_yp_collect():
    return render_template_string(YP_COLLECT_HTML)

@app.route('/api/yp_collect_status')
def api_yp_collect_status():
    """读取 YP 下载状态（download_state.json + us_merchants_clean.json）"""
    try:
        state_file   = OUTPUT_DIR / 'download_state.json'
        approved_f   = OUTPUT_DIR / 'us_merchants_clean.json'
        log_file     = OUTPUT_DIR / 'download_log.txt'

        completed_mids, failed_mids = [], []
        last_updated = ''
        if state_file.exists():
            s = json.loads(state_file.read_text(encoding='utf-8-sig'))
            completed_mids = s.get('completed_mids', [])
            failed_mids    = s.get('failed_mids', [])
            last_updated   = s.get('last_updated', '')

        total_merchants = 0
        if approved_f.exists():
            try:
                d = json.loads(approved_f.read_text(encoding='utf-8-sig'))
                total_merchants = len(d.get('approved_list', []))
            except Exception:
                pass

        # 最后 20 行日志
        log_lines = []
        if log_file.exists():
            try:
                lines = log_file.read_text(encoding='utf-8', errors='replace').splitlines()
                log_lines = lines[-20:]
            except Exception:
                pass

        # 检查是否有 download_only 进程在运行
        running = False
        try:
            import wmi as _wmi
            for p in _wmi.WMI().Win32_Process():
                if 'download_only' in (p.CommandLine or ''):
                    running = True
                    break
        except Exception:
            pass

        return jsonify({
            'running'          : running,
            'total_merchants'  : total_merchants,
            'completed'        : len(completed_mids),
            'failed'           : len(failed_mids),
            'pending'          : max(0, total_merchants - len(completed_mids) - len(failed_mids)),
            'last_updated'     : last_updated,
            'log_lines'        : log_lines,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/yp_collect_start', methods=['POST'])
def api_yp_collect_start():
    """在新 CMD 窗口启动 download_only.py"""
    if YP_STOP_FILE.exists():
        try: YP_STOP_FILE.unlink()
        except Exception: pass

    # 防止重复启动
    try:
        import wmi as _wmi
        running = [p for p in _wmi.WMI().Win32_Process()
                   if 'download_only' in (p.CommandLine or '')]
        if running:
            return jsonify({'ok': False,
                            'msg': f'YP 采集进程已在运行（PID: {", ".join(str(p.ProcessId) for p in running)}），请勿重复启动'})
    except Exception:
        pass

    bat_file = BASE_DIR / '_launch_yp_collect.bat'
    bat_content = (
        f'@echo off\r\n'
        f'cd /d "{BASE_DIR}"\r\n'
        f'title YP Collect\r\n'
        f'"{PYTHON_EXE}" -X utf8 "{YP_COLLECT_SCRIPT}"\r\n'
        f'echo.\r\n'
        f'echo YP 采集已结束，按任意键关闭窗口\r\n'
        f'pause > nul\r\n'
    )
    try:
        bat_file.write_text(bat_content, encoding='gbk')
        subprocess.Popen(
            ['cmd.exe', '/c', 'start', 'YP Collect', 'cmd.exe', '/k', str(bat_file)],
            cwd=str(BASE_DIR),
            shell=False
        )
        return jsonify({'ok': True, 'msg': 'YP 采集任务已在新窗口启动，进度每 5 秒自动刷新'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'启动失败: {e}'})


@app.route('/api/yp_collect_stop', methods=['POST'])
def api_yp_collect_stop():
    """向 download_only.py 写停止信号文件"""
    try:
        YP_STOP_FILE.write_text('stop', encoding='utf-8')
        return jsonify({'ok': True, 'msg': '停止信号已发送，采集脚本处理完当前商户后会安全退出'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'发送停止信号失败: {e}'})


# ─── 入口 ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import threading as _threading
    def _warmup():
        """启动后异步预热缓存，避免首次访问慢"""
        try:
            _cached_count(
                'products_all',
                "SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''"
            )
            print("[warmup] products_all count cached OK")
        except Exception as e:
            print(f"[warmup] products_all failed: {e}")
        try:
            conn = _db()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT category_id, category_name FROM yp_categories ORDER BY category_name")
            cats = [{'id': r['category_id'], 'name': r['category_name']} for r in cur.fetchall()]
            conn.close()
            _count_cache['all_categories'] = (cats, _time.time() + 300)
            print(f"[warmup] {len(cats)} categories cached OK")
        except Exception as e:
            print(f"[warmup] categories failed: {e}")
    # 同步预热：确保第 1 个请求到来前缓存已就绪（约 3-5 秒）
    _warmup()

    print("=" * 55)
    print("  Amazon 采集控制台已启动")
    print("  请用浏览器访问: http://localhost:5050")
    print("=" * 55)
    # threaded=True 是关键：允许同时处理多个 HTTP 请求，不会因一个请求阻塞整个服务
    app.run(host='127.0.0.1', port=5050, debug=False, threaded=True)
