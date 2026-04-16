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
  // 测试作战室 API - 用 merchant 369117（JSON里有但DB没有）
  console.log('=== Test 1: merchant_room/369117 (in JSON, not in DB) ===');
  const d1 = await get('http://localhost:5055/api/merchant_room/369117');
  const j1 = JSON.parse(d1);
  console.log('merchant:', JSON.stringify(j1.merchant));
  console.log('products count:', (j1.products||[]).length);
  console.log('error:', j1.error || 'none');
  
  // 测试作战室 API - 用 merchant 362400（JSON+DB都有）
  console.log('\n=== Test 2: merchant_room/362400 (in both JSON and DB) ===');
  const d2 = await get('http://localhost:5055/api/merchant_room/362400');
  const j2 = JSON.parse(d2);
  console.log('merchant:', JSON.stringify(j2.merchant));
  console.log('products count:', (j2.products||[]).length);
  console.log('error:', j2.error || 'none');
  
  // 测试商品页 API - 用 merchant 369117
  console.log('\n=== Test 3: merchant_products?merchant_id=369117 ===');
  const d3 = await get('http://localhost:5055/api/merchant_products?merchant_id=369117&page=1&size=20');
  const j3 = JSON.parse(d3);
  console.log('merchant:', JSON.stringify(j3.merchant));
  console.log('total:', j3.total, 'items:', (j3.items||[]).length);
  console.log('error:', j3.error || 'none');
}
main().catch(console.error);
