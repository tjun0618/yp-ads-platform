#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
将采集的数据上传到飞书多维表格
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')

try:
    from lark_oapi.api.bitable.v1 import *
    from lark_oapi.api.docx.v1 import *
    from lark_oapi.api.drive.v1 import *
    import lark_oapi as lark
except ImportError:
    print("[错误] 未安装飞书SDK，请运行: pip install lark-oapi")
    sys.exit(1)


class FeishuUploader:
    """飞书数据上传器"""
    
    def __init__(self, app_id: str, app_secret: str):
        """初始化飞书客户端"""
        self.app_id = app_id
        self.app_secret = app_secret
        
        # 创建飞书客户端
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    
    def upload_data_to_bitable(self, data: List[Dict[str, Any]], 
                               app_token: str = None,
                               table_id: str = None,
                               table_name: str = "采集数据"):
        """
        上传数据到飞书多维表格
        
        Args:
            data: 要上传的数据列表
            app_token: 应用Token（表格ID）
            table_id: 表格ID（可选）
            table_name: 表格名称
            
        Returns:
            成功返回表格URL，失败返回None
        """
        try:
            print(f"[开始] 上传{len(data)}条数据到飞书...")
            
            if not app_token:
                print("[提示] 未提供应用Token，创建新表格...")
                return self.create_new_bitable(data, table_name)
            else:
                print(f"[信息] 使用现有表格: {app_token}")
                return self.append_to_existing_bitable(app_token, table_id, data)
                
        except Exception as e:
            print(f"[错误] 上传失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def create_new_bitable(self, data: List[Dict[str, Any]], table_name: str):
        """
        创建新的多维表格并上传数据
        """
        try:
            print("[步骤1] 创建多维表格...")
            
            # 创建多维表格请求
            create_req = CreateAppTableRequest.builder() \
                .app(App.builder()
                    .name(table_name)
                    .build()) \
                .build()
            
            create_resp = self.client.bitable.v1.app.create(create_req)
            
            if not create_resp.success():
                print(f"[错误] 创建表格失败: {create_resp.code} - {create_resp.msg}")
                return None
            
            app_token = create_resp.data.app.app_token
            print(f"[成功] 表格已创建，Token: {app_token}")
            
            # 创建数据表
            print("[步骤2] 创建数据表...")
            table_req = CreateAppTableTableRequest.builder() \
                .app_token(app_token) \
                .table(Table.builder()
                    .name("商品数据")
                    .default_view_name("全部数据")
                    .build()) \
                .build()
            
            table_resp = self.client.bitable.v1.app_table.create(table_req)
            
            if not table_resp.success():
                print(f"[错误] 创建数据表失败: {table_resp.code} - {table_resp.msg}")
                return None
            
            table_id = table_resp.data.table.table_id
            print(f"[成功] 数据表已创建，ID: {table_id}")
            
            # 添加列
            print("[步骤3] 添加表格列...")
            self._add_columns_to_table(app_token, table_id, data[0])
            
            # 上传数据
            print("[步骤4] 上传数据...")
            result = self._batch_upload_records(app_token, table_id, data)
            
            if result:
                # 生成表格链接
                table_url = f"https://example.feishu.cn/base/{app_token}"
                print(f"\n[完成] 数据上传成功！")
                print(f"[链接] {table_url}")
                return table_url
            
            return None
            
        except Exception as e:
            print(f"[错误] 创建表格失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def append_to_existing_bitable(self, app_token: str, 
                                   table_id: str, 
                                   data: List[Dict[str, Any]]):
        """
        向现有表格追加数据
        """
        try:
            print(f"[信息] 向现有表格追加{len(data)}条数据...")
            
            if not table_id:
                # 获取第一个表格
                list_req = ListAppTableRequest.builder() \
                    .app_token(app_token) \
                    .build()
                
                list_resp = self.client.bitable.v1.app_table.list(list_req)
                
                if not list_resp.success() or not list_resp.data.items:
                    print("[错误] 未找到表格")
                    return None
                
                table_id = list_resp.data.items[0].table_id
                print(f"[信息] 使用表格ID: {table_id}")
            
            # 上传数据
            result = self._batch_upload_records(app_token, table_id, data)
            
            if result:
                table_url = f"https://example.feishu.cn/base/{app_token}"
                print(f"\n[完成] 数据追加成功！")
                print(f"[链接] {table_url}")
                return table_url
            
            return None
            
        except Exception as e:
            print(f"[错误] 追加数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def _add_columns_to_table(self, app_token: str, table_id: str, 
                              sample_record: Dict[str, Any]):
        """
        根据数据样本添加表格列
        """
        try:
            # 定义字段映射
            field_mapping = {
                'yp_merchant_name': {'name': '商家名称', 'type': 1},  # text
                'yp_commission': {'name': '佣金', 'type': 1},  # text
                'yp_category': {'name': '类别', 'type': 1},  # text
                'amazon_asin': {'name': 'ASIN', 'type': 1},  # text
                'amazon_title': {'name': '商品名称', 'type': 1},  # text
                'amazon_price': {'name': '价格', 'type': 2},  # number
                'amazon_rating': {'name': '评分', 'type': 2},  # number
                'amazon_reviews': {'name': '评论数', 'type': 2},  # number
                'amazon_image_url': {'name': '图片链接', 'type': 1},  # text
                'amazon_product_url': {'name': '商品链接', 'type': 15},  # url
                'amazon_description': {'name': '商品描述', 'type': 1},  # text
                'amazon_brand': {'name': '品牌', 'type': 1},  # text
                'amazon_features': {'name': '商品特性', 'type': 1},  # text
            }
            
            for key, field_info in field_mapping.items():
                if key in sample_record:
                    create_field_req = CreateAppTableFieldRequest.builder() \
                        .app_token(app_token) \
                        .table_id(table_id) \
                        .field(AppTableField.builder()
                            .field_name(field_info['name'])
                            .type(field_info['type'])
                            .build()) \
                        .build()
                    
                    field_resp = self.client.bitable.v1.app_table_field.create(create_field_req)
                    
                    if field_resp.success():
                        print(f"  [OK] 已添加列: {field_info['name']}")
                    else:
                        print(f"  [跳过] {field_info['name']} (可能已存在)")
            
        except Exception as e:
            print(f"[警告] 添加列时出错: {str(e)}")
    
    def _batch_upload_records(self, app_token: str, table_id: str, 
                               data: List[Dict[str, Any]]):
        """
        批量上传记录
        """
        try:
            # 飞书批量上传限制为500条
            batch_size = 500
            uploaded = 0
            
            for i in range(0, len(data), batch_size):
                batch = data[i:i + batch_size]
                
                # 转换为飞书记录格式
                records = []
                for item in batch:
                    record = self._convert_to_record(item)
                    records.append(record)
                
                # 批量创建记录
                create_req = BatchCreateAppTableRecordRequest.builder() \
                    .app_token(app_token) \
                    .table_id(table_id) \
                    .records(records) \
                    .build()
                
                resp = self.client.bitable.v1.app_table_record.batch_create(create_req)
                
                if resp.success():
                    uploaded += len(batch)
                    print(f"  [进度] 已上传 {uploaded}/{len(data)} 条记录")
                else:
                    print(f"[错误] 批量上传失败: {resp.code} - {resp.msg}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"[错误] 批量上传失败: {str(e)}")
            return False
    
    def _convert_to_record(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        将数据项转换为飞书记录格式
        """
        fields = {}
        
        # YP商家信息
        if 'yp_merchant_name' in item:
            fields['商家名称'] = item['yp_merchant_name']
        if 'yp_commission' in item:
            fields['佣金'] = str(item['yp_commission'])
        if 'yp_category' in item:
            fields['类别'] = str(item.get('yp_category', ''))
        
        # 亚马逊产品信息
        if 'amazon_asin' in item:
            fields['ASIN'] = item['amazon_asin']
        if 'amazon_title' in item:
            fields['商品名称'] = item['amazon_title']
        if 'amazon_price' in item:
            try:
                fields['价格'] = float(item['amazon_price'])
            except:
                fields['价格'] = 0
        if 'amazon_rating' in item:
            try:
                fields['评分'] = float(item['amazon_rating'])
            except:
                fields['评分'] = 0
        if 'amazon_reviews' in item:
            try:
                fields['评论数'] = int(item['amazon_reviews'])
            except:
                fields['评论数'] = 0
        if 'amazon_image_url' in item:
            fields['图片链接'] = item['amazon_image_url']
        if 'amazon_product_url' in item:
            fields['商品链接'] = item['amazon_product_url']
        if 'amazon_description' in item:
            fields['商品描述'] = item['amazon_description']
        if 'amazon_brand' in item:
            fields['品牌'] = item['amazon_brand']
        if 'amazon_features' in item:
            features = item['amazon_features']
            if isinstance(features, list):
                fields['商品特性'] = ' | '.join(str(f) for f in features)
            else:
                fields['商品特性'] = str(features)
        
        # 添加采集时间
        fields['采集时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return {'fields': fields}
    
    def upload_json_file(self, json_file: Path, 
                         app_token: str = None,
                         table_name: str = "采集数据"):
        """
        从JSON文件上传数据
        """
        try:
            print(f"[开始] 读取JSON文件: {json_file}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                print("[错误] JSON文件为空")
                return None
            
            print(f"[信息] 读取到 {len(data)} 条记录")
            
            return self.upload_data_to_bitable(data, app_token, table_name=table_name)
            
        except Exception as e:
            print(f"[错误] 读取JSON文件失败: {str(e)}")
            return None
    
    def upload_csv_file(self, csv_file: Path, 
                       app_token: str = None,
                       table_name: str = "采集数据"):
        """
        从CSV文件上传数据
        """
        try:
            print(f"[开始] 读取CSV文件: {csv_file}")
            
            data = []
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            
            if not data:
                print("[错误] CSV文件为空")
                return None
            
            print(f"[信息] 读取到 {len(data)} 条记录")
            
            return self.upload_data_to_bitable(data, app_token, table_name=table_name)
            
        except Exception as e:
            print(f"[错误] 读取CSV文件失败: {str(e)}")
            return None


def main():
    """主函数"""
    print("=" * 60)
    print("  飞书数据上传工具")
    print("=" * 60)
    
    # 配置信息（请替换为真实的飞书凭证）
    APP_ID = "cli_xxxxxxxxx"  # 请替换为您的飞书应用ID
    APP_SECRET = "xxxxxxxxxxxx"  # 请替换为您的飞书应用密钥
    
    # 可选：使用现有表格
    # APP_TOKEN = "bascxxxxxxxxxxxxx"  # 现有表格的app_token
    # TABLE_ID = "tblxxxxxxxxxxxxx"  # 现有表格的table_id
    
    # 文件路径
    project_dir = Path(__file__).parent
    output_dir = project_dir / 'output'
    comprehensive_json = output_dir / 'comprehensive_yp_amazon_data_v2.json'
    comprehensive_csv = output_dir / 'comprehensive_yp_amazon_data_v2.csv'
    
    # 选择文件类型
    if comprehensive_json.exists():
        data_file = comprehensive_json
        print(f"\n[信息] 使用JSON文件: {data_file.name}")
    elif comprehensive_csv.exists():
        data_file = comprehensive_csv
        print(f"\n[信息] 使用CSV文件: {data_file.name}")
    else:
        print(f"\n[错误] 未找到数据文件")
        print(f"[提示] 请确保以下文件存在:")
        print(f"  - {comprehensive_json}")
        print(f"  - {comprehensive_csv}")
        return
    
    # 创建上传器
    print(f"\n[信息] 初始化飞书客户端...")
    uploader = FeishuUploader(APP_ID, APP_SECRET)
    
    # 上传数据
    print(f"\n[开始] 上传数据到飞书...")
    result = uploader.upload_json_file(data_file, table_name="YP商家和亚马逊商品数据")
    
    if result:
        print(f"\n{'=' * 60}")
        print(f"  上传完成！")
        print(f"{'=' * 60}")
        print(f"\n[链接] {result}")
        print(f"\n[提示] 您可以点击上面的链接在飞书中查看数据")
    else:
        print(f"\n{'=' * 60}")
        print(f"  上传失败")
        print(f"{'=' * 60}")
        print(f"\n[提示] 请检查:")
        print(f"  1. 飞书应用ID和密钥是否正确")
        print(f"  2. 飞书应用是否有足够的权限")
        print(f"  3. 网络连接是否正常")


if __name__ == "__main__":
    main()
