const http = require('http');
http.get('http://localhost:5055/api/merchant_room/362400', (r) => {
  let d = '';
  r.on('data', c => d += c);
  r.on('end', () => {
    const j = JSON.parse(d);
    console.log('merchant:', JSON.stringify(j.merchant).substring(0, 150));
    console.log('products count:', j.products ? j.products.length : 'undefined');
    console.log('error:', j.error || 'none');
    if (j.products && j.products.length > 0) {
      console.log('first product keys:', Object.keys(j.products[0]));
    }
  });
}).on('error', e => console.error(e));
