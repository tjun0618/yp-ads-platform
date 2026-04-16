# SOP: YP 平台类别数据（Categories）采集

## 1. 概述

本 SOP 用于从 YeahPromos (YP) 平台通过 Category API 采集全部类别数据，包括类别 ID 和类别名称，并可选上传至飞书多维表格。

**适用场景**: 需要获取 YP 平台的商品类别列表，用于商品分类筛选、类别分析和按类别采集商品数据。

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
| **端点** | `https://www.yeahpromos.com/index/apioffer/getcategory` |
| **方法** | GET |
| **认证方式** | GET 参数: `?token=YOUR_TOKEN&site_id=YOUR_SITE_ID` |
| **速率限制** | 无明确限制 |

**重要差异**: Category API 的 Token 传递方式与 Merchant/Offer API 不同:
- Merchant/Offer API: Token 放在 **HTTP Header** 中
- Category API: Token 作为 **GET 参数** 传递

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| site_id | string | 是 | 频道 ID |
| token | string | 是 | API Token（注意：不是 Header） |

**响应格式（两种可能）**:

格式 A - 直接返回列表:
```json
[
  {"category_id": 1, "category_name": "Clothing, Shoes & Jewelry"},
  {"category_id": 2, "category_name": "Baby Products"}
]
```

格式 B - 包装在对象中:
```json
{
  "code": 100000,
  "data": [
    {"category_id": 1, "category_name": "Clothing, Shoes & Jewelry"}
  ]
}
```

脚本已自动兼容两种格式。

**响应字段**:

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| category_id | int | 类别 ID | 1 |
| category_name | string | 类别名称 | "Clothing, Shoes & Jewelry" |

---

## 4. 执行步骤

### 4.1 采集全部类别

```bash
cd c:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu
python collect_categories.py
```

**输出**: `output/categories_data.json`（约 148 条类别数据）

**说明**: 类别数据量较小（约 148 条），一次性获取全部，无需分页。

### 4.2 采集并上传到飞书

```bash
python collect_categories.py --upload
```

**输出**:
- `output/categories_data.json` - 类别数据
- `output/categories_feishu_result.json` - 飞书上传结果

---

## 5. 输出数据格式

```json
{
  "category_id": 1,
  "category_name": "Clothing, Shoes & Jewelry"
}
```

**清洗转换说明**:
- 兼容 `category_id` 和 `id` 两种字段名
- 兼容 `category_name` 和 `name` 两种字段名
- 确保 `category_id` 为整数类型

---

## 6. 飞书表格字段

| 飞书字段名 | 类型 | 来源字段 |
|-----------|------|---------|
| Category ID | Number (0) | category_id |
| Category Name | Text | category_name |

---

## 7. 数据分析指标

脚本自动输出以下统计:

| 指标 | 说明 | 用途 |
|------|------|------|
| 总类别数 | 类别总数 | 数据完整性检查 |
| 有效类别名 | 有名称的类别数 | 数据质量检查 |
| 首字母分布 | 各首字母的类别数量 | 类别分布概览 |

---

## 8. 类别数据用途

### 8.1 按类别采集商品

```bash
# 先获取类别 ID
python collect_categories.py

# 查看输出的类别列表，找到感兴趣的 category_id
# 例如: Women's T-Shirts 的 category_id 是 110

# 按类别采集商品
python collect_offers.py --category=110
```

### 8.2 类别数量分析

当前 YP 平台共有约 **148** 个类别，主要分布在:

| 首字母 | 类别数量 | 代表类别 |
|--------|---------|---------|
| W | 59 | Women's 系列（鞋、服装、配饰等） |
| M | 27 | Men's 系列 |
| B | 11 | Beauty、Boots 等 |
| G | 8 | Girls'、Grocery 等 |

### 8.3 常用类别参考

| 类别 ID | 类别名称 | 商品特点 |
|---------|---------|---------|
| 1 | Clothing, Shoes & Jewelry | 服装鞋饰（大类） |
| 16 | Electronics | 电子产品 |
| 7 | Home & Kitchen | 家居厨房 |
| 12 | Beauty & Personal Care | 美妆个护 |
| 13 | Toys & Games | 玩具游戏 |
| 5 | Sports & Outdoors | 运动户外 |

---

## 9. 常见问题

### Q1: Token 认证失败
**检查**: Category API 的 Token 作为 GET 参数传递，不是 Header。请确认请求 URL 中包含 `token=YOUR_TOKEN`。

### Q2: 采集到 0 条数据
**检查**: Site ID 和 Token 是否正确。如果更换了频道，需要更新 Site ID。

### Q3: 类别名称有重复
**说明**: YP 平台的类别 ID 是唯一的，但类别名称可能在不同层级存在相似名称。使用 `category_id` 作为唯一标识。

### Q4: 如何获取子类别
**说明**: Category API 返回的是所有类别（包括父类别和子类别），子类别的 `category_id` 通常更大。当前约 148 个类别已包含所有层级。

---

## 10. 文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 采集脚本 | `yp_to_feishu/collect_categories.py` | 独立的类别采集脚本 |
| 输出数据 | `yp_to_feishu/output/categories_data.json` | 类别 JSON 数据 |
| 飞书结果 | `yp_to_feishu/output/categories_feishu_result.json` | 上传结果 |

---

## 11. 完成标准

- [ ] 脚本运行无报错
- [ ] `output/categories_data.json` 文件存在且非空
- [ ] 类别数约为 148 条
- [ ] 每条记录包含 category_id 和 category_name
- [ ] （可选）飞书多维表格创建成功

---

*SOP 版本: v1.0 | 最后更新: 2026-03-22*
