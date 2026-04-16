
function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}
</script>

<div class="container">
  <h1 style="font-size: 20px; margin-bottom: 20px;">🔍 竞品文案参考库</h1>
  
  <!-- 统计栏 -->
  <div class="stats-bar-comp" id="stats-bar">
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-total-ads">-</div>
      <div class="stat-comp-label">总文案数</div>
    </div>
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-merchants">-</div>
      <div class="stat-comp-label">商户数</div>
    </div>
    <div class="stat-comp">
      <div class="stat-comp-value" id="stat-latest" style="font-size:14px;color:#888;">-</div>
      <div class="stat-comp-label">最新采集时间</div>
    </div>
  </div>
  
  <div class="competitor-layout">
    <!-- 左侧筛选 -->
    <div class="sidebar">
      <h3>🏢 商户筛选</h3>
      <div style="margin-bottom:12px;">
        <button class="btn btn-secondary btn-sm" onclick="selectAllMerchants(true)">全选</button>
        <button class="btn btn-secondary btn-sm" onclick="selectAllMerchants(false)">清空</button>
      </div>
      <div class="merchant-list" id="merchant-list">
        <div style="color:#666;padding:20px;text-align:center;">加载中...</div>
      </div>
    </div>
    
    <!-- 右侧内容 -->
    <div>
      <!-- 搜索栏 -->
      <div class="search-bar">
        <input type="text" class="search-input" id="search-input" placeholder="搜索文案内容..." onkeyup="handleSearch()">
        <button class="btn btn-primary" onclick="loadCompetitorAds()">🔍 搜索</button>
        <button class="btn btn-secondary" onclick="clearSearch()">清空</button>
      </div>
      
      <!-- 文案网格 -->
      <div class="ads-grid" id="ads-grid">
        <div class="empty-state-comp">
          <div class="empty-state-comp-icon">📋</div>
          <div>请选择商户或输入关键词搜索</div>
        </div>
      </div>
    </div>
  </div>
</div>

<script>
let allMerchants = [];
let selectedMerchants = new Set();
let allAds = [];

function toast(msg, type) {
  type = type || 'info';
  var c = document.getElementById('toast-container');
  var t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(function() { t.remove(); }, 3500);
}

function compHtmlEsc(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

async function loadMerchants() {
  try {
    const res = await fetch('/api/competitor/merchants');
    const data = await res.json();
    
    if (!data.ok) {
      console.error('loadMerchants API error:', data.msg);
      document.getElementById('merchant-list').innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">加载失败: ' + compHtmlEsc(data.msg || '未知错误') + '</div>';
      toast(data.msg || '加载商户失败', 'error');
      return;
    }
    
    allMerchants = data.merchants || [];
    renderMerchantList();
    updateStats(data.stats || {});
  } catch (e) {
    console.error('loadMerchants 异常:', e);
    document.getElementById('merchant-list').innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">加载异常: ' + compHtmlEsc(e.message) + '</div>';
    toast(e.message, 'error');
  }
}

function renderMerchantList() {
  const container = document.getElementById('merchant-list');
  if (allMerchants.length === 0) {
    container.innerHTML = '<div style="color:#666;padding:20px;text-align:center;">暂无商户数据</div>';
    return;
  }
  
  try {
    // m.id 统一转字符串，避免数字/字符串 Set 判断失效
    container.innerHTML = allMerchants.map(m => {
      const sid = String(m.id);
      const isActive = selectedMerchants.has(sid);
      const safeName = compHtmlEsc(m.name);
      const safeId = compHtmlEsc(sid);
      return `<div class="merchant-item ${isActive ? 'active' : ''}" data-id="${safeId}" onclick="toggleMerchant(this.dataset.id)">
        <input type="checkbox" class="merchant-checkbox" ${isActive ? 'checked' : ''} onclick="event.stopPropagation()">
        <span class="merchant-name">${safeName}</span>
        <span class="merchant-count">${m.ad_count || 0}</span>
      </div>`;
    }).join('');
  } catch(renderErr) {
    console.error('renderMerchantList 渲染失败:', renderErr);
    container.innerHTML = '<div style="color:#ef5350;padding:20px;text-align:center;">渲染失败: ' + compHtmlEsc(renderErr.message) + '</div>';
  }
}

function toggleMerchant(id) {
  // id 统一转字符串
  const sid = String(id);
  if (selectedMerchants.has(sid)) {
    selectedMerchants.delete(sid);
  } else {
    selectedMerchants.add(sid);
  }
  renderMerchantList();
  loadCompetitorAds();
}

function selectAllMerchants(select) {
  if (select) {
    allMerchants.forEach(m => selectedMerchants.add(String(m.id)));
  } else {
    selectedMerchants.clear();
  }
  renderMerchantList();
  loadCompetitorAds();
}

function updateStats(stats) {
  document.getElementById('stat-total-ads').textContent = stats.total_ads || 0;
  document.getElementById('stat-merchants').textContent = stats.merchant_count || 0;
  document.getElementById('stat-latest').textContent = stats.latest_scraped || '-';
}

async function loadCompetitorAds() {
  const keyword = document.getElementById('search-input').value.trim();
  const merchantIds = Array.from(selectedMerchants);
  
  try {
    const params = new URLSearchParams();
    if (keyword) params.append('keyword', keyword);
    if (merchantIds.length > 0) params.append('merchants', merchantIds.join(','));
    
    const res = await fetch('/api/competitor/ads?' + params.toString());
    const data = await res.json();
    
    if (!data.ok) {
      toast(data.msg || '加载失败', 'error');
      return;
    }
    
    allAds = data.ads || [];
    renderAdsGrid();
  } catch (e) {
    toast(e.message, 'error');
  }
}

function renderAdsGrid() {
  const container = document.getElementById('ads-grid');
  if (allAds.length === 0) {
    container.innerHTML = '<div class="empty-state-comp" style="grid-column:1/-1;"><div class="empty-state-comp-icon">🔍</div><div>未找到匹配的文案</div></div>';
    return;
  }
  
  try {
    container.innerHTML = allAds.map(ad => {
      // headlines/descriptions 是 JSON 字符串，需要解析
      let headlines = [];
      let descriptions = [];
      try { headlines = typeof ad.headlines === 'string' ? JSON.parse(ad.headlines) : (ad.headlines || []); } catch(e) {}
      try { descriptions = typeof ad.descriptions === 'string' ? JSON.parse(ad.descriptions) : (ad.descriptions || []); } catch(e) {}
      
      const headlineText = (headlines[0] && headlines[0].text) ? headlines[0].text : (ad.headline || ad.title || '无标题');
      const descText = (descriptions[0] && descriptions[0].text) ? descriptions[0].text : (ad.description || '无描述');
      
      const safeMerchant = compHtmlEsc(ad.merchant_name || '未知商户');
      const safeHeadline = compHtmlEsc(headlineText);
      const safeDesc = compHtmlEsc(descText);
      // 所有标题/描述拼接用于复制，存入 data-* 属性
      const allHeadlines = headlines.map(h => h.text || '').filter(Boolean).join(' | ');
      const allDescs = descriptions.map(d => d.text || '').filter(Boolean).join(' | ');
      const safeCopyH = compHtmlEsc(allHeadlines || headlineText);
      const safeCopyD = compHtmlEsc(allDescs || descText);
      
      return `<div class="ad-card">
        <div class="ad-card-header">
          <span class="ad-card-source">🏢 ${safeMerchant}</span>
          <span class="ad-card-date">${compHtmlEsc(ad.scraped_at || '')}</span>
        </div>
        <div class="ad-card-headline">${safeHeadline}</div>
        <div class="ad-card-desc">${safeDesc}</div>
        <div class="ad-card-footer">
          <span class="ad-card-tag">QS: ${ad.quality_score ? Math.round(ad.quality_score) : '-'}</span>
          <span class="ad-card-tag">${compHtmlEsc(ad.asin || '')}</span>
          <button class="copy-btn" data-headline="${safeCopyH}" data-desc="${safeCopyD}" onclick="copyAd(this)">📋 复制</button>
        </div>
      </div>`;
    }).join('');
  } catch(renderErr) {
    console.error('renderAdsGrid 渲染失败:', renderErr);
    container.innerHTML = '<div class="empty-state-comp" style="grid-column:1/-1;color:#ef5350;">渲染失败: ' + compHtmlEsc(renderErr.message) + '</div>';
  }
}

function escapeHtml(text) {
  return compHtmlEsc(text);
}

async function copyAd(btn) {
  // 通过 data-* 属性安全获取内容（避免引号嵌套）
  const headline = btn.dataset.headline || '';
  const desc = btn.dataset.desc || '';
  // data-* 属性里的内容是 HTML 实体，需要解码回原始字符串
  const tmp = document.createElement('textarea');
  tmp.innerHTML = headline;
  const rawH = tmp.value;
  tmp.innerHTML = desc;
  const rawD = tmp.value;
  const text = rawH + '
' + rawD;
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = '✅ 已复制';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = '📋 复制';
      btn.classList.remove('copied');
    }, 2000);
  } catch (e) {
    toast('复制失败', 'error');
  }
}

function handleSearch() {
  clearTimeout(window.searchTimeout);
  window.searchTimeout = setTimeout(loadCompetitorAds, 300);
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  loadCompetitorAds();
}

window.onload = function() {
  loadMerchants();
  loadCompetitorAds();
};
