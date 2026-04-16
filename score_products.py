#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
商品投放价值评分脚本
计算商品的投资价值评分并更新到 yp_us_products.investment_score 字段

评分公式：
投放价值分 = 
  min(佣金率(%) × 商品价格($) × 0.4, 30)     # 单次转化佣金价值，上限30分
+ min(评论数/500, 1) × 20                      # 市场验证，上限20分
+ (评分/5) × 20                                # 商品质量，上限20分
+ min(cookie天数/30, 1) × 10                   # Cookie价值，上限10分
+ min(SEMrush付费词数/100, 1) × 20             # 竞争热度，上限20分
"""

import os
import sys
import argparse
import logging
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json
from decimal import Decimal
from pathlib import Path

# 配置常量
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'affiliate_marketing',
    'user': 'root',
    'password': 'admin',
    'charset': 'utf8mb4',
}

# 设置日志
def setup_logging():
    """配置日志记录"""
    LOGS_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger('yp_score_products')
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    file_handler = logging.FileHandler(LOGS_DIR / 'score_products.log', encoding='utf-8')
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def parse_paid_keywords_count(keywords_json: Optional[str]) -> int:
    """解析SEMrush付费关键词数量"""
    if not keywords_json:
        return 0
    
    try:
        if isinstance(keywords_json, str):
            keywords_data = json.loads(keywords_json)
        else:
            keywords_data = keywords_json
            
        # 确保keywords_data是一个列表
        if isinstance(keywords_data, list):
            return len(keywords_data)
        else:
            return 0
    except Exception as e:
        logger.debug(f"解析付费关键词JSON失败: {e}")
        return 0

def calculate_investment_score(row: Dict) -> float:
    """计算商品的投资价值评分"""
    score = 0.0
    
    # 1. 佣金价值分: min(佣金率(%) × 商品价格($) × 0.4, 30)
    try:
        commission_pct = float(str(row.get('commission', '0')).replace('%', '').strip())
        price = float(str(row.get('price', '0')).replace('$', '').replace(',', '').strip())
        commission_value = commission_pct * price * 0.4
        score += min(commission_value, 30.0)
    except Exception as e:
        logger.debug(f"计算佣金价值分失败: {e}")
    
    # 2. 市场验证分: min(评论数/500, 1) × 20
    try:
        review_count = float(str(row.get('review_count', '0')).replace(',', '').strip())
        market_validation = min(review_count / 500.0, 1.0)
        score += market_validation * 20.0
    except Exception as e:
        logger.debug(f"计算市场验证分失败: {e}")
    
    # 3. 商品质量分: (评分/5) × 20
    try:
        rating = float(str(row.get('rating', '0')).strip())
        quality_score = (rating / 5.0) * 20.0
        score += quality_score
    except Exception as e:
        logger.debug(f"计算商品质量分失败: {e}")
    
    # 4. Cookie价值分: min(cookie天数/30, 1) × 10
    try:
        cookie_days = int(str(row.get('cookie_days', '0')).strip())
        cookie_value = min(cookie_days / 30.0, 1.0)
        score += cookie_value * 10.0
    except Exception as e:
        logger.debug(f"计算Cookie价值分失败: {e}")
    
    # 5. 竞争热度分: min(SEMrush付费词数/100, 1) × 20
    try:
        paid_keywords_count = parse_paid_keywords_count(row.get('top_paid_keywords'))
        competition_heat = min(paid_keywords_count / 100.0, 1.0)
        score += competition_heat * 20.0
    except Exception as e:
        logger.debug(f"计算竞争热度分失败: {e}")
    
    # 确保分数在0-100范围内
    return max(0.0, min(100.0, score))

def update_single_asin(asin: str) -> Tuple[bool, Optional[Dict]]:
    """更新单个ASIN的评分"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 获取商品数据
        query = """
            SELECT 
                yp.asin,
                yp.price,
                yp.commission,
                yp.cookie_days,
                apd.rating,
                apd.review_count,
                scd.top_paid_keywords
            FROM yp_us_products yp

            LEFT JOIN amazon_product_details apd ON yp.asin = apd.asin

            LEFT JOIN semrush_competitor_data scd ON yp.merchant_name = scd.domain

            WHERE yp.asin = %s

            LIMIT 1

        """

        
        cursor.execute(query, (asin,))

        result = cursor.fetchone()

        
        if not result:

            logger.error(f"未找到ASIN: {asin}")

            cursor.close()

            conn.close()

            return False, None

        
        # 计算评分

        investment_score = calculate_investment_score(result)

        
        # 更新数据库

        update_query = "UPDATE yp_us_products SET investment_score = %s WHERE asin = %s"

        cursor.execute(update_query, (investment_score, asin))

        conn.commit()

        
        stats = {
            "asin": asin,
            "score": round(investment_score, 2),
            "updated_at": datetime.now().isoformat()
        }

        
        cursor.close()

        conn.close()

        
        logger.info(f"ASIN {asin} 评分更新成功: {investment_score:.2f}分")

        return True, stats

        
    except Error as e:

        logger.error(f"更新ASIN {asin} 评分失败: {e}")

        return False, None

def update_top_products(limit: int = 50) -> Dict:
    """更新Top N高价值商品的评分"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        cursor = conn.cursor(dictionary=True)

        
        # 获取Top N商品数据（基于当前investment_score排序）

        query = """
            SELECT 
                yp.asin,
                yp.price,
                yp.commission,
                yp.cookie_days,
                apd.rating,
                apd.review_count,
                scd.top_paid_keywords

            FROM yp_us_products yp

            LEFT JOIN amazon_product_details apd ON yp.asin = apd.asin

            LEFT JOIN semrush_competitor_data scd ON yp.merchant_name = scd.domain

            ORDER BY yp.investment_score DESC

            LIMIT %s

        """

        
        cursor.execute(query, (limit,))

        results = cursor.fetchall()

        
        if not results:

            logger.warning(f"未找到商品数据")

            cursor.close()

            conn.close()

            return {"updated": 0, "avg_score": 0, "top10": []}

        
        updated_count = 0

        total_score = 0.0

        top10_asin = []

        
        for i, row in enumerate(results):

            asin = row.get('asin')

            
            # 计算评分

            investment_score = calculate_investment_score(row)

            
            # 更新数据库

            update_query = "UPDATE yp_us_products SET investment_score = %s WHERE asin = %s"

            cursor.execute(update_query, (investment_score, asin))

            
            updated_count += 1

            total_score += investment_score

            
            # 记录Top10

            if i < 10:

                top10_asin.append({
                    "asin": asin,
                    "score": round(investment_score, 2),
                    "rank": i + 1
                })

            
            # 每10条记录提交一次

            if updated_count % 10 == 0:

                conn.commit()

        
        # 最终提交

        conn.commit()

        
        # 计算平均分

        avg_score = total_score / updated_count if updated_count > 0 else 0

        
        stats = {

            "updated": updated_count,

            "avg_score": round(avg_score, 2),

            "top10": top10_asin,

            "total_updated": updated_count,

            "timestamp": datetime.now().isoformat()

        }

        
        cursor.close()

        conn.close()

        
        logger.info(f"Top{limit}商品评分更新完成: 更新{updated_count}条, 平均分{avg_score:.2f}")

        
        return stats

        
    except Error as e:

        logger.error(f"更新Top{limit}商品评分失败: {e}")

        return {"updated": 0, "avg_score": 0, "top10": []}

def update_all_products(batch_size: int = 100) -> Dict:
    """更新所有商品的评分（分批处理）"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)

        cursor = conn.cursor(dictionary=True)

        
        # 获取商品总数

        cursor.execute("SELECT COUNT(*) as total FROM yp_us_products")

        total_count = cursor.fetchone()['total']

        
        logger.info(f"开始更新所有商品评分, 总数: {total_count}, 批次大小: {batch_size}")

        
        updated_total = 0

        total_score_sum = 0.0

        batch_number = 0

        
        # 分批处理

        for offset in range(0, total_count, batch_size):

            batch_number += 1

            
            # 获取本批次商品数据

            query = """
                SELECT 
                    yp.asin,
                    yp.price,
                    yp.commission,
                    yp.cookie_days,
                    apd.rating,
                    apd.review_count,
                    scd.top_paid_keywords

                FROM yp_us_products yp

                LEFT JOIN amazon_product_details apd ON yp.asin = apd.asin

                LEFT JOIN semrush_competitor_data scd ON yp.merchant_name = scd.domain

                ORDER BY yp.id

                LIMIT %s OFFSET %s

            """

            
            cursor.execute(query, (batch_size, offset))

            results = cursor.fetchall()

            
            if not results:

                break

            
            # 更新本批次数据

            for row in results:

                asin = row.get('asin')

                investment_score = calculate_investment_score(row)

                
                update_query = "UPDATE yp_us_products SET investment_score = %s WHERE asin = %s"

                cursor.execute(update_query, (investment_score, asin))

                
                updated_total += 1

                total_score_sum += investment_score

            
            # 每批次提交一次

            conn.commit()

            
            logger.info(f"批次{batch_number}完成: 已更新{updated_total}/{total_count}条商品")

        
        # 获取Top10作为统计

        cursor.execute("""
            SELECT asin, investment_score 
            FROM yp_us_products 
            ORDER BY investment_score DESC 
            LIMIT 10
        """)

        top10_results = cursor.fetchall()

        
        top10_asin = []
        for i, row in enumerate(top10_results):
            top10_asin.append({
                "asin": row['asin'],
                "score": round(row['investment_score'], 2),
                "rank": i + 1
            })

        
        avg_score = total_score_sum / updated_total if updated_total > 0 else 0

        
        stats = {

            "updated": updated_total,

            "avg_score": round(avg_score, 2),

            "top10": top10_asin,

            "total_count": total_count,

            "batches": batch_number,

            "timestamp": datetime.now().isoformat()

        }

        
        cursor.close()

        conn.close()

        
        logger.info(f"所有商品评分更新完成: 更新{updated_total}/{total_count}条, 平均分{avg_score:.2f}")

        
        return stats

        
    except Error as e:

        logger.error(f"更新所有商品评分失败: {e}")

        return {"updated": 0, "avg_score": 0, "top10": []}

def generate_stats_report(stats: Dict, title: str) -> None:
    """生成统计报告"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")
    
    if not stats or stats.get("updated", 0) == 0:
        print("⚠️  没有商品被更新")
        return
    
    print(f"📊 更新统计:")
    print(f"   • 已更新商品数: {stats['updated']}")
    print(f"   • 平均评分: {stats['avg_score']:.2f}分")
    
    if stats.get("total_count"):
        print(f"   • 总商品数: {stats['total_count']}")
    if stats.get("batches"):
        print(f"   • 处理批次: {stats['batches']}")
    
    if stats.get("top10") and len(stats["top10"]) > 0:
        print(f"\n🏆 Top10商品:")
        for item in stats['top10']:
            if isinstance(item, dict):
                print(f"   #{item.get('rank', 0)} ASIN: {item.get('asin', 'N/A')} - {item.get('score', 0):.2f}分")
    
    print(f"\n⏰ 更新时间: {stats.get('timestamp', 'N/A')}")
    print(f"{'='*60}")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='商品投放价值评分脚本')
    parser.add_argument('--asin', type=str, help='更新单个ASIN的评分')
    parser.add_argument('--top', type=int, default=50, help='更新TopN高价值商品评分，默认50')
    parser.add_argument('--all', action='store_true', help='更新所有商品评分')
    parser.add_argument('--batch-size', type=int, default=100, help='批处理大小，默认100')
    parser.add_argument('--stats', action='store_true', help='显示当前评分统计')
    
    args = parser.parse_args()
    
    logger.info("开始商品评分任务")
    
    # 根据参数执行相应操作
    if args.asin:
        success, stats = update_single_asin(args.asin)
        if success and stats:
            generate_stats_report({"updated": 1, "avg_score": stats["score"], "top10": [stats]}, 
                                f"单个ASIN评分更新: {args.asin}")
    
    elif args.all:
        stats = update_all_products(args.batch_size)
        generate_stats_report(stats, "全部商品评分更新")
    
    else:
        # 默认更新TopN
        stats = update_top_products(args.top)
        generate_stats_report(stats, f"Top{args.top}商品评分更新")
    
    # 显示总体统计
    if args.stats:
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
            
            # 获取总体统计
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    AVG(investment_score) as avg_score,
                    MAX(investment_score) as max_score,
                    MIN(investment_score) as min_score
                FROM yp_us_products
                WHERE investment_score > 0
            """)
            
            overall_stats = cursor.fetchone()
            
            if overall_stats:
                print(f"\n📈 总体统计:")
                print(f"   • 已评分商品数: {overall_stats['total']}")
                print(f"   • 平均分: {overall_stats['avg_score']:.2f}")
                print(f"   • 最高分: {overall_stats['max_score']:.2f}")
                print(f"   • 最低分: {overall_stats['min_score']:.2f}")
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
    
    logger.info("商品评分任务完成")

if __name__ == "__main__":
    main()