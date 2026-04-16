#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP 平台数据采集脚本
采集 100 条数据作为样本
"""

import requests
import json
import time
from datetime import datetime

# YP API 凭证
SITE_ID = "12002"
TOKEN = "7951dc7484fa9f9d"

# API 端点
MERCHANT_API_URL = "https://www.yeahpromos.com/index/getadvert/getadvert"
OFFER_API_URL = "https://www.yeahpromos.com/index/apioffer/getoffer"
CATEGORY_API_URL = "https://www.yeahpromos.com/index/apioffer/getcategory"

def get_merchants(limit=20):
    """获取品牌列表"""
    headers = {
        "token": TOKEN
    }
    
    params = {
        "site_id": SITE_ID,
        "elite": 0,
        "page": 1,
        "limit": limit
    }
    
    response = requests.get(MERCHANT_API_URL, headers=headers, params=params)
    
    # 打印调试信息
    print(f"  HTTP 状态码: {response.status_code}")
    
    try:
        data = response.json()
        
        # Merchant API 的响应格式
        if isinstance(data, dict):
            if data.get("status") == "SUCCESS":
                # 数据在 data.Data 字段中
                if "Data" in data and isinstance(data["Data"], list):
                    return data["Data"]
                elif "data" in data and isinstance(data["data"], dict):
                    return data["data"].get("Data", [])
                else:
                    return []
            else:
                print(f"  获取品牌列表失败: {data}")
                return []
        else:
            print(f"  获取品牌列表失败: {data}")
            return []
    except Exception as e:
        print(f"  解析响应失败: {e}")
        return []

def get_offers(limit=100):
    """获取商品列表"""
    headers = {
        "token": TOKEN
    }
    
    params = {
        "site_id": SITE_ID,
        "page": 1,
        "limit": limit
    }
    
    response = requests.get(OFFER_API_URL, headers=headers, params=params)
    
    # 打印调试信息
    print(f"  HTTP 状态码: {response.status_code}")
    
    try:
        data = response.json()
        
        # Offer API 的响应格式
        if isinstance(data, dict):
            if data.get("status") == "SUCCESS":
                # 数据在 data.data 字段中（小写）
                if "data" in data and isinstance(data["data"], dict):
                    return data["data"].get("data", [])
                elif "data" in data and isinstance(data["data"], list):
                    return data["data"]
                elif "Data" in data and isinstance(data["Data"], list):
                    return data["Data"]
                else:
                    print(f"  数据结构: {list(data.keys())}")
                    return []
            else:
                print(f"  获取商品列表失败: {data}")
                return []
        else:
            print(f"  获取商品列表失败: {data}")
            return []
    except Exception as e:
        print(f"  解析响应失败: {e}")
        return []

def get_categories():
    """获取类别列表"""
    params = {
        "site_id": SITE_ID,
        "token": TOKEN
    }
    
    response = requests.get(CATEGORY_API_URL, params=params)
    data = response.json()
    
    # Category API 的响应格式不同
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        if data.get("code") == 100000 or data.get("status") == "SUCCESS":
            return data.get("data", [])
        else:
            print(f"获取类别列表失败: {data}")
            return []
    else:
        print(f"获取类别列表失败: {data}")
        return []

def save_to_json(data, filename):
    """保存数据到 JSON 文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到: {filename}")

def main():
    print("=" * 60)
    print("YP 平台数据采集 - 100 条样本数据")
    print("=" * 60)
    print()
    
    # 获取类别
    print("[1/3] 获取类别列表...")
    categories = get_categories()
    print(f"[OK] 获取到 {len(categories)} 个类别")
    save_to_json(categories, "yp_to_feishu/categories_sample.json")
    print()
    
    time.sleep(1)
    
    # 获取品牌
    print("[2/3] 获取品牌列表...")
    merchants = get_merchants(limit=20)
    print(f"[OK] 获取到 {len(merchants)} 个品牌")
    save_to_json(merchants, "yp_to_feishu/merchants_sample.json")
    print()
    
    time.sleep(1)
    
    # 获取商品
    print("[3/3] 获取商品列表...")
    offers = get_offers(limit=100)
    print(f"[OK] 获取到 {len(offers)} 个商品")
    save_to_json(offers, "yp_to_feishu/offers_sample.json")
    print()
    
    # 汇总统计
    print("=" * 60)
    print("采集完成！")
    print("=" * 60)
    print(f"类别数: {len(categories)}")
    print(f"品牌数: {len(merchants)}")
    print(f"商品数: {len(offers)}")
    print()
    
    # 显示样本数据
    print("=" * 60)
    print("类别样本")
    print("=" * 60)
    for cat in categories[:5]:
        print(f"  {cat['category_id']}: {cat['category_name']}")
    
    print()
    print("=" * 60)
    print("品牌样本")
    print("=" * 60)
    for merch in merchants[:5]:
        print(f"  {merch['mid']}: {merch['merchant_name']}")
        print(f"    佣金: {merch.get('avg_payout', 0)}{merch.get('payout_unit', '%')}")
        print(f"    网站: {merch.get('site_url', 'N/A')}")
        print()
    
    print()
    print("=" * 60)
    print("商品样本")
    print("=" * 60)
    for offer in offers[:5]:
        print(f"  ID: {offer['product_id']}")
        print(f"  ASIN: {offer['asin']}")
        print(f"  名称: {offer['product_name']}")
        print(f"  价格: ${offer['price']}")
        print(f"  佣金: {offer['payout']}")
        print(f"  类别: {offer['category_name']}")
        print()

if __name__ == "__main__":
    main()
