"""
创建完整的YP商家列表并重新整合数据
"""

import json
from pathlib import Path
from datetime import datetime
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')


def create_full_merchant_list():
    """从页面内容提取完整的商家列表"""
    
    # 基于之前采集的页面内容，创建完整的商家列表
    merchants = [
        {"mid": "356364", "name": "OlliePets_US", "commission": "34.50 USD"},
        {"mid": "204545", "name": "Sik Silk PL", "commission": "6.00%"},
        {"mid": "268598", "name": "bofrost DE", "commission": "0.98%"},
        {"mid": "359638", "name": "Lepro", "commission": "15.00%"},
        {"mid": "146730", "name": "iHerb", "commission": "0.75%"},
        {"mid": "362142", "name": "oneisall", "commission": "15.00%"},
        {"mid": "151556", "name": "Gravity Performance", "commission": "3.75%"},
        {"mid": "284073", "name": "СоюзЦветТорг", "commission": "6.09%"},
        {"mid": "363225", "name": "DOVOH", "commission": "30.00%"},
        {"mid": "111621", "name": "Hoka US", "commission": "2.25%"},
        {"mid": "362312", "name": "VANTRUE", "commission": "0.0000%"},
        {"mid": "151815", "name": "Techem wycieraczki", "commission": "7.50%"},
        {"mid": "285561", "name": "Three Spirit US", "commission": "4.20%"},
        {"mid": "363168", "name": "KiddyCare", "commission": "18.75%"},
        {"mid": "111335", "name": "iHerb", "commission": "0.75%"},
        {"mid": "362349", "name": "SUNUV", "commission": "21.00%"},
        {"mid": "151050", "name": "Allpowers", "commission": "7.50%"},
        {"mid": "119732", "name": "Mobile24", "commission": "3.41%"},
        {"mid": "363193", "name": "Perfect Remedy", "commission": "15.00%"},
        {"mid": "255233", "name": "Amazon Music", "commission": "€1.33"},
    ]
    
    return merchants


def main():
    """主函数"""
    print("=" * 60)
    print("创建完整商家列表并重新整合数据")
    print("=" * 60)
    
    # 创建完整商家列表
    merchants = create_full_merchant_list()
    print(f"\n创建商家列表: {len(merchants)} 个商家")
    
    # 保存商家列表
    output_dir = Path('output')
    output_dir.mkdir(exist_ok=True)
    
    # 保存JSON格式
    merchants_json = output_dir / 'yp_full_merchants.json'
    with open(merchants_json, 'w', encoding='utf-8') as f:
        json.dump(merchants, f, ensure_ascii=False, indent=2)
    print(f"✓ 商家列表JSON: {merchants_json}")
    
    # 保存CSV格式
    import csv
    merchants_csv = output_dir / 'yp_full_merchants.csv'
    if merchants:
        with open(merchants_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=merchants[0].keys())
            writer.writeheader()
            writer.writerows(merchants)
    print(f"✓ 商家列表CSV: {merchants_csv}")
    
    # 现在重新整合数据
    print("\n" + "=" * 60)
    print("重新整合YP商家和亚马逊产品数据")
    print("=" * 60)
    
    # 加载亚马逊数据
    amazon_search_file = output_dir / 'amazon_search_results_improved.json'
    with open(amazon_search_file, 'r', encoding='utf-8') as f:
        amazon_products = json.load(f)
    print(f"\n亚马逊产品数据: {len(amazon_products)} 条记录")
    
    amazon_details_file = output_dir / 'amazon_product_details_improved.json'
    with open(amazon_details_file, 'r', encoding='utf-8') as f:
        amazon_details = json.load(f)
    print(f"亚马逊产品详情: {len(amazon_details)} 条记录")
    
    # 创建ASIN到详情的映射
    details_map = {item['asin']: item for item in amazon_details}
    
    # 合并数据
    merged_data = []
    
    for merchant in merchants:
        merchant_name = merchant['name']
        
        # 查找该商家的亚马逊产品
        merchant_products = [p for p in amazon_products if p.get('merchant_name') == merchant_name]
        
        for product in merchant_products:
            # 获取产品详情
            asin = product.get('asin', '')
            details = details_map.get(asin, {})
            
            # 创建合并记录
            merged_record = {
                # YP商家信息
                'yp_mid': merchant['mid'],
                'yp_merchant_name': merchant_name,
                'yp_commission': merchant['commission'],
                
                # 亚马逊产品信息
                'amazon_asin': asin,
                'amazon_title': product.get('title', ''),
                'amazon_price': product.get('price', ''),
                'amazon_rating': product.get('rating', ''),
                'amazon_reviews': product.get('reviews', ''),
                'amazon_image_url': product.get('image_url', ''),
                'amazon_product_url': product.get('product_url', ''),
                
                # 产品详情
                'amazon_description': details.get('description', '')[:500] if details.get('description') else '',
                'amazon_brand': details.get('brand', ''),
                'amazon_review_count': details.get('review_count', ''),
                
                # 元数据
                'collected_at': product.get('collected_at', ''),
                'match_source': 'YP->Amazon'
            }
            
            merged_data.append(merged_record)
    
    print(f"\n合并后数据: {len(merged_data)} 条记录")
    
    # 保存合并数据
    comprehensive_json = output_dir / 'comprehensive_yp_amazon_data_v2.json'
    with open(comprehensive_json, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)
    print(f"✓ 综合数据JSON: {comprehensive_json}")
    
    # 保存CSV格式
    comprehensive_csv = output_dir / 'comprehensive_yp_amazon_data_v2.csv'
    if merged_data:
        with open(comprehensive_csv, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=merged_data[0].keys())
            writer.writeheader()
            writer.writerows(merged_data)
    print(f"✓ 综合数据CSV: {comprehensive_csv}")
    
    # 打印匹配统计
    print("\n" + "=" * 60)
    print("匹配统计")
    print("=" * 60)
    
    matched_merchants = set([m['yp_merchant_name'] for m in merged_data])
    print(f"\n匹配的商家数: {len(matched_merchants)}")
    print(f"总记录数: {len(merged_data)}")
    
    print("\n匹配的商家:")
    for merchant_name in sorted(matched_merchants):
        merchant_products = [m for m in merged_data if m['yp_merchant_name'] == merchant_name]
        print(f"  {merchant_name}: {len(merchant_products)} 个产品")
    
    # 生成更新后的统计报告
    stats = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'yp_merchants': {
            'total_count': len(merchants),
            'unique_mids': len(set([m['mid'] for m in merchants])),
            'unique_names': len(set([m['name'] for m in merchants])),
        },
        'amazon_products': {
            'total_count': len(amazon_products),
            'unique_asins': len(set([p['asin'] for p in amazon_products])),
        },
        'merged_data': {
            'total_records': len(merged_data),
            'matched_merchants': len(matched_merchants),
            'matched_asins': len(set([m['amazon_asin'] for m in merged_data])),
        },
        'coverage': {
            'merchant_coverage': f"{len(matched_merchants) / len(merchants) * 100:.1f}%",
            'product_per_merchant': f"{len(merged_data) / len(matched_merchants):.1f}" if matched_merchants else "0",
        }
    }
    
    stats_file = output_dir / 'data_statistics_v2.json'
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] 统计报告: {stats_file}")
    
    print("\n" + "=" * 60)
    print("✅ 数据整合完成！")
    print("=" * 60)
    
    return comprehensive_json, comprehensive_csv


if __name__ == '__main__':
    main()
