# YP 平台所有 API 测试结果分析

## 测试信息

- **测试时间**: 2026-03-22 17:47
- **Channel Name**: shelovable
- **Site ID**: 12002
- **Token**: 7951dc7484fa9f9d

---

## API 概览

| API 名称 | URL | 功能 | 状态 |
|---------|-----|------|------|
| **Merchant API** | /index/getadvert/getadvert | 获取品牌列表 | ✅ 成功 |
| **Offer API** | /index/apioffer/getoffer | 获取商品列表 | ✅ 成功 |
| **Category API** | /index/apioffer/getcategory | 获取类别列表 | ✅ 成功 |

---

## 1. Merchant API 详细分析

### 基本信息

| 参数 | 值 |
|-----|---|
| **URL** | `https://yeahpromos.com/index/getadvert/getadvert` |
| **返回格式** | JSON |
| **HTTP 方法** | GET |
| **请求限制** | 每分钟 10 次 |

### 请求参数

| 参数名 | 说明 | 示例值 |
|--------|------|--------|
| **token** | 网站 token（Header） | 7951dc7484fa9f9d |
| **site_id** | 网站 ID | 12002 |
| **elite** | 是否只返回精英品牌（0: 否, 1: 是） | 0 |
| **page** | 页码，默认 1 | 1 |
| **limit** | 每页数量，默认 1000 | 100 |

### 返回数据

**响应状态**: 成功 ✅
- HTTP 状态码: 200
- 响应码: 100000
- 状态: SUCCESS

**数据摘要**:
- 总品牌数 (Num): 10,019
- 总页数 (PageTotal): 101
- 当前页 (PageNow): 1
- 每页限制 (Limit): 100

### 返回字段

| 字段名 | 说明 | 示例值 |
|--------|------|--------|
| **mid** | 品牌 ID | 111334 |
| **merchant_name** | 品牌名称 | Farfetch US |
| **logo** | 品牌 logo URL | https://yeahpromos.com//index/excel/81.jpg |
| **avg_payout** | 平均佣金 | 0.75 |
| **payout_unit** | 佣金单位 | % |
| **rd** | 返现天数 | 45 |
| **site_url** | 品牌网站 URL | https://www.iherb.com |
| **country** | 国家/地区 | US/United States(US) |
| **transaction_type** | 交易类型 | CPS |
| **tracking_url** | 追踪链接 | null |
| **track** | 追踪信息 | null |
| **advert_status** | 广告状态 | 1 |
| **is_deeplink** | 是否支持深度链接 | 1 |
| **status** | 状态 | UNAPPLIED |
| **merchant_status** | 品牌状态 | onLine |

### 实际品牌数据示例

#### 品牌 #1: Farfetch US
- **品牌 ID**: 111334
- **品牌名称**: Farfetch US
- **Logo**: https://yeahpromos.com//index/excel/81.jpg
- **平均佣金**: 0%
- **佣金单位**: %
- **返现天数**: 30
- **网站 URL**: http://www.farfetch.com
- **国家**: AU/Australia(AU)
- **交易类型**: CPS
- **状态**: UNAPPLIED
- **品牌状态**: onLine

#### 品牌 #2: iHerb
- **品牌 ID**: 111335
- **品牌名称**: iHerb
- **Logo**: https://yeahpromos.com/\\storage/\\/20220915/b17a84153b0e4d65b873ba8f5946182a.jpeg
- **平均佣金**: 0.75%
- **佣金单位**: %
- **返现天数**: 45
- **网站 URL**: https://www.iherb.com
- **国家**: US/United States(US)
- **交易类型**: CPS
- **状态**: UNAPPLIED
- **品牌状态**: onLine

### Merchant API 能力分析

✅ **可以获取的数据**:
- ✅ 品牌名称 (merchant_name)
- ✅ 品牌 ID (mid)
- ✅ 品牌 logo (logo)
- ✅ 平均佣金 (avg_payout)
- ✅ 佣金单位 (payout_unit)
- ✅ 返现天数 (rd)
- ✅ 品牌网站 URL (site_url)
- ✅ 国家/地区 (country)
- ✅ 交易类型 (transaction_type)
- ✅ 品牌 ID 状态 (is_deeplink)
- ✅ 品牌 ID 状态 (status)
- ✅ 品牌状态 (merchant_status)

⚠️ **无法获取的数据**:
- ⚠️ 品牌的原始链接（site_url 是品牌自己的网站，不是 YP 的链接）
- ⚠️ 具体商品信息
- ⚠️ 商品的原始链接

---

## 2. Offer API 详细分析

### 基本信息

| 参数 | 值 |
|-----|---|
| **URL** | `https://yeahpromos.com/index/apioffer/getoffer` |
| **返回格式** | JSON |
| **HTTP 方法** | GET |
| **请求限制** | 每分钟 10 次，最大 1000 条/页 |

### 请求参数

| 参数名 | 说明 | 示例值 | 是否必需 |
|--------|------|--------|----------|
| **token** | 网站 token（Header） | 7951dc7484fa9f9d | ✅ 是 |
| **site_id** | 网站 ID | 12002 | ✅ 是 |
| **link_status** | 链接状态（Pending, Joined, Rejected） | Joined | ❌ 否 |
| **asin** | 商品 ASIN 代码 | B0C5X2G933 | ❌ 否 |
| **category_id** | 类别 ID | 1 | ❌ 否 |
| **page** | 页码，默认 1 | 1 | ❌ 否 |
| **limit** | 每页数量，默认 1000，最大 1000 | 100 | ❌ 否 |

### 返回数据

**响应状态**: 成功 ✅
- HTTP 状态码: 200
- 响应码: 100000
- 状态: SUCCESS

**数据摘要**:
- 总商品数 (total): 759,986
- 每页数量 (per_page): 100
- 当前页 (current_page): 1
- 总页数 (last_page): 7,600

### 返回字段

| 字段名 | 说明 | 示例值 |
|--------|------|--------|
| **product_id** | 商品 ID | 1350703 |
| **asin** | 商品 ASIN | B0DWHPW5CB |
| **product_name** | 商品名称 | SALAV® Heavy Duty Smart Auto Shut-off Commercial Full-Size Garment Steamer... |
| **price** | 价格 | USD 164.99 |
| **image** | 商品图片 URL | https://m.media-amazon.com/images/I/714sO1AJQ7L.jpg |
| **category_id** | 类别 ID | 9461 |
| **category_name** | 类别名称 | Garment Steamers |
| **discount** | 折扣 | "" |
| **link_status** | 链接状态 | "" |
| **payout** | 佣金 | 15 |
| **tracking_url** | 追踪链接 | "" |
| **product_status** | 商品状态 | Online |

### 实际商品数据示例

#### 商品 #1: SALAV® 蒸汽挂烫机
- **商品 ID**: 1350703
- **ASIN**: B0DWHPW5CB
- **商品名称**: SALAV® Heavy Duty Smart Auto Shut-off Commercial Full-Size Garment Steamer, Beeping Alert when Water Runs out, Foot Pedal Control, XL 3L (101.5 oz) Tank, 1800 watts, 90+min of Continuous Steam, White
- **价格**: USD 164.99
- **图片**: https://m.media-amazon.com/images/I/714sO1AJQ7L.jpg
- **类别 ID**: 9461
- **类别名称**: Garment Steamers
- **折扣**: ""
- **链接状态**: ""
- **佣金**: 15
- **追踪链接**: ""
- **商品状态**: Online

#### 商品 #2: USB C 笔记本扩展坞
- **商品 ID**: 1350702
- **ASIN**: B0GLYCCGVZ
- **商品名称**: USB C Laptop Docking Station Stand Dual Monitor, Single 8K for Windows DP 1.4 or Dual 4K for Win and Mac, 9 in 1 USB C Hub with HDMI+DP, 2*USB 3.0, PD 100W, USB C 3.0, SD/TF, Universal Dock Station
- **价格**: USD 109.99
- **图片**: https://m.media-amazon.com/images/I/71v3B167hXL.jpg
- **类别 ID**: 8458
- **类别名称**: Laptop Docking Stations
- **折扣**: ""
- **链接状态**: ""
- **佣金**: 15
- **追踪链接**: ""
- **商品状态**: Online

#### 商品 #3: Mr. Pen 治愈系眼膜
- **商品 ID**: 1350698
- **ASIN**: B0D5BNT42K
- **商品名称**: BLOOMORA 24K Gold Under Eye Patches (30 Pairs) - For Dark Circles & Puffiness - Hydrating Eye Mask for a Revitalized Look
- **价格**: USD 6.39
- **图片**: https://m.media-amazon.com/images/I/71uchIdI9SL.jpg
- **类别 ID**: 911
- **类别名称**: Eye Masks
- **折扣**: ""
- **链接状态**: ""
- **佣金**: 7.5
- **追踪链接**: ""
- **商品状态**: Online

### Offer API 能力分析

✅ **可以获取的数据**:
- ✅ 商品名称 (product_name)
- ✅ 商品 ASIN (asin)
- ✅ 商品价格 (price)
- ✅ 商品图片 (image)
- ✅ 类别名称 (category_name)
- ✅ 类别 ID (category_id)
- ✅ 折扣 (discount)
- ✅ 佣金 (payout)
- ✅ 链接状态 (link_status)
- ✅ 追踪链接 (tracking_url)
- ✅ 商品状态 (product_status)

⚠️ **无法获取的数据**:
- ⚠️ 商品的原始链接（Amazon 链接）
- ⚠️ 品牌信息（品牌名称、品牌 ID 等）
- ⚠️ 商品描述
- ⚠️ 商品评分
- ⚠️ 评论数
- ⚠️ 商品特性

---

## 3. Category API 详细分析

### 基本信息

| 参数 | 值 |
|-----|---|
| **URL** | `https://yeahpromos.com/index/apioffer/getcategory` |
| **返回格式** | JSON |
| **HTTP 方法** | GET |

### 请求参数

| 参数名 | 说明 | 示例值 | 是否必需 |
|--------|------|--------|----------|
| **token** | 网站 token（Header） | 7951dc7484fa9f9d | ✅ 是 |

### 返回数据

**响应状态**: 成功 ✅
- HTTP 状态码: 200
- 响应码: 100000
- 状态: SUCCESS

**数据摘要**:
- 类别数量: 148

### 返回字段

| 字段名 | 说明 | 示例值 |
|--------|------|--------|
| **category_id** | 类别 ID | 1 |
| **category_name** | 类别名称 | Clothing, Shoes & Jewelry |

### 实际类别数据示例

#### 类别 #1-10
1. Clothing, Shoes & Jewelry (ID: 1)
2. Baby Products (ID: 2)
3. Tools & Home Improvement (ID: 3)
4. Arts, Crafts & Sewing (ID: 4)
5. Sports & Outdoors (ID: 5)
6. Health & Household (ID: 6)
7. Beauty & Personal Care (ID: 7)
8. Electronics (ID: 8)
9. Automotive (ID: 9)
10. Pet Supplies (ID: 10)

---

## 用户需求 vs API 能力对比

### 您需要的数据

| 数据字段 | Merchant API | Offer API | Category API | 是否满足 |
|---------|-------------|-----------|--------------|---------|
| **商家名称** | ✅ | ❌ | ❌ | ✅ Merchant API |
| **佣金** | ✅ (avg_payout) | ✅ (payout) | ❌ | ✅ 两者都可以 |
| **类别** | ❌ | ✅ (category_name) | ✅ | ✅ Offer API |
| **ASIN** | ❌ | ✅ (asin) | ❌ | ✅ Offer API |
| **商品名称** | ❌ | ✅ (product_name) | ❌ | ✅ Offer API |
| **价格** | ❌ | ✅ (price) | ❌ | ✅ Offer API |
| **评分** | ❌ | ❌ | ❌ | ❌ 无法获取 |
| **评论数** | ❌ | ❌ | ❌ | ❌ 无法获取 |
| **图片链接** | ✅ (logo) | ✅ (image) | ❌ | ✅ 两者都可以 |
| **商品链接** | ⚠️ (site_url) | ❌ | ❌ | ⚠️ 部分满足 |
| **商品描述** | ❌ | ❌ | ❌ | ❌ 无法获取 |
| **品牌** | ❌ | ❌ | ❌ | ❌ 无法获取 |
| **商品特性** | ❌ | ❌ | ❌ | ❌ 无法获取 |

### 结论

**好消息** ✅:

1. ✅ **Merchant API** 可以获取完整的品牌列表（10,019 个品牌）
   - 品牌名称
   - 品牌 logo
   - 平均佣金
   - 返现天数
   - 品牌网站 URL

2. ✅ **Offer API** 可以获取完整的商品列表（759,986 个商品）
   - 商品名称
   - 商品 ASIN
   - 商品价格
   - 商品图片
   - 类别名称
   - 佣金

3. ✅ **Category API** 可以获取所有类别（148 个类别）

**局限性** ⚠️:

1. ❌ 无法获取商品描述
2. ❌ 无法获取商品评分
3. ❌ 无法获取评论数
4. ❌ 无法获取商品特性
5. ⚠️ 无法获取 Amazon 商品链接（需要使用 ASIN 构建）
6. ❌ 无法获取品牌与商品的关联关系

---

## 推荐数据采集方案

### 方案 A：使用 API（推荐）⭐⭐⭐⭐⭐

**步骤**:

1. **获取品牌列表**
   - 调用 Merchant API
   - 获取所有品牌（10,019 个）
   - 保存品牌信息

2. **获取商品列表**
   - 调用 Offer API
   - 获取所有商品（759,986 个）
   - 保存商品信息

3. **获取类别列表**
   - 调用 Category API
   - 获取所有类别（148 个）
   - 保存类别信息

4. **补充数据（可选）**
   - 使用 Amazon Product Advertising API
   - 获取商品评分、评论数等

5. **上传到飞书**
   - 整合所有数据
   - 上传到飞书表格

**优点**:
- ✅ 数据完整
- ✅ 速度快
- ✅ 官方 API，稳定可靠
- ✅ 维护成本低

**缺点**:
- ⚠️ 需要处理大量数据（76 万+ 商品）
- ⚠️ 需要遵守 API 限制（每分钟 10 次）
- ⚠️ 部分数据无法获取（评分、评论等）

### 方案 B：混合方案（推荐）⭐⭐⭐⭐

**步骤**:

1. **使用 API 获取基础数据**
   - Merchant API: 获取品牌列表
   - Offer API: 获取商品列表（可以分批获取，比如只获取有链接状态的商品）
   - Category API: 获取类别列表

2. **使用 Amazon API 补充数据**
   - 使用 ASIN 查询 Amazon
   - 获取商品评分、评论数
   - 获取商品描述
   - 获取 Amazon 商品链接

3. **整合数据**
   - 合并 API 数据和 Amazon 数据
   - 建立品牌与商品的关联关系

4. **上传到飞书**

**优点**:
- ✅ 数据最完整
- ✅ 速度快（API 获取基础数据）
- ✅ 可以获取所有需要的数据

**缺点**:
- ⚠️ 需要申请 Amazon API 密钥
- ⚠️ 需要处理大量数据

---

## 下一步行动

### 立即行动（优先级：高）⭐⭐⭐⭐⭐

1. ✅ **创建完整的数据采集脚本**
   - 使用 Merchant API 获取所有品牌
   - 使用 Offer API 获取所有商品
   - 使用 Category API 获取所有类别
   - 整合数据

2. ✅ **创建数据导出脚本**
   - 导出为 CSV 文件
   - 导出为 JSON 文件

3. ✅ **创建飞书上传脚本**
   - 读取数据
   - 上传到飞书表格

### 中期规划（优先级：中）⭐⭐⭐

1. 📋 **申请 Amazon Product Advertising API**
   - 获取 API 密钥
   - 补充商品数据

2. 📋 **优化数据采集**
   - 分页处理
   - 错误处理
   - 进度显示

3. 📋 **设置定时任务**
   - 每日/每周自动采集
   - 自动更新飞书数据

---

## 总结

**核心结论**:

1. ✅ **YP 平台提供了完整的 API**，可以获取品牌、商品和类别数据
2. ✅ **Merchant API**: 10,019 个品牌
3. ✅ **Offer API**: 759,986 个商品
4. ✅ **Category API**: 148 个类别
5. ⚠️ 部分数据无法通过 API 获取（评分、评论等），需要使用 Amazon API
6. ⚠️ 无法获取品牌与商品的关联关系

**推荐方案**:

- **最优方案**: 使用 API + Amazon API 混合方案
- **次优方案**: 仅使用 API
- **备选方案**: 使用浏览器自动化（不推荐，速度慢）

准备开始采集数据了吗？
