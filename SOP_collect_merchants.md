# SOP: YP 平台品牌数据（Merchants）采集

## 1. 概述

本 SOP 用于从 YeahPromos (YP) 平台通过 Merchant API 采集品牌数据，包括品牌名称、佣金率、Cookie 天数、网站、国家等信息，并可选上传至飞书多维表格。

**适用场景**: 需要获取 YP 平台可合作的品牌列表，用于品牌筛选、佣金率对比和合作决策。

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
| **端点** | `https://www.yeahpromos.com/index/getadvert/getadvert` |
| **方法** | GET |
| **认证** | HTTP Header: `{"token": "YOUR_TOKEN"}` |
| **速率限制** | 每分钟 10 次 |

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| site_id | string | 是 | 频道 ID |
| page | int | 否 | 页码，从 1 开始，默认 1 |
| limit | int | 否 | 每页数量，默认 20 |
| elite | int | 否 | 0=全部品牌，1=仅精英品牌 |

**响应结构**:
```json
{
  "code": 100000,
  "status": "SUCCESS",
  "data": {
    "Num": 10019,
    "PageTotal": 2004,
    "PageNow": "1",
    "Limit": "20",
    "Data": [
      { /* 品牌数据 */ }
    ]
  }
}
```

**注意**: 数据路径为 `data.data.Data`（嵌套结构），脚本已自动处理两种格式。

**响应字段（data.data.Data 数组）**:

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| mid | int | 品牌 ID | 111334 |
| merchant_name | string | 品牌名称 | Farfetch US |
| logo | string | 品牌 Logo URL | https://yeahpromos.com/... |
| avg_payout | float | 平均佣金率 (%) | 0.75 |
| payout_unit | string | 佣金单位 | "%" |
| rd | int | Cookie 持续天数 | 30 |
| site_url | string | 品牌网站 URL | https://www.iherb.com |
| country | string | 国家信息 | "US/United States(US)" |
| transaction_type | string | 交易类型 | "CPS" |
| is_deeplink | string | 是否深度链接 | "1" / "0" |
| status | string | 申请状态 | "UNAPPLIED" / "APPROVED" / "PENDING" |
| merchant_status | string | 在线状态 | "onLine" / "offLine" |

---

## 4. 执行步骤

### 4.1 单页采集（20 条，快速预览）

```bash
cd c:/Users/wuhj/WorkBuddy/20260322085355/yp_to_feishu
python collect_merchants.py
```

**输出**: `output/merchants_data.json`（20 条品牌数据）

### 4.2 全量采集（所有品牌）

```bash
python collect_merchants.py --all
```

**说明**: YP 平台有约 10,019 个品牌，自动分页采集，每次间隔 0.5 秒。

### 4.3 仅采集精英品牌

```bash
python collect_merchants.py --all --elite
```

### 4.4 采集并上传到飞书

```bash
python collect_merchants.py --upload
```

**输出**:
- `output/merchants_data.json` - 品牌数据
- `output/merchants_feishu_result.json` - 飞书上传结果

---

## 5. 输出数据格式

```json
{
  "merchant_id": 111335,
  "merchant_name": "iHerb",
  "logo": "https://yeahpromos.com/...",
  "avg_payout": 0.75,
  "payout_unit": "%",
  "cookie_days": 45,
  "website": "https://www.iherb.com",
  "country_raw": "US/United States(US)",
  "country": "US - United States(US)",
  "transaction_type": "CPS",
  "is_deeplink": "Yes",
  "status": "UNAPPLIED",
  "online_status": "onLine",
  "tracking_url": ""
}
```

**清洗转换说明**:
- `country`: "US/United States(US)" -> "US - United States(US)"
- `is_deeplink`: "1"/"0" -> "Yes"/"No"
- `avg_payout`: 确保为浮点数
- `cookie_days`: 从 `rd` 字段重命名

---

## 6. 飞书表格字段

| 飞书字段名 | 类型 | 来源字段 |
|-----------|------|---------|
| Merchant ID | Number | merchant_id |
| Merchant Name | Text | merchant_name |
| Avg Payout (%) | Number (0.00) | avg_payout |
| Cookie Days | Number (0) | cookie_days |
| Website | Text | website |
| Country | Text | country |
| Transaction Type | Text | transaction_type |
| Status | Select | status |
| Online Status | Select | online_status |
| Deep Link | Select | is_deeplink |
| Logo | Text | logo |

---

## 7. 数据分析指标

脚本自动输出以下统计:

| 指标 | 说明 | 用途 |
|------|------|------|
| 总品牌数 | 采集到的品牌总数 | 数据量评估 |
| 在线/离线 | 品牌上下线状态 | 可合作品牌筛选 |
| 已申请/未申请 | 品牌申请状态 | 合作进度跟踪 |
| 平均佣金率 | 有佣金品牌的平均值 | 收益预估 |
| 平均 Cookie 天数 | Cookie 追踪有效期 | 转化周期参考 |
| 佣金率分布 | 各佣金率区间的品牌数 | 高佣金品牌筛选 |
| 国家分布 | 各国家的品牌数量 | 市场覆盖分析 |
| 高佣金 Top 5 | 佣金率最高的 5 个品牌 | 重点合作目标 |

---

## 8. 品牌筛选策略

### 高佣金策略
筛选 `avg_payout >= 10%` 的品牌，适合追求高 ROI 的推广。

### 长 Cookie 策略
筛选 `cookie_days >= 30` 的品牌，给用户更多时间完成购买。

### 美国市场策略
筛选 `country` 以 "US" 开头的品牌，专注于美国市场。

### 深度链接策略
筛选 `is_deeplink == "Yes"` 的品牌，可直接链接到商品页面。

---

## 9. 常见问题

### Q1: 采集到 0 条数据
**检查**: Token 是否放在 HTTP Header 中（不是 URL 参数）。YP API 可能更新了响应格式，脚本已兼容新旧两种格式。

### Q2: 部分品牌佣金率为 0
**说明**: 这些品牌尚未设置佣金率，可能是新入驻或暂停合作的品牌。

### Q3: 全量采集需要多长时间
**估算**: 10,019 个品牌 / 100 条每页 = 约 101 页，约 50-60 秒（含 0.5 秒间隔）。

### Q4: status 各状态的含义
- `UNAPPLIED`: 未申请，需要先在 YP 平台申请合作
- `APPROVED`: 已批准，可以直接推广
- `PENDING`: 待审核，已提交申请等待审批

---

## 10. 文件位置

| 文件 | 路径 | 说明 |
|------|------|------|
| 采集脚本 | `yp_to_feishu/collect_merchants.py` | 独立的品牌采集脚本 |
| 输出数据 | `yp_to_feishu/output/merchants_data.json` | 品牌 JSON 数据 |
| 飞书结果 | `yp_to_feishu/output/merchants_feishu_result.json` | 上传结果 |

---

## 11. 完成标准

- [ ] 脚本运行无报错
- [ ] `output/merchants_data.json` 文件存在且非空
- [ ] 数据包含 merchant_id、merchant_name、avg_payout 等字段
- [ ] 统计信息输出正确（总品牌数、平均佣金率等）
- [ ] （可选）飞书多维表格创建成功

---

*SOP 版本: v1.0 | 最后更新: 2026-03-22*
