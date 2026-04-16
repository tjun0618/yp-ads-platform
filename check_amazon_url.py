#!/usr/bin/env python
# -*- coding: utf-8 -*-
import mysql.connector

conn = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM yp_products')
total = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM yp_products WHERE tracking_url IS NOT NULL AND tracking_url != ''")
has_track = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM yp_products WHERE amazon_url IS NOT NULL AND amazon_url != ''")
has_amazon = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM yp_products WHERE (amazon_url IS NULL OR amazon_url = '') AND tracking_url IS NOT NULL AND tracking_url != ''")
pending = cur.fetchone()[0]

# Excel 同步的增量脚本状态
import os, json
sync_state = 'c:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu/output/sync_state.json'
if os.path.exists(sync_state):
    s = json.load(open(sync_state, encoding='utf-8'))
    print(f'MySQL 增量同步状态:')
    print(f'  上次同步时间: {s.get("last_sync_time", "未知")}')
    print(f'  上次同步行数: {s.get("last_row_count", 0):,}')
    print()

print(f'MySQL yp_products 汇总:')
print(f'  总记录数:        {total:,}')
print(f'  有 tracking_url: {has_track:,}')
print(f'  有 amazon_url:   {has_amazon:,}')
print(f'  无 amazon_url:   {pending:,}  ← 待处理')
if has_track:
    print(f'  amazon_url 覆盖率: {has_amazon/has_track*100:.1f}%')

conn.close()
