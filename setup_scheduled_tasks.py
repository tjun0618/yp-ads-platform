#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Windows 计划任务设置脚本
自动注册YP Affiliate平台的定时任务
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# 配置常量
BASE_DIR = Path(__file__).parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 设置日志
def setup_logging():
    """配置日志记录"""
    logger = logging.getLogger('yp_task_setup')
    logger.setLevel(logging.INFO)
    
    # 文件处理器
    file_handler = logging.FileHandler(LOGS_DIR / 'task_setup.log', encoding='utf-8')
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

def run_command(command: str, description: str) -> bool:
    """运行命令并记录结果"""
    logger.info(f"执行: {description}")
    logger.debug(f"命令: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode == 0:
            logger.info(f"✓ {description} 成功")
            if result.stdout.strip():
                logger.debug(f"输出: {result.stdout.strip()}")
            return True
        else:
            logger.error(f"✗ {description} 失败")
            logger.error(f"错误代码: {result.returncode}")
            if result.stderr.strip():
                logger.error(f"错误信息: {result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"✗ {description} 异常: {e}")
        return False

def check_task_exists(task_name: str) -> bool:
    """检查任务是否已存在"""
    command = f'schtasks /query /tn "{task_name}"'
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode == 0
    except Exception:
        return False

def delete_task(task_name: str) -> bool:
    """删除计划任务"""
    if not check_task_exists(task_name):
        logger.info(f"任务 '{task_name}' 不存在，无需删除")
        return True
    
    command = f'schtasks /delete /tn "{task_name}" /f'
    return run_command(command, f"删除任务 '{task_name}'")

def create_monitor_task():
    """创建监控任务（每5分钟运行）"""
    task_name = "AffiliateMonitor"
    script_path = BASE_DIR / "monitor.py"
    
    # 确保脚本存在
    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return False
    
    # 删除已存在的任务
    if not delete_task(task_name):
        return False
    
    # 创建新任务
    command = f'schtasks /create /tn "{task_name}" /tr "python -X utf8 \\"{script_path}\\" " /sc minute /mo 5 /st 00:00 /ed 23:59 /ru "SYSTEM" /rl HIGHEST'
    
    success = run_command(command, f"创建监控任务 '{task_name}'（每5分钟运行）")
    
    if success:
        # 立即运行一次测试
        test_command = f'schtasks /run /tn "{task_name}"'
        run_command(test_command, f"立即运行任务 '{task_name}' 进行测试")
    
    return success

def create_daily_report_task():
    """创建日报任务（每天08:00运行）"""
    task_name = "AffiliateDailyReport"
    script_path = BASE_DIR / "daily_report.py"
    
    # 确保脚本存在
    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return False
    
    # 删除已存在的任务
    if not delete_task(task_name):
        return False
    
    # 创建新任务
    command = f'schtasks /create /tn "{task_name}" /tr "python -X utf8 \\"{script_path}\\" " /sc daily /st 08:00 /ru "SYSTEM" /rl HIGHEST'
    
    success = run_command(command, f"创建日报任务 '{task_name}'（每天08:00运行）")
    
    if success:
        # 立即运行一次测试
        test_command = f'schtasks /run /tn "{task_name}"'
        run_command(test_command, f"立即运行任务 '{task_name}' 进行测试")
    
    return success

def create_score_products_task():
    """创建商品评分任务（每天06:00运行）"""
    task_name = "AffiliateScoreProducts"
    script_path = BASE_DIR / "score_products.py"
    
    # 确保脚本存在
    if not script_path.exists():
        logger.error(f"脚本不存在: {script_path}")
        return False
    
    # 删除已存在的任务
    if not delete_task(task_name):
        return False
    
    # 创建新任务 - 更新Top50商品
    command = f'schtasks /create /tn "{task_name}" /tr "python -X utf8 \\"{script_path}\\" --top 50 " /sc daily /st 06:00 /ru "SYSTEM" /rl HIGHEST'
    
    success = run_command(command, f"创建商品评分任务 '{task_name}'（每天06:00运行，更新Top50商品）")
    
    if success:
        # 立即运行一次测试
        test_command = f'schtasks /run /tn "{task_name}"'
        run_command(test_command, f"立即运行任务 '{task_name}' 进行测试")
    
    return success

def create_merchant_sync_task():
    """创建商户同步任务（每天08:30运行）"""
    task_name = "AffiliateMerchantSync"
    script_path = BASE_DIR / "sync_merchants.py"
    
    # 检查脚本是否存在
    script_exists = script_path.exists()
    
    if not script_exists:
        logger.warning(f"脚本不存在: {script_path}")
        logger.warning("将创建占位任务，请后续创建 sync_merchants.py 脚本")
    
    # 删除已存在的任务
    if not delete_task(task_name):
        return False
    
    if script_exists:
        # 创建实际任务
        command = f'schtasks /create /tn "{task_name}" /tr "python -X utf8 \\"{script_path}\\" " /sc daily /st 08:30 /ru "SYSTEM" /rl HIGHEST'
        success = run_command(command, f"创建商户同步任务 '{task_name}'（每天08:30运行）")
    else:
        # 创建占位任务
        command = f'schtasks /create /tn "{task_name}" /tr "echo \"商户同步脚本未实现，请创建 {script_path}\" " /sc daily /st 08:30 /ru "SYSTEM" /rl HIGHEST'
        success = run_command(command, f"创建商户同步占位任务 '{task_name}'（每天08:30运行）")
    
    if success:
        # 立即运行一次测试
        test_command = f'schtasks /run /tn "{task_name}"'
        run_command(test_command, f"立即运行任务 '{task_name}' 进行测试")
    
    return success

def create_batch_task():
    """创建批处理脚本任务（作为备选方案）"""
    task_name = "AffiliateBatchRunner"
    batch_path = BASE_DIR / "run_all_tasks.bat"
    
    # 创建批处理文件
    batch_content = f"""@echo off
chcp 65001 > nul
echo 开始执行YP平台定时任务...
echo 时间: %date% %time%
echo.

REM 切换到脚本目录
cd /d "%~dp0"

REM 1. 运行监控脚本
echo 执行监控脚本...
python -X utf8 monitor.py
echo.

REM 2. 运行日报脚本（如果是8点后）
echo 检查是否需要生成日报...
REM 这里可以添加时间判断逻辑

echo 所有任务执行完成
pause
"""
    
    try:
        with open(batch_path, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        logger.info(f"创建批处理文件: {batch_path}")
    except Exception as e:
        logger.error(f"创建批处理文件失败: {e}")
        return False
    
    # 删除已存在的任务
    if not delete_task(task_name):
        return False
    
    # 创建批处理任务（每小时运行一次）
    command = f'schtasks /create /tn "{task_name}" /tr "\\"{batch_path}\\" " /sc hourly /mo 1 /ru "SYSTEM" /rl HIGHEST'
    
    success = run_command(command, f"创建批处理任务 '{task_name}'（每小时运行一次）")
    
    if success:
        logger.info(f"批处理任务已创建，文件位置: {batch_path}")
        logger.info("此任务作为备选方案，可以手动编辑批处理文件添加更多功能")
    
    return success

def list_all_tasks():
    """列出所有相关的计划任务"""
    logger.info("=" * 60)
    logger.info("当前已注册的计划任务:")
    logger.info("=" * 60)
    
    tasks = [
        "AffiliateMonitor",
        "AffiliateDailyReport", 
        "AffiliateScoreProducts",
        "AffiliateMerchantSync",
        "AffiliateBatchRunner"
    ]
    
    for task_name in tasks:
        if check_task_exists(task_name):
            logger.info(f"✓ {task_name}")
        else:
            logger.info(f"✗ {task_name} (未注册)")
    
    logger.info("=" * 60)

def export_tasks_to_file():
    """导出任务配置到文件"""
    export_file = LOGS_DIR / "scheduled_tasks_export.txt"
    
    try:
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write("YP Affiliate 平台计划任务配置\n")
            f.write(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            
            # 获取所有任务详情
            command = 'schtasks /query /fo list /v'
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0:
                f.write(result.stdout)
            else:
                f.write("获取任务详情失败\n")
        
        logger.info(f"任务配置已导出到: {export_file}")
        return True
    except Exception as e:
        logger.error(f"导出任务配置失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("   YP Affiliate 平台 Windows 计划任务设置")
    print("=" * 60)
    print()
    
    logger.info("开始设置计划任务...")
    
    # 1. 创建监控任务（每5分钟运行）
    print("1. 设置监控任务 (每5分钟运行)...")
    if create_monitor_task():
        print("   ✓ 监控任务设置成功")
    else:
        print("   ✗ 监控任务设置失败")
    
    # 2. 创建日报任务（每天08:00运行）
    print("\n2. 设置日报任务 (每天08:00运行)...")
    if create_daily_report_task():
        print("   ✓ 日报任务设置成功")
    else:
        print("   ✗ 日报任务设置失败")
    
    # 3. 创建商品评分任务（每天06:00运行）
    print("\n3. 设置商品评分任务 (每天06:00运行)...")
    if create_score_products_task():
        print("   ✓ 商品评分任务设置成功")
    else:
        print("   ✗ 商品评分任务设置失败")
    
    # 4. 创建商户同步任务（每天08:30运行）
    print("\n4. 设置商户同步任务 (每天08:30运行)...")
    if create_merchant_sync_task():
        print("   ✓ 商户同步任务设置成功")
    else:
        print("   ✗ 商户同步任务设置失败")
    
    # 5. 创建批处理任务（可选）
    print("\n5. 设置批处理任务 (每小时运行，可选)...")
    create_batch = input("   是否创建批处理任务？(y/N): ").strip().lower()
    if create_batch == 'y':
        if create_batch_task():
            print("   ✓ 批处理任务设置成功")
        else:
            print("   ✗ 批处理任务设置失败")
    else:
        print("   ⏭️  跳过批处理任务设置")
    
    # 列出所有任务
    print("\n" + "=" * 60)
    print("任务设置完成，当前状态:")
    list_all_tasks()
    
    # 导出任务配置
    print("\n导出任务配置...")
    if export_tasks_to_file():
        print("✓ 任务配置已导出到 logs/scheduled_tasks_export.txt")
    else:
        print("✗ 任务配置导出失败")
    
    # 使用说明
    print("\n" + "=" * 60)
    print("使用说明:")
    print("1. 手动运行任务: schtasks /run /tn \"任务名\"")
    print("2. 查看任务状态: schtasks /query /tn \"任务名\"")
    print("3. 删除任务: schtasks /delete /tn \"任务名\" /f")
    print("4. 查看所有任务: schtasks /query /fo list")
    print("\n任务目录: Task Scheduler → Task Scheduler Library")
    print("=" * 60)
    
    logger.info("计划任务设置完成")

if __name__ == "__main__":
    main()