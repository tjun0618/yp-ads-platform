"""
YP Affiliate 管理台 - 共享模板组件
BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK, _SCRAPE_TOPNAV

使用方式：
  from templates_shared import BASE_CSS, NAV_HTML, _BASE_STYLE_DARK, _PAGER_JS_DARK, _SCRAPE_TOPNAV
"""

# ═══════════════════════════════════════════════════════════════════════════
# 全局通用深色主题 CSS（用于 str.format 渲染的页面）
# ═══════════════════════════════════════════════════════════════════════════
BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
.topbar { background: #1a1a2e; border-bottom: 1px solid #23262f; padding: 0 28px;
          display: flex; align-items: center; gap: 20px; height: 56px;
          position: sticky; top: 0; z-index: 200; }
.topbar-title { font-size: 1.05rem; font-weight: 700; color: #fff; white-space: nowrap; }
.topbar-nav { display: flex; align-items: center; gap: 4px; }
.topbar-nav a { color: #adb5bd; text-decoration: none; font-size: .87rem;
                padding: 6px 12px; border-radius: 6px; transition: background .15s; }
.topbar-nav a:hover, .topbar-nav a.active { background: #23262f; color: #fff; }
.container { max-width: 1440px; margin: 0 auto; padding: 28px 20px; }
.card { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
        padding: 20px 24px; margin-bottom: 20px; }
.card h2 { font-size: 15px; font-weight: 600; color: #fff; margin-bottom: 16px; }
input, select, button { font-family: inherit; }
.btn { display: inline-flex; align-items: center; gap: 6px;
       padding: 7px 15px; border-radius: 8px; border: none;
       font-size: 13px; font-weight: 600; cursor: pointer; transition: all .15s; }
.btn-primary   { background: #1565c0; color: #fff; }
.btn-primary:hover   { background: #1976d2; }
.btn-success   { background: #2e7d32; color: #fff; }
.btn-success:hover   { background: #388e3c; }
.btn-warning   { background: #e65100; color: #fff; }
.btn-warning:hover   { background: #ef6c00; }
.btn-danger    { background: #c62828; color: #fff; }
.btn-danger:hover    { background: #d32f2f; }
.btn-secondary { background: #23262f; color: #adb5bd; border: 1px solid #2a2d36; }
.btn-secondary:hover { background: #2a2d36; color: #e0e0e0; }
.btn-sm { padding: 4px 10px; font-size: 12px; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 99px;
         font-size: 11px; font-weight: 600; }
.badge-green  { background: #1a3d1a; color: #66bb6a; }
.badge-blue   { background: #0a2040; color: #64b5f6; }
.badge-orange { background: #3d2a0a; color: #ffa726; }
.badge-red    { background: #3d1a1a; color: #ef5350; }
.badge-gray   { background: #23262f; color: #888; }
.badge-purple { background: #2a1a4a; color: #ce93d8; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #15181f; padding: 10px 14px; text-align: left;
     border-bottom: 1px solid #2a2d36; color: #888;
     font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .4px; white-space: nowrap; }
td { padding: 10px 14px; border-bottom: 1px solid #23262f; vertical-align: middle; }
tr:hover td { background: #1e2129; }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px;
       font-size: 11px; background: #23262f; color: #adb5bd; margin: 1px; }
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 16px; }
.filters input, .filters select {
    padding: 7px 12px; border: 1px solid #2a2d36; border-radius: 8px;
    background: #1a1d24; color: #e0e0e0; font-size: 13px; outline: none; }
.filters input:focus, .filters select:focus { border-color: #2196f3; }
.pagination { display: flex; gap: 6px; align-items: center; justify-content: center; margin-top: 20px; }
.pagination a { padding: 5px 12px; border-radius: 6px; border: 1px solid #2a2d36;
                text-decoration: none; color: #adb5bd; font-size: 13px;
                background: #1a1d24; transition: all .15s; }
.pagination a:hover, .pagination a.active { background: #2196f3; color: #fff; border-color: #2196f3; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
             gap: 14px; margin-bottom: 24px; }
.stat-card { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 12px;
             padding: 16px; text-align: center; }
.stat-num { font-size: 28px; font-weight: 700; color: #64b5f6; }
.stat-label { font-size: 12px; color: #888; margin-top: 4px; }
.spinner { display: inline-block; width: 13px; height: 13px;
           border: 2px solid rgba(255,255,255,.25); border-top-color: #fff;
           border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }
.toast { padding: 11px 18px; border-radius: 8px; color: #fff; font-size: 13px;
         margin-bottom: 10px; box-shadow: 0 4px 16px rgba(0,0,0,.4);
         animation: slideIn .3s ease; }
.toast-success { background: #2e7d32; }
.toast-error   { background: #c62828; }
.toast-info    { background: #1565c0; }
@keyframes slideIn { from { transform: translateX(110%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
code { background: #23262f; padding: 2px 7px; border-radius: 4px;
       font-family: monospace; font-size: .88em; color: #90caf9; }
/* 商品列表双栏布局 */
.list-layout { display: flex; gap: 18px; align-items: flex-start; }
.cat-sidebar { width: 200px; flex-shrink: 0; }
.cat-list { background: #1a1d24; border: 1px solid #2a2d36; border-radius: 10px;
            overflow: hidden; max-height: calc(100vh - 140px); overflow-y: auto;
            position: sticky; top: 72px; }
.cat-item { padding: 8px 14px; font-size: .83rem; cursor: pointer;
            border-bottom: 1px solid #1e2129; transition: background .12s;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #adb5bd; }
.cat-item:hover { background: #23262f; color: #fff; }
.cat-item.active { background: #1565c0; color: #fff; }
.list-main { flex: 1; min-width: 0; }
"""

# ═══════════════════════════════════════════════════════════════════════════
# 导航栏（带 active 高亮的版本，用于 str.format 渲染的页面）
# 使用: NAV_HTML.format(p0="active", p1="", ..., p9="")
# ═══════════════════════════════════════════════════════════════════════════
NAV_HTML = """
<div class="topbar">
  <span class="topbar-title">YP Affiliate 管理台</span>
  <nav class="topbar-nav">
    <a href="/yp_sync" class="{p9}">🌐 全量同步</a><a href="/yp_collect" class="{p4}">⬇ YP采集</a>
    <a href="/amazon_scrape" class="{p3}">🔄 Amazon采集</a>
    <a href="/merchants" class="{p5}">🏬 商户管理</a>
    <a href="/" class="{p0}">📦 商品列表</a>
    <a href="/plans" class="{p1}">📋 广告方案</a>
    <a href="/workflow" class="{p11}" style="color:#e879f9">🎯 广告流程</a>
    <a href="/qs_dashboard" class="{p7}">⭐ 质量评分</a>
    <a href="/competitor_ads" class="{p8}">🔍 竞品参考</a>
    <a href="/optimize" class="{p6}" style="color:#ffa726">📈 投放优化</a>
    <a href="/agent_chat" class="{p10}" style="color:#4c6ef5">🤖 Agent对话</a>
  </nav>
</div>
<div class="toast-container" id="toast-container"></div>
<script>
function toast(msg, type) {{
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() {{ t.remove(); }}, 3500);
}}
</script>
"""

# ═══════════════════════════════════════════════════════════════════════════
# 采集模块导航栏（无高亮状态，内联样式）
# 用于 Response() 直接返回和 Jinja2 render_template_string 的页面
# ═══════════════════════════════════════════════════════════════════════════
_SCRAPE_TOPNAV = """
<div class="topbar" style="background:#1a1a2e;border-bottom:1px solid #23262f;padding:0 28px;display:flex;align-items:center;gap:20px;height:56px;position:sticky;top:0;z-index:200;">
  <span style="font-size:1.1rem;font-weight:700;color:#fff;white-space:nowrap;">YP Affiliate 管理台</span>
  <nav style="display:flex;gap:4px;">
    <a href="/yp_sync" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">🌐 全量同步</a>
    <a href="/yp_collect" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">⬇ YP采集</a>
    <a href="/amazon_scrape" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">🔄 Amazon采集</a>
    <a href="/merchants" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">🏬 商户管理</a>
    <a href="/" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">📦 商品列表</a>
    <a href="/plans" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">📋 广告方案</a>
    <a href="/workflow" style="color:#e879f9;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">🎯 广告流程</a>
    <a href="/qs_dashboard" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">⭐ 质量评分</a>
    <a href="/competitor_ads" style="color:#adb5bd;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">🔍 竞品参考</a>
    <a href="/optimize" style="color:#ffa726;text-decoration:none;font-size:.87rem;padding:6px 12px;border-radius:6px;">📈 投放优化</a>
  </nav>
</div>
"""

# ═══════════════════════════════════════════════════════════════════════════
# 采集模块基础深色样式（内联 <style> 标签）
# ═══════════════════════════════════════════════════════════════════════════
_BASE_STYLE_DARK = """
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f1117; color: #e0e0e0; min-height: 100vh; }
.topbar { background: #1a1a2e; border-bottom: 1px solid #23262f; padding: 0 28px; display: flex; align-items: center; gap: 12px; height: 56px; position: sticky; top: 0; z-index: 200; }
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
.td-id { color: #888; font-family: monospace; font-size: .8rem; }
.td-num { text-align: right; font-family: monospace; }
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
.badge { display: inline-block; padding: 3px 12px; border-radius: 20px; font-size: .78rem; font-weight: 600; text-transform: uppercase; }
.badge-running  { background: #1a4a1f; color: #4caf50; border: 1px solid #4caf50; }
.badge-stopped  { background: #4a1a1a; color: #f44336; border: 1px solid #f44336; }
.badge-finished { background: #1a3a4a; color: #2196f3; border: 1px solid #2196f3; }
.badge-idle     { background: #2a2d36; color: #888;    border: 1px solid #444; }
.link-btn { display: inline-block; padding: 4px 12px; border-radius: 6px; font-size: .78rem; font-weight: 600; text-decoration: none; background: #1a3a4a; color: #64b5f6; border: 1px solid #2a5a6a; transition: background .15s; cursor: pointer; }
.link-btn:hover { background: #2196f3; color: #fff; border-color: #2196f3; }
.btn-primary { background: #1565c0; color: #fff; padding: 4px 12px; border: none; border-radius: 6px; font-size: .78rem; font-weight: 600; cursor: pointer; transition: background .15s; }
.btn-primary:hover { background: #1976d2; }
.btn-primary:disabled { opacity: .6; cursor: not-allowed; }
.btn-warning { background: #e65100; color: #fff; padding: 4px 12px; border: none; border-radius: 6px; font-size: .78rem; font-weight: 600; cursor: pointer; }
.btn-warning:hover { background: #ef6c00; }
.toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }
.toast { padding: 11px 18px; border-radius: 8px; color: #fff; font-size: 13px;
         margin-bottom: 10px; box-shadow: 0 4px 16px rgba(0,0,0,.4);
         animation: slideIn .3s ease; }
.toast-success { background: #2e7d32; }
.toast-error   { background: #c62828; }
.toast-info    { background: #1565c0; }
@keyframes slideIn { from { transform: translateX(110%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════
# 分页器 JS 函数
# ═══════════════════════════════════════════════════════════════════════════
_PAGER_JS_DARK = """
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
