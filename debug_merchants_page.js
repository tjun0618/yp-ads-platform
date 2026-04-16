const http = require('http');

// 获取 /merchants 页面，分析所有 fetch 调用和可能导致500的路由
http.get('http://localhost:5055/merchants', (r) => {
  let d = '';
  r.on('data', c => d += c);
  r.on('end', () => {
    console.log('Page len:', d.length, 'Status:', r.statusCode);
    
    // 找所有 fetch( 调用
    const re = /fetch\s*\(\s*[`'"]([^`'"]+)[`'"]/g;
    let m;
    const fetches = new Set();
    while ((m = re.exec(d)) !== null) fetches.add(m[1]);
    console.log('\nfetch calls:');
    fetches.forEach(f => console.log(' ', f));
    
    // 找所有 href
    const re2 = /href\s*=\s*["']([^"'#][^"']*)["']/g;
    const hrefs = new Set();
    while ((m = re2.exec(d)) !== null) {
      if (!m[1].startsWith('http')) hrefs.add(m[1]);
    }
    console.log('\nhref links:');
    hrefs.forEach(h => console.log(' ', h));

    // 找含tab的输入
    const tabRe = /curTab\s*=\s*['"`](\w+)['"`]/g;
    const tabs = new Set();
    while ((m = tabRe.exec(d)) !== null) tabs.add(m[1]);
    console.log('\ntab values:', [...tabs]);
    
    // 找loadTable()函数
    const loadIdx = d.indexOf('function loadTable');
    if (loadIdx >= 0) {
      console.log('\n--- loadTable function ---');
      console.log(d.substring(loadIdx, loadIdx + 600));
    }
  });
}).on('error', e => console.error(e));
