const http = require('http');

// 获取主页HTML，找导航中"商户管理"→"商户"的链接
http.get('http://localhost:5055/', (r) => {
  let d = '';
  r.on('data', c => d += c);
  r.on('end', () => {
    // 找 href 包含 merchant 的链接
    const hrefs = [];
    const re = /href\s*=\s*["']([^"']*merchant[^"']*)["']/gi;
    let m;
    while ((m = re.exec(d)) !== null) hrefs.push(m[1]);
    console.log('merchant links:', [...new Set(hrefs)]);

    // 找 onclick 包含 merchant 的
    const re2 = /onclick\s*=\s*["']([^"']*merchant[^"']*)["']/gi;
    const onclicks = [];
    while ((m = re2.exec(d)) !== null) onclicks.push(m[1].substring(0, 120));
    console.log('merchant onclicks:', [...new Set(onclicks)]);

    // 找导航区域（nav）
    const navIdx = d.indexOf('商户管理');
    if (navIdx >= 0) {
      console.log('\n--- 商户管理 周边 HTML (300字符) ---');
      console.log(d.substring(navIdx - 50, navIdx + 400));
    }
  });
}).on('error', e => console.error(e));
