"""
直接采集 YP 商家数据（假设已经登录）
"""

import requests
import json
from pathlib import Path
import time


def collect_yp_merchants():
    """采集 YP 商家数据"""
    
    print("\n" + "="*50)
    print("YP 商家数据采集工具")
    print("="*50 + "\n")
    
    # API 端点
    api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    
    # 创建 session
    session = requests.Session()
    
    # 设置 headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.yeahpromos.com/index/index/merchantlogin',
        'X-Requested-With': 'XMLHttpRequest',
        'Connection': 'keep-alive'
    }
    
    session.headers.update(headers)
    
    print("[1/3] 正在请求商家数据 API...")
    
    try:
        response = session.get(api_url, timeout=15)
        print(f"      HTTP 状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("[2/3] 解析响应数据...")
            
            try:
                data = response.json()
                
                # 检查响应结构
                if 'code' in data:
                    code = data.get('code')
                    msg = data.get('msg', '')
                    
                    if code == 1:
                        merchants = data.get('data', [])
                        print(f"      OK: 成功获取 {len(merchants)} 个商家数据")
                        
                        # 保存数据
                        return save_merchants(merchants)
                    else:
                        print(f"      ERROR: API 返回错误 (code={code})")
                        print(f"      消息: {msg}")
                        return False
                else:
                    print("      ERROR: 响应格式不符合预期")
                    print(f"      响应内容: {str(data)[:200]}")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"      ERROR: JSON 解析失败 - {e}")
                print(f"      响应内容: {response.text[:200]}")
                return False
                
        else:
            print(f"      ERROR: HTTP 请求失败")
            return False
            
    except requests.exceptions.Timeout:
        print("      ERROR: 请求超时")
        return False
    except Exception as e:
        print(f"      ERROR: {e}")
        return False


def save_merchants(merchants):
    """保存商家数据"""
    
    if not merchants:
        print("[3/3] 没有数据可保存")
        return False
    
    print("\n[3/3] 保存商家数据...")
    
    try:
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存 JSON
        json_file = output_dir / "yp_merchants.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merchants, f, ensure_ascii=False, indent=2)
        print(f"      OK: 已保存到 {json_file}")
        
        # 保存 CSV
        if merchants:
            csv_file = output_dir / "yp_merchants.csv"
            import csv
            
            # 收集所有字段名
            all_keys = set()
            for merchant in merchants:
                all_keys.update(merchant.keys())
            fieldnames = sorted(all_keys)
            
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(merchants)
            
            print(f"      OK: 已保存到 {csv_file}")
        
        # 显示统计信息
        print(f"\n{'='*50}")
        print("采集完成！")
        print(f"{'='*50}")
        print(f"商家总数: {len(merchants)}")
        
        # 显示示例数据
        if merchants:
            print(f"\n第一个商家示例:")
            sample = merchants[0]
            for i, (key, value) in enumerate(sample.items()):
                if i >= 5:  # 只显示前5个字段
                    break
                value_str = str(value)
                if len(value_str) > 60:
                    value_str = value_str[:60] + "..."
                print(f"  {key}: {value_str}")
        
        return True
        
    except Exception as e:
        print(f"      ERROR: 保存数据时出错 - {e}")
        return False


if __name__ == "__main__":
    success = collect_yp_merchants()
    
    if success:
        print("\n[成功] 采集任务完成！")
    else:
        print("\n[失败] 采集任务失败")
        print("\n提示: 可能需要先在浏览器中登录 YP 平台")
    
    input("\n按回车键退出...")
