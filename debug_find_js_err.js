const fs = require('fs');
let js = fs.readFileSync('debug_script_block.js','utf-8');
js = js.replace(/^<script[^>]*>\s*/,'').replace(/\s*<\/script>\s*$/,'');

const lines = js.split('\n');
console.log('Total lines:', lines.length);

// 逐行累加，找到第一个出错的位置
const vm = require('vm');
let lastOk = 0;
for (let i = 1; i <= lines.length; i++) {
  const sub = lines.slice(0, i).join('\n');
  try {
    new vm.Script(sub + '\n;'); // 加分号避免incomplete expression
  } catch(e) {
    if (e.constructor.name === 'SyntaxError') {
      // 找到了错误边界
      console.log(`\nFirst syntax error at line ${i}: ${e.message}`);
      // 显示上下文
      for(let j = Math.max(0, i-6); j < Math.min(lines.length, i+3); j++) {
        const marker = (j === i-1) ? '>>>' : '   ';
        const lineHex = Buffer.from(lines[j]).slice(0,20).toString('hex');
        console.log(`${marker} ${j+1}: ${lines[j].substring(0,120)}  [hex: ${lineHex}]`);
      }
      break;
    }
  }
  lastOk = i;
}
if (lastOk === lines.length) {
  console.log('No syntax error found (all lines OK)');
}
