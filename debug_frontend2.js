const http = require('http');

function get(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (r) => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => resolve(d));
    }).on('error', reject);
  });
}

async function analyzeHtml(url, label) {
  console.log(`\n========== ${label} (${url}) ==========`);
  const html = await get(url);
  console.log('Length:', html.length);
  
  // 找"加载中"
  let idx = 0;
  while (true) {
    idx = html.indexOf('加载中', idx);
    if (idx < 0) break;
    console.log(`\n[加载中 @ ${idx}]:`);
    console.log(html.substring(Math.max(0, idx - 150), idx + 100));
    idx += 3;
  }
  
  // 找 fetch 调用（包含模板字符串）
  const re = /fetch\s*\([\s\S]{0,150}?\)/g;
  let m;
  const seen = new Set();
  while ((m = re.exec(html)) !== null) {
    const s = m[0].substring(0, 120);
    if (!seen.has(s)) {
      seen.add(s);
      console.log('[fetch]', s);
    }
  }
  
  // 找 DOMContentLoaded 或 window.onload
  ['DOMContentLoaded', 'window.onload', 'loadTable', 'loadMerchants', 'loadData', 'init('].forEach(k => {
    const i = html.indexOf(k);
    if (i >= 0) {
      console.log(`\n[${k} @ ${i}]:`, html.substring(i, i + 200));
    }
  });
}

async function main() {
  await analyzeHtml('http://localhost:5055/merchants', 'Merchants Page');
  
  // 也检查 /products 页面
  try {
    await analyzeHtml('http://localhost:5055/products', 'Products Page');
  } catch(e) {
    console.log('products error:', e.message);
  }
}

main().catch(console.error);
