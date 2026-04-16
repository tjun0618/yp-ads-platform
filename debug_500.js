const http = require('http');

function testUrl(label, url) {
  return new Promise((resolve) => {
    http.get(url, (r) => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => {
        console.log(`\n=== ${label} ===`);
        console.log('Status:', r.statusCode);
        if (r.statusCode >= 400) {
          console.log(d.substring(0, 3000));
        } else {
          try {
            const j = JSON.parse(d);
            console.log('total:', j.total, 'items:', j.items && j.items.length, 'error:', j.error || 'none');
          } catch(e) {
            console.log('HTML len:', d.length);
          }
        }
        resolve();
      });
    }).on('error', e => { console.log(`${label} ERROR:`, e.message); resolve(); });
  });
}

(async () => {
  await testUrl('GET /merchants', 'http://localhost:5055/merchants');
  await testUrl('GET /api/merchants?tab=approved', 'http://localhost:5055/api/merchants?tab=approved&page=1&size=20');
  await testUrl('GET /api/merchants?tab=all', 'http://localhost:5055/api/merchants?tab=all&page=1&size=20');
  await testUrl('GET /api/merchants?tab=unapplied', 'http://localhost:5055/api/merchants?tab=unapplied&page=1&size=20');
})();
