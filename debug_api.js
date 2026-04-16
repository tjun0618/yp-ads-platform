const http = require('http');
http.get('http://localhost:5055/api/merchants?tab=approved&page=1&size=20', (r) => {
  let d = '';
  r.on('data', c => d += c);
  r.on('end', () => {
    const j = JSON.parse(d);
    console.log('total:', j.total, 'items:', j.items.length, 'pages:', j.pages);
    if(j.items.length > 0) {
      console.log('first item keys:', Object.keys(j.items[0]));
      console.log('first item:', JSON.stringify(j.items[0]).substring(0,300));
    } else {
      console.log('EMPTY items!');
    }
    if(j.error) console.log('error:', j.error);
  });
}).on('error', e => console.error(e));
