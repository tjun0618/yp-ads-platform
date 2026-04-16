"""
US 商户清洗 + 全商品抓取方案 - 数据分析
分析现有数据，规划方案
"""
import json
from collections import Counter

print("=" * 60)
print("YP 平台 US 商户数据分析")
print("=" * 60)

# 加载商户数据
with open('output/merchants_mid_list.json', 'r', encoding='utf-8') as f:
    all_merchants = json.load(f)

# ① 全平台统计
print(f"\n全平台商户总数: {len(all_merchants)}")

# 国家分布
country_counter = Counter()
for m in all_merchants:
    c = m.get('country', 'UNKNOWN')
    code = c.split(' - ')[0] if ' - ' in c else c[:2]
    country_counter[code] += 1

print("\n国家分布 Top 10:")
for country, count in country_counter.most_common(10):
    pct = count / len(all_merchants) * 100
    print(f"  {country}: {count} ({pct:.1f}%)")

# ② US 商户详情
us_merchants = [m for m in all_merchants if 'United States' in m.get('country', '')]
print(f"\n--- US 商户 ---")
print(f"总数: {len(us_merchants)}")

us_status = Counter(m.get('status', '') for m in us_merchants)
for s, c in us_status.most_common():
    print(f"  {s}: {c}")

# ③ 已申请的 US 商户（APPROVED）
approved_us = [m for m in us_merchants if m.get('status') == 'APPROVED']
print(f"\n已申请审批通过 (APPROVED): {len(approved_us)} 个")
print("这些商户的 brand_detail 页面有投放链接")

# ④ 未申请的 US 商户（UNAPPLIED）
unapplied_us = [m for m in us_merchants if m.get('status') == 'UNAPPLIED']
print(f"\n未申请 (UNAPPLIED): {len(unapplied_us)} 个")
print("这些商户的 brand_detail 页面可能有商品但没有投放链接")

# ⑤ 保存 US 商户清洗结果
us_clean = {
    'total': len(us_merchants),
    'approved': len(approved_us),
    'unapplied': len(unapplied_us),
    'approved_list': approved_us,
    'unapplied_list': unapplied_us
}

with open('output/us_merchants_clean.json', 'w', encoding='utf-8') as f:
    json.dump(us_clean, f, ensure_ascii=False, indent=2)

print(f"\n已保存到: output/us_merchants_clean.json")

# ⑥ 方案评估
print("\n" + "=" * 60)
print("方案评估")
print("=" * 60)

print(f"""
【方案 A】只抓 APPROVED US 商户（3,727 个）
- 优点：有投放链接，可直接推广，数据完整
- 预计商品量：3,727 × 平均商品数
- 估算（参考 NORTIV 8 的 5,490 个）：如果平均每商户 100 个商品 → 37 万条

【方案 B】抓所有 US 商户（7,479 个）
- APPROVED 3,727 个：有商品 + 有投放链接
- UNAPPLIED 3,752 个：可能有商品目录，但无投放链接
- 优先 APPROVED，UNAPPLIED 可视情况补充

【方案 C】分批优先策略（推荐）
1. 先抓 APPROVED US 商户，获取商品+投放链接
2. 按佣金率排序，优先抓高佣金商户
3. 飞书只存有投放链接的商品（质量优先）

每页 30 个商品，每请求 1-2 秒间隔
3,727 个商户，假设平均 50 页/商户 → 约 186,350 次请求 ≈ 约 52 小时
→ 建议优先抓高佣金商户
""")

# ⑦ 按名称看几个知名品牌示例
print("APPROVED US 商户示例 (前20):")
for m in approved_us[:20]:
    print(f"  mid={m['mid']}, name={m['name']}")
