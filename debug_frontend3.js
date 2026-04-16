const http = require('http');

function get(url, binary=false) {
  return new Promise((resolve, reject) => {
    http.get(url, (r) => {
      const chunks = [];
      r.on('data', c => chunks.push(c));
      r.on('end', () => {
        const buf = Buffer.concat(chunks);
        resolve(binary ? buf : buf.toString('utf8'));
      });
    }).on('error', reject);
  });
}

async function main() {
  // ===== 1. 测试 merchants API =====
  console.log('=== 1. Test /api/merchants ===');
  const apiData = await get('http://localhost:5055/api/merchants?tab=all&page=1&size=20');
  const apiJson = JSON.parse(apiData);
  console.log('API status:', apiJson.status || 'no status field');
  console.log('Keys:', Object.keys(apiJson));
  console.log('Total:', apiJson.total || apiJson.count || 'N/A');
  console.log('Items count:', (apiJson.items || apiJson.data || apiJson.merchants || []).length);
  console.log('Full response (first 400 chars):', apiData.substring(0, 400));

  // ===== 2. 找 loadTable 完整函数 =====
  console.log('\n=== 2. loadTable() function ===');
  const html = await get('http://localhost:5055/merchants');
  const idx = html.indexOf('function loadTable()');
  if (idx >= 0) {
    // 找到函数结尾
    console.log(html.substring(idx, idx + 1200));
  } else {
    console.log('loadTable function NOT FOUND');
    // 找 loadTable 调用点
    const callIdx = html.indexOf('loadTable()');
    if (callIdx >= 0) {
      console.log('loadTable() call context:', html.substring(Math.max(0, callIdx-100), callIdx+200));
    }
  }

  // ===== 3. 找 renderTable 或 tblBody innerHTML 设置 =====
  console.log('\n=== 3. tblBody innerHTML setting ===');
  let search = html;
  let pos = 0;
  while (true) {
    const i = search.indexOf('tblBody', pos);
    if (i < 0) break;
    console.log(`[tblBody @ ${i}]:`, html.substring(Math.max(0,i-30), i+120));
    pos = i + 7;
  }
}

main().catch(console.error);
