
function selectCat(el) {
  document.querySelectorAll('.cat-item').forEach(function(e) { e.classList.remove('active'); });
  el.classList.add('active');
  document.getElementById('hiddenCat').value = el.getAttribute('data-cat') || '';
  document.getElementById('mainForm').submit();
}
var priceTimer;
function delaySubmit() {
  clearTimeout(priceTimer);
  priceTimer = setTimeout(function() { document.getElementById('mainForm').submit(); }, 600);
}
async function generateAd(btn) {
  var asin = btn.getAttribute('data-asin');
  openStrategistPanel(asin, false);
}

async function resetPlan(btn) {
  var asin = btn.getAttribute('data-asin');
  openStrategistPanel(asin, true);
}

// ─── AI 广告策略师面板 ─────────────────────────────────────────────────────

function openStrategistPanel(asin, force) {
  // 检查 key 状态
  fetch('/api/get_deepseek_key_status')
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (!d.configured) {
        showKeyDialog(function(key) {
          if (key) startStrategistStream(asin, force);
        });
      } else {
        startStrategistStream(asin, force);
      }
    })
    .catch(function() { startStrategistStream(asin, force); });
}

function showKeyDialog(callback) {
  // 简单 prompt 输入 key
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

function startStrategistStream(asin, force) {
  // 创建/显示 overlay 面板
  var overlay = document.getElementById('strategist-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'strategist-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.82);z-index:9999;display:flex;align-items:center;justify-content:center;';
    overlay.innerHTML = '<div id="strategist-panel" style="background:#0d1117;border:1px solid #30363d;border-radius:12px;width:min(860px,96vw);max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 8px 48px rgba(0,0,0,0.7);">'
      + '<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid #21262d;background:#161b22;">'
      + '<div style="display:flex;align-items:center;gap:10px;">'
      + '<span style="font-size:22px;">🤖</span>'
      + '<div><div style="font-size:15px;font-weight:600;color:#e6edf3;">AI 广告策略师</div>'
      + '<div style="font-size:12px;color:#8b949e;" id="strat-asin-label"></div></div></div>'
      + '<button onclick="closeStrategistPanel()" style="background:none;border:none;color:#8b949e;font-size:20px;cursor:pointer;padding:4px 8px;border-radius:4px;">✕</button></div>'
      + '<div id="strat-log" style="flex:1;overflow-y:auto;padding:16px 20px;font-family:Consolas,monospace;font-size:13px;line-height:1.7;color:#c9d1d9;min-height:320px;max-height:52vh;"></div>'
      + '<div id="strat-result" style="display:none;padding:16px 20px;border-top:1px solid #21262d;background:#0d1117;max-height:200px;overflow-y:auto;"></div>'
      + '<div style="padding:12px 20px;border-top:1px solid #21262d;background:#161b22;display:flex;justify-content:flex-end;gap:10px;">'
      + '<button id="strat-view-btn" style="display:none;" onclick="window.open(strat_current_asin_url,'_blank')" class="btn btn-success btn-sm">📋 查看广告方案</button>'
      + '<button onclick="closeStrategistPanel()" class="btn btn-secondary btn-sm">关闭</button>'
      + '</div></div>';
    document.body.appendChild(overlay);
  }
  
  var logEl = document.getElementById('strat-log');
  var resultEl = document.getElementById('strat-result');
  var viewBtn = document.getElementById('strat-view-btn');
  var asinLabel = document.getElementById('strat-asin-label');
  
  // 重置
  logEl.innerHTML = '';
  resultEl.style.display = 'none';
  resultEl.innerHTML = '';
  viewBtn.style.display = 'none';
  asinLabel.textContent = 'ASIN: ' + asin;
  window.strat_current_asin_url = '/plans/' + asin;
  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';
  
  function appendLog(html) {
    logEl.insertAdjacentHTML('beforeend', html);
    logEl.scrollTop = logEl.scrollHeight;
  }
  
  appendLog('<div style="color:#58a6ff;margin-bottom:8px;">🚀 启动 AI 广告策略师分析...</div>');
  
  var url = '/api/generate_ai/' + asin + (force ? '?force=1' : '');
  var evtSource = new EventSource(url);
  window.strat_evtsource = evtSource;
  
  evtSource.onmessage = function(e) {
    try {
      var msg = JSON.parse(e.data);
      if (msg.type === 'start') {
        appendLog('<div style="color:#79c0ff;">' + htmlEscSimple(msg.text) + '</div>');
      } else if (msg.type === 'progress') {
        appendLog('<div style="color:#3fb950;margin:4px 0;">' + htmlEscSimple(msg.text) + '</div>');
      } else if (msg.type === 'thinking') {
        // 流式思考文本 — 不换行，追加到最后一个 thinking span
        var last = logEl.querySelector('.thinking-line:last-child');
        if (!last) {
          var span = document.createElement('span');
          span.className = 'thinking-line';
          span.style.cssText = 'display:block;color:#e6edf3;white-space:pre-wrap;word-break:break-all;margin:2px 0;';
          logEl.appendChild(span);
          last = span;
        }
        last.textContent += msg.text;
        logEl.scrollTop = logEl.scrollHeight;
      } else if (msg.type === 'done') {
        var r = msg.result || {};
        appendLog('<div style="color:#3fb950;font-weight:bold;margin-top:12px;">✅ 广告方案生成完成！</div>');
        // 展示策略摘要
        var sa = r.strategy_analysis || {};
        var bs = r.budget_summary || {};
        var summaryHtml = '<div style="background:#161b22;border-radius:8px;padding:12px;margin-top:8px;">'
          + '<div style="color:#58a6ff;font-weight:bold;margin-bottom:8px;">📊 策略分析摘要</div>';
        if (sa.product_strengths) summaryHtml += '<div style="margin-bottom:6px;"><span style="color:#8b949e;">产品优势: </span><span style="color:#c9d1d9;">' + htmlEscSimple(sa.product_strengths) + '</span></div>';
        if (sa.target_audience) summaryHtml += '<div style="margin-bottom:6px;"><span style="color:#8b949e;">目标受众: </span><span style="color:#c9d1d9;">' + htmlEscSimple(sa.target_audience) + '</span></div>';
        if (sa.affiliate_opportunity) summaryHtml += '<div style="margin-bottom:6px;"><span style="color:#8b949e;">联盟机会: </span><span style="color:#c9d1d9;">' + htmlEscSimple(sa.affiliate_opportunity) + '</span></div>';
        if ((sa.key_messaging_angles||[]).length) summaryHtml += '<div style="margin-bottom:6px;"><span style="color:#8b949e;">核心卖点: </span><span style="color:#c9d1d9;">' + (sa.key_messaging_angles||[]).map(htmlEscSimple).join(' · ') + '</span></div>';
        summaryHtml += '<div style="margin-top:8px;padding-top:8px;border-top:1px solid #21262d;display:flex;gap:20px;">'
          + '<span style="color:#8b949e;">广告系列: <span style="color:#f0883e;">' + (r.campaigns||0) + '</span></span>'
          + '<span style="color:#8b949e;">广告组: <span style="color:#f0883e;">' + (r.ad_groups||0) + '</span></span>'
          + '<span style="color:#8b949e;">广告: <span style="color:#f0883e;">' + (r.ads||0) + '</span></span>';
        if (bs.total_daily_budget_usd) summaryHtml += '<span style="color:#8b949e;">日预算: <span style="color:#3fb950;">$' + (+bs.total_daily_budget_usd).toFixed(2) + '</span></span>';
        summaryHtml += '</div></div>';
        resultEl.innerHTML = summaryHtml;
        resultEl.style.display = 'block';
        viewBtn.style.display = 'inline-flex';
        evtSource.close();
      } else if (msg.type === 'error') {
        appendLog('<div style="color:#f85149;margin-top:8px;">❌ 错误: ' + htmlEscSimple(msg.message) + '</div>');
        evtSource.close();
      }
    } catch(parseErr) {
      // 忽略解析失败的 chunk
    }
  };
  
  evtSource.onerror = function() {
    appendLog('<div style="color:#f85149;">⚠ SSE 连接断开</div>');
    evtSource.close();
  };
}

function closeStrategistPanel() {
  var overlay = document.getElementById('strategist-overlay');
  if (overlay) overlay.style.display = 'none';
  document.body.style.overflow = '';
  if (window.strat_evtsource) { window.strat_evtsource.close(); window.strat_evtsource = null; }
}

function htmlEscSimple(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}


async function fetchAmazon(btn) {
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 采集中...';
  toast('正在采集 Amazon 数据：' + asin + '（需要调试Chrome已启动）', 'info');
  try {
    var res = await fetch('/api/fetch_amazon/' + asin, {method:'POST'});
    var data = await res.json();
    if (data.success) {
      toast('Amazon 数据采集完成！', 'success');
      setTimeout(function() { location.reload(); }, 1500);
    } else {
      var msg = data.message || '未知错误';
      if (msg.indexOf('9222') !== -1 || msg.indexOf('connect') !== -1 || msg.indexOf('Connection') !== -1) {
        toast('❌ 采集失败：请先启动调试Chrome（端口9222）再重试', 'error');
      } else {
        toast('采集失败：' + msg.substring(0, 120), 'error');
      }
      btn.disabled = false;
      btn.innerHTML = '采集Amazon';
    }
  } catch(e) {
    toast('请求失败：' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '采集Amazon';
  }
}

async function fetchSuggest(btn) {
  var mid = btn.getAttribute('data-mid');
  var asin = btn.getAttribute('data-asin');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> 采集中...';
  toast('正在采集 Google Suggest 关键词，请稍候（约15-30秒）...', 'info');
  try {
    var res = await fetch('/api/fetch_suggest/' + mid, {method:'POST'});
    var data = await res.json();
    if (data.success) {
      var cnt = data.keyword_count || 0;
      // 更新该商户的所有关键词 badge（同商户多条商品都更新）
      var containers = document.querySelectorAll('#kw-' + mid);
      containers.forEach(function(el) {
        el.innerHTML = '<span class="badge badge-green" title="已有' + cnt + '个品牌关键词">🔑 ' + cnt + '个词</span>';
      });
      toast('🔑 关键词采集完成，共 ' + cnt + ' 个！', 'success');
    } else {
      var msg = data.message || '未知错误';
      if (msg.indexOf('9222') !== -1 || msg.indexOf('Chrome') !== -1) {
        toast('❌ 采集失败：请先启动调试Chrome（端口9222）再重试', 'error');
      } else {
        toast('采集失败：' + msg.substring(0, 150), 'error');
      }
      btn.disabled = false;
      btn.innerHTML = '🔑 采集关键词';
    }
  } catch(e) {
    toast('请求失败：' + e.message, 'error');
    btn.disabled = false;
    btn.innerHTML = '🔑 采集关键词';
  }
}
