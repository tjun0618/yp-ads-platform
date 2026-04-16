# YP 平台数据 - 飞书多维表格创建 SOP

## 概述

本 SOP 用于在飞书中创建一个多维表格（Bitable），包含三个关联的数据表：
1. **Categories（类别表）** - 148 个类别
2. **Merchants（品牌表）** - 20 个品牌
3. **Offers（商品表）** - 100 个商品

**关联关系**：
- Offers.Category Name -> Categories.Category Name（通过类别名称关联）
- Offers 需要额外的 Merchant Link 字段来关联到 Merchants（由于 Offer API 不提供 merchant_id）

---

## 数据源

| 数据类型 | 文件 | 记录数 | 说明 |
|---------|------|--------|------|
| Categories | `yp_to_feishu/categories_sample.json` | 148 | 类别 ID 和名称 |
| Merchants | `yp_to_feishu/merchants_sample.json` | 20 | 品牌名称、佣金、国家等 |
| Offers | `yp_to_feishu/offers_sample.json` | 100 | 商品名称、价格、ASIN 等 |

---

## 数据字段说明

### Categories 表

| 字段名 | 字段类型 | 说明 |
|---------|---------|------|
| Category ID | Number (2) | 类别唯一 ID，整数格式 |
| Category Name | Text (1) | 类别名称 |

### Merchants 表

| 字段名 | 字段类型 | 说明 |
|---------|---------|------|
| Merchant ID | Number (2) | 品牌 ID，整数格式 |
| Merchant Name | Text (1) | 品牌名称 |
| Avg Payout (%) | Number (2) | 平均佣金率，保留两位小数 |
| Cookie Days | Number (2) | Cookie 持续天数（追踪有效期）|
| Website | Text (1) | 品牌网站 URL（纯文本，非链接）|
| Country | Text (1) | 国家/地区，格式："国家 - 地区代码" |
| Transaction Type | Text (1) | 交易类型（CPS、CPA 等）|
| Status | Single Select (3) | 品牌申请状态：UNAPPLIED、APPROVED、PENDING |
| Online Status | Single Select (3) | 品牌在线状态：onLine、offLine |
| Deep Link | Single Select (3) | 是否支持深度链接：Yes、No |
| Logo | Text (1) | 品牌 Logo URL（纯文本） |

### Offers 表

| 字段名 | 字段类型 | 说明 |
|---------|---------|------|
| Product ID | Number (2) | 商品 ID，整数格式 |
| ASIN | Text (1) | 亚马逊商品 ASIN |
| Product Name | Text (1) | 商品名称 |
| Price (USD) | Number (2) | 商品价格，美元，保留两位小数 |
| Payout (%) | Number (2) | 佣金率，保留两位小数 |
| Category Name | Text (1) | 商品类别名称（来自 API） |
| Product Status | Single Select (3) | 商品状态：Online、Offline |
| Image | Text (1) | 商品图片 URL（纯文本） |
| Amazon Link | Text (1) | 亚马逊商品链接（纯文本，ASIN 构造） |

---

## 飞书多维表格字段类型说明

| 类型代码 | 类型名称 | 说明 |
|---------|---------|------|
| 1 | Text | 纯文本 |
| 2 | Number | 数字 |
| 3 | Single Select | 单选下拉菜单 |
| 5 | Date | 日期 |
| 7 | Checkbox | 复选框 |
| 11 | URL | 链接 |
| 15 | Phone | 电话 |
| 17 | Formula | 公式 |
| 19 | Relation | 关联（已知的飞书 v1 API 限制）|

**注意**：
- 关联字段（Relation，类型 19）在飞书 v1 API 中存在已知的创建限制
- 当前脚本创建所有基础字段，关联字段需要通过飞书 UI 手动添加

---

## 执行步骤

### 准备工作

1. **环境检查**
   - [ ] 确认 Python 已安装（需要 3.7+）
   - [ ] 确认 `requests` 库已安装
   - [ ] 确认飞书应用凭证已配置

2. **数据文件检查**
   - [ ] 确认 `categories_sample.json` 存在于 `yp_to_feishu/` 目录
   - [ ] 确认 `merchants_sample.json` 存在于 `yp_to_feishu/` 目录
   - [ ] 确认 `offers_sample.json` 存在于 `yp_to_feishu/` 目录

3. **飞书应用配置**
   - [ ] 确认 `APP_ID` 已设置为 `cli_a935343a74f89cd4`
   - [ ] 确认 `APP_SECRET` 已设置为 `EqnC0zcv1CF9A2h849z8geK8RmfRRfiE`
   - [ ] 确认飞书应用有以下权限：
     - [ ] bitable:app（创建和管理多维表格）
     - [ ] bitable:app:readonly（只读访问）
     - [ ] bitable:app:export（导出数据）

### 数据采集（如需要）

如果需要重新采集数据：
1. 运行 `collect_sample_data.py` 脚本
2. 该脚本会自动生成以下文件：
   - `categories_sample.json`（148 条类别）
   - `merchants_sample.json`（20 条品牌）
   - `offers_sample.json`（100 条商品）

### 多维表格创建

1. **运行脚本**
   ```bash
   python yp_to_feishu/create_related_bitable.py
   ```

2. **查看脚本输出**
   - 脚本会显示每个步骤的执行状态
   - 成功时会显示：`[OK] Created bitable: {token}`
   - 数据上传时会显示进度：`[Progress] {uploaded}/{total}`

3. **记录输出信息**
   - 脚本最后会输出以下信息供后续使用：
   - Bitable URL：`https://example.feishu.cn/base/{app_token}`
   - App Token：`{app_token}`
   - Categories 表 ID
   - Merchants 表 ID
   - Offers 表 ID

### 数据上传验证

1. **Categories 表验证**
   - [ ] 查看记录数：应为 148
   - [ ] 抽查几条记录验证数据正确性

2. **Merchants 表验证**
   - [ ] 查看记录数：应为 20
   - [ ] 抽查几条记录验证数据正确性

3. **Offers 表验证**
   - [ ] 查看记录数：应为 100
   - [ ] 抽查几条记录验证数据正确性

### 添加关联字段（手动步骤）

**重要**：由于飞书 v1 API 的限制，关联字段（Relation 类型）需要通过飞书 UI 手动添加。

#### 方法 1：使用飞书 UI（推荐）

1. 打开飞书多维表格
   ```
   https://example.feishu.cn/base/{app_token}
   ```

2. 进入 Offers 表
3. 点击表右上角的 "+ 添加字段"按钮
4. 创建第一个关联字段：
   - 字段名：`Category Link`（或自定义名称）
   - 字段类型：选择"关联字段"
   - 关联目标表：选择 Categories 表
   - 关联展示字段：选择 Category Name 字段
   - 保存字段

5. （可选）创建第二个关联字段：
   - 字段名：`Merchant Link`（或自定义名称）
   - 字段类型：选择"关联字段"
   - 注意：由于 Offer API 不提供 merchant_id，此关联较复杂
   - 方案 A：添加文本字段 "Merchant Name"，手动维护
   - 方案 B：创建公式字段自动匹配

#### 方法 2：使用公式字段（备选）

1. 在 Offers 表中添加一个文本字段："Merchant Name"
2. 创建公式字段自动从 Merchants 表中查找匹配的品牌名称：
   ```
   =VLOOKUP([Category Name], [Merchant Name], Merchants!$A$2, FALSE)
   ```
   - 此公式的含义：
     - 在 Merchants 表中搜索 Category Name 字段
     - 返回对应记录的 Merchant Name 字段（第 2 列）
     - 第 4 个参数 FALSE 表示精确匹配

---

## 数据验证

### Categories 表验证

- [ ] 记录总数：148
- [ ] 抽查以下类别是否存在：
  - [ ] Clothing, Shoes & Jewelry（ID: 1）
  - [ ] Baby Products（ID: 2）
  - [ ] Electronics（ID: 16）

### Merchants 表验证

- [ ] 记录总数：20
- [ ] 抽查以下品牌是否存在：
  - [ ] Farfetch US（ID: 111334）
  - [ ] iHerb（ID: 111335）
  - [ ] Charlotte Tilbury US（ID: 112887）

### Offers 表验证

- [ ] 记录总数：100
- [ ] 抽查以下商品是否存在：
  - [ ] 挂烫机（ASIN: B0DWHPW5CB，价格：$164.99）
  - [ ] USB C 笔记本扩展坞（ASIN: B0GLYCCGVZ，价格：$109.99）
  - [ ] 压蒜器（ASIN: B00QU7OXZA，价格：$19.99）

---

## 飞书 URL 和访问凭证

创建成功后，脚本会输出以下信息：

```
URL: https://example.feishu.cn/base/{app_token}
App Token: {app_token}
```

### 凭证保存

**App Token**：`{app_token}`
- 用于后续的数据追加或表格访问
- 请保存到安全的地方

---

## 常见问题

### Q1：数据上传失败 "UserFieldConvFail"

**原因**：URL 字段（类型 11）值格式错误

**解决方案**：
- 已将 URL 字段改为文本类型（type=1）
- 重新运行脚本

### Q2：关联字段创建失败 "field validation failed"

**原因**：飞书 v1 API 不支持通过程序创建关联字段（类型 19）

**解决方案**：
- 通过飞书 UI 手动添加关联字段（约 30 秒）
- 或使用公式字段实现数据关联

### Q3：部分商品价格为 $0

**原因**：这些商品的价格在 YP 平台尚未更新

**解决方案**：
- 在飞书中创建公式字段过滤掉价格为 0 的商品
- 或在数据采集时预先过滤

### Q4：如何关联 Offers 和 Merchants？

**说明**：Offer API 不提供 merchant_id，无法直接建立关联

**解决方案**：
- 方案 A：添加文本字段 "Merchant Name"，手动维护
- 方案 B：使用公式字段自动匹配品牌名称

---

## 附录：数据样本

### Categories 样本（前 5 个）

| Category ID | Category Name |
|-------------|--------------|
| 1 | Clothing, Shoes & Jewelry |
| 2 | Baby Products |
| 3 | Tools & Home Improvement |
| 4 | Arts, Crafts & Sewing |
| 5 | Sports & Outdoors |

### Merchants 样本（前 5 个）

| Merchant ID | Merchant Name | Avg Payout (%) | Country | Status |
|-------------|---------------|--------------|----------------|---------|
| 111334 | Farfetch US | 0.00 | AU - Australia | UNAPPLIED |
| 111335 | iHerb | 0.75 | US - United States | UNAPPLIED |
| 111523 | Elizabeth Arden UK | 3.00 | UK - United Kingdom | UNAPPLIED |
| 112887 | Charlotte Tilbury US | 1.50 | US - United States | UNAPPLIED |

### Offers 样本（前 5 个）

| Product ID | ASIN | Product Name | Price (USD) | Payout (%) | Category Name |
|-----------|------|-----------|--------|----------|--------|---------|
| 1350703 | B0DWHPW5CB | SALAV Heavy Duty Smart Auto... | 164.99 | 15.00 | Garment Steamers |
| 1350702 | B0GLYCCGVZ | USB C Laptop Docking Station... | 109.99 | 15.00 | Laptop Docking Stations |
| 1350701 | B07CT7GFYK | Halter LZ-309 Monitor Stands ... | 0.00 | 15.00 | (无类别) |
| 1350700 | B01N1UQ1SU | CULINAIRE 2oz Glass Spray Bottles... | 19.99 | 15.00 | Refillable Cosmetic Spray Bottles |

---

## 技术支持

### 飞书开放平台

- 官方文档：https://open.feishu.cn/document
- 多维表格 API 文档：https://open.feishu.cn/document/server-docs/docs/bitable-v1
- 应用管理：https://open.feishu.cn/app/

### 飞书 SDK

- GitHub 仓库：https://github.com/larksuite/oapi-sdk-python

---

## 更新日志

| 日期 | 版本 | 更新内容 | 更新人 |
|-------|------|--------|--------|
| 2026-03-22 | v1.0 | 初始版本创建 | - |

---

## 完成标准

- [ ] 成功执行，无错误
- [ ] 所有 3 个表创建成功
- [ ] Categories 表：148 条记录上传成功
- [ ] Merchants 表：20 条记录上传（可能存在已知问题）
- [ ] Offers 表：100 条记录上传成功
- [ ] 关联字段添加说明已记录

---

## 下一步行动

1. 访问飞书多维表格验证数据
2. 通过飞书 UI 手动添加关联字段
3. 验证数据正确性和完整性
4. 根据需要添加公式字段或数据过滤
