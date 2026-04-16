"""
数据汇总和备份脚本
整合YP商家数据和亚马逊产品数据，生成综合数据集
"""

import json
import csv
from pathlib import Path
from typing import Dict, List
import shutil
from datetime import datetime
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')


class DataMerger:
    def __init__(self):
        self.base_dir = Path('.')
        self.output_dir = Path('output')
        self.backup_dir = Path('backup')
        
        # 确保备份目录存在
        self.backup_dir.mkdir(exist_ok=True)
    
    def load_json(self, filepath: Path) -> List[Dict]:
        """加载JSON文件"""
        if not filepath.exists():
            print(f"文件不存在: {filepath}")
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data if isinstance(data, list) else [data]
    
    def load_csv(self, filepath: Path) -> List[Dict]:
        """加载CSV文件"""
        if not filepath.exists():
            print(f"文件不存在: {filepath}")
            return []
        
        data = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        
        return data
    
    def merge_yp_amazon_data(self) -> List[Dict]:
        """合并YP商家数据和亚马逊产品数据"""
        print("=" * 60)
        print("合并YP商家数据和亚马逊产品数据")
        print("=" * 60)
        
        # 加载YP商家数据
        yp_file = self.output_dir / 'yp_elite_merchants.json'
        yp_merchants = self.load_json(yp_file)
        print(f"\nYP商家数据: {len(yp_merchants)} 条记录")
        
        # 加载亚马逊搜索结果
        amazon_file = self.output_dir / 'amazon_search_results_improved.json'
        amazon_products = self.load_json(amazon_file)
        print(f"亚马逊产品数据: {len(amazon_products)} 条记录")
        
        # 加载亚马逊产品详情
        amazon_details_file = self.output_dir / 'amazon_product_details_improved.json'
        amazon_details = self.load_json(amazon_details_file)
        print(f"亚马逊产品详情: {len(amazon_details)} 条记录")
        
        # 创建ASIN到详情的映射
        details_map = {item['asin']: item for item in amazon_details}
        
        # 合并数据
        merged_data = []
        
        # 为每个YP商家找到对应的亚马逊产品
        for merchant in yp_merchants:
            merchant_name = merchant.get('name', '')
            
            # 查找该商家的亚马逊产品
            merchant_products = [p for p in amazon_products if p.get('merchant_name') == merchant_name]
            
            for product in merchant_products:
                # 获取产品详情
                asin = product.get('asin', '')
                details = details_map.get(asin, {})
                
                # 创建合并记录
                merged_record = {
                    # YP商家信息
                    'yp_mid': merchant.get('mid', ''),
                    'yp_merchant_name': merchant_name,
                    'yp_commission': merchant.get('commission', ''),
                    
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
        return merged_data
    
    def save_comprehensive_data(self, data: List[Dict]):
        """保存综合数据"""
        print("\n" + "=" * 60)
        print("保存综合数据")
        print("=" * 60)
        
        # 保存JSON格式
        json_file = self.output_dir / 'comprehensive_yp_amazon_data.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON文件: {json_file}")
        
        # 保存CSV格式
        csv_file = self.output_dir / 'comprehensive_yp_amazon_data.csv'
        if data:
            fieldnames = list(data[0].keys())
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            print(f"✓ CSV文件: {csv_file}")
        
        return json_file, csv_file
    
    def create_backup(self):
        """创建数据备份"""
        print("\n" + "=" * 60)
        print("创建数据备份")
        print("=" * 60)
        
        # 创建带时间戳的备份目录
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'backup_{timestamp}'
        backup_path.mkdir(exist_ok=True)
        
        # 要备份的文件
        files_to_backup = [
            'output/yp_elite_merchants.json',
            'output/yp_elite_merchants.csv',
            'output/amazon_search_results_improved.json',
            'output/amazon_search_results_improved.csv',
            'output/amazon_product_details_improved.json',
            'output/amazon_product_details_improved.csv',
            'output/comprehensive_yp_amazon_data.json',
            'output/comprehensive_yp_amazon_data.csv',
        ]
        
        backed_up_files = []
        for file_path in files_to_backup:
            source = Path(file_path)
            if source.exists():
                dest = backup_path / source.name
                shutil.copy2(source, dest)
                backed_up_files.append(source.name)
                print(f"✓ 已备份: {source.name}")
        
        print(f"\n备份位置: {backup_path}")
        print(f"备份文件数: {len(backed_up_files)}")
        
        return backup_path
    
    def generate_statistics_report(self, yp_data: List[Dict], amazon_data: List[Dict], merged_data: List[Dict]):
        """生成统计报告"""
        print("\n" + "=" * 60)
        print("生成统计报告")
        print("=" * 60)
        
        # YP商家统计
        yp_mids = set([m.get('mid', '') for m in yp_data])
        yp_names = set([m.get('name', '') for m in yp_data])
        
        # 亚马逊产品统计
        amazon_asins = set([p.get('asin', '') for p in amazon_data])
        amazon_ratings = [float(r) for r in [p.get('rating', '0') for p in amazon_data] if r.replace('.', '').isdigit()]
        
        # 合并数据统计
        matched_merchants = set([m.get('yp_merchant_name', '') for m in merged_data])
        matched_asins = set([m.get('amazon_asin', '') for m in merged_data])
        
        # 生成报告
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            
            'yp_merchants': {
                'total_count': len(yp_data),
                'unique_mids': len(yp_mids),
                'unique_names': len(yp_names),
            },
            
            'amazon_products': {
                'total_count': len(amazon_data),
                'unique_asins': len(amazon_asins),
                'avg_rating': sum(amazon_ratings) / len(amazon_ratings) if amazon_ratings else 0,
                'high_rated_products': len([r for r in amazon_ratings if r >= 4.5]),
            },
            
            'merged_data': {
                'total_records': len(merged_data),
                'matched_merchants': len(matched_merchants),
                'matched_asins': len(matched_asins),
            },
            
            'coverage': {
                'merchant_coverage': f"{len(matched_merchants) / len(yp_names) * 100:.1f}%" if yp_names else "0%",
                'product_per_merchant': f"{len(amazon_data) / len(yp_names):.1f}" if yp_names else "0",
            }
        }
        
        # 保存统计报告
        stats_file = self.output_dir / 'data_statistics.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"✓ 统计报告: {stats_file}")
        
        return report
    
    def print_summary(self, report: Dict):
        """打印汇总信息"""
        print("\n" + "=" * 60)
        print("数据汇总")
        print("=" * 60)
        
        print(f"\n📊 YP商家数据:")
        print(f"  总数: {report['yp_merchants']['total_count']}")
        print(f"  唯一MID数: {report['yp_merchants']['unique_mids']}")
        
        print(f"\n📦 亚马逊产品数据:")
        print(f"  总数: {report['amazon_products']['total_count']}")
        print(f"  唯一ASIN数: {report['amazon_products']['unique_asins']}")
        print(f"  平均评分: {report['amazon_products']['avg_rating']:.2f}")
        print(f"  高评分产品数: {report['amazon_products']['high_rated_products']}")
        
        print(f"\n🔗 合并数据:")
        print(f"  总记录数: {report['merged_data']['total_records']}")
        print(f"  匹配商家数: {report['merged_data']['matched_merchants']}")
        print(f"  匹配产品数: {report['merged_data']['matched_asins']}")
        
        print(f"\n📈 覆盖率:")
        print(f"  商家覆盖率: {report['coverage']['merchant_coverage']}")
        print(f"  平均每商家产品数: {report['coverage']['product_per_merchant']}")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("YP商家数据和亚马逊产品数据整合系统")
    print("=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    merger = DataMerger()
    
    # 1. 合并数据
    merged_data = merger.merge_yp_amazon_data()
    
    # 2. 保存综合数据
    json_file, csv_file = merger.save_comprehensive_data(merged_data)
    
    # 3. 创建备份
    backup_path = merger.create_backup()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 4. 生成统计报告
    yp_data = merger.load_json(merger.output_dir / 'yp_elite_merchants.json')
    amazon_data = merger.load_json(merger.output_dir / 'amazon_search_results_improved.json')
    report = merger.generate_statistics_report(yp_data, amazon_data, merged_data)
    
    # 5. 打印汇总
    merger.print_summary(report)
    
    # 6. 创建README
    readme_content = f"""# YP商家和亚马逊产品数据集

## 生成时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 数据文件

### 1. YP商家数据
- `yp_elite_merchants.json` - YP商家数据（JSON格式）
- `yp_elite_merchants.csv` - YP商家数据（CSV格式）

### 2. 亚马逊产品数据
- `amazon_search_results_improved.json` - 亚马逊搜索结果（JSON格式）
- `amazon_search_results_improved.csv` - 亚马逊搜索结果（CSV格式）
- `amazon_product_details_improved.json` - 亚马逊产品详情（JSON格式）
- `amazon_product_details_improved.csv` - 亚马逊产品详情（CSV格式）

### 3. 综合数据
- `comprehensive_yp_amazon_data.json` - YP商家和亚马逊产品合并数据（JSON格式）
- `comprehensive_yp_amazon_data.csv` - YP商家和亚马逊产品合并数据（CSV格式）

### 4. 统计报告
- `data_statistics.json` - 数据统计报告

### 5. 备份文件
- 备份位置: backup/backup_{timestamp}/
- 备份时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 数据统计

- YP商家总数: {report['yp_merchants']['total_count']}
- 亚马逊产品总数: {report['amazon_products']['total_count']}
- 合并记录总数: {report['merged_data']['total_records']}
- 匹配商家数: {report['merged_data']['matched_merchants']}
- 平均评分: {report['amazon_products']['avg_rating']:.2f}

## 数据字段说明

### YP商家字段
- `mid`: 商家ID
- `name`: 商家名称
- `commission`: 佣金信息

### 亚马逊产品字段
- `asin`: 亚马逊产品ID
- `title`: 产品标题
- `price`: 价格
- `rating`: 评分
- `reviews`: 评论数
- `image_url`: 产品图片URL
- `product_url`: 产品链接
- `description`: 产品描述
- `brand`: 品牌
- `review_count`: 评论计数

### 综合数据字段
综合数据包含YP商家信息和亚马逊产品信息的所有字段，通过商家名称进行关联。

## 使用建议

1. **数据分析**: 使用 `comprehensive_yp_amazon_data.csv` 进行数据分析
2. **程序处理**: 使用 `comprehensive_yp_amazon_data.json` 进行程序处理
3. **查看统计**: 查看 `data_statistics.json` 了解数据概况
4. **数据备份**: 备份文件保存在 `backup/` 目录

## 注意事项

- 数据采集时间: 2026-03-22
- 数据来源: YP平台和Amazon.com
- 数据用途: 仅用于研究和分析
- 价格变动: 产品价格可能会随时间变化
- 产品可用性: 部分产品可能缺货或下架

---
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    readme_file = merger.output_dir / 'README_DATA.md'
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"\n✓ 数据说明文档: {readme_file}")
    
    print("\n" + "=" * 60)
    print("✅ 所有任务完成！")
    print("=" * 60)
    print(f"\n综合数据文件:")
    print(f"  JSON: {json_file}")
    print(f"  CSV: {csv_file}")
    print(f"\n备份位置: {backup_path}")
    print(f"说明文档: {readme_file}")
    print(f"统计报告: {merger.output_dir / 'data_statistics.json'}")


if __name__ == '__main__':
    main()
