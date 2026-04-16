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
  const html = await get('http://localhost:5055/merchants');
  // 找curTab初始值
  const curTabIdx = html.indexOf('curTab');
  console.log('[curTab context]', html.substring(Math.max(0,curTabIdx-10), curTabIdx+200));
  
  // 找tab按钮
  const tabIdx = html.indexOf('tab-btn') >= 0 ? html.indexOf('tab-btn') : html.indexOf('data-tab');
  if (tabIdx >= 0) console.log('[tab buttons]', html.substring(tabIdx-20, tabIdx+300));
  
  // 找loadTable调用链
  const initIdx = html.indexOf('loadTable();\n');
  console.log('[loadTable() first call]', initIdx, html.substring(Math.max(0,initIdx-100), initIdx+50));
}
main().catch(console.error);
