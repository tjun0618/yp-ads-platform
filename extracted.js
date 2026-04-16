

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

const mid = new URLSearchParams(location.search).get('merchant_id') || '';
let curPage=1, curSearch='', curTotal=0, curPages=1;
const PAGE_SIZE=50;
function starsHtml(r){const n=parseFloat(r)||0;const full=Math.floor(n),half=n-full>=.5?1:0;let s='';for(let i=0;i<full;i++)s+='★';if(half)s+='½';return '<span style="color:#ffa726">'+s+'</span> <span style="color:#888;font-size:.8rem">'+( n||'')+'</span>';}
function loadMerchantInfo(data){const m=data.merchant||{};document.getElementById('pageTitle').textContent=m.merchant_name||'商户商品';document.getElementById('pageSub').textContent='商户ID: '+(m.merchant_id||mid)+'  ·  佣金: $'+parseFloat(m.avg_payout||0).toFixed(2)+'/次  ·  Cookie: '+(m.cookie_days||'-')+'天  ·  共 '+data.total.toLocaleString()+' 件商品';}
function htmlEsc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function renderBody(items){
  const body=document.getElementById('tblBody');const offset=(curPage-1)*PAGE_SIZE;
  if(!items||!items.length){body.innerHTML='<tr><td colspan="11" class="empty">暂无商品</td></tr>';return;}
  body.innerHTML=items.map((p,i)=>{
    const img=p.image_url?'<img src="'+htmlEsc(p.image_url)+'" style="width:48px;height:48px;object-fit:contain;background:#23262f;border-radius:4px;" onerror="this.hidden=1">'  :'<span style="color:#555;font-size:.75rem">无图</span>';
    const amzBadge=p.has_amazon?'<span class="pill pill-green">已采集</span>':'<span class="pill pill-gray">未采集</span>';
    const nameEsc=htmlEsc(p.product_name);
    const nameShort=(p.product_name||'').length>60?htmlEsc(p.product_name.slice(0,60))+'…':nameEsc||'-';
    const earnHtml=p.earn?'<span style="color:#69f0ae;font-weight:600">'+p.earn+'</span>':'<span style="color:#555">-</span>';
    let adBtn='';
    if(p.has_plan){
      adBtn='<button style="background:#2e7d32;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="downloadPlan(this.dataset.asin)">下载方案</button>';
    }else if(p.has_amazon){
      adBtn='<button style="background:#1565c0;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="generateAd(this)">制作广告</button>';
    }else{
      adBtn='<button style="background:#e65100;color:#fff;padding:4px 12px;border:none;border-radius:6px;font-size:.78rem;font-weight:600;cursor:pointer;" data-asin="'+p.asin+'" onclick="generateAd(this)" title="建议先采集Amazon数据">制作广告</button>';
    }
    return '<tr><td class="td-id">'+(offset+i+1)+'</td><td>'+img+'</td><td class="td-id"><a href="https://www.amazon.com/dp/'+p.asin+'" target="_blank" style="color:#64b5f6">'+p.asin+'</a></td><td class="td-name" title="'+nameEsc+'">'+nameShort+'</td><td class="td-num">'+(p.yp_price?'$'+parseFloat(p.yp_price).toFixed(2):'-')+'</td><td class="td-num">'+(p.commission||'-')+'</td><td class="td-num">'+earnHtml+'</td><td>'+starsHtml(p.rating)+'</td><td class="td-num">'+(p.review_count||'-')+'</td><td>'+amzBadge+'</td><td style="white-space:nowrap">'+adBtn+'</td></tr>';
  }).join('');
}
function loadTable(){
  document.getElementById('tblBody').innerHTML='<tr><td colspan="11" class="loading">加载中...</td></tr>';
  let url='/api/merchant_products?merchant_id='+encodeURIComponent(mid)+'&page='+curPage+'&size='+PAGE_SIZE;
  if(curSearch) url+='&q='+encodeURIComponent(curSearch);
  fetch(url).then(r=>r.json()).then(data=>{
    try{
      if(data.error){document.getElementById('tblBody').innerHTML='<tr><td colspan="11" class="empty">错误: '+data.error+'</td></tr>';return;}
      loadMerchantInfo(data);curTotal=data.total;curPages=data.pages;
      document.getElementById('totalCount').textContent='共 '+data.total.toLocaleString()+' 件商品';
      renderBody(data.items);renderPager('pager',curPage,curPages,curTotal,PAGE_SIZE,'goPage');
    }catch(e){console.error('loadTable render error:',e);document.getElementById('tblBody').innerHTML='<tr><td colspan="11" class="empty">渲染错误: '+e.message+'</td></tr>';}
  }).catch(e=>{document.getElementById('tblBody').innerHTML='<tr><td colspan="11" class="empty">加载失败: '+e+'</td></tr>';});
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
