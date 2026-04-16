import requests
import json
from datetime import datetime, timedelta

def test_merchant_api():
    """
    测试 Merchant API（获取品牌列表）
    """
    print("=" * 80)
    print("测试 Merchant API")
    print("=" * 80)
    
    api_url = "https://yeahpromos.com/index/getadvert/getadvert"
    
    token = "7951dc7484fa9f9d"
    site_id = "12002"
    
    headers = {
        "token": token
    }
    
    params = {
        "site_id": site_id,
        "elite": 0,  # 0: no, 1: yes
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
            
            print("✅ API 响应成功！")
            print()
            
            # 保存完整响应
            with open("yp_to_feishu/merchant_api_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("完整响应已保存到: yp_to_feishu/merchant_api_response.json")
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
                
                if "Data" in data and isinstance(data["Data"], list):
                    merchants = data["Data"]
                    print(f"品牌数量: {len(merchants)}")
                    print()
                    
                    if len(merchants) > 0:
                        print("=" * 80)
                        print("第一条品牌数据:")
                        print("=" * 80)
                        first_merchant = merchants[0]
                        for key, value in first_merchant.items():
                            print(f"  {key}: {value}")
                        print()
                        
                        # 显示前 5 条品牌
                        print("=" * 80)
                        print(f"前 {min(5, len(merchants))} 条品牌数据:")
                        print("=" * 80)
                        for i, merchant in enumerate(merchants[:5]):
                            print(f"\n品牌 #{i+1}:")
                            for key, value in merchant.items():
                                print(f"  {key}: {value}")
                        print()
                else:
                    print("没有找到品牌数据（Data 字段）")
        
        else:
            print(f"❌ API 请求失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print()
    return response.status_code == 200


def test_offer_api():
    """
    测试 Offer API（获取商品列表）
    """
    print("=" * 80)
    print("测试 Offer API")
    print("=" * 80)
    
    api_url = "https://yeahpromos.com/index/apioffer/getoffer"
    
    token = "7951dc7484fa9f9d"
    site_id = "12002"
    
    headers = {
        "token": token
    }
    
    params = {
        "site_id": site_id,
        "link_status": "Joined",  # Pending, Joined, Rejected
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
            
            print("✅ API 响应成功！")
            print()
            
            # 保存完整响应
            with open("yp_to_feishu/offer_api_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("完整响应已保存到: yp_to_feishu/offer_api_response.json")
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
            print(f"❌ API 请求失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print()
    return response.status_code == 200


def test_category_api():
    """
    测试 Category API（获取类别列表）
    """
    print("=" * 80)
    print("测试 Category API")
    print("=" * 80)
    
    api_url = "https://yeahpromos.com/index/apioffer/getcategory"
    
    token = "7951dc7484fa9f9d"
    
    headers = {
        "token": token
    }
    
    try:
        print(f"API URL: {api_url}")
        print()
        
        response = requests.get(api_url, headers=headers, timeout=30)
        
        print(f"HTTP 状态码: {response.status_code}")
        print()
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ API 响应成功！")
            print()
            
            # 保存完整响应
            with open("yp_to_feishu/category_api_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print("完整响应已保存到: yp_to_feishu/category_api_response.json")
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
                    categories = data["data"]
                    print(f"类别数量: {len(categories)}")
                    print()
                    
                    if len(categories) > 0:
                        print("=" * 80)
                        print("所有类别:")
                        print("=" * 80)
                        for i, category in enumerate(categories):
                            print(f"{i+1}. {category.get('name', 'N/A')} (ID: {category.get('id', 'N/A')})")
                        print()
                else:
                    print("没有找到类别数据（data 字段）")
        
        else:
            print(f"❌ API 请求失败: HTTP {response.status_code}")
            print(f"响应内容: {response.text}")
    
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print()
    return response.status_code == 200


def main():
    """
    测试所有 API
    """
    print("=" * 80)
    print("YP 平台 API 全面测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Channel: shelovable")
    print(f"Site ID: 12002")
    print(f"Token: 7951dc7484fa9f9d")
    print("=" * 80)
    print()
    
    results = {}
    
    # 测试 Merchant API
    results["Merchant API"] = test_merchant_api()
    
    # 测试 Offer API
    results["Offer API"] = test_offer_api()
    
    # 测试 Category API
    results["Category API"] = test_category_api()
    
    # 总结
    print("=" * 80)
    print("测试总结")
    print("=" * 80)
    for api_name, success in results.items():
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{api_name}: {status}")
    print("=" * 80)


if __name__ == "__main__":
    main()
