# YeahPromos API 完整文档

## 文档概述

本文档详细说明了 YeahPromos 平台的 API 使用方法，包括 Transaction API、Monetization API 和 Post Back URL 的完整信息。

---

## 1. Transaction API（交易 API）

### 1.1 功能说明

Transaction API 用于获取详细的交易记录、佣金状态等信息。您可以使用此 API 拉取详细的订单数据。

### 1.2 请求信息

#### 基本信息

| 参数 | 值 |
|-----|---|
| **URL** | `https://yeahpromos.com/index/Getorder/getorder` |
| **返回格式** | JSON |
| **HTTP 方法** | GET |
| **Content-Type** | application/x-www-form-urlencoded |
| **请求限制** | 每分钟 10 次 |

#### Header 参数

| 参数名 | 说明 |
|--------|------|
| **token** | 您的网站 token |

#### GET 参数

| 参数名 | 说明 | 示例 |
|--------|------|------|
| **site_id** | 您的网站 ID | `12345` |
| **startDate** | 开始日期，格式：YYYY-MM-DD | `2024-01-01` |
| **endDate** | 结束日期，格式：YYYY-MM-DD | `2024-01-31` |
| **is_amazon** | 是否只返回亚马逊订单（1: 是） | `1` |
| **page** | 页码，默认 1 | `1` |
| **limit** | 每页数量，默认 1000 | `1000` |

### 1.3 返回参数

#### 分页信息

| 参数名 | 说明 |
|--------|------|
| **PageTotal** | 总页数 |
| **PageNow** | 当前页码 |
| **Num** | 销售交易总数 |
| **Limit** | 每次输出的最大数量 |

#### 交易数据

| 参数名 | 说明 |
|--------|------|
| **id** | 记录 ID |
| **advert_id** | 广告 ID |
| **oid** | 订单 ID |
| **creationDate_time** | 交易时间 |
| **amount** | 销售金额 |
| **sale_comm** | 销售佣金 |
| **status** | 佣金状态 |
| **tag1** | 您的标签 1（用于跟踪用户链接） |
| **tag2** | 您的标签 2（用于跟踪用户链接） |
| **tag3** | 您的标签 3（用于跟踪用户链接） |

### 1.4 返回码

| 返回码 | 说明 |
|--------|------|
| **100000** | 成功 |
| **100001** | 错误 |

### 1.5 请求示例

```bash
# 基本请求
curl -X GET "https://yeahpromos.com/index/Getorder/getorder?site_id=12345&startDate=2024-01-01&endDate=2024-01-31&is_amazon=1&page=1&limit=1000" \
  -H "token: YOUR_TOKEN_HERE"

# 使用 Python requests
import requests

url = "https://yeahpromos.com/index/Getorder/getorder"
params = {
    "site_id": "12345",
    "startDate": "2024-01-01",
    "endDate": "2024-01-31",
    "is_amazon": "1",
    "page": "1",
    "limit": "1000"
}
headers = {
    "token": "YOUR_TOKEN_HERE"
}

response = requests.get(url, params=params, headers=headers)
data = response.json()

print(f"总页数: {data['PageTotal']}")
print(f"当前页: {data['PageNow']}")
print(f"总交易数: {data['Num']}")

for transaction in data['data']:
    print(f"订单 ID: {transaction['oid']}")
    print(f"金额: {transaction['amount']}")
    print(f"佣金: {transaction['sale_comm']}")
```

### 1.6 返回示例

```json
{
  "code": 100000,
  "message": "Success",
  "PageTotal": 5,
  "PageNow": 1,
  "Num": 423,
  "Limit": 1000,
  "data": [
    {
      "id": 12345,
      "advert_id": 67890,
      "oid": "ORDER123456",
      "creationDate_time": "2024-01-15 10:30:00",
      "amount": "99.99",
      "sale_comm": "9.99",
      "status": "Approved",
      "tag1": "campaign1",
      "tag2": "source1",
      "tag3": ""
    },
    ...
  ]
}
```

---

## 2. Monetization API（变现 API）

### 2.1 功能说明

Monetization API 用于获取变现相关的数据。其 API 结构与 Transaction API 类似。

### 2.2 请求信息

#### 基本信息

| 参数 | 值 |
|-----|---|
| **URL** | `https://yeahpromos.com/index/Getorder/getorder` |
| **返回格式** | JSON |
| **HTTP 方法** | GET |
| **Content-Type** | application/x-www-form-urlencoded |
| **请求限制** | 每分钟 10 次 |

#### Header 参数

| 参数名 | 说明 |
|--------|------|
| **token** | 您的网站 token |

#### GET 参数

| 参数名 | 说明 | 示例 |
|--------|------|------|
| **site_id** | 您的网站 ID | `12345` |
| **startDate** | 开始日期，格式：YYYY-MM-DD | `2024-01-01` |
| **endDate** | 结束日期，格式：YYYY-MM-DD | `2024-01-31` |
| **is_amazon** | 是否只返回亚马逊订单（1: 是） | `1` |
| **page** | 页码，默认 1 | `1` |
| **limit** | 每页数量，默认 1000 | `1000` |

---

## 3. Post Back URL（回传 URL）

### 3.1 功能说明

Post Back URL 用于设置 YP 平台在交易发生时向您的服务器发送通知的 URL。这样可以实时跟踪交易状态。

### 3.2 回传参数

当有新的交易或交易状态更新时，YP 平台会向您设置的 Post Back URL 发送以下参数：

| 参数名 | 说明 |
|--------|------|
| **oid** | 订单 ID |
| **amount** | 销售金额 |
| **sale_comm** | 销售佣金 |
| **creationDate_time** | 交易时间 |
| **status** | 佣金状态 |
| **tag1** | 您的标签 1 |
| **tag2** | 您的标签 2 |
| **tag3** | 您的标签 3 |

### 3.3 设置 Post Back URL

1. 登录 YP 平台
2. 进入 Tools > Post Back URL
3. 输入您的回传 URL
4. 保存设置

### 3.4 回传示例

当交易发生时，YP 平台会向您的 URL 发送 GET 请求：

```
https://your-domain.com/yp-postback?
  oid=ORDER123456&
  amount=99.99&
  sale_comm=9.99&
  creationDate_time=2024-01-15+10%3A30%3A00&
  status=Approved&
  tag1=campaign1&
  tag2=source1&
  tag3=
```

---

## 4. 如何获取 Token 和 Site ID

### 4.1 获取 Site ID

1. 登录 YP 平台
2. 进入 Channels 页面
3. 查看您的网站列表
4. 每个网站都有一个唯一的 site_id

### 4.2 获取 Token

Token 通常在您的账户设置中可以找到，或者需要联系 YP 平台客服获取。

---

## 5. 使用注意事项

### 5.1 请求限制

- 每分钟最多 10 次请求
- 超过限制可能会被暂时封禁

### 5.2 错误处理

建议实现以下错误处理机制：

1. **重试机制**：遇到网络错误时自动重试
2. **速率限制**：避免超过每分钟 10 次的限制
3. **数据验证**：验证返回的数据格式和完整性

### 5.3 最佳实践

1. **分页获取**：对于大量数据，使用分页逐步获取
2. **缓存数据**：缓存已获取的数据，避免重复请求
3. **监控状态**：监控 API 调用状态和成功率
4. **日志记录**：记录所有 API 调用和响应

---

## 6. Python 完整示例

### 6.1 获取交易数据

```python
import requests
import time
from datetime import datetime, timedelta

class YPTransactionAPI:
    def __init__(self, token, site_id):
        self.base_url = "https://yeahpromos.com/index/Getorder/getorder"
        self.token = token
        self.site_id = site_id
        self.request_limit = 10  # 每分钟 10 次
        self.request_count = 0
        self.last_request_time = None
    
    def get_transactions(self, start_date, end_date, is_amazon=1, page=1, limit=1000):
        """
        获取交易数据
        
        Args:
            start_date: 开始日期，格式：YYYY-MM-DD
            end_date: 结束日期，格式：YYYY-MM-DD
            is_amazon: 是否只返回亚马逊订单（1: 是）
            page: 页码
            limit: 每页数量
        
        Returns:
            dict: 包含交易数据和分页信息的字典
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
            response = requests.get(self.base_url, params=params, headers=headers)
            response.raise_for_status()
            
            # 解析 JSON 响应
            data = response.json()
            
            # 更新请求计数
            self._update_request_count()
            
            return data
        
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return None
    
    def get_all_transactions(self, start_date, end_date, is_amazon=1):
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
        
        while True:
            # 获取当前页数据
            data = self.get_transactions(start_date, end_date, is_amazon, page)
            
            if not data or data.get('code') != 100000:
                break
            
            # 添加交易数据
            all_transactions.extend(data.get('data', []))
            
            # 检查是否还有下一页
            if page >= data.get('PageTotal', 1):
                break
            
            page += 1
        
        return all_transactions
    
    def _check_rate_limit(self):
        """检查速率限制"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < 60 and self.request_count >= self.request_limit:
                wait_time = 60 - elapsed
                print(f"达到速率限制，等待 {wait_time:.2f} 秒...")
                time.sleep(wait_time)
                self.request_count = 0
    
    def _update_request_count(self):
        """更新请求计数"""
        self.request_count += 1
        self.last_request_time = time.time()
    
    def export_to_csv(self, transactions, filename):
        """
        导出交易数据到 CSV 文件
        
        Args:
            transactions: 交易数据列表
            filename: CSV 文件名
        """
        import csv
        
        if not transactions:
            print("没有交易数据可导出")
            return
        
        # CSV 字段
        fieldnames = [
            'id', 'advert_id', 'oid', 'creationDate_time',
            'amount', 'sale_comm', 'status', 'tag1', 'tag2', 'tag3'
        ]
        
        # 写入 CSV
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(transactions)
        
        print(f"成功导出 {len(transactions)} 条交易数据到 {filename}")

# 使用示例
if __name__ == "__main__":
    # 初始化 API 客户端
    api = YPTransactionAPI(
        token="YOUR_TOKEN_HERE",
        site_id="YOUR_SITE_ID_HERE"
    )
    
    # 获取最近 7 天的数据
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    print(f"获取从 {start_date} 到 {end_date} 的交易数据...")
    
    # 获取所有交易数据
    transactions = api.get_all_transactions(start_date, end_date, is_amazon=1)
    
    print(f"共获取 {len(transactions)} 条交易数据")
    
    # 导出到 CSV
    api.export_to_csv(transactions, "transactions.csv")
```

### 6.2 设置 Post Back URL 接收端

```python
from flask import Flask, request
import json

app = Flask(__name__)

@app.route('/yp-postback', methods=['GET', 'POST'])
def yp_postback():
    """
    YP Post Back URL 接收端
    """
    # 获取参数
    oid = request.args.get('oid')
    amount = request.args.get('amount')
    sale_comm = request.args.get('sale_comm')
    creationDate_time = request.args.get('creationDate_time')
    status = request.args.get('status')
    tag1 = request.args.get('tag1')
    tag2 = request.args.get('tag2')
    tag3 = request.args.get('tag3')
    
    # 处理交易数据
    transaction = {
        'oid': oid,
        'amount': amount,
        'sale_comm': sale_comm,
        'creationDate_time': creationDate_time,
        'status': status,
        'tag1': tag1,
        'tag2': tag2,
        'tag3': tag3
    }
    
    # 记录到数据库或日志
    print(f"收到交易通知: {transaction}")
    
    # 返回成功响应
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 7. 常见问题

### Q1: 如何获取 token 和 site_id？

**A**: 
- **site_id**: 登录 YP 平台后，进入 Channels 页面查看您的网站列表
- **token**: 需要联系 YP 平台客服获取，或者在账户设置中查找

### Q2: API 请求限制是什么？

**A**: 每分钟最多 10 次请求。超过限制可能会被暂时封禁。

### Q3: 如何处理大量数据？

**A**: 使用分页功能，逐步获取数据。建议每次请求限制在 1000 条记录。

### Q4: Post Back URL 有什么用？

**A**: Post Back URL 可以让您实时接收交易通知，无需定期轮询 API。

### Q5: 交易状态有哪些？

**A**: 常见的状态包括：
- Approved：已批准
- Pending：待处理
- Rejected：已拒绝
- Cancelled：已取消

---

## 8. 更新日志

| 日期 | 版本 | 说明 |
|------|------|------|
| 2024-03-22 | 1.0 | 初始版本，包含 Transaction API、Monetization API 和 Post Back URL 的完整文档 |

---

## 9. 联系支持

如果您在使用 API 过程中遇到问题，请联系 YP 平台客服。
