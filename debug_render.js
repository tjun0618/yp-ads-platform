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
  
  // 找renderBody函数
  let idx = html.indexOf('function renderBody(');
  if (idx >= 0) {
    console.log('=== renderBody ===');
    console.log(html.substring(idx, idx + 2000));
  } else {
    console.log('renderBody NOT FOUND');
  }
  
  // 找renderHead函数
  idx = html.indexOf('function renderHead(');
  if (idx >= 0) {
    console.log('\n=== renderHead ===');
    console.log(html.substring(idx, idx + 500));
  }
}
main().catch(console.error);
