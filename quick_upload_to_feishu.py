#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速上传数据到飞书 - 简化版本

使用说明：
1. 替换下面的 APP_ID 和 APP_SECRET 为您的飞书凭证
2. 运行脚本：python quick_upload_to_feishu.py
"""

import json
from pathlib import Path
from datetime import datetime
import sys
import io

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

# 可选：使用现有表格（如果要创建新表格，留空即可）
APP_TOKEN = ""  # 现有表格的app_token（从URL中获取）
TABLE_ID = ""  # 现有表格的table_id

# ============================================================


def create_bitable(client):
    """
    创建新的多维表格
    返回 app_token 或 None
    """
    try:
        print("[信息] 创建新的多维表格...")
        
        # 使用 CreateAppRequest 创建
        create_req = v1.CreateAppRequest.builder() \
            .request_body(
                v1.App.builder()
                    .name("YP商家和亚马逊商品数据")
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
    """
    获取多维表格中的第一个数据表
    返回 table_id 或 None
    """
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
    """
    添加表格列
    """
    try:
        print(f"[步骤4] 添加表格列...")
        
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
                    print(f"  [OK] {col_name}")
                else:
                    print(f"  [跳过] {col_name} (可能已存在: {field_resp.msg})")
            except Exception as e:
                print(f"  [跳过] {col_name} ({str(e)[:60]})")
    
    except Exception as e:
        print(f"[警告] 添加列时出错: {str(e)}")


def convert_to_record(item):
    """
    将数据项转换为飞书记录格式
    """
    fields = {}
    
    # 字段映射
    field_map = {
        'yp_merchant_name': '商家名称',
        'yp_commission': '佣金',
        'yp_category': '类别',
        'amazon_asin': 'ASIN',
        'amazon_title': '商品名称',
        'amazon_price': '价格',
        'amazon_rating': '评分',
        'amazon_reviews': '评论数',
        'amazon_image_url': '图片链接',
        'amazon_product_url': '商品链接',
        'amazon_description': '商品描述',
        'amazon_brand': '品牌',
        'amazon_features': '商品特性',
    }
    
    for src_key, dst_key in field_map.items():
        if src_key in item:
            value = item[src_key]
            # 特殊处理数字字段
            if dst_key in ['价格', '评分', '评论数']:
                try:
                    fields[dst_key] = float(value) if value else 0
                except:
                    fields[dst_key] = 0
            # 特殊处理列表字段
            elif dst_key == '商品特性' and isinstance(value, list):
                fields[dst_key] = ' | '.join(str(v) for v in value)
            # 特殊处理URL字段
            elif dst_key == '商品链接':
                fields[dst_key] = str(value) if value else ''
            else:
                fields[dst_key] = str(value) if value is not None else ''
    
    # 添加采集时间（使用正确的飞书时间格式）
    fields['采集时间'] = int(datetime.now().timestamp() * 1000)
    
    return {'fields': fields}


def upload_data(client, app_token, table_id, data):
    """
    批量上传数据
    返回成功上传的数量
    """
    try:
        print(f"\n[步骤5] 上传数据...")
        
        batch_size = 500
        uploaded = 0
        failed = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            # 转换为飞书记录格式
            records = [convert_to_record(item) for item in batch]
            
            # 创建记录对象
            record_objects = []
            for record in records:
                record_obj = v1.AppTableRecord.builder()
                record_obj = record_obj.fields(record['fields'])
                record_objects.append(record_obj.build())
            
            # 批量创建记录
            create_req = v1.BatchCreateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .request_body(
                    v1.BatchCreateAppTableRecordRequestBody.builder()
                        .records(record_objects)
                        .build()
                ) \
                .build()
            
            resp = client.bitable.v1.app_table_record.batch_create(create_req)
            
            if resp.success():
                uploaded += len(batch)
                print(f"  [进度] {uploaded}/{len(data)} 条已上传")
            else:
                failed += len(batch)
                print(f"  [错误] 批量上传失败: {resp.code} - {resp.msg}")
        
        if uploaded > 0:
            print(f"\n[成功] 成功上传 {uploaded} 条记录")
            if failed > 0:
                print(f"[警告] {failed} 条记录上传失败")
        
        return uploaded
        
    except Exception as e:
        print(f"[错误] 上传数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """主函数"""
    print("=" * 70)
    print("  飞书数据快速上传工具")
    print("=" * 70)
    
    # 检查配置
    if "cli_a935343a74f89cd4" not in APP_ID:
        print("\n[错误] 请先配置飞书凭证！")
        return
    
    # 文件路径
    project_dir = Path(__file__).parent
    output_dir = project_dir / 'output'
    
    # 查找数据文件
    json_file = output_dir / 'comprehensive_yp_amazon_data_v2.json'
    csv_file = output_dir / 'comprehensive_yp_amazon_data_v2.csv'
    
    data_file = None
    file_type = None
    
    if json_file.exists():
        data_file = json_file
        file_type = 'json'
        print(f"\n[信息] 使用JSON文件: {data_file.name}")
    elif csv_file.exists():
        data_file = csv_file
        file_type = 'csv'
        print(f"\n[信息] 使用CSV文件: {data_file.name}")
    else:
        print(f"\n[错误] 未找到数据文件")
        print(f"[提示] 请确保以下文件存在:")
        print(f"  - {json_file}")
        print(f"  - {csv_file}")
        return
    
    # 读取数据
    print(f"\n[步骤1] 读取数据文件...")
    try:
        if file_type == 'json':
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            import csv
            data = []
            with open(data_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
        
        print(f"[成功] 读取到 {len(data)} 条记录")
        
        if not data:
            print("[错误] 数据文件为空")
            return
            
    except Exception as e:
        print(f"[错误] 读取文件失败: {str(e)}")
        return
    
    # 创建飞书客户端
    print(f"\n[步骤2] 连接飞书...")
    try:
        client = lark.Client.builder() \
            .app_id(APP_ID) \
            .app_secret(APP_SECRET) \
            .log_level(lark.LogLevel.INFO) \
            .build()
        print("[成功] 飞书客户端已初始化")
    except Exception as e:
        print(f"[错误] 初始化飞书客户端失败: {str(e)}")
        return
    
    # 创建或使用表格
    print(f"\n[步骤3] 准备多维表格...")
    try:
        # 尝试使用现有表格
        if APP_TOKEN:
            print(f"[信息] 使用现有表格: {APP_TOKEN}")
            app_token = APP_TOKEN
            table_id = TABLE_ID
            
            if not table_id:
                table_id = get_first_table(client, app_token)
                if not table_id:
                    return
        else:
            # 创建新表格
            app_token = create_bitable(client)
            if not app_token:
                return
            
            # 获取表格
            table_id = get_first_table(client, app_token)
            if not table_id:
                return
            
            # 添加列
            add_columns(client, app_token, table_id)
    
    except Exception as e:
        print(f"[错误] 准备表格失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # 上传数据
    uploaded = upload_data(client, app_token, table_id, data)
    
    if uploaded > 0:
        # 生成表格链接
        table_url = f"https://example.feishu.cn/base/{app_token}"
        
        print(f"\n{'=' * 70}")
        print(f"  ✅ 上传完成！")
        print(f"{'=' * 70}")
        print(f"\n[链接] {table_url}")
        print(f"\n[提示] 点击上面的链接在飞书中查看数据")
        print(f"[App Token] {app_token}")
        print(f"[Table ID] {table_id}")
        print(f"\n[下次使用] 如果要追加数据到此表格，可以在脚本中设置:")
        print(f"  APP_TOKEN = \"{app_token}\"")
        print(f"  TABLE_ID = \"{table_id}\"")
        print(f"\n保存这些信息以便下次使用！")


if __name__ == "__main__":
    main()
