const http = require('http');

const routes = [
  '/yp_sync',
  '/yp_collect',
  '/amazon_scrape',
  '/merchant_room/369117',
  '/merchant_products?merchant_id=369117',
  '/plans',
  '/qs_dashboard',
  '/competitor_ads',
  '/optimize',
];

async function test(url) {
  return new Promise((resolve) => {
    const fullUrl = 'http://localhost:5055' + url;
    http.get(fullUrl, (r) => {
      let d = '';
      r.on('data', c => d += c);
      r.on('end', () => {
        let preview = '';
        if (r.statusCode >= 400) {
          // 提取Flask错误信息
          const errMatch = d.match(/Internal Server Error.*?(?=<\/p>|<pre>|$)/s);
          preview = d.substring(0, 300).replace(/\s+/g, ' ');
        }
        console.log(`[${r.statusCode}] ${url}${r.statusCode >= 400 ? '\n  ERROR: ' + preview : ''}`);
        resolve();
      });
    }).on('error', e => { console.log(`[ERR] ${url}: ${e.message}`); resolve(); });
  });
}

(async () => {
  for (const r of routes) await test(r);
})();
