import json

with open('output/asin_merchant_map.json', 'r', encoding='utf-8') as f:
    asin_map = json.load(f)

# 统计各种状态
has_url = 0
no_url_has_track = 0
no_url_no_track = 0

for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        no_url_no_track += 1
        continue
    url = info.get('tracking_url', '') or ''
    track = info.get('track_token', '') or ''
    
    if url and url.strip():
        has_url += 1
    elif track and track.strip():
        no_url_has_track += 1
    else:
        no_url_no_track += 1

total = len(asin_map)
print(f'ASIN 映射总数: {total:,}')
print()
print(f'有完整投放链接:       {has_url:>8,} ({has_url/total*100:.1f}%)')
print(f'有track但无URL:       {no_url_has_track:>8,} ({no_url_has_track/total*100:.1f}%)')
print(f'无track无URL(未申请):  {no_url_no_track:>8,} ({no_url_no_track/total*100:.1f}%)')
print()

# 飞书情况
with open('output/feishu_offers_asins.json', 'r') as f:
    feishu_asins = set(json.load(f))

feishu_matched = 0
feishu_has_url = 0
feishu_no_url = 0
for asin in feishu_asins:
    if asin in asin_map:
        info = asin_map[asin]
        if not info or not isinstance(info, dict):
            continue
        feishu_matched += 1
        url = (info.get('tracking_url', '') or '').strip()
        if url:
            feishu_has_url += 1
        else:
            feishu_no_url += 1

print(f'飞书 ASIN 在 map 中的: {feishu_matched}')
print(f'  有投放链接: {feishu_has_url}')
print(f'  无投放链接(未申请): {feishu_no_url}')

# 无URL样本
print()
print('--- 无投放链接的ASIN样本 ---')
count = 0
for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    url = (info.get('tracking_url', '') or '').strip()
    if not url:
        mid = info.get('merchant_id', '')
        merchant = info.get('merchant_name', '')[:30]
        track = info.get('track_token', '')[:20]
        print(f'  ASIN={asin}, mid={mid}, merchant={merchant}, track={track}')
        count += 1
        if count >= 5:
            break

# 按商户维度统计
print()
print('--- 按商户维度统计 ---')
from collections import Counter
merchant_stats = Counter()
for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    mid = info.get('merchant_id', '')
    url = (info.get('tracking_url', '') or '').strip()
    has_u = 1 if url else 0
    merchant_stats[mid] += has_u

merchant_total = Counter()
for asin, info in asin_map.items():
    if not info or not isinstance(info, dict):
        continue
    mid = info.get('merchant_id', '')
    merchant_total[mid] += 1

# 找出部分有链接部分没有的商户
mixed = 0
all_no_url = 0
all_has_url = 0
for mid in merchant_total:
    total_m = merchant_total[mid]
    has_u = merchant_stats.get(mid, 0)
    if has_u == 0:
        all_no_url += 1
    elif has_u == total_m:
        all_has_url += 1
    else:
        mixed += 1

print(f'所有商品都有链接的商户: {all_has_url}')
print(f'所有商品都没链接的商户: {all_no_url}')
print(f'部分有部分没有的商户:   {mixed}')
