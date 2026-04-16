import requests
import json
import sys
import io

# 设置标准输出为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_offer_api_no_filter():
    """
    测试 Offer API（不添加 link_status 参数，获取所有商品）
    """
    print("=" * 80)
    print("测试 Offer API（不添加 link_status 参数）")
    print("=" * 80)
    
    api_url = "https://yeahpromos.com/index/apioffer/getoffer"
    
    token = "7951dc7484fa9f9d"
    site_id = "12002"
    
    headers = {
        "token": token
    }
    
    params = {
        "site_id": site_id,
        "page": 1,
        "limit": 100
    }
    
    try:
        print(f"API URL: {api_url}")
        print(f"参数: {params}")
        print()
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        print(f"HTTP 状态码: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            
            print("[成功] API 响应成功！")
            print()
            
            # 保存完整响应
            with open("yp_to_feishu/offer_api_response_no_filter.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("完整响应已保存到: yp_to_feishu/offer_api_response_no_filter.json")
            print()
            
            # 显示数据
            if isinstance(data, dict):
                print("顶层字段:")
                for key in data.keys():
                    value = data[key]
                    if isinstance(value, list):
                        print(f"  {key}: 列表 (长度: {len(value)})")
                    elif isinstance(value, dict):
                        print(f"  {key}: 对象")
                    else:
                        print(f"  {key}: {value}")
                print()
                
                if "data" in data and isinstance(data["data"], list):
                    products = data["data"]
                    print(f"商品数量: {len(products)}")
                    print()
                    
                    if len(products) > 0:
                        print("=" * 80)
                        print("第一条商品数据:")
                        print("=" * 80)
                        first_product = products[0]
                        for key, value in first_product.items():
                            print(f"  {key}: {value}")
                        print()
                        
                        # 显示前 5 条商品
                        print("=" * 80)
                        print(f"前 {min(5, len(products))} 条商品数据:")
                        print("=" * 80)
                        for i, product in enumerate(products[:5]):
                            print(f"\n商品 #{i+1}:")
                            for key, value in product.items():
                                print(f"  {key}: {value}")
                        print()
                else:
                    print("没有找到商品数据（data 字段）")
        
        else:
            print(f"[失败] API 请求失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except Exception as e:
        print(f"[失败] 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print()
    return response.status_code == 200


if __name__ == "__main__":
    test_offer_api_no_filter()
