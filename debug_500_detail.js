const http = require('http');

http.get('http://localhost:5055/merchant_products?merchant_id=369117', (r) => {
  let d = '';
  r.on('data', c => d += c);
  r.on('end', () => {
    console.log('Status:', r.statusCode);
    if (r.statusCode >= 400) {
      // 找 Traceback 或具体错误
      const tbIdx = d.indexOf('Traceback');
      if (tbIdx >= 0) {
        console.log('Traceback found:');
        console.log(d.substring(tbIdx, tbIdx + 2000));
      } else {
        // 找 jinja / template error
        const errIdx = d.indexOf('TemplateSyntax') >= 0 ? d.indexOf('TemplateSyntax') : d.indexOf('Error');
        console.log('Error section:');
        console.log(d.substring(Math.max(0, errIdx - 100), errIdx + 1000));
      }
    }
  });
}).on('error', e => console.error(e));
