# YP平台商品数据采集到飞书文档 - 架构设计

## 📋 项目概述

从 YeahPromos (YP) 平台获取所有商家信息，并通过追踪链接采集亚马逊商品数据，最终同步到飞书文档。

## 🎯 目标

1. 从 YP API 获取所有商家列表
2. 解析每个商家的追踪链接
3. 批量采集亚马逊商品信息（名称、价格、描述、ASIN、评分、评论数）
4. 整合数据并同步到飞书文档

## 🏗️ 系统架构

```
┌─────────────────┐
│   YP Platform   │
│  Monetization   │
│      API        │
└────────┬────────┘
         │
         │ 1. 获取商家列表
         │    (商家名称、佣金率、追踪链接)
         ↓
┌─────────────────────────┐
│  Data Collector Core   │
│  (Python Script)       │
│                         │
│  - YP API 调用模块     │
│  - 链接解析模块        │
│  - 亚马逊爬虫模块      │
│  - 数据清洗模块        │
└────────┬────────────────┘
         │
         │ 2. 解析追踪链接
         │    → 提取亚马逊商品页URL
         ↓
┌─────────────────────────┐
│   Amazon Crawler       │
│   (Playwright)         │
│                         │
│  - 商品信息提取        │
│  - ASIN 提取           │
│  - 价格采集            │
│  - 评分/评论数采集     │
└────────┬────────────────┘
         │
         │ 3. 批量采集商品数据
         ↓
┌─────────────────────────┐
│  Data Processor        │
│                         │
│  - 数据清洗            │
│  - 字段映射            │
│  - 格式标准化          │
└────────┬────────────────┘
         │
         │ 4. 结构化数据
         ↓
┌─────────────────────────┐
│   Feishu Integration   │
│                         │
│  - 飞书 API 调用       │
│  - 文档创建/更新       │
│  - 表格写入            │
│  - 错误重试机制        │
└────────┬────────────────┘
         │
         │ 5. 同步到飞书文档
         ↓
┌─────────────────────────┐
│   Feishu Document       │
│   (飞书文档)            │
│                         │
│  - 商家商品表格        │
│  - 实时数据更新        │
└─────────────────────────┘
```

## 📊 数据流程

### 阶段 1：YP 数据采集

**输入**：
- YP Monetization API
- 商家列表 API 端点

**输出**：
```json
{
  "merchants": [
    {
      "merchant_id": "123",
      "merchant_name": "Nike Official Store",
      "commission_rate": "8.5%",
      "tracking_link": "https://yeahpromos.com/track?offer=123&url=...",
      "description": "Nike官方亚马逊店铺"
    }
  ]
}
```

### 阶段 2：链接解析

**处理逻辑**：
1. 解析追踪链接，提取最终的亚马逊URL
2. 识别商品ASIN（如果链接指向单个商品）
3. 识别商家店铺页面（如果链接指向店铺）

**输出**：
```json
{
  "merchant_id": "123",
  "merchant_name": "Nike Official Store",
  "commission_rate": "8.5%",
  "amazon_urls": [
    "https://www.amazon.com/dp/B08XXXXX01",
    "https://www.amazon.com/dp/B08XXXXX02"
  ],
  "is_shop_page": true
}
```

### 阶段 3：亚马逊数据采集

**使用 Playwright 爬取**：
```python
商品信息字段：
{
  "asin": "B08XXXXX01",
  "product_name": "Nike Air Max 270",
  "price": 129.99,
  "price_currency": "USD",
  "rating": 4.5,
  "review_count": 12345,
  "description": "Nike Air Max 270 运动鞋...",
  "product_url": "https://www.amazon.com/dp/B08XXXXX01",
  "product_image": "https://...",
  "category": "Shoes"
}
```

### 阶段 4：数据整合

**最终数据结构**：
```json
{
  "merchant_name": "Nike Official Store",
  "merchant_commission": "8.5%",
  "product_asin": "B08XXXXX01",
  "product_name": "Nike Air Max 270",
  "product_price": 129.99,
  "product_rating": 4.5,
  "review_count": 12345,
  "product_description": "...",
  "tracking_link": "https://yeahpromos.com/track?offer=123&url=...",
  "collected_at": "2026-03-22T10:42:00Z"
}
```

### 阶段 5：飞书同步

**飞书文档表格结构**：

| 商家名称 | 商品ASIN | 商品名称 | 价格 | 佣金率 | 评分 | 评论数 | 商品描述 | 追踪链接 | 采集时间 |
|---------|---------|---------|------|-------|------|-------|---------|---------|---------|
| Nike Official Store | B08XXXXX01 | Nike Air Max 270 | $129.99 | 8.5% | 4.5 | 12345 | Nike Air Max 270... | https://... | 2026-03-22 10:42 |

## 🔧 技术栈

### 核心技术

1. **数据采集**
   - Python 3.9+
   - Playwright (浏览器自动化)
   - Requests (API 调用)

2. **数据处理**
   - Pandas (数据处理)
   - BeautifulSoup (HTML 解析)

3. **飞书集成**
   - Feishu Python SDK
   - OpenAPI

4. **配置管理**
   - YAML/JSON 配置文件
   - 环境变量

## ⚡ 性能优化策略

### 1. API 限流处理

- YP API: 10次/分钟限制
- 实现请求队列和延迟机制
- 使用指数退避算法

### 2. 并发爬取

- 使用异步 I/O (asyncio)
- 控制并发数 (建议 5-10)
- 防止亚马逊反爬

### 3. 数据缓存

- Redis 缓存已采集商品
- 避免重复采集
- 定期刷新机制

### 4. 增量更新

- 只更新新增/变化商品
- 基于上次采集时间
- 降低 API 调用次数

## 🛡️ 反爬策略

1. **请求伪装**
   - 随机 User-Agent
   - 请求延迟
   - 使用代理轮换

2. **浏览器指纹规避**
   - Playwright 隐身模式
   - 禁用自动化特征
   - 模拟真实用户行为

3. **CAPTCHA 处理**
   - 检测验证码
   - 手动干预或第三方服务

## 📝 错误处理

### 1. API 错误

- 网络超时重试
- 限流等待
- 错误日志记录

### 2. 爬虫错误

- 页面加载失败重试
- 数据缺失标记
- 异常商品跳过

### 3. 飞书同步错误

- API 限流重试
- 文档权限检查
- 数据校验

## 🚀 实施计划

### Phase 1: 基础设施搭建
- [ ] 创建项目结构
- [ ] 配置飞书应用
- [ ] 测试 YP API 连接

### Phase 2: 核心功能开发
- [ ] 实现 YP 商家采集
- [ ] 实现链接解析
- [ ] 实现亚马逊爬虫

### Phase 3: 数据处理
- [ ] 数据清洗和标准化
- [ ] 错误处理和重试

### Phase 4: 飞书集成
- [ ] 实现飞书文档创建
- [ ] 实现表格写入
- [ ] 实现增量更新

### Phase 5: 测试和优化
- [ ] 小规模测试
- [ ] 性能优化
- [ ] 监控和日志

## 📦 文件结构

```
yp_to_feishu/
├── config/
│   ├── config.yaml              # 配置文件
│   └── feishu_config.yaml        # 飞书配置
├── src/
│   ├── yp_api/
│   │   ├── __init__.py
│   │   ├── merchant_collector.py # YP 商家采集
│   │   └── link_parser.py       # 链接解析
│   ├── amazon/
│   │   ├── __init__.py
│   │   ├── crawler.py           # 亚马逊爬虫
│   │   └── parser.py            # 商品数据解析
│   ├── feishu/
│   │   ├── __init__.py
│   │   ├── client.py            # 飞书客户端
│   │   └── document.py          # 文档操作
│   ├── data/
│   │   ├── __init__.py
│   │   ├── processor.py         # 数据处理
│   │   └── validator.py         # 数据验证
│   └── main.py                   # 主程序入口
├── tests/
│   ├── test_yp_api.py
│   ├── test_amazon.py
│   └── test_feishu.py
├── logs/
│   └── app.log
├── requirements.txt
├── README.md
└── run.py
```

## 🔐 安全和隐私

1. **凭证安全**
   - 使用环境变量存储敏感信息
   - 不提交凭证到代码仓库
   - 使用加密存储

2. **数据合规**
   - 遵守平台 Terms of Service
   - 尊重 robots.txt
   - 不采集敏感个人信息

3. **访问控制**
   - 飞书文档权限管理
   - API 密钥轮换
   - 审计日志

## 📈 监控和维护

1. **监控指标**
   - 采集成功率
   - API 响应时间
   - 数据完整性

2. **日志记录**
   - 详细操作日志
   - 错误日志
   - 性能指标

3. **维护计划**
   - 定期更新反爬策略
   - 监控 API 变更
   - 数据备份
