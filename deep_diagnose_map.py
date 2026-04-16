# -*- coding: utf-8 -*-
"""
深度诊断 asin_merchant_map.json 数据质量
检查维度：
1. 链接有效性（格式、域名）
2. 同一ASIN多商户映射
3. 商户维度统计（多少商户有链接、多少没有）
4. 跟 Excel 下载的商品交叉对比
"""

import json
from collections import Counter, defaultdict
from urllib.parse import urlparse
import os

print("=" * 80)
print("asin_merchant_map.json 深度数据质量诊断")
print("=" * 80)

# 读取数据
map_path = 'output/asin_merchant_map.json'
with open(map_path, 'r', encoding='utf-8') as f:
    asin_map = json.load(f)

print(f"\n[1] 基础统计")
print(f"  总 ASIN 数: {len(asin_map):,}")

# 检查数据结构
sample_keys = set()
for asin, info in list(asin_map.items())[:100]:
    if info and isinstance(info, dict):
        sample_keys.update(info.keys())
print(f"  字段: {sorted(sample_keys)}")

# 2. 链接分析
print(f"\n[2] 投放链接分析")
has_url = 0
no_url = 0
has_track_no_url = 0
url_domains = Counter()
url_with_pid = 0
url_without_pid = 0

for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        no_url += 1
        continue
    
    url = (info.get('tracking_url', '') or '').strip()
    track = (info.get('track_token', '') or '').strip()
    
    if url:
        has_url += 1
        try:
            parsed = urlparse(url)
            url_domains[parsed.netloc] += 1
            if 'pid=' in url:
                url_with_pid += 1
            else:
                url_without_pid += 1
        except:
            pass
    elif track:
        has_track_no_url += 1
    else:
        no_url += 1

print(f"  有完整投放链接: {has_url:,} ({has_url/len(asin_map)*100:.1f}%)")
print(f"  有track但无URL: {has_track_no_url:,}")
print(f"  无链接(未申请): {no_url:,} ({no_url/len(asin_map)*100:.1f}%)")

if url_domains:
    print(f"\n  链接域名分布:")
    for domain, count in url_domains.most_common():
        print(f"    {domain}: {count}")

print(f"\n  链接含pid参数: {url_with_pid:,}")
print(f"  链接不含pid: {url_without_pid:,}")

# 3. 商户维度分析
print(f"\n[3] 商户维度分析")
merchant_asins = defaultdict(list)
for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    mid = str(info.get('merchant_id', '') or '').strip()
    if mid:
        merchant_asins[mid].append(asin)

print(f"  有商户映射的ASIN: {sum(len(v) for v in merchant_asins.values()):,}")
print(f"  涉及商户数: {len(merchant_asins):,}")

# 商户链接覆盖
merchant_all_have_url = 0
merchant_none_have_url = 0
merchant_partial = 0

for mid, asins in merchant_asins.items():
    has = 0
    for asin in asins:
        info = asin_map.get(asin, {})
        if info and isinstance(info, dict):
            url = (info.get('tracking_url', '') or '').strip()
            if url:
                has += 1
    if has == len(asins):
        merchant_all_have_url += 1
    elif has == 0:
        merchant_none_have_url += 1
    else:
        merchant_partial += 1

print(f"\n  所有商品都有链接的商户: {merchant_all_have_url:,}")
print(f"  所有商品都没链接的商户: {merchant_none_have_url:,}")
print(f"  部分有链接的商户: {merchant_partial:,}")

# TOP 10 商户(按商品数)
top_merchants = sorted(merchant_asins.items(), key=lambda x: -len(x[1]))[:10]
print(f"\n  TOP 10 商户(按商品数):")
for mid, asins in top_merchants:
    sample_info = asin_map.get(asins[0], {})
    name = (sample_info.get('merchant_name', '') or '未知')[:30]
    has = sum(1 for a in asins if asin_map.get(a, {}) and isinstance(asin_map.get(a), dict) and (asin_map.get(a, {}).get('tracking_url', '') or '').strip())
    print(f"    MID:{mid} {name}: {len(asins)} 个ASIN, {has} 有链接")

# 4. 同一ASIN多商户问题
print(f"\n[4] 同一ASIN多商户映射（通过merchant_id去重后检查）")
# 在当前结构中，一个ASIN只映射一个商户，但不同ASIN可能属于同一商户
# 检查是否有重复的merchant_id对应不同merchant_name
mid_names = defaultdict(set)
for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    mid = str(info.get('merchant_id', '') or '').strip()
    name = (info.get('merchant_name', '') or '').strip()
    if mid and name:
        mid_names[mid].add(name)

multi_name = {mid: names for mid, names in mid_names.items() if len(names) > 1}
print(f"  同一MID有多个名称的商户: {len(multi_name)}")
if multi_name:
    for mid, names in list(multi_name.items())[:5]:
        print(f"    MID:{mid} -> {names}")

# 5. 与 NORTIV 8 Excel 交叉对比
print(f"\n[5] 与 NORTIV 8 Excel 交叉对比")
excel_path = r'C:\Users\wuhj\Downloads\Offer_20260323232258_2131.xlsx'
if os.path.exists(excel_path):
    import openpyxl
    wb = openpyxl.load_workbook(excel_path, read_only=True)
    ws = wb.active
    
    excel_asins = {}
    excel_commissions = {}
    excel_prices = {}
    excel_links = {}
    
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0]:
            asin = str(row[0]).strip()
            excel_asins[asin] = {
                'name': row[1],
                'category': row[2],
                'commission': row[3],
                'price': row[4],
                'tracking_link': row[5]
            }
    
    wb.close()
    print(f"  Excel ASIN数: {len(excel_asins):,}")
    
    # 在 asin_map 中找到的
    found_in_map = 0
    found_with_url = 0
    found_diff_merchant = 0
    
    not_in_map = []
    
    for asin, einfo in excel_asins.items():
        if asin in asin_map:
            found_in_map += 1
            minfo = asin_map[asin]
            if minfo and isinstance(minfo, dict):
                url = (minfo.get('tracking_url', '') or '').strip()
                if url:
                    found_with_url += 1
                mid = minfo.get('merchant_id', '')
                mname = (minfo.get('merchant_name', '') or '')[:30]
                if mid != '362548' and mname.upper() != 'NORTIV 8':
                    found_diff_merchant += 1
                    if found_diff_merchant <= 5:
                        print(f"    ASIN={asin} 在map中属于商户: {mname}(MID:{mid}), Excel属于NORTIV 8")
        else:
            not_in_map.append(asin)
    
    print(f"  在 asin_map 中找到: {found_in_map}/{len(excel_asins)} ({found_in_map/len(excel_asins)*100:.1f}%)")
    print(f"  其中map中有链接: {found_with_url}")
    print(f"  其中商户归属不同: {found_diff_merchant}")
    print(f"  不在 asin_map 中: {len(not_in_map)}")
else:
    print(f"  Excel文件不存在: {excel_path}")

# 6. 链接格式深度检查
print(f"\n[6] 链接格式深度检查")
track_tokens = Counter()
pid_formats = Counter()

for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    url = (info.get('tracking_url', '') or '').strip()
    if not url:
        continue
    
    try:
        parsed = urlparse(url)
        qs = parsed.query
        
        # 提取 track 和 pid
        for param in qs.split('&'):
            if param.startswith('track='):
                track_tokens[param[:20]] += 1
            elif param.startswith('pid='):
                pid_val = param[4:]
                if pid_val.isdigit():
                    pid_formats[f'numeric({len(pid_val)}位)'] += 1
                else:
                    pid_formats[f'other({pid_val[:10]})'] += 1
    except:
        pass

print(f"  不同track token数(前缀): {len(track_tokens)}")
print(f"  TOP 5 track token:")
for token, count in track_tokens.most_common(5):
    print(f"    {token}...: {count} 个ASIN")

print(f"\n  pid格式分布:")
for fmt, count in pid_formats.most_common():
    print(f"    {fmt}: {count}")

print("\n" + "=" * 80)
print("asin_map 诊断完成")
print("=" * 80)
