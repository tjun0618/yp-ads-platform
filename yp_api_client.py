"""
YeahPromos API Client
用于访问 YP 平台的 Transaction API
"""

import requests
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class YPAPIClient:
    """YeahPromos API 客户端"""
    
    def __init__(self, token: str, site_id: str):
        """
        初始化 API 客户端
        
        Args:
            token: YP 平台 token
            site_id: 网站站点 ID
        """
        self.base_url = "https://yeahpromos.com/index/Getorder/getorder"
        self.token = token
        self.site_id = site_id
        self.request_limit = 10  # 每分钟 10 次
        self.request_count = 0
        self.last_request_time = None
        self.session = requests.Session()
    
    def get_transactions(
        self,
        start_date: str,
        end_date: str,
        is_amazon: int = 1,
        page: int = 1,
        limit: int = 1000
    ) -> Optional[Dict]:
        """
        获取交易数据
        
        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            is_amazon: 是否只返回亚马逊订单（1: 是）
            page: 页码，默认 1
            limit: 每页数量，默认 1000
        
        Returns:
            dict: 包含交易数据和分页信息的字典，失败返回 None
        """
        # 检查速率限制
        self._check_rate_limit()
        
        # 构建请求参数
        params = {
            "site_id": self.site_id,
            "startDate": start_date,
            "endDate": end_date,
            "is_amazon": is_amazon,
            "page": page,
            "limit": limit
        }
        
        headers = {
            "token": self.token
        }
        
        try:
            # 发送请求
            print(f"[信息] 正在获取第 {page} 页数据（{start_date} 到 {end_date}）...")
            response = self.session.get(
                self.base_url,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            # 解析 JSON 响应
            data = response.json()
            
            # 检查返回码
            if data.get('code') != 100000:
                print(f"[错误] API 返回错误: {data.get('message', '未知错误')}")
                return None
            
            # 更新请求计数
            self._update_request_count()
            
            # 打印结果
            print(f"[成功] 获取到 {len(data.get('data', []))} 条记录")
            print(f"[信息] 当前页: {data.get('PageNow')} / 总页数: {data.get('PageTotal')}")
            print(f"[信息] 总记录数: {data.get('Num')}")
            
            return data
        
        except requests.exceptions.Timeout:
            print(f"[错误] 请求超时")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[错误] 请求失败: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"[错误] JSON 解析失败: {e}")
            return None
    
    def get_all_transactions(
        self,
        start_date: str,
        end_date: str,
        is_amazon: int = 1
    ) -> List[Dict]:
        """
        获取所有页的交易数据
        
        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            is_amazon: 是否只返回亚马逊订单（1: 是）
        
        Returns:
            list: 包含所有交易数据的列表
        """
        all_transactions = []
        page = 1
        total_pages = 1
        
        print(f"[开始] 开始获取从 {start_date} 到 {end_date} 的所有交易数据...")
        
        while True:
            # 获取当前页数据
            data = self.get_transactions(start_date, end_date, is_amazon, page)
            
            if not data:
                print(f"[错误] 获取第 {page} 页数据失败，停止获取")
                break
            
            # 添加交易数据
            transactions = data.get('data', [])
            all_transactions.extend(transactions)
            
            # 检查是否还有下一页
            total_pages = data.get('PageTotal', 1)
            if page >= total_pages:
                print(f"[完成] 已获取所有 {total_pages} 页数据")
                break
            
            page += 1
            
            # 短暂延迟，避免请求过快
            time.sleep(1)
        
        print(f"[完成] 共获取 {len(all_transactions)} 条交易数据")
        return all_transactions
    
    def get_transactions_last_days(self, days: int = 7, is_amazon: int = 1) -> List[Dict]:
        """
        获取最近 N 天的交易数据
        
        Args:
            days: 天数
            is_amazon: 是否只返回亚马逊订单（1: 是）
        
        Returns:
            list: 包含所有交易数据的列表
        """
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        return self.get_all_transactions(start_date, end_date, is_amazon)
    
    def get_transactions_today(self, is_amazon: int = 1) -> List[Dict]:
        """
        获取今天的交易数据
        
        Args:
            is_amazon: 是否只返回亚马逊订单（1: 是）
        
        Returns:
            list: 包含所有交易数据的列表
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.get_all_transactions(today, today, is_amazon)
    
    def export_to_csv(self, transactions: List[Dict], filename: str):
        """
        导出交易数据到 CSV 文件
        
        Args:
            transactions: 交易数据列表
            filename: CSV 文件名
        """
        import csv
        
        if not transactions:
            print("[警告] 没有交易数据可导出")
            return
        
        # CSV 字段
        fieldnames = [
            'id', 'advert_id', 'oid', 'creationDate_time',
            'amount', 'sale_comm', 'status', 'tag1', 'tag2', 'tag3'
        ]
        
        try:
            # 写入 CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(transactions)
            
            print(f"[成功] 成功导出 {len(transactions)} 条交易数据到 {filename}")
        
        except Exception as e:
            print(f"[错误] 导出 CSV 失败: {e}")
    
    def export_to_json(self, transactions: List[Dict], filename: str):
        """
        导出交易数据到 JSON 文件
        
        Args:
            transactions: 交易数据列表
            filename: JSON 文件名
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(transactions, f, ensure_ascii=False, indent=2)
            
            print(f"[成功] 成功导出 {len(transactions)} 条交易数据到 {filename}")
        
        except Exception as e:
            print(f"[错误] 导出 JSON 失败: {e}")
    
    def get_summary(self, transactions: List[Dict]) -> Dict:
        """
        获取交易数据摘要
        
        Args:
            transactions: 交易数据列表
        
        Returns:
            dict: 包含摘要信息的字典
        """
        if not transactions:
            return {}
        
        total_amount = 0
        total_commission = 0
        status_count = {}
        
        for transaction in transactions:
            # 累计金额和佣金
            try:
                total_amount += float(transaction.get('amount', 0))
                total_commission += float(transaction.get('sale_comm', 0))
            except (ValueError, TypeError):
                pass
            
            # 统计状态
            status = transaction.get('status', 'Unknown')
            status_count[status] = status_count.get(status, 0) + 1
        
        return {
            'total_transactions': len(transactions),
            'total_amount': round(total_amount, 2),
            'total_commission': round(total_commission, 2),
            'average_amount': round(total_amount / len(transactions), 2) if transactions else 0,
            'average_commission': round(total_commission / len(transactions), 2) if transactions else 0,
            'status_count': status_count
        }
    
    def _check_rate_limit(self):
        """检查速率限制"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < 60 and self.request_count >= self.request_limit:
                wait_time = 60 - elapsed
                print(f"[速率限制] 已达到每分钟 {self.request_limit} 次的限制，等待 {wait_time:.2f} 秒...")
                time.sleep(wait_time)
                self.request_count = 0
    
    def _update_request_count(self):
        """更新请求计数"""
        self.request_count += 1
        self.last_request_time = time.time()


# 使用示例
if __name__ == "__main__":
    # 注意：请替换为您的实际 token 和 site_id
    TOKEN = "YOUR_TOKEN_HERE"
    SITE_ID = "YOUR_SITE_ID_HERE"
    
    # 创建 API 客户端
    api = YPAPIClient(token=TOKEN, site_id=SITE_ID)
    
    # 获取最近 7 天的数据
    print("\n" + "="*60)
    print("示例 1: 获取最近 7 天的交易数据")
    print("="*60)
    
    transactions = api.get_transactions_last_days(days=7, is_amazon=1)
    
    # 获取摘要
    summary = api.get_summary(transactions)
    print("\n[摘要]")
    print(f"总交易数: {summary.get('total_transactions', 0)}")
    print(f"总金额: ${summary.get('total_amount', 0)}")
    print(f"总佣金: ${summary.get('total_commission', 0)}")
    print(f"平均金额: ${summary.get('average_amount', 0)}")
    print(f"平均佣金: ${summary.get('average_commission', 0)}")
    print(f"状态分布: {summary.get('status_count', {})}")
    
    # 导出到 CSV
    api.export_to_csv(transactions, "transactions_last_7_days.csv")
    
    # 导出到 JSON
    api.export_to_json(transactions, "transactions_last_7_days.json")
    
    # 获取今天的交易数据
    print("\n" + "="*60)
    print("示例 2: 获取今天的交易数据")
    print("="*60)
    
    today_transactions = api.get_transactions_today(is_amazon=1)
    
    # 获取摘要
    today_summary = api.get_summary(today_transactions)
    print("\n[今天的摘要]")
    print(f"总交易数: {today_summary.get('total_transactions', 0)}")
    print(f"总金额: ${today_summary.get('total_amount', 0)}")
    print(f"总佣金: ${today_summary.get('total_commission', 0)}")
    
    # 导出今天的交易数据
    api.export_to_csv(today_transactions, "transactions_today.csv")
