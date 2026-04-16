#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把日志中出现 "解析失败: File is not a zip file" 对应的商户
从 completed_mids 移回待处理（即从 state 中删除）
"""
import json, re, os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "output"
STATE_FILE = OUTPUT_DIR / "download_state.json"
LOG_FILE   = OUTPUT_DIR / "download_log.txt"

# 1. 从日志中找出所有在 "解析失败" 前一条的商户 mid
log_text = LOG_FILE.read_text(encoding='utf-8', errors='ignore')
lines = log_text.splitlines()

bad_mids = set()
for i, line in enumerate(lines):
    if "解析失败: File is not a zip file" in line or "File is not a zip file" in line:
        # 往前找最近一条 [MAIN] 含 mid= 的行
        for j in range(i-1, max(i-5, 0)-1, -1):
            m = re.search(r'mid=(\d+)', lines[j])
            if m:
                bad_mids.add(m.group(1))
                break

print(f"发现解析失败的商户 mid: {len(bad_mids)} 个")
print(f"  {sorted(bad_mids)[:20]}{'...' if len(bad_mids)>20 else ''}")

if not bad_mids:
    print("没有需要重置的商户，退出")
    exit(0)

# 2. 从 state 的 completed_mids 中移除这些 mid
state = json.loads(STATE_FILE.read_text(encoding='utf-8'))
before = len(state['completed_mids'])
state['completed_mids'] = [m for m in state['completed_mids'] if m not in bad_mids]
# 同时从 failed_mids 中也移除（防止之前意外加入）
state['failed_mids'] = [m for m in state['failed_mids'] if m not in bad_mids]
after = len(state['completed_mids'])

print(f"\ncompleted_mids: {before} → {after} (移除 {before-after} 个)")

# 3. 保存
tmp = str(STATE_FILE) + ".tmp"
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(state, f, ensure_ascii=False, indent=2)
os.replace(tmp, str(STATE_FILE))
print("✅ state.json 已更新，这些商户下次会重新处理")
