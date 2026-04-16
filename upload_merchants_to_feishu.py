#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上传品牌和商品数据到飞书

使用说明：
1. 确保 yp_merchants_and_products.csv 文件存在
2. 替换下面的 APP_ID 和 APP_SECRET 为您的飞书凭证
3. 运行脚本：python upload_merchants_to_feishu.py
"""

import csv
import sys
import io
from pathlib import Path
from datetime import datetime

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

try:
    from lark_oapi.api.bitable import v1
    import lark_oapi as lark
except ImportError as e:
    print(f"[错误] 未安装飞书SDK: {e}")
    print("请运行: pip install lark-oapi")
    sys.exit(1)


# ============================================================
# 🔧 配置区域 - 请修改此处
# ============================================================

# 飞书应用凭证（从飞书开放平台获取）
APP_ID = "cli_a935343a74f89cd4"  # 🔴 请替换为您的飞书应用ID
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"  # 🔴 请替换为您的飞书应用密钥

# CSV 文件路径
CSV_FILE = "yp_merchants_and_products.csv"

# ============================================================


def create_client():
    """创建飞书客户端"""
    try:
        client = lark.Client.builder() \
            .app_id(APP_ID) \
            .app_secret(APP_SECRET) \
            .build()
        return client
    except Exception as e:
        print(f"[错误] 创建飞书客户端失败: {e}")
        return None


def create_bitable(client):
    """创建新的多维表格"""
    try:
        print("[信息] 创建新的多维表格...")
        
        create_req = v1.CreateAppRequest.builder() \
            .request_body(
                v1.App.builder()
                    .name("YP品牌和商品数据")
                    .build()
            ) \
            .build()
        
        create_resp = client.bitable.v1.app.create(create_req)
        
        if not create_resp.success():
            print(f"[错误] 创建表格失败: {create_resp.code} - {create_resp.msg}")
            return None
        
        app_token = create_resp.data.app.app_token
        print(f"[成功] 新表格已创建，Token: {app_token}")
        return app_token
        
    except Exception as e:
        print(f"[错误] 创建表格异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_first_table(client, app_token):
    """获取多维表格中的第一个数据表"""
    try:
        print("[信息] 获取表格列表...")
        
        list_req = v1.ListAppTableRequest.builder() \
            .app_token(app_token) \
            .build()
        
        list_resp = client.bitable.v1.app_table.list(list_req)
        
        if not list_resp.success():
            print(f"[错误] 获取表格列表失败: {list_resp.code} - {list_resp.msg}")
            return None
        
        if not list_resp.data.items:
            print("[错误] 表格中没有数据表")
            return None
        
        table_id = list_resp.data.items[0].table_id
        table_name = list_resp.data.items[0].name
        print(f"[成功] 找到数据表: {table_name} (ID: {table_id})")
        return table_id
        
    except Exception as e:
        print(f"[错误] 获取表格异常: {str(e)}")
        return None


def add_columns(client, app_token, table_id):
    """添加表格列"""
    try:
        print("[信息] 添加表格列...")
        
        columns = [
            ("商家名称", 1),      # text
            ("佣金", 1),         # text
            ("类别", 1),         # text
            ("ASIN", 1),         # text
            ("商品名称", 1),     # text
            ("价格", 2),         # number
            ("评分", 2),         # number
            ("评论数", 2),       # number
            ("图片链接", 1),     # text
            ("商品链接", 1),     # text
            ("商品描述", 1),     # text
            ("品牌", 1),         # text
            ("商品特性", 1),     # text
            ("采集时间", 5),     # datetime
        ]
        
        for col_name, col_type in columns:
            try:
                create_field_req = v1.CreateAppTableFieldRequest.builder() \
                    .app_token(app_token) \
                    .table_id(table_id) \
                    .request_body(
                        v1.AppTableField.builder()
                            .field_name(col_name)
                            .type(col_type)
                            .build()
                    ) \
                    .build()
                
                field_resp = client.bitable.v1.app_table_field.create(create_field_req)
                
                if field_resp.success():
                    print(f"  ✓ 已添加列: {col_name}")
                else:
                    print(f"  ✗ 添加列失败: {col_name} - {field_resp.code}")
                
                # 避免速率限制
                time.sleep(0.5)
                
            except Exception as e:
                print(f"  ✗ 添加列异常: {col_name} - {e}")
        
        print("[成功] 表格列已添加")
        
    except Exception as e:
        print(f"[错误] 添加表格列异常: {str(e)}")
        import traceback
        traceback.print_exc()


def read_csv_file(csv_file):
    """读取 CSV 文件"""
    try:
        print(f"[信息] 读取 CSV 文件: {csv_file}")
        
        if not Path(csv_file).exists():
            print(f"[错误] CSV 文件不存在: {csv_file}")
            return None
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        print(f"[成功] 读取到 {len(rows)} 条记录")
        return rows
        
    except Exception as e:
        print(f"[错误] 读取 CSV 文件失败: {e}")
        return None


def upload_data_to_feishu(client, app_token, table_id, rows):
    """上传数据到飞书"""
    try:
        print(f"[信息] 开始上传 {len(rows)} 条记录到飞书...")
        
        success_count = 0
        error_count = 0
        
        for i, row in enumerate(rows):
            try:
                # 构建记录
                record = {}
                for key, value in row.items():
                    if value:
                        # 处理数字字段
                        if key in ['价格', '评分', '评论数']:
                            try:
                                # 提取数字
                                import re
                                match = re.search(r'[\d.]+', str(value))
                                if match:
                                    record[key] = float(match.group())
                                else:
                                    record[key] = 0
                            except:
                                record[key] = 0
                        elif key == '采集时间':
                            # 处理时间字段
                            try:
                                record[key] = int(datetime.strptime(value, "%Y-%m-%d %H:%M:%S").timestamp() * 1000)
                            except:
                                record[key] = int(datetime.now().timestamp() * 1000)
                        else:
                            record[key] = str(value)
                
                # 创建记录请求
                create_record_req = v1.CreateAppTableRecordRequest.builder() \
                    .app_token(app_token) \
                    .table_id(table_id) \
                    .request_body(
                        v1.AppTableRecord.builder()
                            .fields(record)
                            .build()
                    ) \
                    .build()
                
                # 发送请求
                record_resp = client.bitable.v1.app_table_record.create(create_record_req)
                
                if record_resp.success():
                    success_count += 1
                    if (i + 1) % 10 == 0:
                        print(f"  进度: {i + 1}/{len(rows)} (成功: {success_count}, 失败: {error_count})")
                else:
                    error_count += 1
                    print(f"  ✗ 上传失败 (第 {i+1} 条): {record_resp.code} - {record_resp.msg}")
                
                # 避免速率限制
                time.sleep(0.3)
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ 上传异常 (第 {i+1} 条): {e}")
        
        print(f"\n[完成] 上传完成")
        print(f"  成功: {success_count} 条")
        print(f"  失败: {error_count} 条")
        print(f"  总计: {len(rows)} 条")
        
    except Exception as e:
        print(f"[错误] 上传数据异常: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print("="*60)
    print("上传品牌和商品数据到飞书")
    print("="*60)
    
    # 读取 CSV 文件
    rows = read_csv_file(CSV_FILE)
    
    if not rows:
        print("[错误] 无法读取 CSV 文件")
        return
    
    # 创建飞书客户端
    client = create_client()
    
    if not client:
        print("[错误] 无法创建飞书客户端")
        return
    
    # 创建多维表格
    app_token = create_bitable(client)
    
    if not app_token:
        print("[错误] 无法创建多维表格")
        return
    
    # 获取第一个数据表
    table_id = get_first_table(client, app_token)
    
    if not table_id:
        print("[错误] 无法获取数据表")
        return
    
    # 添加表格列
    add_columns(client, app_token, table_id)
    
    # 上传数据
    upload_data_to_feishu(client, app_token, table_id, rows)
    
    print("\n[完成] 数据上传完成！")


if __name__ == "__main__":
    import time  # 延迟导入，避免与全局变量冲突
    main()
