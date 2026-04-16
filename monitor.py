#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
YP Affiliate 平台系统监控脚本
监控内容：MySQL健康、Flask服务、磁盘空间、采集脚本、数据新鲜度
每5分钟运行一次，状态变化时发飞书报警
"""

import os
import sys
import time
import json
import logging
import subprocess
import psutil
import requests
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# 配置常量
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
OUTPUT_DIR = BASE_DIR / "output"
MONITOR_LOG = LOGS_DIR / "monitor.log"
STATE_FILE = LOGS_DIR / "monitor_state.json"

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
FLASK_URL = "http://localhost:5055/api/health"

# 飞书配置（待授权）
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_USER_ID = ""  # 待授权后填写

# 监控阈值
MYSQL_TIMEOUT = 2.0  # 秒
DISK_WARNING_GB = 2.0  # GB
YP_FRESH_DAYS = 7  # yp_products 数据新鲜度阈值（天）
AMAZON_FRESH_DAYS = 3  # amazon_product_details 数据新鲜度阈值（天）

# 采集脚本名称
SCRAPER_SCRIPTS = ["scrape_amazon_details.py", "download_only.py"]

# 设置日志
def setup_logging():
    """配置日志记录"""
    LOGS_DIR.mkdir(exist_ok=True)
    
    # 创建滚动文件处理器（最大5MB，保留5个备份）
    from logging.handlers import RotatingFileHandler
    
    handler = RotatingFileHandler(
        MONITOR_LOG,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger('yp_monitor')
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    # 同时输出到控制台
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

def load_previous_state() -> Dict[str, Any]:
    """加载上次监控状态"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载状态文件失败: {e}")
    return {}

def save_current_state(state: Dict[str, Any]):
    """保存当前监控状态"""
    try:
        # 先写入临时文件，再重命名，确保原子性
        temp_file = STATE_FILE.with_suffix('.tmp')
        
        # 如果临时文件已存在，先删除
        if temp_file.exists():
            temp_file.unlink()
        
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)
        
        # 如果目标文件已存在，先删除
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        
        temp_file.rename(STATE_FILE)
        logger.debug(f"状态文件已保存: {STATE_FILE}")
    except Exception as e:
        logger.error(f"保存状态文件失败: {e}")

def check_mysql() -> Dict[str, Any]:
    """检查MySQL健康状态"""
    start_time = time.time()
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # 执行简单查询测试
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        latency_ms = (time.time() - start_time) * 1000
        
        cursor.close()
        conn.close()
        
        if result and result[0] == 1:
            return {
                "ok": True,
                "latency_ms": round(latency_ms, 2),
                "error": None
            }
        else:
            return {
                "ok": False,
                "latency_ms": round(latency_ms, 2),
                "error": "查询结果异常"
            }
            
    except Error as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "ok": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(e)
        }

def check_flask() -> Dict[str, Any]:
    """检查Flask服务健康状态"""
    start_time = time.time()
    try:
        response = requests.get(FLASK_URL, timeout=5)
        latency_ms = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            return {
                "ok": data.get("status") == "ok",
                "latency_ms": round(latency_ms, 2),
                "error": None if data.get("status") == "ok" else f"状态异常: {data}",
                "response": data
            }
        else:
            return {
                "ok": False,
                "latency_ms": round(latency_ms, 2),
                "error": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except requests.exceptions.RequestException as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "ok": False,
            "latency_ms": round(latency_ms, 2),
            "error": str(e)
        }

def check_disk() -> Dict[str, Any]:
    """检查磁盘空间"""
    try:
        if not OUTPUT_DIR.exists():
            OUTPUT_DIR.mkdir(exist_ok=True)
            
        # 计算output目录大小
        total_size = 0
        for file_path in OUTPUT_DIR.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        size_mb = total_size / (1024 * 1024)
        size_gb = size_mb / 1024
        
        return {
            "ok": size_gb < DISK_WARNING_GB,
            "size_mb": round(size_mb, 2),
            "size_gb": round(size_gb, 2),
            "error": None if size_gb < DISK_WARNING_GB else f"磁盘使用超过{DISK_WARNING_GB}GB"
        }
    except Exception as e:
        return {
            "ok": False,
            "size_mb": 0,
            "size_gb": 0,
            "error": str(e)
        }

def check_scrapers() -> Dict[str, Any]:
    """检查采集脚本是否在运行"""
    running_scripts = []
    try:
        # 获取所有Python进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'python' in proc.info.get('name', '').lower():
                    # 检查是否运行我们的采集脚本
                    cmdline_str = ' '.join(cmdline)
                    for script in SCRAPER_SCRIPTS:
                        if script in cmdline_str:
                            running_scripts.append({
                                "script": script,
                                "pid": proc.info['pid'],
                                "cmdline": cmdline_str[:200]  # 截断过长的命令行
                            })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            "running": running_scripts,
            "count": len(running_scripts)
        }
    except Exception as e:
        return {
            "running": [],
            "count": 0,
            "error": str(e)
        }

def check_data_freshness() -> Dict[str, Any]:
    """检查数据新鲜度"""
    warnings = []
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 检查yp_products最新数据时间
        cursor.execute("""
            SELECT MAX(scraped_at) as latest_time 
            FROM yp_products 
            WHERE scraped_at IS NOT NULL
        """)
        yp_result = cursor.fetchone()
        
        if yp_result and yp_result['latest_time']:
            yp_latest = yp_result['latest_time']
            if isinstance(yp_latest, str):
                yp_latest = datetime.fromisoformat(yp_latest.replace('Z', '+00:00'))
            
            yp_days_ago = (datetime.now() - yp_latest).days
            if yp_days_ago > YP_FRESH_DAYS:
                warnings.append(f"yp_products数据已{yp_days_ago}天未更新（阈值{YP_FRESH_DAYS}天）")
        else:
            warnings.append("yp_products无有效数据")
        
        # 检查amazon_product_details最新数据时间
        cursor.execute("""
            SELECT MAX(scraped_at) as latest_time 
            FROM amazon_product_details 
            WHERE scraped_at IS NOT NULL
        """)
        amazon_result = cursor.fetchone()
        
        if amazon_result and amazon_result['latest_time']:
            amazon_latest = amazon_result['latest_time']
            if isinstance(amazon_latest, str):
                amazon_latest = datetime.fromisoformat(amazon_latest.replace('Z', '+00:00'))
            
            amazon_days_ago = (datetime.now() - amazon_latest).days
            if amazon_days_ago > AMAZON_FRESH_DAYS:
                warnings.append(f"amazon_product_details数据已{amazon_days_ago}天未更新（阈值{AMAZON_FRESH_DAYS}天）")
        else:
            warnings.append("amazon_product_details无有效数据")
        
        cursor.close()
        conn.close()
        
        return {
            "yp_fresh": yp_days_ago <= YP_FRESH_DAYS if yp_result and yp_result['latest_time'] else False,
            "amazon_fresh": amazon_days_ago <= AMAZON_FRESH_DAYS if amazon_result and amazon_result['latest_time'] else False,
            "warnings": warnings,
            "yp_days_ago": yp_days_ago if yp_result and yp_result['latest_time'] else None,
            "amazon_days_ago": amazon_days_ago if amazon_result and amazon_result['latest_time'] else None
        }
        
    except Error as e:
        return {
            "yp_fresh": False,
            "amazon_fresh": False,
            "warnings": [f"数据库查询失败: {str(e)}"]
        }

def get_feishu_token() -> Optional[str]:
    """获取飞书tenant_access_token"""
    try:
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {
            "app_id": FEISHU_APP_ID,
            "app_secret": FEISHU_APP_SECRET
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                return result.get("tenant_access_token")
            else:
                logger.error(f"获取飞书token失败: {result}")
                return None
        else:
            logger.error(f"飞书token请求失败: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"获取飞书token异常: {e}")
        return None

def send_feishu_alert(message: str, title: str = "YP系统监控报警"):
    """发送飞书报警消息"""
    if not FEISHU_USER_ID:
        logger.info(f"飞书报警（待授权）: {title} - {message}")
        return False
    
    token = get_feishu_token()
    if not token:
        logger.error("无法获取飞书token，跳过发送")
        return False
    
    try:
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "user_id"}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        content = {
            "text": f"{title}\n{message}"
        }
        
        data = {
            "receive_id": FEISHU_USER_ID,
            "msg_type": "text",
            "content": json.dumps(content, ensure_ascii=False)
        }
        
        response = requests.post(url, params=params, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                logger.info(f"飞书报警发送成功: {message[:50]}...")
                return True
            else:
                logger.error(f"飞书发送失败: {result}")
                return False
        else:
            logger.error(f"飞书请求失败: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"发送飞书报警异常: {e}")
        return False

def run_all_checks() -> Dict[str, Any]:
    """运行所有检查"""
    logger.info("开始执行系统监控检查")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "mysql": check_mysql(),
        "flask": check_flask(),
        "disk": check_disk(),
        "scrapers": check_scrapers(),
        "data_freshness": check_data_freshness(),
        "overall_ok": True
    }
    
    # 计算整体状态
    for key in ["mysql", "flask", "disk"]:
        if not results[key]["ok"]:
            results["overall_ok"] = False
    
    # 记录日志
    log_message = f"监控结果: 整体状态{'正常' if results['overall_ok'] else '异常'}"
    if not results["overall_ok"]:
        log_message += f" - 异常项: "
        issues = []
        for key in ["mysql", "flask", "disk"]:
            if not results[key]["ok"]:
                issues.append(f"{key}: {results[key].get('error', '未知错误')}")
        log_message += "; ".join(issues)
    
    logger.info(log_message)
    
    # 记录详细结果
    for key, result in results.items():
        if key not in ["timestamp", "overall_ok"]:
            if isinstance(result, dict) and "ok" in result:
                status = "正常" if result["ok"] else "异常"
                logger.debug(f"{key}: {status}")
    
    return results

def format_alert_message(results: Dict[str, Any], prev_results: Dict[str, Any]) -> Optional[str]:
    """格式化报警消息"""
    alerts = []
    
    # 检查各项状态变化
    for key in ["mysql", "flask", "disk"]:
        prev_ok = prev_results.get(key, {}).get("ok", True)
        curr_ok = results[key]["ok"]
        
        if prev_ok and not curr_ok:  # 从正常变异常
            error_msg = results[key].get("error", "未知错误")
            alerts.append(f"❌ {key.upper()} 服务异常: {error_msg}")
        elif not prev_ok and curr_ok:  # 从异常变正常
            alerts.append(f"✅ {key.upper()} 服务已恢复")
    
    # 检查数据新鲜度警告
    freshness_warnings = results["data_freshness"].get("warnings", [])
    if freshness_warnings:
        for warning in freshness_warnings:
            alerts.append(f"⚠️ 数据新鲜度: {warning}")
    
    # 检查采集脚本运行状态
    running_count = results["scrapers"].get("count", 0)
    if running_count == 0:
        alerts.append(f"⚠️ 无采集脚本运行")
    elif running_count > 0:
        scripts = [s["script"] for s in results["scrapers"].get("running", [])]
        alerts.append(f"📊 采集脚本运行中: {', '.join(scripts)}")
    
    if not alerts:
        return None
    
    # 添加时间戳和整体状态
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    overall_status = "正常" if results["overall_ok"] else "异常"
    
    message = f"【YP系统监控】{timestamp} - 状态: {overall_status}\n\n"
    message += "\n".join(alerts)
    
    # 添加详细信息
    if not results["overall_ok"]:
        message += f"\n\n详细状态:"
        for key in ["mysql", "flask", "disk"]:
            if not results[key]["ok"]:
                error = results[key].get("error", "未知错误")
                message += f"\n- {key.upper()}: {error}"
    
    return message

def main():
    """主函数"""
    try:
        # 加载上次状态
        prev_state = load_previous_state()
        
        # 执行所有检查
        current_results = run_all_checks()
        
        # 保存当前状态
        save_current_state(current_results)
        
        # 检查是否需要发送报警
        if prev_state:  # 不是第一次运行
            alert_message = format_alert_message(current_results, prev_state)
            if alert_message:
                logger.info(f"检测到状态变化，准备发送报警")
                send_feishu_alert(alert_message)
        
        # 返回整体状态码
        return 0 if current_results["overall_ok"] else 1
        
    except Exception as e:
        logger.error(f"监控脚本执行异常: {e}", exc_info=True)
        return 2

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)