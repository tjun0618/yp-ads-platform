"""
爬取亚马逊商品数据脚本
从YP商家数据中提取亚马逊ASIN，并爬取对应的商品信息
"""

import requests
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')


class AmazonScraper:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self.headers)
        
        # 创建输出目录
        self.output_dir = Path('output')
        self.output_dir.mkdir(exist_ok=True)
    
    def parse_asin_from_url(self, url: str) -> Optional[str]:
        """从URL中提取ASIN"""
        # Amazon ASIN通常是10位字母数字组合
        asin_pattern = r'/([A-Z0-9]{10})(?:/|$|\?)'
        match = re.search(asin_pattern, url)
        return match.group(1) if match else None
    
    def search_amazon_product(self, merchant_name: str) -> List[Dict]:
        """在亚马逊搜索商家名称并返回产品列表"""
        try:
            # 构建搜索URL
            search_query = merchant_name.replace(' ', '+')
            search_url = f'https://www.amazon.com/s?k={search_query}'
            
            print(f"正在搜索: {merchant_name}")
            
            # 发送请求
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            # 解析HTML获取产品信息
            products = []
            html = response.text
            
            # 使用正则表达式提取产品信息
            # ASIN
            asin_pattern = r'data-asin="([^"]+)"'
            asins = re.findall(asin_pattern, html)
            
            # 产品标题
            title_pattern = r'<span\s+class="a-size-medium[^"]*"[^>]*>([^<]+)</span>'
            titles = re.findall(title_pattern, html)
            
            # 价格
            price_pattern = r'\$([0-9,]+\.[0-9]{2})'
            prices = re.findall(price_pattern, html)
            
            # 评分
            rating_pattern = r'([0-9]\.[0-9])\s+out\s+of\s+5'
            ratings = re.findall(rating_pattern, html)
            
            # 组合产品信息
            num_products = min(len(asins), len(titles), len(prices))
            for i in range(num_products):
                product = {
                    'asin': asins[i],
                    'title': titles[i].strip(),
                    'price': prices[i],
                    'rating': ratings[i] if i < len(ratings) else 'N/A',
                    'merchant_name': merchant_name,
                    'search_url': search_url,
                    'product_url': f'https://www.amazon.com/dp/{asins[i]}',
                    'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                products.append(product)
                
            print(f"  找到 {len(products)} 个产品")
            return products
            
        except Exception as e:
            print(f"  错误: {e}")
            return []
    
    def scrape_product_details(self, asin: str) -> Optional[Dict]:
        """爬取单个产品的详细信息"""
        try:
            product_url = f'https://www.amazon.com/dp/{asin}'
            print(f"正在爬取产品详情: {asin}")
            
            response = self.session.get(product_url, timeout=10)
            response.raise_for_status()
            
            html = response.text
            
            # 提取产品详细信息
            details = {
                'asin': asin,
                'product_url': product_url,
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 提取标题
            title_pattern = r'<title\s+id="productTitle"[^>]*>([^<]+)</title>'
            title_match = re.search(title_pattern, html)
            if title_match:
                details['title'] = title_match.group(1).strip()
            
            # 提取价格
            price_pattern = r'<span\s+id="priceblock_ourprice"[^>]*>([^<]+)</span>'
            price_match = re.search(price_pattern, html)
            if price_match:
                details['price'] = price_match.group(1).strip()
            
            # 提取描述
            desc_pattern = r'<div\s+id="productDescription"[^>]*>(.*?)</div>'
            desc_match = re.search(desc_pattern, html, re.DOTALL)
            if desc_match:
                # 移除HTML标签
                desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1))
                details['description'] = desc.strip()[:500]  # 限制500字符
            
            # 提取特性
            feature_pattern = r'<li><span\s+class="a-list-item">([^<]+)</span></li>'
            features = re.findall(feature_pattern, html)
            if features:
                details['features'] = features[:5]  # 限制5个特性
            
            print(f"  成功爬取产品详情")
            return details
            
        except Exception as e:
            print(f"  错误: {e}")
            return None


def main():
    """主函数"""
    scraper = AmazonScraper()
    
    # 示例商家列表（从YP采集的商家）
    merchants = [
        'OlliePets_US',
        'Sik Silk PL',
        'Lepro',
        'iHerb',
        'DOVOH',
        'Hoka US',
        'VANTRUE',
        'SUNUV',
        'Allpowers',
        'KiddyCare',
        'Perfect Remedy',
        'Amazon Music',
        'Ikarao',
        'Zyllion, Inc.',
        'Roborock Amazon Seller',
        'Protect Life',
        'Ulike',
        'PuroAir',
        'Nutricost',
        'REDTIGER',
        'Brooklyn Nets',
    ]
    
    print("=" * 60)
    print("开始爬取亚马逊商品数据")
    print("=" * 60)
    print(f"需要爬取 {len(merchants)} 个商家\n")
    
    all_products = []
    all_details = []
    
    # 限制爬取数量以避免被亚马逊封禁
    max_search_results = 5  # 每个商家最多搜索5个产品
    max_detail_scrapes = 3  # 最多爬取3个产品详情
    
    for i, merchant in enumerate(merchants[:max_search_results], 1):
        print(f"\n[{i}/{len(merchants)}] 处理商家: {merchant}")
        
        # 搜索产品
        products = scraper.search_amazon_product(merchant)
        all_products.extend(products)
        
        # 爬取前几个产品的详情
        for j, product in enumerate(products[:max_detail_scrapes], 1):
            print(f"  [{j}/{len(products)}] 爬取详情: {product['asin']}")
            details = scraper.scrape_product_details(product['asin'])
            if details:
                all_details.append(details)
            
            # 添加延迟以避免被检测
            time.sleep(2)
        
        # 商家之间的延迟
        time.sleep(3)
    
    # 保存结果
    print("\n" + "=" * 60)
    print("保存结果")
    print("=" * 60)
    
    # 保存搜索结果
    search_file = scraper.output_dir / 'amazon_search_results.json'
    with open(search_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)
    print(f"搜索结果已保存到: {search_file}")
    print(f"  共 {len(all_products)} 个产品")
    
    # 保存产品详情
    details_file = scraper.output_dir / 'amazon_product_details.json'
    with open(details_file, 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=2)
    print(f"产品详情已保存到: {details_file}")
    print(f"  共 {len(all_details)} 个产品详情")
    
    # 生成CSV格式
    import csv
    
    # 搜索结果CSV
    search_csv = scraper.output_dir / 'amazon_search_results.csv'
    if all_products:
        with open(search_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_products[0].keys())
            writer.writeheader()
            writer.writerows(all_products)
        print(f"搜索结果CSV已保存到: {search_csv}")
    
    # 产品详情CSV
    details_csv = scraper.output_dir / 'amazon_product_details.csv'
    if all_details:
        # 处理嵌套字段
        flat_details = []
        for detail in all_details:
            flat_detail = detail.copy()
            if 'features' in flat_detail:
                flat_detail['features'] = '; '.join(flat_detail['features'])
            flat_details.append(flat_detail)
        
        with open(details_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=flat_details[0].keys())
            writer.writeheader()
            writer.writerows(flat_details)
        print(f"产品详情CSV已保存到: {details_csv}")
    
    print("\n" + "=" * 60)
    print("爬取完成！")
    print("=" * 60)
    print(f"总爬取商家数: {len(merchants[:max_search_results])}")
    print(f"总搜索产品数: {len(all_products)}")
    print(f"总爬取详情数: {len(all_details)}")
    print("\n注意事项:")
    print("1. 为了避免被亚马逊封禁，限制了爬取数量")
    print("2. 实际使用时可以增加延迟或使用代理IP")
    print("3. 可以通过调整 max_search_results 和 max_detail_scrapes 参数来控制爬取数量")


if __name__ == '__main__':
    main()
