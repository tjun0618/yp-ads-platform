#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
YP 平台品牌和商品采集脚本

使用 bb-browser 采集 YP 平台的品牌和商品信息，并上传到飞书

字段说明：
- 商家名称：YP 平台上的品牌名称
- 佣金：佣金率
- 类别：商品类别
- ASIN：亚马逊商品唯一标识
- 商品名称：商品标题
- 价格：商品价格
- 评分：商品评分
- 评论数：商品评论数
- 图片链接：商品图片 URL
- 商品链接：亚马逊原始链接
- 商品描述：商品详细描述
- 品牌：商品品牌
- 商品特性：商品特性标签
- 采集时间：数据采集时间
"""

import subprocess
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
import re


class YPMerchantsAndProductsCollector:
    """YP 平台品牌和商品采集器"""
    
    def __init__(self):
        self.merchants = []
        self.products = []
        self.collected_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def run_bb_browser(self, command: str) -> Optional[str]:
        """
        运行 bb-browser 命令
        
        Args:
            command: bb-browser 命令
        
        Returns:
            命令输出
        """
        try:
            result = subprocess.run(
                f"bb-browser {command}",
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"[错误] 命令执行失败: {command}")
                print(f"[错误] {result.stderr}")
                return None
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            print(f"[错误] 命令超时: {command}")
            return None
        except Exception as e:
            print(f"[错误] 命令执行异常: {e}")
            return None
    
    def collect_merchants(self) -> List[Dict]:
        """
        采集品牌列表
        
        Returns:
            品牌列表
        """
        print("\n" + "="*60)
        print("[步骤 1] 采集品牌列表")
        print("="*60)
        
        # 打开商家页面
        print("[信息] 打开品牌页面...")
        result = self.run_bb_browser("open https://www.yeahpromos.com/index/advert/index")
        
        if not result:
            print("[错误] 无法打开品牌页面")
            return []
        
        # 等待页面加载
        time.sleep(3)
        
        # 使用 JavaScript 提取品牌数据
        print("[信息] 提取品牌数据...")
        js_code = """
        (function() {
            var merchants = [];
            
            // 查找所有品牌行
            var rows = document.querySelectorAll('tbody tr');
            
            for (var i = 0; i < rows.length; i++) {
                var row = rows[i];
                var cells = row.querySelectorAll('td');
                
                if (cells.length >= 3) {
                    var merchant = {
                        name: cells[0].textContent.trim(),
                        commission: cells[1].textContent.trim(),
                        category: cells[2].textContent.trim()
                    };
                    merchants.push(merchant);
                }
            }
            
            return JSON.stringify(merchants);
        })();
        """
        
        # 执行 JavaScript
        result = self.run_bb_browser(f'eval "{js_code}"')
        
        if not result:
            print("[错误] 无法提取品牌数据")
            return []
        
        # 解析 JSON
        try:
            merchants_data = json.loads(result)
            self.merchants = merchants_data
            print(f"[成功] 采集到 {len(merchants_data)} 个品牌")
            
            # 打印前 5 个品牌
            print("\n前 5 个品牌:")
            for i, merchant in enumerate(merchants_data[:5]):
                print(f"  {i+1}. {merchant['name']} - {merchant['commission']} - {merchant['category']}")
            
            return merchants_data
        
        except json.JSONDecodeError as e:
            print(f"[错误] JSON 解析失败: {e}")
            print(f"[错误] 原始数据: {result[:500]}")
            return []
    
    def collect_products_from_merchant(self, merchant_name: str, max_products: int = 10) -> List[Dict]:
        """
        从指定品牌采集商品
        
        Args:
            merchant_name: 品牌名称
            max_products: 最大商品数量
        
        Returns:
            商品列表
        """
        print(f"\n[信息] 采集品牌 '{merchant_name}' 的商品...")
        
        # 打开商品页面
        print("[信息] 打开商品页面...")
        result = self.run_bb_browser("open https://www.yeahpromos.com/index/offer/products")
        
        if not result:
            print("[错误] 无法打开商品页面")
            return []
        
        # 等待页面加载
        time.sleep(3)
        
        # 使用 JavaScript 提取商品数据
        print("[信息] 提取商品数据...")
        js_code = f"""
        (function() {{
            var products = [];
            
            // 查找所有商品行
            var rows = document.querySelectorAll('tbody tr');
            
            for (var i = 0; i < Math.min(rows.length, {max_products}); i++) {{
                var row = rows[i];
                var cells = row.querySelectorAll('td');
                
                if (cells.length >= 8) {{
                    var product = {{
                        merchant_name: "{merchant_name}",
                        asin: cells[0].textContent.trim(),
                        product_name: cells[1].textContent.trim(),
                        price: cells[2].textContent.trim(),
                        rating: cells[3].textContent.trim(),
                        review_count: cells[4].textContent.trim(),
                        image_url: cells[5].textContent.trim(),
                        product_url: cells[6].textContent.trim(),
                        description: cells[7].textContent.trim()
                    }};
                    products.push(product);
                }}
            }}
            
            return JSON.stringify(products);
        }})();
        """
        
        # 执行 JavaScript
        result = self.run_bb_browser(f'eval "{js_code}"')
        
        if not result:
            print(f"[错误] 无法提取品牌 '{merchant_name}' 的商品数据")
            return []
        
        # 解析 JSON
        try:
            products_data = json.loads(result)
            print(f"[成功] 采集到 {len(products_data)} 个商品")
            return products_data
        
        except json.JSONDecodeError as e:
            print(f"[错误] JSON 解析失败: {e}")
            print(f"[错误] 原始数据: {result[:500]}")
            return []
    
    def collect_all_products(self, max_merchants: int = 5, max_products_per_merchant: int = 10) -> List[Dict]:
        """
        采集所有品牌的商品
        
        Args:
            max_merchants: 最大品牌数量
            max_products_per_merchant: 每个品牌最大商品数量
        
        Returns:
            所有商品列表
        """
        print("\n" + "="*60)
        print("[步骤 2] 采集商品信息")
        print("="*60)
        
        # 如果还没有采集品牌，先采集品牌
        if not self.merchants:
            self.collect_merchants()
        
        all_products = []
        
        # 采集前 N 个品牌的商品
        for i, merchant in enumerate(self.merchants[:max_merchants]):
            print(f"\n[{i+1}/{min(len(self.merchants), max_merchants)}] 采集品牌: {merchant['name']}")
            
            products = self.collect_products_from_merchant(
                merchant['name'],
                max_products=max_products_per_merchant
            )
            
            all_products.extend(products)
        
        self.products = all_products
        print(f"\n[成功] 总共采集到 {len(all_products)} 个商品")
        
        return all_products
    
    def export_to_json(self, filename: str):
        """
        导出数据到 JSON 文件
        
        Args:
            filename: 文件名
        """
        data = {
            "collected_time": self.collected_time,
            "merchants_count": len(self.merchants),
            "products_count": len(self.products),
            "merchants": self.merchants,
            "products": self.products
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"[成功] 数据已导出到 {filename}")
        
        except Exception as e:
            print(f"[错误] 导出 JSON 失败: {e}")
    
    def export_to_csv_for_feishu(self, filename: str):
        """
        导出数据到 CSV 文件（用于飞书）
        
        Args:
            filename: 文件名
        """
        import csv
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                fieldnames = [
                    '商家名称', '佣金', '类别', 'ASIN', '商品名称',
                    '价格', '评分', '评论数', '图片链接', '商品链接',
                    '商品描述', '品牌', '商品特性', '采集时间'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                
                # 写入商品数据
                for product in self.products:
                    row = {
                        '商家名称': product.get('merchant_name', ''),
                        '佣金': '',  # 从品牌数据中获取
                        '类别': '',  # 从品牌数据中获取
                        'ASIN': product.get('asin', ''),
                        '商品名称': product.get('product_name', ''),
                        '价格': product.get('price', ''),
                        '评分': product.get('rating', ''),
                        '评论数': product.get('review_count', ''),
                        '图片链接': product.get('image_url', ''),
                        '商品链接': product.get('product_url', ''),
                        '商品描述': product.get('description', ''),
                        '品牌': product.get('merchant_name', ''),  # 暂时使用商家名称作为品牌
                        '商品特性': '',
                        '采集时间': self.collected_time
                    }
                    writer.writerow(row)
            
            print(f"[成功] CSV 数据已导出到 {filename}")
        
        except Exception as e:
            print(f"[错误] 导出 CSV 失败: {e}")


def main():
    """主函数"""
    print("="*60)
    print("YP 平台品牌和商品采集器")
    print("="*60)
    
    # 创建采集器
    collector = YPMerchantsAndProductsCollector()
    
    # 采集品牌
    merchants = collector.collect_merchants()
    
    if not merchants:
        print("[错误] 无法采集品牌数据")
        return
    
    # 采集商品
    products = collector.collect_all_products(
        max_merchants=5,  # 采集前 5 个品牌
        max_products_per_merchant=10  # 每个品牌最多采集 10 个商品
    )
    
    if not products:
        print("[错误] 无法采集商品数据")
        return
    
    # 导出数据
    print("\n" + "="*60)
    print("[步骤 3] 导出数据")
    print("="*60)
    
    collector.export_to_json("yp_merchants_and_products.json")
    collector.export_to_csv_for_feishu("yp_merchants_and_products.csv")
    
    # 打印摘要
    print("\n" + "="*60)
    print("采集摘要")
    print("="*60)
    print(f"品牌数量: {len(collector.merchants)}")
    print(f"商品数量: {len(collector.products)}")
    print(f"采集时间: {collector.collected_time}")
    print("\n已完成采集！")
    print("下一步：使用飞书脚本上传 CSV 文件")


if __name__ == "__main__":
    main()
