"""
快速采集 YP 商家数据
"""

import requests
import json
from pathlib import Path


def main():
    print("\n开始采集 YP 商家数据...\n")
    
    # API URL
    api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
    
    # Headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Referer': 'https://www.yeahpromos.com/',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        print("正在请求 API...")
        response = requests.get(api_url, headers=headers, timeout=10)
        
        print(f"状态码: {response.status_code}")
        print(f"响应类型: {type(response.text)}")
        print(f"响应长度: {len(response.text)}")
        
        # 显示响应内容的前 200 个字符
        print(f"\n响应内容（前200字符）:\n{response.text[:200]}")
        
        # 尝试解析 JSON
        try:
            data = response.json()
            print(f"\nJSON 解析成功！")
            print(f"Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        except Exception as e:
            print(f"\nJSON 解析失败: {e}")
            print(f"完整响应:\n{response.text}")
            return False
        
        if isinstance(data, dict) and data.get('code') == 1:
            merchants = data.get('data', [])
            print(f"\n成功获取 {len(merchants)} 个商家数据")
            
            if not isinstance(merchants, list):
                print(f"警告: data 不是列表，类型为 {type(merchants)}")
                return False
            
            # 保存数据
            output_dir = Path("output")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # JSON
            json_file = output_dir / "yp_merchants.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(merchants, f, ensure_ascii=False, indent=2)
            print(f"\n已保存: {json_file}")
            
            # CSV
            csv_file = output_dir / "yp_merchants.csv"
            import csv
            
            all_keys = set()
            for m in merchants:
                all_keys.update(m.keys())
            
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
                writer.writeheader()
                writer.writerows(merchants)
            
            print(f"已保存: {csv_file}")
            
            # 显示第一个商家的信息
            if merchants:
                print(f"\n第一个商家:")
                for key, value in list(merchants[0].items())[:3]:
                    val_str = str(value)
                    if len(val_str) > 50:
                        val_str = val_str[:50] + "..."
                    print(f"  {key}: {val_str}")
            
            return True
        else:
            print(f"\nAPI 错误或响应格式不正确")
            return False
            
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    main()
