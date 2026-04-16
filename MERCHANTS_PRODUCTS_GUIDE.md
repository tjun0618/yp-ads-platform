# YP 平台品牌和商品数据采集指南

## 文档概述

本文档详细说明了如何从 YP 平台采集品牌（Merchants）和商品（Products）数据，并上传到飞书。

---

## 1. 数据需求分析

### 1.1 需要采集的数据

根据您的需求，需要采集以下数据：

| 字段 | 说明 | 来源 |
|-----|------|------|
| **商家名称** | YP 平台上的品牌名称 | YP Merchants 页面 |
| **佣金** | 品牌的佣金率 | YP Merchants 页面 |
| **类别** | 品牌所属类别 | YP Merchants 页面 |
| **ASIN** | 亚马逊商品唯一标识 | YP Products 页面 |
| **商品名称** | 商品标题 | YP Products 页面 |
| **价格** | 商品价格 | YP Products 页面 |
| **评分** | 商品评分 | YP Products 页面 |
| **评论数** | 商品评论数 | YP Products 页面 |
| **图片链接** | 商品图片 URL | YP Products 页面 |
| **商品链接** | 亚马逊原始链接 | YP Products 页面 |
| **商品描述** | 商品详细描述 | YP Products 页面 |
| **品牌** | 商品品牌 | YP Products 页面 |
| **商品特性** | 商品特性标签 | YP Products 页面 |
| **采集时间** | 数据采集时间 | 自动生成 |

---

## 2. 技术方案对比

### 2.1 方案 A：使用 YP API（推荐）⭐⭐⭐⭐⭐

**优点**:
- ✅ 官方提供的 API，稳定可靠
- ✅ 数据格式规范，易于解析
- ✅ 请求速度快，效率高
- ✅ 维护成本低

**缺点**:
- ⚠️ 需要获取 API token 和 site_id
- ⚠️ 可能没有提供品牌和商品的完整 API

**适用场景**:
- ✅ 如果 YP 平台提供了品牌和商品的 API

**实现步骤**:
1. 获取 API token 和 site_id
2. 调用品牌 API 获取品牌列表
3. 调用商品 API 获取商品列表
4. 合并数据并上传到飞书

### 2.2 方案 B：使用浏览器自动化（bb-browser）⭐⭐⭐⭐

**优点**:
- ✅ 可以获取页面上的所有数据
- ✅ 无需 API 密钥
- ✅ 可以模拟人工操作

**缺点**:
- ⚠️ 速度较慢
- ⚠️ 资源占用高
- ⚠️ 页面结构变化需要更新
- ⚠️ 动态加载数据需要等待

**适用场景**:
- ✅ 如果 YP 平台没有提供品牌和商品的 API
- ✅ 需要获取页面上的完整数据

**实现步骤**:
1. 使用 bb-browser 打开品牌页面
2. 等待页面加载完成
3. 提取页面上的品牌数据
4. 打开商品页面
5. 提取页面上的商品数据
6. 合并数据并上传到飞书

### 2.3 方案 C：使用现有采集脚本（推荐）⭐⭐⭐⭐⭐

**优点**:
- ✅ 已经有完整的采集脚本
- ✅ 已经验证可行
- ✅ 已经有飞书上传脚本

**缺点**:
- ⚠️ 需要检查脚本是否需要更新

**适用场景**:
- ✅ 快速启动
- ✅ 利用现有资源

---

## 3. 推荐实施步骤

### 步骤 1：检查 YP 平台是否提供品牌和商品 API ⭐⭐⭐⭐⭐

#### 方法 1：查看 YP API 文档

访问 YP 平台的 API 文档页面：
- URL: `https://www.yeahpromos.com/index/tools/select`

检查是否有以下 API：
- Merchants API（品牌 API）
- Products API（商品 API）
- Offers API（优惠 API）

#### 方法 2：检查现有的 API 端点

尝试访问以下 URL，看是否返回数据：

```bash
# 尝试品牌 API
curl "https://yeahpromos.com/api/merchants?site_id=YOUR_SITE_ID&token=YOUR_TOKEN"

# 尝试商品 API
curl "https://yeahpromos.com/api/products?site_id=YOUR_SITE_ID&token=YOUR_TOKEN"
```

### 步骤 2：如果有 API，使用 API 采集 ⭐⭐⭐⭐⭐

#### 2.1 创建品牌 API 客户端

```python
"""
YP 品牌和商品 API 客户端
"""

import requests
from typing import List, Dict, Optional
from datetime import datetime


class YPMerchantsAndProductsAPI:
    """YP 品牌和商品 API 客户端"""
    
    def __init__(self, token: str, site_id: str):
        """
        初始化 API 客户端
        
        Args:
            token: YP 平台 token
            site_id: 网站 site_id
        """
        self.token = token
        self.site_id = site_id
        self.base_url = "https://yeahpromos.com"
        self.session = requests.Session()
    
    def get_merchants(self, page: int = 1, limit: int = 100) -> Optional[Dict]:
        """
        获取品牌列表
        
        Args:
            page: 页码
            limit: 每页数量
        
        Returns:
            品牌数据
        """
        url = f"{self.base_url}/api/merchants"  # 需要确认实际端点
        params = {
            "site_id": self.site_id,
            "page": page,
            "limit": limit
        }
        headers = {
            "token": self.token
        }
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[错误] 获取品牌失败: {e}")
            return None
    
    def get_products(self, merchant_id: str, page: int = 1, limit: int = 100) -> Optional[Dict]:
        """
        获取指定品牌的商品列表
        
        Args:
            merchant_id: 品牌 ID
            page: 页码
            limit: 每页数量
        
        Returns:
            商品数据
        """
        url = f"{self.base_url}/api/products"  # 需要确认实际端点
        params = {
            "site_id": self.site_id,
            "merchant_id": merchant_id,
            "page": page,
            "limit": limit
        }
        headers = {
            "token": self.token
        }
        
        try:
            response = self.session.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[错误] 获取商品失败: {e}")
            return None
    
    def get_all_merchants_and_products(self, max_merchants: int = 10, max_products_per_merchant: int = 100) -> List[Dict]:
        """
        获取所有品牌和商品
        
        Args:
            max_merchants: 最大品牌数量
            max_products_per_merchant: 每个品牌最大商品数量
        
        Returns:
            所有商品数据（包含品牌信息）
        """
        # 获取品牌列表
        merchants_resp = self.get_merchants()
        
        if not merchants_resp or merchants_resp.get('code') != 100000:
            print("[错误] 无法获取品牌列表")
            return []
        
        merchants = merchants_resp.get('data', [])
        
        # 限制品牌数量
        merchants = merchants[:max_merchants]
        
        all_products = []
        
        for merchant in merchants:
            merchant_id = merchant.get('id')
            merchant_name = merchant.get('name')
            commission = merchant.get('commission')
            category = merchant.get('category')
            
            print(f"[信息] 获取品牌 '{merchant_name}' 的商品...")
            
            # 获取该品牌的商品
            products_resp = self.get_products(merchant_id, limit=max_products_per_merchant)
            
            if products_resp and products_resp.get('code') == 100000:
                products = products_resp.get('data', [])
                
                for product in products:
                    product['merchant_name'] = merchant_name
                    product['commission'] = commission
                    product['category'] = category
                
                all_products.extend(products)
        
        return all_products
```

#### 2.2 使用 API 客户端

```python
from yp_merchants_products_api import YPMerchantsAndProductsAPI

# 创建 API 客户端
api = YPMerchantsAndProductsAPI(
    token="YOUR_TOKEN_HERE",
    site_id="YOUR_SITE_ID_HERE"
)

# 获取所有品牌和商品
products = api.get_all_merchants_and_products(
    max_merchants=10,
    max_products_per_merchant=100
)

# 导出数据
export_to_csv(products, "yp_merchants_and_products.csv")

# 上传到飞书
upload_to_feishu("yp_merchants_and_products.csv")
```

### 步骤 3：如果没有 API，使用浏览器自动化 ⭐⭐⭐⭐

#### 3.1 使用 bb-browser

```python
"""
使用 bb-browser 采集品牌和商品数据
"""

import subprocess
from bs4 import BeautifulSoup


def run_bb_browser(command):
    """运行 bb-browser 命令"""
    result = subprocess.run(
        f"bb-browser {command}",
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    return result.stdout


def collect_merchants():
    """采集品牌列表"""
    # 打开品牌页面
    run_bb_browser("open https://www.yeahpromos.com/index/advert/index")
    
    # 等待页面加载
    time.sleep(5)
    
    # 获取页面 HTML
    html = run_bb_browser('eval "document.documentElement.outerHTML"')
    
    # 解析 HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找所有品牌行（需要根据实际页面结构调整选择器）
    merchants = []
    
    # 这里需要根据实际页面结构调整
    # 例如：
    # for row in soup.select('tbody tr'):
    #     cells = row.select('td')
    #     if len(cells) >= 3:
    #         merchants.append({
    #             'name': cells[0].get_text(strip=True),
    #             'commission': cells[1].get_text(strip=True),
    #             'category': cells[2].get_text(strip=True)
    #         })
    
    return merchants


def collect_products():
    """采集商品列表"""
    # 打开商品页面
    run_bb_browser("open https://www.yeahpromos.com/index/offer/products")
    
    # 等待页面加载
    time.sleep(5)
    
    # 获取页面 HTML
    html = run_bb_browser('eval "document.documentElement.outerHTML"')
    
    # 解析 HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找所有商品行（需要根据实际页面结构调整选择器）
    products = []
    
    # 这里需要根据实际页面结构调整
    # 例如：
    # for row in soup.select('tbody tr'):
    #     cells = row.select('td')
    #     if len(cells) >= 8:
    #         products.append({
    #             'asin': cells[0].get_text(strip=True),
    #             'name': cells[1].get_text(strip=True),
    #             'price': cells[2].get_text(strip=True),
    #             # ... 其他字段
    #         })
    
    return products
```

#### 3.2 使用现有的 QQBrowserSkill

如果您之前已经使用 QQBrowserSkill 采集过品牌和商品数据，可以继续使用：

```python
from yp_to_feishu.auto_collect_with_qqbrowser import YPAutoCollector

# 创建采集器
collector = YPAutoCollector()

# 采集品牌和商品
collector.collect_all()

# 导出数据
collector.export_to_csv("yp_merchants_and_products.csv")
```

### 步骤 4：上传数据到飞书 ⭐⭐⭐⭐⭐

#### 4.1 使用现有的飞书上传脚本

```python
from yp_to_feishu.upload_merchants_to_feishu import main as upload_to_feishu

# 上传到飞书
upload_to_feishu()
```

#### 4.2 手动上传

1. 打开飞书多维表格
2. 导入 CSV 文件：`yp_merchants_and_products.csv`
3. 确认字段映射正确
4. 完成导入

---

## 4. 推荐实施方案

### 方案选择

| 方案 | 推荐度 | 说明 |
|-----|--------|------|
| **方案 A：使用 API** | ⭐⭐⭐⭐⭐ | 如果 YP 平台提供了品牌和商品的 API，这是最优方案 |
| **方案 B：使用现有脚本** | ⭐⭐⭐⭐⭐ | 如果已经采集过数据，直接使用现有脚本 |
| **方案 C：浏览器自动化** | ⭐⭐⭐⭐ | 如果没有 API 且没有现有脚本，需要重新开发 |

### 实施计划

#### 第一阶段：检查 API（1 小时）⭐⭐⭐⭐⭐

1. 查看 YP API 文档
2. 测试品牌和商品 API
3. 确认 API 端点和参数

#### 第二阶段：数据采集（2-4 小时）⭐⭐⭐⭐

**如果有 API**:
1. 创建 API 客户端
2. 测试 API 调用
3. 批量采集数据

**如果没有 API**:
1. 使用现有脚本或浏览器自动化
2. 采集品牌数据
3. 采集商品数据

#### 第三阶段：数据上传（1-2 小时）⭐⭐⭐⭐⭐

1. 准备数据格式
2. 使用飞书脚本上传
3. 验证数据完整性

---

## 5. 常见问题

### Q1: YP 平台是否提供了品牌和商品的 API？

**A**: 需要检查 YP 平台的 API 文档。访问 `https://www.yeahpromos.com/index/tools/select` 查看是否有相关的 API。

### Q2: 如果没有 API，如何采集数据？

**A**: 可以使用浏览器自动化（bb-browser 或 QQBrowserSkill）来采集数据。

### Q3: 如何获取 API token 和 site_id？

**A**: 
- **site_id**: 登录 YP 平台后，进入 Channels 页面查看您的网站列表
- **token**: 需要联系 YP 平台客服获取，或者在账户设置中查找

### Q4: 如何将数据上传到飞书？

**A**: 使用提供的飞书上传脚本 `upload_merchants_to_feishu.py`，或者手动导入 CSV 文件。

### Q5: 采集的数据如何更新？

**A**: 可以设置定时任务，定期采集最新数据并更新到飞书。

---

## 6. 下一步行动

### 立即行动（优先级：高）⭐⭐⭐⭐⭐

1. ✅ **检查 YP API 文档**
   - 访问 `https://www.yeahpromos.com/index/tools/select`
   - 查找品牌和商品 API
   - 确认 API 端点和参数

2. ✅ **测试 API（如果有）**
   - 获取 API token 和 site_id
   - 测试 API 调用
   - 验证数据格式

3. ✅ **采集数据（如果没有 API）**
   - 使用现有脚本或浏览器自动化
   - 采集品牌和商品数据
   - 导出为 CSV 文件

4. ✅ **上传到飞书**
   - 使用飞书脚本上传数据
   - 验证数据完整性

### 中期规划（优先级：中）⭐⭐⭐

1. 📋 **设置定时任务**
   - 配置 Windows 任务计划程序
   - 每日/每周自动采集
   - 自动更新飞书数据

2. 📋 **数据验证**
   - 检查数据完整性
   - 验证数据准确性
   - 处理异常数据

---

## 7. 相关文档和脚本

### 文档
- YP_API_DOCUMENTATION.md - YP API 完整文档
- COMPLETE_SOP_V2.md - 完整 SOP 文档
- YP_LOGIN_SKILL_GUIDE.md - YP 登录 Skill 使用指南

### 脚本
- yp_login_skill.py - YP 登录 Skill
- collect_merchants_and_products.py - 品牌和商品采集脚本
- simple_collect_merchants.py - 简化的采集脚本
- upload_merchants_to_feishu.py - 飞书上传脚本

---

## 8. 总结

**核心要点**:
1. 优先检查 YP 平台是否提供了品牌和商品的 API
2. 如果有 API，使用 API 采集数据（最优方案）
3. 如果没有 API，使用浏览器自动化采集数据
4. 使用飞书脚本上传数据

**推荐方案**:
- **短期**: 使用现有脚本或浏览器快速采集数据
- **中期**: 设置定时任务，定期更新数据
- **长期**: 集成到自动化工作流

**注意事项**:
- ⚠️ 动态加载的页面需要等待加载完成
- ⚠️ 页面结构变化需要更新脚本
- ⚠️ 需要遵守 YP 平台的 API 限制

准备好开始采集了吗？请告诉我您想使用哪个方案，我们一起完成！🚀
