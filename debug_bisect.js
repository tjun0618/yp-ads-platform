const fs = require('fs');
const vm = require('vm');
let js = fs.readFileSync('debug_script_block.js','utf-8');
js = js.replace(/^<script[^>]*>\s*/,'').replace(/\s*<\/script>\s*$/,'');
js = js.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

const lines = js.split('\n');
console.log('Total lines after CRLF norm:', lines.length);

// 二分法
let lo = 0, hi = lines.length;
while (hi - lo > 1) {
  const mid = Math.floor((lo + hi) / 2);
  const sub = lines.slice(0, mid).join('\n');
  let hasErr = false;
  try { new vm.Script(sub); } catch(e) {
    if (e.name === 'SyntaxError') hasErr = true;
  }
  if (hasErr) hi = mid;
  else lo = mid;
}
console.log('\n=== Error boundary: line', hi, '===');
for (let i = Math.max(0, hi-8); i < Math.min(lines.length, hi+4); i++) {
  const mark = (i === hi-1) ? '>>>' : '   ';
  const hex = Buffer.from(lines[i]).toString('hex');
  console.log(`${mark} ${i+1}: ${lines[i].substring(0,120)}`);
  console.log(`       hex[0..30]: ${hex.slice(0,60)}`);
}
