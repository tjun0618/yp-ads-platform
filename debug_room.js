const http = require('http');
function get(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (r) => {
      const chunks = [];
      r.on('data', c => chunks.push(c));
      r.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    }).on('error', reject);
  });
}
async function main() {
  // 1. 测试 merchant_room API
  console.log('=== 1. /api/merchant_room/369117 ===');
  const d1 = await get('http://localhost:5055/api/merchant_room/369117');
  const j1 = JSON.parse(d1);
  console.log('keys:', Object.keys(j1));
  console.log('merchant:', JSON.stringify(j1.merchant || {}).substring(0, 200));
  console.log('products count:', (j1.products||[]).length);
  if(j1.products && j1.products.length > 0) {
    console.log('first product keys:', Object.keys(j1.products[0]));
    console.log('first product:', JSON.stringify(j1.products[0]).substring(0, 300));
  }
  console.log('error:', j1.error || 'none');
  
  // 2. 找作战室页面的renderProducts函数
  console.log('\n=== 2. merchant_room page renderProducts ===');
  const html = await get('http://localhost:5055/merchant_room/369117');
  
  let idx = html.indexOf('function renderProducts(');
  if (idx >= 0) {
    console.log(html.substring(idx, idx + 1500));
  } else {
    console.log('renderProducts NOT FOUND');
    // 找其他渲染函数
    ['renderTable', 'renderList', 'buildRow', 'loadRoom'].forEach(k => {
      const i = html.indexOf('function ' + k);
      if (i >= 0) console.log(`[function ${k}]:`, html.substring(i, i+800));
    });
  }
  
  // 3. 找作战室的prdBody或商品区
  idx = html.indexOf('prdBody');
  if (idx >= 0) {
    console.log('\n=== 3. prdBody context ===');
    console.log(html.substring(Math.max(0, idx-50), idx+200));
  }
}
main().catch(console.error);
