# YP 平台接口汇总报告

> 调研时间：2026-03-24  
> 平台：https://yeahpromos.com  
> 账号：user_id=2864 (Tong Jun)  

---

## 1. 接口认证方式

YP 平台有**两套独立的认证体系**：

| 认证类型 | 用途 | 示例端点 |
|---------|------|---------|
| **Token 认证**（Header: `token: <value>`） | 官方 API，可在代码/脚本中使用 | `/index/apioffer/getoffer` |
| **Cookie Session**（PHPSESSID） | 网页页面，浏览器访问用 | `/index/offer/brands` |

---

## 2. 已验证可用的 API 接口

### 2.1 Token 认证接口（官方 API）

**认证方式**：HTTP Header 加 `token: 7951dc7484fa9f9d`，Site ID: `12002`

---

#### ✅ `/index/apioffer/getoffer` — 商品（Offers）列表

- **方法**：POST
- **用途**：获取全平台可推广商品列表
- **支持参数**：
  - `site_id`（必填）
  - `page`（页码，从1开始）
  - `page_size`（每页数量，最大100）
  - `asin`（按 ASIN 搜索，可返回多个站点版本）
  - `keyword`（关键词搜索）
  - `category_id`（按类别过滤，但可能不准确）
  - `advert_id`（⚠️ 无效，不会按商户过滤）
- **返回字段**：product_id, asin, product_name, price, commission_rate, category_name, product_status, merchant_id, merchant_name, tracking_url（通常为空）
- **总量**：约 76 万条
- **已知问题**：
  - **混入非美国站商品**（EUR/CAD 价格的商品也会出现）
  - `advert_id` 过滤参数**不生效**（被服务端忽略）
  - `tracking_url` 字段永远为空

---

#### ✅ `/index/getadvert/getadvert` — 商户（Merchants）列表

- **方法**：POST
- **用途**：获取全平台商户（品牌）列表
- **支持参数**：
  - `site_id`（必填）
  - `page`、`page_size`
  - `advert_id`（⚠️ 无效，不会按商户过滤）
- **返回字段**：advert_id, name, commission, track（审批后才有值）, category, country, status, remark
- **总量**：约 10,020 个商户
- **已知问题**：
  - `track` 字段只有申请审批通过后才有值
  - `advert_id` 过滤参数**不生效**

---

#### ✅ `/index/apioffer/getcategory` — 类别列表

- **方法**：GET
- **认证**：`token` 放在 **URL 参数**中（与其他 API 不同！）
- **用途**：获取商品类别列表
- **参数**：`token=7951dc7484fa9f9d&site_id=12002`
- **返回**：约 148 个类别（id, name）
- **无分页**，一次返回全部

---

### 2.2 Cookie 认证接口（网页端）

**认证方式**：HTTP Cookie `PHPSESSID=<value>; user_id=2864`

---

#### ✅ `/index/offer/brands` — 已申请品牌列表（网页）

- **方法**：GET
- **用途**：查看已申请加入的品牌列表
- **分页**：支持 `?is_delete=0&page=N`
- **规模**：**123 页，每页约 48 个品牌** = 约 5,904 个已申请品牌
- **返回内容**：品牌卡片（服务端渲染 HTML），包含 advert_id、品牌名、类别、Commission、状态
- **关键链接**：每个品牌卡片有 `/index/offer/brand_detail?advert_id={mid}&site_id=12002` 链接

---

#### ✅ `/index/offer/brand_detail?advert_id={mid}&site_id=12002` — 品牌商品详情（网页）

- **方法**：GET
- **用途**：查看某个品牌下的所有商品，包含 **完整投放链接**
- **分页**：支持 `?is_delete=0&advert_id={mid}&page=N`
- **规模（以 NORTIV 8 为例）**：**183 页 × 30 条 = 约 5,490 个商品**
- **数据质量**：⭐⭐⭐⭐⭐（最高）
  - ASIN 100% 准确
  - 投放链接 100% 有效（已审批品牌）
  - 只含美国站商品
- **返回字段**（HTML 解析）：
  - 商品名称（`div.col-xs-5.product-name > div`）
  - ASIN（`div.asin-code`）
  - 评论数（括号内数字）
  - 投放链接（`data-clipboard-text` 或 `ClipboardJS.copy()` 参数）
    - 格式：`https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}`
- **对应关系**：ASIN 与 tracking link 通过 DOM 位置绑定，需要精准解析行结构

---

#### ✅ `/index/advert/export_top_merchants` — Top 商户 Excel 导出

- **方法**：GET（或POST）
- **用途**：导出 Top 推荐商户列表（Excel）
- **规模**：约 102 个 Top Merchants
- **返回字段**：MID, Merchant Name, Stars, Country, Category, Advert URL, RD（Cookie天数）, Channel, Commission, Link（部分有）
- **限制**：只有 Top 102 个，不是全部商户

---

#### ✅ `/index/advert/injoin2` — 申请加入商户

- **方法**：POST
- **用途**：向某个商户提交申请
- **参数**：`advert_id=...&site_id=...`
- **返回**：`{"status": "2", "msg": "Application data empty exception!"}` 或成功信息
- **注意**：`/index/advert/injoin` 已弃用（返回 `deprecated`）

---

#### ✅ `/index/offer/report_performance` — 推广效果报表（网页）

- **方法**：GET
- **用途**：查看推广效果数据（Merchant ID, Merchant, Product ID, ASIN, Click, Detail Page Views 等）
- **参数**：`start_date`, `end_date`, `site_id`, `dim`（维度）
- **返回**：HTML（服务端渲染），包含报表数据
- **特点**：这正是你最初提到的那个报表页面，数据直接嵌在 HTML 里，没有独立 JSON API

---

#### ⚠️ `/index/advert/index` — 全部商户列表（网页）

- **方法**：GET
- **用途**：查看全部商户（不只是已申请的）
- **状态**：页面超时（数据量太大）

---

## 3. 不存在 / 无效的接口

以下端点经测试**不存在或返回 404**：

- `/index/offer/product_list` — 404
- `/index/offer/brand_product` — 404  
- `/index/offer/get_products` — 404
- 所有以 `?advert_id=xxx` 过滤商品的 API 端点 — 参数均被忽略

---

## 4. 核心结论：如何获取商户-商品对应关系？

### 你的问题："有没有 API 能获取某商户下所有商品？"

**答案：有，但不是纯 API，而是网页抓取。**

| 方法 | 是否可行 | 数据质量 | 规模 |
|------|---------|---------|------|
| `getoffer` API + advert_id 过滤 | ❌ 参数无效 | 低 | 76万条但无法过滤 |
| `brand_detail` 网页抓取 | ✅ **推荐** | 100% | 每品牌约30-5000+条 |
| Excel 下载（Download Products） | ✅ 最准确 | 100% | 手动操作 |

### 推荐方案：`brand_detail` 网页抓取

通过 Cookie 访问 `/index/offer/brand_detail?advert_id={mid}&site_id=12002&page=N`，解析 HTML 即可得到：
- ✅ 商品名称
- ✅ ASIN  
- ✅ 投放链接（track + pid）
- ✅ 评论数

**每个品牌需抓 N 页（每页30条），分页 URL 格式已确认。**

---

## 5. 数据规模估计

| 资源 | 规模 | 获取方式 |
|------|------|---------|
| 已申请品牌 | ~5,904 个（123页×48） | `/index/offer/brands` 抓取 |
| NORTIV 8 商品 | ~5,490 条（183页×30） | `/index/offer/brand_detail` 抓取 |
| 全平台商品 | ~76 万条 | `getoffer` API（但含非美国站） |
| 全平台商户 | ~10,020 个 | `getadvert` API |

---

## 6. 下一步建议

1. **立即可做**：开发 `brand_detail` 批量抓取脚本，针对已申请且已审批的品牌，批量抓取所有商品和投放链接
2. **数据入库**：将抓取结果直接写入飞书（绕过 API 的数据质量问题）
3. **定时刷新**：每天/每周自动刷新已知品牌的商品数据

---

*报告生成时间：2026-03-24*
