#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
YP Affiliate 平台日报生成脚本
每天早上8点运行，生成HTML格式日报
内容包括：数据概览、今日待办、投放状态、系统健康
"""

import os
import sys
import json
import logging
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import subprocess
import requests

# 配置常量
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"
DAILY_REPORT_DIR = LOGS_DIR / "daily_reports"
DAILY_REPORT_DIR.mkdir(exist_ok=True)

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'affiliate_marketing',
    'user': 'root',
    'password': 'admin',
    'charset': 'utf8mb4',
}

# Flask 服务配置
FLASK_URL = "http://localhost:5055"

# 设置日志
def setup_logging():
    """配置日志记录"""
    LOGS_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger('yp_daily_report')
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    file_handler = logging.FileHandler(LOGS_DIR / 'daily_report.log', encoding='utf-8')
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

def execute_query(query: str, params: tuple = None) -> List[Dict]:
    """执行SQL查询并返回结果"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute(query, params or ())
        results = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return results
    except Error as e:
        logger.error(f"数据库查询失败: {e}")
        return []

def get_scalar(query: str, params: tuple = None) -> Any:
    """获取单个标量值"""
    results = execute_query(query, params)
    if results and len(results) > 0:
        first_row = results[0]
        if first_row:
            return list(first_row.values())[0]
    return None

def get_data_overview() -> Dict[str, Any]:
    """获取数据概览"""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    overview = {}
    
    # yp_products 统计
    yp_total = get_scalar("SELECT COUNT(*) as cnt FROM yp_products")
    yp_yesterday = get_scalar("""
        SELECT COUNT(*) as cnt FROM yp_products 
        WHERE DATE(scraped_at) = %s
    """, (yesterday,))
    
    # amazon_product_details 统计
    amazon_total = get_scalar("SELECT COUNT(*) as cnt FROM amazon_product_details")
    amazon_yesterday = get_scalar("""
        SELECT COUNT(*) as cnt FROM amazon_product_details 
        WHERE DATE(scraped_at) = %s
    """, (yesterday,))
    
    # ads_plans 统计
    ads_total = get_scalar("SELECT COUNT(*) as cnt FROM ads_plans")
    ads_yesterday = get_scalar("""
        SELECT COUNT(*) as cnt FROM ads_plans 
        WHERE DATE(generated_at) = %s
    """, (yesterday,))
    
    overview.update({
        "yp_products": {
            "total": yp_total or 0,
            "yesterday": yp_yesterday or 0
        },
        "amazon_product_details": {
            "total": amazon_total or 0,
            "yesterday": amazon_yesterday or 0
        },
        "ads_plans": {
            "total": ads_total or 0,
            "yesterday": ads_yesterday or 0
        }
    })
    
    logger.info(f"数据概览: yp_products={yp_total}, amazon_details={amazon_total}, ads_plans={ads_total}")
    
    return overview

def get_today_todos() -> Dict[str, Any]:
    """获取今日待办事项"""
    todos = {
        "high_value_products": [],
        "semrush_stale_merchants": [],
        "google_keywords_stale_count": 0
    }
    
    # 1. 没有广告方案的高价值商品（commission>8%, price>$30）Top 10
    high_value_query = """
        SELECT 
            p.id, p.asin, p.product_name, p.price, p.commission, p.merchant_name,
            apd.rating, apd.review_count
        FROM yp_products p
        LEFT JOIN amazon_product_details apd ON p.asin = apd.asin
        WHERE p.commission > 8.0 
            AND p.price > 30.0
            AND p.asin NOT IN (SELECT asin FROM ads_plans)
        ORDER BY p.commission DESC, p.price DESC
        LIMIT 10
    """
    
    high_value_results = execute_query(high_value_query)
    for row in high_value_results:
        todos["high_value_products"].append({
            "asin": row.get("asin"),
            "product_name": row.get("product_name", "")[:100],
            "price": row.get("price"),
            "commission": row.get("commission"),
            "merchant": row.get("merchant_name"),
            "rating": row.get("rating"),
            "review_count": row.get("review_count")
        })
    
    # 2. SEMrush数据超30天未更新的商户 Top 5
    semrush_stale_query = """
        SELECT 
            m.id as merchant_id, m.merchant_name, m.website,
            MAX(s.scraped_at) as last_updated,
            DATEDIFF(NOW(), MAX(s.scraped_at)) as days_stale
        FROM yp_merchants m
        LEFT JOIN semrush_competitor_data s ON m.merchant_name = s.domain
        WHERE m.status = 'active' AND m.country LIKE 'US%'
        GROUP BY m.id, m.merchant_name, m.website
        HAVING last_updated IS NULL OR days_stale > 30
        ORDER BY days_stale DESC
        LIMIT 5
    """
    
    semrush_results = execute_query(semrush_stale_query)
    for row in semrush_results:
        todos["semrush_stale_merchants"].append({
            "merchant_id": row.get("merchant_id"),
            "merchant_name": row.get("merchant_name"),
            "website": row.get("website"),
            "last_updated": row.get("last_updated"),
            "days_stale": row.get("days_stale")
        })
    
    # 3. google_suggest_keywords超7天未更新的商户数量
    google_stale_query = """
        SELECT COUNT(DISTINCT merchant_id) as stale_count
        FROM google_suggest_keywords
        WHERE DATEDIFF(NOW(), scraped_at) > 7
    """
    
    google_stale_count = get_scalar(google_stale_query) or 0
    todos["google_keywords_stale_count"] = google_stale_count
    
    logger.info(f"今日待办: {len(todos['high_value_products'])}个高价值商品, "
                f"{len(todos['semrush_stale_merchants'])}个SEMrush过期商户, "
                f"{google_stale_count}个Google关键词过期商户")
    
    return todos

def get_performance_status() -> Dict[str, Any]:
    """获取投放状态"""
    performance = {
        "has_data": False,
        "metrics": {}
    }
    
    # 检查是否有ads_kpi_actuals表
    table_exists_query = """
        SELECT COUNT(*) as cnt FROM information_schema.tables 
        WHERE table_schema = %s AND table_name = 'ads_kpi_actuals'
    """
    
    table_exists = get_scalar(table_exists_query, (DB_CONFIG['database'],))
    
    if table_exists and table_exists > 0:
        # 获取最近一次上传的ROAS/CTR/CVR
        # 注意：ads_kpi_actuals表结构不同，需要根据实际数据调整
        # 这里先检查是否有数据
        latest_performance_query = """
            SELECT 
                MAX(recorded_at) as latest_date,
                COUNT(*) as records_count
            FROM ads_kpi_actuals
        """
        
        results = execute_query(latest_performance_query)
        if results and len(results) > 0:
            row = results[0]
            if row.get("latest_date"):
                performance.update({
                    "has_data": True,
                    "metrics": {
                        "latest_date": row.get("latest_date"),
                        "records_count": row.get("records_count", 0)
                    }
                })
                
                logger.info(f"投放状态: 最近更新={performance['metrics']['latest_date']}, "
                          f"记录数={performance['metrics']['records_count']}")
    
    return performance

def get_system_health() -> Dict[str, Any]:
    """获取系统健康状态"""
    health = {
        "mysql": {"ok": False, "error": None},
        "flask": {"ok": False, "error": None},
        "disk": {"ok": False, "size_mb": 0, "size_gb": 0, "error": None},
        "overall_ok": False
    }
    
    # 检查MySQL
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
        health["mysql"]["ok"] = True
    except Error as e:
        health["mysql"]["error"] = str(e)
    
    # 检查Flask
    try:
        response = requests.get(f"{FLASK_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            health["flask"]["ok"] = data.get("status") == "ok"
            if not health["flask"]["ok"]:
                health["flask"]["error"] = f"状态异常: {data}"
        else:
            health["flask"]["error"] = f"HTTP {response.status_code}"
    except Exception as e:
        health["flask"]["error"] = str(e)
    
    # 检查磁盘
    try:
        total_size = 0
        for file_path in OUTPUT_DIR.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        size_mb = total_size / (1024 * 1024)
        size_gb = size_mb / 1024
        
        health["disk"]["size_mb"] = round(size_mb, 2)
        health["disk"]["size_gb"] = round(size_gb, 2)
        health["disk"]["ok"] = size_gb < 2.0  # 阈值2GB
    except Exception as e:
        health["disk"]["error"] = str(e)
    
    # 计算整体状态
    health["overall_ok"] = (
        health["mysql"]["ok"] and 
        health["flask"]["ok"] and 
        health["disk"]["ok"]
    )
    
    logger.info(f"系统健康: MySQL={health['mysql']['ok']}, "
                f"Flask={health['flask']['ok']}, "
                f"磁盘={health['disk']['size_gb']}GB")
    
    return health

def generate_html_report(data: Dict[str, Any]) -> str:
    """生成HTML格式报告"""
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    overview = data.get("overview", {})
    todos = data.get("todos", {})
    performance = data.get("performance", {})
    health = data.get("health", {})
    
    # 整体健康状态
    overall_status = "正常" if health.get("overall_ok") else "异常"
    status_color = "#10B981" if health.get("overall_ok") else "#EF4444"
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YP平台日报 - {today}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }}
        
        body {{
            background-color: #0F172A;
            color: #E2E8F0;
            line-height: 1.6;
            padding: 20px;
            font-size: 14px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #1E293B 0%, #334155 100%);
            border-radius: 12px;
            border: 1px solid #475569;
        }}
        
        .header h1 {{
            color: #F8FAFC;
            font-size: 28px;
            margin-bottom: 10px;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            background-color: {status_color};
            color: white;
            border-radius: 20px;
            font-weight: bold;
            font-size: 16px;
            margin-top: 10px;
        }}
        
        .timestamp {{
            color: #94A3B8;
            font-size: 14px;
            margin-top: 5px;
        }}
        
        .section {{
            background-color: #1E293B;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid #334155;
        }}
        
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 2px solid #334155;
        }}
        
        .section-title {{
            color: #F8FAFC;
            font-size: 20px;
            font-weight: 600;
        }}
        
        .section-subtitle {{
            color: #94A3B8;
            font-size: 14px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        
        .stat-card {{
            background-color: #334155;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #3B82F6;
        }}
        
        .stat-card h3 {{
            color: #CBD5E1;
            font-size: 16px;
            margin-bottom: 10px;
        }}
        
        .stat-value {{
            color: #F8FAFC;
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .stat-label {{
            color: #94A3B8;
            font-size: 14px;
        }}
        
        .table-container {{
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #1E293B;
        }}
        
        th {{
            background-color: #334155;
            color: #CBD5E1;
            text-align: left;
            padding: 12px 16px;
            border-bottom: 2px solid #475569;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid #334155;
            color: #E2E8F0;
        }}
        
        tr:hover {{
            background-color: #2D3748;
        }}
        
        .metric-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        .metric-good {{
            background-color: #10B981;
            color: white;
        }}
        
        .metric-warning {{
            background-color: #F59E0B;
            color: white;
        }}
        
        .metric-critical {{
            background-color: #EF4444;
            color: white;
        }}
        
        .status-icon {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        
        .status-ok {{
            background-color: #10B981;
        }}
        
        .status-error {{
            background-color: #EF4444;
        }}
        
        .no-data {{
            text-align: center;
            color: #94A3B8;
            padding: 40px;
            font-style: italic;
        }}
        
        .footer {{
            text-align: center;
            color: #64748B;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #334155;
        }}
        
        @media (max-width: 768px) {{
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>YP Affiliate 平台日报</h1>
            <div class="status-badge">{overall_status}</div>
            <div class="timestamp">{timestamp}</div>
        </div>
        
        <!-- 数据概览 -->
        <div class="section">
            <div class="section-header">
                <div>
                    <h2 class="section-title">📊 数据概览</h2>
                    <div class="section-subtitle">平台数据统计与昨日增长</div>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>YP 商品总数</h3>
                            <div class="stat-value">{overview.get('yp_products', {}).get('total', 0) or 0:,}</div>
                            <div class="stat-label">昨日新增: {overview.get('yp_products', {}).get('yesterday', 0) or 0:,}</div>
                </div>
                
                <div class="stat-card">
                    <h3>亚马逊详情总数</h3>
                            <div class="stat-value">{overview.get('amazon_product_details', {}).get('total', 0) or 0:,}</div>
                            <div class="stat-label">昨日新增: {overview.get('amazon_product_details', {}).get('yesterday', 0) or 0:,}</div>
                </div>
                
                <div class="stat-card">
                    <h3>广告方案总数</h3>
                            <div class="stat-value">{overview.get('ads_plans', {}).get('total', 0) or 0:,}</div>
                            <div class="stat-label">昨日新增: {overview.get('ads_plans', {}).get('yesterday', 0) or 0:,}</div>
                </div>
            </div>
        </div>
        
        <!-- 今日待办 -->
        <div class="section">
            <div class="section-header">
                <div>
                    <h2 class="section-title">📋 今日待办</h2>
                    <div class="section-subtitle">高价值商品与数据更新任务</div>
                </div>
            </div>
            
            <h3 style="margin-bottom: 16px; color: #CBD5E1;">🎯 高价值商品（无广告方案）</h3>
'''
    
    # 高价值商品表格
    if todos.get("high_value_products"):
        html += '''
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>ASIN</th>
                            <th>商品名称</th>
                            <th>价格</th>
                            <th>佣金率</th>
                            <th>评分</th>
                            <th>评论数</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        
        for product in todos.get("high_value_products", [])[:10]:
            html += f'''
                        <tr>
                            <td>{product.get('asin', '')}</td>
                            <td>{product.get('product_name', '')}</td>
                            <td>${product.get('price', 0):.2f}</td>
                            <td>{product.get('commission', 0)}%</td>
                            <td>{product.get('rating', 'N/A')}</td>
                            <td>{product.get('review_count') if product.get('review_count') is not None else 'N/A'}</td>
                        </tr>
'''
        
        html += '''
                    </tbody>
                </table>
            </div>
'''
    else:
        html += '''
            <div class="no-data">
                暂无高价值商品待处理
            </div>
'''
    
    # SEMrush过期商户
    html += f'''
            <h3 style="margin: 24px 0 16px; color: #CBD5E1;">🔄 SEMrush数据过期商户（>30天）</h3>
'''
    
    if todos.get("semrush_stale_merchants"):
        html += '''
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>商户ID</th>
                            <th>商户名称</th>
                            <th>网站</th>
                            <th>最后更新</th>
                            <th>过期天数</th>
                        </tr>
                    </thead>
                    <tbody>
'''
        
        for merchant in todos.get("semrush_stale_merchants", [])[:5]:
            days_stale = merchant.get('days_stale', 0)
            badge_class = "metric-critical" if days_stale > 60 else "metric-warning"
            
            html += f'''
                        <tr>
                            <td>{merchant.get('merchant_id', '')}</td>
                            <td>{merchant.get('merchant_name', '')}</td>
                            <td><a href="{merchant.get('website', '')}" style="color: #60A5FA;" target="_blank">{merchant.get('website', '')}</a></td>
                            <td>{merchant.get('last_updated', '从未更新')}</td>
                            <td>
                                <span class="metric-badge {badge_class}">
                                    {days_stale if days_stale else 'N/A'} 天
                                </span>
                            </td>
                        </tr>
'''
        
        html += '''
                    </tbody>
                </table>
            </div>
'''
    else:
        html += '''
            <div class="no-data">
                暂无SEMrush数据过期商户
            </div>
'''
    
    # Google关键词过期统计
    google_stale_count = todos.get("google_keywords_stale_count", 0)
    google_badge_class = "metric-critical" if google_stale_count > 50 else "metric-warning" if google_stale_count > 10 else "metric-good"
    
    html += f'''
            <div style="margin-top: 24px; padding: 16px; background-color: #334155; border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4 style="color: #CBD5E1; margin-bottom: 4px;">🔍 Google关键词数据</h4>
                        <div style="color: #94A3B8; font-size: 13px;">超过7天未更新的商户数量</div>
                    </div>
                    <span class="metric-badge {google_badge_class}">
                        {google_stale_count} 个商户
                    </span>
                </div>
            </div>
        </div>
'''
    
    # 投放状态
    html += '''
        <div class="section">
            <div class="section-header">
                <div>
                    <h2 class="section-title">🚀 投放状态</h2>
                    <div class="section-subtitle">Google Ads表现指标</div>
                </div>
            </div>
'''
    
    if performance.get("has_data"):
        metrics = performance.get("metrics", {})
        html += f'''
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>最近更新</h3>
                    <div class="stat-value">{metrics.get('latest_date', 'N/A')}</div>
                    <div class="stat-label">数据记录数: {metrics.get('records_count', 0)}</div>
                </div>
                
                <div class="stat-card">
                    <h3>监控状态</h3>
                    <div class="stat-value">待完善</div>
                    <div class="stat-label">请上传Google Ads报告以获取ROAS/CTR/CVR数据</div>
                </div>
                
                <div class="stat-card">
                    <h3>下一步</h3>
                    <div class="stat-value">数据集成</div>
                    <div class="stat-label">将Google Ads API数据导入ads_kpi_actuals表</div>
                </div>
            </div>
'''
    else:
        html += '''
            <div class="no-data">
                暂无投放数据，请上传Google Ads报告或等待数据采集
            </div>
'''
    
    html += '''
        </div>
'''
    
    # 系统健康
    html += '''
        <div class="section">
            <div class="section-header">
                <div>
                    <h2 class="section-title">⚙️ 系统健康</h2>
                    <div class="section-subtitle">基础设施运行状态</div>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>MySQL 数据库</h3>
                    <div style="display: flex; align-items: center; margin-top: 8px;">
'''
    
    if health.get("mysql", {}).get("ok"):
        html += '''
                        <span class="status-icon status-ok"></span>
                        <span style="color: #10B981; font-weight: 600;">正常</span>
'''
    else:
        html += f'''
                        <span class="status-icon status-error"></span>
                        <div>
                            <div style="color: #EF4444; font-weight: 600;">异常</div>
                            <div style="color: #94A3B8; font-size: 12px; margin-top: 4px;">{health.get('mysql', {}).get('error', '未知错误')}</div>
                        </div>
'''
    
    html += '''
                    </div>
                </div>
                
                <div class="stat-card">
                    <h3>Flask 服务</h3>
                    <div style="display: flex; align-items: center; margin-top: 8px;">
'''
    
    if health.get("flask", {}).get("ok"):
        html += '''
                        <span class="status-icon status-ok"></span>
                        <span style="color: #10B981; font-weight: 600;">正常</span>
'''
    else:
        html += f'''
                        <span class="status-icon status-error"></span>
                        <div>
                            <div style="color: #EF4444; font-weight: 600;">异常</div>
                            <div style="color: #94A3B8; font-size: 12px; margin-top: 4px;">{health.get('flask', {}).get('error', '未知错误')}</div>
                        </div>
'''
    
    html += '''
                    </div>
                </div>
                
                <div class="stat-card">
                    <h3>磁盘使用</h3>
                    <div style="margin-top: 8px;">
'''
    
    disk_size = health.get("disk", {}).get("size_gb", 0)
    disk_ok = health.get("disk", {}).get("ok", False)
    
    if disk_ok:
        html += f'''
                        <div style="color: #10B981; font-weight: 600; font-size: 24px;">{disk_size:.1f} GB</div>
                        <div style="color: #94A3B8; font-size: 13px; margin-top: 4px;">正常范围</div>
'''
    else:
        html += f'''
                        <div style="color: #EF4444; font-weight: 600; font-size: 24px;">{disk_size:.1f} GB</div>
                        <div style="color: #94A3B8; font-size: 13px; margin-top: 4px;">超过2GB阈值</div>
'''
    
    html += '''
                    </div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>YP Affiliate 平台日报系统 | 生成时间: {timestamp}</p>
            <p>数据来源: MySQL affiliate_marketing 数据库 | 平台入口: http://localhost:5055</p>
        </div>
    </div>
</body>
</html>
'''.format(timestamp=timestamp)
    
    return html

def save_report(html_content: str):
    """保存HTML报告"""
    today = datetime.now().strftime("%Y-%m-%d")
    report_file = DAILY_REPORT_DIR / f"daily_report_{today}.html"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"日报已保存: {report_file}")
        
        # 同时保存到logs目录下方便访问
        logs_report_file = LOGS_DIR / f"daily_report_{today}.html"
        with open(logs_report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"日报副本已保存: {logs_report_file}")
        
    except Exception as e:
        logger.error(f"保存报告失败: {e}")

def main():
    """主函数"""
    try:
        logger.info("开始生成日报")
        
        # 收集所有数据
        data = {
            "overview": get_data_overview(),
            "todos": get_today_todos(),
            "performance": get_performance_status(),
            "health": get_system_health()
        }
        
        # 生成HTML报告
        html_report = generate_html_report(data)
        
        # 保存报告
        save_report(html_report)
        
        logger.info("日报生成完成")
        
        return 0
        
    except Exception as e:
        logger.error(f"日报生成异常: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)