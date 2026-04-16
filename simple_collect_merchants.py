#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简化的 YP 品牌和商品采集脚本

使用说明：
1. 确保已登录 YP 平台（使用 yp_login_skill.py）
2. 运行脚本：python simple_collect_merchants.py
"""

import subprocess
import json
import time
import csv
from datetime import datetime
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')


def run_bb_browser(command):
    """运行 bb-browser 命令"""
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
            return None
        
        return result.stdout
    
    except Exception as e:
        print(f"[错误] 命令执行异常: {e}")
        return None


def collect_merchants():
    """采集品牌列表"""
    print("\n[步骤 1] 采集品牌列表")
    print("="*60)
    
    # 打开品牌页面
    print("[信息] 打开品牌页面...")
    result = run_bb_browser("open https://www.yeahpromos.com/index/advert/index")
    
    if not result:
        print("[错误] 无法打开品牌页面")
        return []
    
    time.sleep(3)
    
    # 获取页面 HTML
    print("[信息] 获取页面内容...")
    result = run_bb_browser('eval "document.documentElement.outerHTML"')
    
    if not result:
        print("[错误] 无法获取页面内容")
        return []
    
    # 保存 HTML 到文件
    html_file = "merchants_page.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"[信息] 页面内容已保存到 {html_file}")
    
    # 使用 BeautifulSoup 解析
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(result, 'html.parser')
        
        # 查找所有品牌行
        merchants = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            
            if len(cells) >= 3:
                merchant_name = cells[0].get_text(strip=True)
                commission = cells[1].get_text(strip=True)
                category = cells[2].get_text(strip=True)
                
                # 过滤空行和标题行
                if merchant_name and merchant_name != "Merchant":
                    merchants.append({
                        'merchant_name': merchant_name,
                        'commission': commission,
                        'category': category
                    })
        
        print(f"[成功] 采集到 {len(merchants)} 个品牌")
        
        # 打印前 5 个品牌
        print("\n前 5 个品牌:")
        for i, merchant in enumerate(merchants[:5]):
            print(f"  {i+1}. {merchant['merchant_name']} - {merchant['commission']} - {merchant['category']}")
        
        return merchants
    
    except ImportError:
        print("[错误] 未安装 BeautifulSoup")
        print("请运行: pip install beautifulsoup4")
        return []
    except Exception as e:
        print(f"[错误] 解析 HTML 失败: {e}")
        return []


def collect_products():
    """采集商品列表"""
    print("\n[步骤 2] 采集商品列表")
    print("="*60)
    
    # 打开商品页面
    print("[信息] 打开商品页面...")
    result = run_bb_browser("open https://www.yeahpromos.com/index/offer/products")
    
    if not result:
        print("[错误] 无法打开商品页面")
        return []
    
    time.sleep(3)
    
    # 获取页面 HTML
    print("[信息] 获取页面内容...")
    result = run_bb_browser('eval "document.documentElement.outerHTML"')
    
    if not result:
        print("[错误] 无法获取页面内容")
        return []
    
    # 保存 HTML 到文件
    html_file = "products_page.html"
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"[信息] 页面内容已保存到 {html_file}")
    
    # 使用 BeautifulSoup 解析
    from bs4 import BeautifulSoup
    
    try:
        soup = BeautifulSoup(result, 'html.parser')
        
        # 查找所有商品行
        products = []
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            
            if len(cells) >= 8:
                asin = cells[0].get_text(strip=True)
                product_name = cells[1].get_text(strip=True)
                price = cells[2].get_text(strip=True)
                rating = cells[3].get_text(strip=True)
                review_count = cells[4].get_text(strip=True)
                image_url = cells[5].get_text(strip=True)
                product_url = cells[6].get_text(strip=True)
                description = cells[7].get_text(strip=True)
                
                # 过滤空行和标题行
                if asin and asin != "ASIN":
                    products.append({
                        'asin': asin,
                        'product_name': product_name,
                        'price': price,
                        'rating': rating,
                        'review_count': review_count,
                        'image_url': image_url,
                        'product_url': product_url,
                        'description': description
                    })
        
        print(f"[成功] 采集到 {len(products)} 个商品")
        
        # 打印前 5 个商品
        print("\n前 5 个商品:")
        for i, product in enumerate(products[:5]):
            print(f"  {i+1}. {product['product_name']} - {product['price']}")
        
        return products
    
    except ImportError:
        print("[错误] 未安装 BeautifulSoup")
        print("请运行: pip install beautifulsoup4")
        return []
    except Exception as e:
        print(f"[错误] 解析 HTML 失败: {e}")
        return []


def export_to_csv(merchants, products):
    """导出数据到 CSV 文件"""
    print("\n[步骤 3] 导出数据到 CSV")
    print("="*60)
    
    try:
        csv_file = "yp_merchants_and_products.csv"
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                '商家名称', '佣金', '类别', 'ASIN', '商品名称',
                '价格', '评分', '评论数', '图片链接', '商品链接',
                '商品描述', '品牌', '商品特性', '采集时间'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            # 写入商品数据（每个商品对应一行）
            collected_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for product in products:
                # 查找对应品牌的佣金和类别
                merchant_name = "Unknown"
                commission = ""
                category = ""
                
                # 这里简化处理，实际需要根据品牌名称匹配
                if merchants:
                    merchant = merchants[0]
                    merchant_name = merchant.get('merchant_name', '')
                    commission = merchant.get('commission', '')
                    category = merchant.get('category', '')
                
                row = {
                    '商家名称': merchant_name,
                    '佣金': commission,
                    '类别': category,
                    'ASIN': product.get('asin', ''),
                    '商品名称': product.get('product_name', ''),
                    '价格': product.get('price', ''),
                    '评分': product.get('rating', ''),
                    '评论数': product.get('review_count', ''),
                    '图片链接': product.get('image_url', ''),
                    '商品链接': product.get('product_url', ''),
                    '商品描述': product.get('description', ''),
                    '品牌': merchant_name,
                    '商品特性': '',
                    '采集时间': collected_time
                }
                writer.writerow(row)
        
        print(f"[成功] 数据已导出到 {csv_file}")
    
    except Exception as e:
        print(f"[错误] 导出 CSV 失败: {e}")


def main():
    """主函数"""
    print("="*60)
    print("YP 平台品牌和商品采集器（简化版）")
    print("="*60)
    
    # 采集品牌
    merchants = collect_merchants()
    
    if not merchants:
        print("[错误] 无法采集品牌数据")
        return
    
    # 采集商品
    products = collect_products()
    
    if not products:
        print("[错误] 无法采集商品数据")
        return
    
    # 导出数据
    export_to_csv(merchants, products)
    
    # 打印摘要
    print("\n" + "="*60)
    print("采集摘要")
    print("="*60)
    print(f"品牌数量: {len(merchants)}")
    print(f"商品数量: {len(products)}")
    print("\n已完成采集！")
    print("下一步：使用 upload_merchants_to_feishu.py 上传到飞书")


if __name__ == "__main__":
    main()
