#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json, os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = str(SCRIPT_DIR / "output")

d = json.load(open(os.path.join(OUTPUT_DIR, "download_state.json"), encoding="utf-8"))
print(f"completed_mids : {len(d['completed_mids'])} 个")
print(f"failed_mids    : {len(d['failed_mids'])} 个")
print(f"products       : {len(d['products']):,} 条")
print(f"last_updated   : {d['last_updated']}")

# 最后 3 条商品
last3 = d["products"][-3:]
print()
print("最后3条商品:")
for p in last3:
    print(f"  [{p.get('merchant_name','?')}] ASIN={p.get('asin','?')}")

# 商户列表
merchants_file = os.path.join(OUTPUT_DIR, "us_merchants_clean.json")
if os.path.exists(merchants_file):
    us = json.load(open(merchants_file, encoding="utf-8"))
    all_m = us["approved_list"]
    done   = set(d["completed_mids"])
    failed = set(d["failed_mids"])
    pending = [m for m in all_m if m["mid"] not in done and m["mid"] not in failed]
    print(f"\n商户总数  : {len(all_m)}")
    print(f"已完成   : {len(done)}")
    print(f"失败     : {len(failed)}")
    print(f"待处理   : {len(pending)}")
    if pending:
        print(f"下一个   : {pending[0]}")
