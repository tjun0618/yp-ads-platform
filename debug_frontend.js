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

async function main() {
  const html = await get('http://localhost:5055/');
  
  // 找所有 fetch( 调用
  const fetchRe = /fetch\s*\(\s*[`'"]/g;
  let m;
  const fetches = [];
  const re2 = /fetch\s*\(([^)]{1,200})\)/g;
  while ((m = re2.exec(html)) !== null) {
    fetches.push(m[1].substring(0, 100));
  }
  console.log('=== fetch calls ===');
  [...new Set(fetches)].forEach(f => console.log(f));
  
  // 找加载中 / 正在加载
  const loadIdx = html.indexOf('加载中');
  if (loadIdx >= 0) {
    console.log('\n=== 加载中 context ===');
    console.log(html.substring(Math.max(0, loadIdx - 200), loadIdx + 200));
  }
  
  // 找 loadTable / loadMerchants
  ['loadTable', 'loadMerchants', 'DOMContentLoaded'].forEach(key => {
    const idx = html.indexOf(key);
    if (idx >= 0) {
      console.log(`\n=== ${key} context ===`);
      console.log(html.substring(Math.max(0, idx - 30), idx + 120));
    }
  });
}

main().catch(console.error);
