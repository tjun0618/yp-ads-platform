"""
改进版亚马逊商品爬取脚本
使用BeautifulSoup进行更精确的HTML解析
"""

import requests
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
import sys
import io
from bs4 import BeautifulSoup

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
    
    def search_amazon_product(self, merchant_name: str, max_results: int = 10) -> List[Dict]:
        """在亚马逊搜索商家名称并返回产品列表"""
        try:
            # 构建搜索URL
            search_query = merchant_name.replace(' ', '+')
            search_url = f'https://www.amazon.com/s?k={search_query}'
            
            print(f"正在搜索: {merchant_name}")
            
            # 发送请求
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            products = []
            
            # 查找所有产品容器
            product_containers = soup.find_all('div', {'data-component-type': 's-search-result'})
            
            print(f"  找到 {len(product_containers)} 个产品容器")
            
            for container in product_containers[:max_results]:
                try:
                    # 提取ASIN
                    asin = container.get('data-asin')
                    if not asin:
                        continue
                    
                    # 提取产品标题
                    title_element = container.find('h2', class_='a-size-mini')
                    if not title_element:
                        title_element = container.find('h2')
                    
                    if title_element:
                        title_link = title_element.find('a')
                        if title_link:
                            title = title_link.get_text(strip=True)
                        else:
                            title_span = title_element.find('span')
                            title = title_span.get_text(strip=True) if title_span else 'N/A'
                    else:
                        title = 'N/A'
                    
                    # 提取价格
                    price_element = container.find('span', class_='a-price')
                    if price_element:
                        price_whole = price_element.find('span', class_='a-price-whole')
                        price_fraction = price_element.find('span', class_='a-price-fraction')
                        if price_whole and price_fraction:
                            price = f"${price_whole.get_text(strip=True)}.{price_fraction.get_text(strip=True)}"
                        else:
                            price = price_element.get_text(strip=True)
                    else:
                        price = 'N/A'
                    
                    # 提取评分
                    rating_element = container.find('span', class_='a-icon-alt')
                    if rating_element:
                        rating_text = rating_element.get_text(strip=True)
                        rating_match = re.search(r'([0-9]\.[0-9])', rating_text)
                        rating = rating_match.group(1) if rating_match else 'N/A'
                    else:
                        rating = 'N/A'
                    
                    # 提取评论数
                    review_element = container.find('span', {'aria-label': re.compile(r'reviews')})
                    if review_element:
                        reviews = review_element.get_text(strip=True)
                    else:
                        reviews = 'N/A'
                    
                    # 提取图片URL
                    img_element = container.find('img', class_='s-image')
                    image_url = img_element.get('src', 'N/A') if img_element else 'N/A'
                    
                    product = {
                        'asin': asin,
                        'title': title,
                        'price': price,
                        'rating': rating,
                        'reviews': reviews,
                        'image_url': image_url,
                        'merchant_name': merchant_name,
                        'search_url': search_url,
                        'product_url': f'https://www.amazon.com/dp/{asin}',
                        'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    products.append(product)
                    
                except Exception as e:
                    print(f"    解析产品时出错: {e}")
                    continue
            
            print(f"  成功提取 {len(products)} 个产品")
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
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            details = {
                'asin': asin,
                'product_url': product_url,
                'collected_at': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # 提取标题
            title_element = soup.find('span', id='productTitle')
            if title_element:
                details['title'] = title_element.get_text(strip=True)
            
            # 提取价格
            price_element = soup.find('span', id='priceblock_ourprice')
            if not price_element:
                price_element = soup.find('span', id='priceblock_dealprice')
            if price_element:
                details['price'] = price_element.get_text(strip=True)
            
            # 提取评分
            rating_element = soup.find('span', class_='a-icon-alt')
            if rating_element:
                rating_text = rating_element.get_text(strip=True)
                rating_match = re.search(r'([0-9]\.[0-9])', rating_text)
                details['rating'] = rating_match.group(1) if rating_match else 'N/A'
            
            # 提取评论数
            review_count_element = soup.find('span', id='acrCustomerReviewText')
            if review_count_element:
                details['review_count'] = review_count_element.get_text(strip=True)
            
            # 提取描述
            desc_element = soup.find('div', id='productDescription')
            if desc_element:
                desc = desc_element.get_text(strip=True)
                details['description'] = desc[:1000]  # 限制1000字符
            
            # 提取特性
            features = []
            feature_list = soup.find('ul', id='feature-bullets')
            if feature_list:
                for li in feature_list.find_all('li'):
                    span = li.find('span')
                    if span:
                        feature_text = span.get_text(strip=True)
                        if feature_text and not feature_text.startswith('Make sure this fits'):
                            features.append(feature_text)
            
            details['features'] = features[:8]  # 限制8个特性
            
            # 提取图片
            img_elements = soup.find_all('img', id=re.compile(r'landingImage'))
            if img_elements:
                images = [img.get('src') for img in img_elements]
                details['images'] = images[:5]  # 限制5张图片
            
            # 提取品牌
            brand_element = soup.find('a', id='bylineInfo')
            if brand_element:
                details['brand'] = brand_element.get_text(strip=True)
            
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
        'Zyllion',
        'Roborock',
        'Protect Life',
        'Ulike',
        'PuroAir',
        'Nutricost',
        'REDTIGER',
    ]
    
    print("=" * 60)
    print("开始爬取亚马逊商品数据（改进版）")
    print("=" * 60)
    print(f"需要爬取 {len(merchants)} 个商家\n")
    
    all_products = []
    all_details = []
    
    # 控制爬取数量以避免被亚马逊封禁
    max_search_merchants = 8  # 最多搜索8个商家
    max_products_per_merchant = 5  # 每个商家最多5个产品
    max_detail_scrapes = 4  # 最多爬取4个产品详情
    
    for i, merchant in enumerate(merchants[:max_search_merchants], 1):
        print(f"\n[{i}/{len(merchants)}] 处理商家: {merchant}")
        
        # 搜索产品
        products = scraper.search_amazon_product(merchant, max_results=max_products_per_merchant)
        all_products.extend(products)
        
        # 爬取前几个产品的详情
        for j, product in enumerate(products[:max_detail_scrapes], 1):
            print(f"  [{j}/{len(products)}] 爬取详情: {product['asin']} - {product['title'][:50]}")
            details = scraper.scrape_product_details(product['asin'])
            if details:
                all_details.append(details)
            
            # 添加延迟以避免被检测
            time.sleep(3)
        
        # 商家之间的延迟
        time.sleep(4)
    
    # 保存结果
    print("\n" + "=" * 60)
    print("保存结果")
    print("=" * 60)
    
    # 保存搜索结果
    search_file = scraper.output_dir / 'amazon_search_results_improved.json'
    with open(search_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, ensure_ascii=False, indent=2)
    print(f"搜索结果已保存到: {search_file}")
    print(f"  共 {len(all_products)} 个产品")
    
    # 保存产品详情
    details_file = scraper.output_dir / 'amazon_product_details_improved.json'
    with open(details_file, 'w', encoding='utf-8') as f:
        json.dump(all_details, f, ensure_ascii=False, indent=2)
    print(f"产品详情已保存到: {details_file}")
    print(f"  共 {len(all_details)} 个产品详情")
    
    # 生成CSV格式
    import csv
    
    # 搜索结果CSV
    search_csv = scraper.output_dir / 'amazon_search_results_improved.csv'
    if all_products:
        with open(search_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_products[0].keys())
            writer.writeheader()
            writer.writerows(all_products)
        print(f"搜索结果CSV已保存到: {search_csv}")
    
    # 产品详情CSV
    details_csv = scraper.output_dir / 'amazon_product_details_improved.csv'
    if all_details:
        # 处理嵌套字段，收集所有字段名
        all_fieldnames = set()
        for detail in all_details:
            all_fieldnames.update(detail.keys())
        
        # 处理嵌套字段并转换
        flat_details = []
        for detail in all_details:
            flat_detail = {}
            for key, value in detail.items():
                if isinstance(value, list):
                    flat_detail[key] = ' | '.join(str(v) for v in value)
                else:
                    flat_detail[key] = str(value) if value is not None else ''
            flat_details.append(flat_detail)
        
        fieldnames = list(all_fieldnames)
        with open(details_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_details)
        print(f"产品详情CSV已保存到: {details_csv}")
    
    print("\n" + "=" * 60)
    print("爬取完成！")
    print("=" * 60)
    print(f"总爬取商家数: {len(merchants[:max_search_merchants])}")
    print(f"总搜索产品数: {len(all_products)}")
    print(f"总爬取详情数: {len(all_details)}")
    print("\n注意事项:")
    print("1. 使用BeautifulSoup进行更精确的HTML解析")
    print("2. 增加了更多产品字段（品牌、评论数、图片等）")
    print("3. 限制了爬取速度以避免被封禁")
    print("4. 可以通过调整参数来控制爬取数量")


if __name__ == '__main__':
    main()
