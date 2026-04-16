#!/usr/bin/env python3
import json
from datetime import datetime

print('='*70)
print('【2026-03-23 YP 投放链接采集 - 最终成果总结】')
print('='*70)
print()

# 加载数据
with open('output/final_statistics.json', 'r', encoding='utf-8') as f:
    stats = json.load(f)

print('📊 关键数据统计')
print('-'*70)
print(f'  YP 平台商户总数        : {stats["total_merchants_yp"]:>10,} 个')
print(f'  本地 ASIN 映射总数     : {stats["total_asin_map"]:>10,} 个')
print(f'  飞书 Offers ASIN 总数  : {stats["total_asin_feishu"]:>10,} 个')
print()
print(f'  飞书 ASIN 中已匹配     : {stats["matched_asin"]:>10,} 个 ({stats["coverage_percent"]:.1f}%)')
print(f'  飞书 ASIN 中未匹配     : {stats["unmatched_asin"]:>10,} 个')
print()
print(f'  本地映射有投放链接     : {stats["asin_with_url"]:>10,} 个')
print(f'  飞书 ASIN 中有链接     : {stats["feishu_asin_with_url"]:>10,} 个 (2.0%)')
print()
print(f'  参与商户数             : {stats["unique_merchants_in_map"]:>10,} 个')
print()

print('🔍 结论')
print('-'*70)
print('  ✅ 已完成：YP 平台全量商户网页抓取')
print('  ✅ 已获得：96,794 个高质量 ASIN→投放链接映射')
print('  ⚠️  发现：飞书 94% 的 ASIN 来自其他渠道（非 YP 已采集商户）')
print('  📋 建议：优先更新飞书中 71 个已有投放链接的 ASIN')
print()

print('📁 重要文件')
print('-'*70)
print('  📄 WORK_SUMMARY_2026-03-23.md      - 简洁工作总结（推荐先看）')
print('  📄 DAILY_SUMMARY_2026-03-23.md     - 详细技术报告')
print('  📊 output/asin_merchant_map.json   - 96,794 个 ASIN 映射数据')
print('  📊 output/final_statistics.json    - 最终统计数据')
print()

print('⏱️  时间线')
print('-'*70)
print('  10:56  - 开始方案评估')
print('  11:13  - 完成方案 1 测试（覆盖率 2.8%，决策放弃）')
print('  11:13  - 启动方案 2 后台抓取')
print('  16:00  - 方案 2 完全完成（96,794 ASIN）')
print('  16:00+ - 数据分析与总结生成')
print()

print('='*70)
print(f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*70)
