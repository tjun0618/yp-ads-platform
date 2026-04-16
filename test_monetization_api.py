import requests
import json
from datetime import datetime, timedelta

def test_monetization_api():
    """
    测试 Monetization API，查看返回的数据
    """
    
    # API 配置
    api_url = "https://yeahpromos.com/index/Getorder/getorder"
    
    # 用户提供的凭证
    token = "7951dc7484fa9f9d"
    site_id = "12002"
    channel_name = "shelovable"
    
    # 计算日期范围（最近 7 天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    # 请求头
    headers = {
        "token": token
    }
    
    # 请求参数
    params = {
        "site_id": site_id,
        "startDate": start_date_str,
        "endDate": end_date_str,
        "is_amazon": 1,  # 只返回亚马逊订单
        "page": 1,
        "limit": 100  # 先获取 100 条看看
    }
    
    print("=" * 80)
    print("Monetization API 测试")
    print("=" * 80)
    print(f"Channel Name: {channel_name}")
    print(f"Site ID: {site_id}")
    print(f"Token: {token}")
    print(f"日期范围: {start_date_str} 到 {end_date_str}")
    print(f"是否只返回亚马逊订单: 是")
    print("=" * 80)
    print()
    
    try:
        # 发送请求
        print("正在发送 API 请求...")
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        print(f"HTTP 状态码: {response.status_code}")
        print()
        
        # 解析响应
        if response.status_code == 200:
            data = response.json()
            
            print("API 响应成功！")
            print()
            
            # 保存完整响应到文件
            with open("yp_to_feishu/api_test_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("完整响应已保存到: yp_to_feishu/api_test_response.json")
            print()
            
            # 显示响应结构
            print("=" * 80)
            print("响应数据结构:")
            print("=" * 80)
            
            if isinstance(data, dict):
                # 显示顶层字段
                print("顶层字段:")
                for key in data.keys():
                    value = data[key]
                    if isinstance(value, list):
                        print(f"  {key}: 列表 (长度: {len(value)})")
                    elif isinstance(value, dict):
                        print(f"  {key}: 对象 (键: {list(value.keys())})")
                    else:
                        print(f"  {key}: {value}")
                print()
                
                # 检查是否有交易数据
                if "data" in data and isinstance(data["data"], list):
                    transactions = data["data"]
                    print(f"交易数量: {len(transactions)}")
                    print()
                    
                    if len(transactions) > 0:
                        print("=" * 80)
                        print("第一条交易数据的字段:")
                        print("=" * 80)
                        first_transaction = transactions[0]
                        for key, value in first_transaction.items():
                            print(f"  {key}: {value}")
                        print()
                        
                        # 显示前 5 条交易数据
                        print("=" * 80)
                        print(f"前 {min(5, len(transactions))} 条交易数据:")
                        print("=" * 80)
                        for i, transaction in enumerate(transactions[:5]):
                            print(f"\n交易 #{i+1}:")
                            for key, value in transaction.items():
                                print(f"  {key}: {value}")
                        print()
                        
                        # 统计信息
                        print("=" * 80)
                        print("数据统计:")
                        print("=" * 80)
                        print(f"总交易数: {len(transactions)}")
                        
                        total_amount = sum(float(t.get("amount", 0)) for t in transactions if t.get("amount"))
                        print(f"总金额: ${total_amount:.2f}")
                        
                        total_commission = sum(float(t.get("sale_comm", 0)) for t in transactions if t.get("sale_comm"))
                        print(f"总佣金: ${total_commission:.2f}")
                        
                        # 检查是否有 advert_id 字段
                        if any("advert_id" in t for t in transactions):
                            advert_ids = set(t.get("advert_id") for t in transactions if "advert_id" in t)
                            print(f"唯一的广告 ID 数量: {len(advert_ids)}")
                            print(f"广告 ID 列表: {list(advert_ids)[:10]}...")
                        print()
                        
                        # 分析数据字段
                        print("=" * 80)
                        print("所有交易数据的字段列表:")
                        print("=" * 80)
                        all_keys = set()
                        for transaction in transactions:
                            all_keys.update(transaction.keys())
                        for key in sorted(all_keys):
                            print(f"  {key}")
                        print()
                        
                else:
                    print("没有找到交易数据（data 字段）")
                    print("响应内容:")
                    print(json.dumps(data, ensure_ascii=False, indent=2))
            
            else:
                print("响应数据类型不是对象:")
                print(type(data))
                print(data)
        
        else:
            print(f"API 请求失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except requests.exceptions.Timeout:
        print("错误: 请求超时")
    except requests.exceptions.ConnectionError:
        print("错误: 连接失败")
    except json.JSONDecodeError:
        print("错误: 无法解析 JSON 响应")
        print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_monetization_api()
