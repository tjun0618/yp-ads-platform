# SOP: YP 平台商品数据（Offers）采集

## 1. 概述

本 SOP 用于从 YeahPromos (YP) 平台通过 Offer API 采集商品数据，包括 ASIN、商品名称、价格、佣金率、类别等信息，并可选上传至飞书多维表格。

**适用场景**: 需要获取 YP 平台可推广的亚马逊商品列表，用于选品分析和 Google Ads 广告投放。

---

## 2. 前置条件

| 条件 | 要求 | 获取方式 |
|------|------|---------|
| Python | 3.7+ | 系统已安装 |
| requests 库 | 已安装 | `pip install requests` |
| Site ID | 你的频道 ID | YP 平台 > Channels 页面 |
| Web Token | API 认证 Token | YP 平台 > Tools > Transaction API |
| 飞书凭证（可选）| APP_ID + APP_SECRET | 飞书开放平台 |

**当前凭证**:
- Site ID: `12002`
- Token: `7951dc7484fa9f9d`

---

## 3. API 信息

| 项目 | 说明 |
|------|------|
| **端点** | `https://www.yeahpromos.com/index/apioffer/getoffer` |
| **方法** | GET |
| **认证** | HTTP Header: `{"token": "YOUR_TOKEN"}` |
| **速率限制** | 每分钟 10 次 |

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| site_id | string | 是 | 频道 ID |
| page | int | 否 | 页码，从 1 开始，默认 1 |
| limit | int | 否 | 每页数量，默认 100 |
| category_id | int | 否 | 按类别 ID 筛选 |

**响应字段（data.data.data 数组）**:

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| product_id | int | 商品 ID | 1350703 |
| asin | string | 亚马逊 ASIN | B0DWHPW5CB |
| product_name | string | 商品名称 | SALAV Heavy Duty... |
| price | string | 价格 | "USD 164.99" |
| image | string | 商品图片 URL | https://m.media-amazon.com/... |
| category_id | int | 类别 ID | 9461 |
| category_name | string | 类别名称 | Garment Steamers |
| discount | string | 折扣信息 | "" |
| payout | float | 佣金率 (%) | 15.0 |
| product_status | string | 商品状态 | "Online" / "Offline" |
| tracking_url | string | 追踪链接 | "" |

**注意**: `price` 字段格式为 `"USD 164.99"`，需要解析出数字部分。脚本已自动处理。

---

## 4. 执行步骤

### 4.1 单页采集（100 条，快速预览）

```bash
cd c:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu
python collect_offers.py
```

**输出**: `output/offers_data.json`（100 条商品数据）

### 4.2 全量采集（所有商品）

```bash
python collect_offers.py --all
```

**说明**: 自动分页采集所有商品，每次请求间隔 0.5 秒。

### 4.3 按类别筛选采集

```bash
# 先查看类别 ID（使用类别采集脚本）
python collect_categories.py

# 按类别 ID 采集
python collect_offers.py --category=9461
```

### 4.4 采集并上传到飞书

```bash
python collect_offers.py --upload
```

**输出**:
- `output/offers_data.json` - 商品数据
- `output/offers_feishu_result.json` - 飞书上传结果
- 飞书多维表格 URL

---

## 5. 输出数据格式

```json
{
  "product_id": 1350703,
  "asin": "B0DWHPW5CB",
  "product_name": "SALAV Heavy Duty...",
  "price": 164.99,
  "price_raw": "USD 164.99",
  "image": "https://m.media-amazon.com/images/I/714sO1AJQ7L.jpg",
  "category_id": 9461,
  "category_name": "Garment Steamers",
  "discount": "",
  "payout": 15.0,
  "product_status": "Online",
  "amazon_link": "https://www.amazon.com/dp/B0DWHPW5CB",
  "tracking_url": ""
}
```

**清洗转换说明**:
- `price`: "USD 164.99" -> 164.99 (float)
- `amazon_link`: 根据 ASIN 自动构造
- `payout`: 确保为数字类型

---

## 6. 飞书表格字段

上传到飞书后，表格包含以下字段:

| 飞书字段名 | 类型 | 来源字段 |
|-----------|------|---------|
| Product ID | Number | product_id |
| ASIN | Text | asin |
| Product Name | Text | product_name |
| Price (USD) | Number (0.00) | price |
| Payout (%) | Number (0.00) | payout |
| Category Name | Text | category_name |
| Product Status | Select (Online/Offline) | product_status |
| Image | Text | image |
| Amazon Link | Text | amazon_link |

---

## 7. 数据分析指标

脚本自动输出以下统计:

| 指标 | 说明 | 用途 |
|------|------|------|
| 总商品数 | 采集到的商品总数 | 数据量评估 |
| 在线/离线 | 商品上下线状态 | 可推广商品筛选 |
| 有/无价格 | 价格是否有效 | 过滤无效商品 |
| 平均价格 | 所有有价格商品的平均值 | 价格区间参考 |
| 平均佣金率 | 所有商品的平均佣金 | 收益预估 |
| 佣金率分布 | 各佣金率区间的商品数 | 高佣金商品筛选 |
| 类别分布 | 各类别的商品数量 | 品类分析 |

---

## 8. 常见问题

### Q1: 采集到 0 条数据
**检查**: Token 是否正确、是否放在 HTTP Header 中。

### Q2: 部分商品价格为 0
**说明**: 这些商品在 YP 平台尚未更新价格，属正常现象。可在数据分析时过滤。

### Q3: 全量采集很慢
**说明**: YP 平台有约 76 万条商品，全量采集需较长时间。建议先用单页采集预览，确认数据结构后再决定是否全量采集。

### Q4: 飞书上传失败
**检查**: APP_ID 和 APP_SECRET 是否正确，飞书应用是否有 `bitable:app` 权限。

---

## 9. 文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 采集脚本 | `yp_to_feishu/collect_offers.py` | 独立的商品采集脚本 |
| 输出数据 | `yp_to_feishu/output/offers_data.json` | 商品 JSON 数据 |
| 飞书结果 | `yp_to_feishu/output/offers_feishu_result.json` | 上传结果（如使用 --upload）|

---

## 10. 完成标准

- [ ] 脚本运行无报错
- [ ] `output/offers_data.json` 文件存在且非空
- [ ] 数据包含 product_id、asin、product_name、price 等字段
- [ ] 统计信息输出正确
- [ ] （可选）飞书多维表格创建成功

---

*SOP 版本: v1.0 | 最后更新: 2026-03-22*
