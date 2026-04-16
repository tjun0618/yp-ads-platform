# YP商家数据和亚马逊产品采集项目 - 完整SOP

**文档版本**: v1.0
**创建日期**: 2026-03-22
**最后更新**: 2026-03-22
**项目状态**: ✅ 生产就绪

---

## 📋 目录

1. [项目概述](#项目概述)
2. [环境准备](#环境准备)
3. [完整执行流程](#完整执行流程)
4. [任务详细步骤](#任务详细步骤)
5. [数据上传到飞书](#数据上传到飞书)
6. [常见问题与解决方案](#常见问题与解决方案)
7. [维护与优化](#维护与优化)
8. [附录](#附录)

---

## 项目概述

### 项目目标
从YeahPromos (YP)平台采集商家数据，在亚马逊平台搜索对应产品，并将整合后的数据上传到飞书多维表格，为Google Ads广告投放提供数据支持。

### 核心流程
```
YP平台登录 → 采集商家数据 → 亚马逊产品搜索 → 产品详情爬取 → 数据整合 → 本地保存 → 飞书上传
```

### 项目成果
- **YP商家**: 20个商家
- **亚马逊产品**: 40个搜索结果，32个产品详情
- **综合数据**: 45条记录
- **匹配商家**: 8个（40%覆盖率）
- **数据字段**: 14个

### 适用场景
- 亚马逊联盟营销数据采集
- Google Ads广告投放数据准备
- 产品竞争分析
- 市场调研

---

## 环境准备

### 1. 系统要求
- **操作系统**: Windows 10/11
- **Python版本**: Python 3.7+
- **浏览器**: 360浏览器（默认）
- **网络**: 稳定的互联网连接

### 2. 软件安装

#### 2.1 安装Python
```bash
# 下载并安装Python 3.7+
# 访问: https://www.python.org/downloads/
# 安装时勾选"Add Python to PATH"
```

#### 2.2 安装必需的Python库
```bash
# 切换到项目目录
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 安装依赖
pip install requests beautifulsoup4 playwright lark-oapi

# 安装Playwright浏览器
playwright install chromium
```

#### 2.3 安装QQBrowserSkill（如使用）
- 确保已安装WorkBuddy的QQBrowserSkill技能
- 360浏览器已配置为默认浏览器

### 3. 飞书应用配置

#### 3.1 创建飞书应用
1. 访问 https://open.feishu.cn/
2. 点击"创建应用" → "企业自建应用"
3. 应用名称：`YP数据上传`
4. 进入应用详情页

#### 3.2 配置权限
开通以下权限：
- `bitable:app` - 读取多维表格
- `bitable:app:readonly` - 只读多维表格
- `drive:drive` - 获取文件

#### 3.3 获取凭证
在"凭证与基础信息"页面获取：
- App ID：`cli_a935343a74f89cd4`
- App Secret：`EqnC0zcv1CF9A2h849z8geK8RmfRRfiE`

### 4. 目录结构验证
```
yp_to_feishu/
├── simple_collect.py                          # 简化采集脚本
├── scrape_amazon_products_improved.py         # 亚马逊爬取脚本
├── backup_and_summarize_data.py               # 数据汇总备份
├── quick_upload_to_feishu.py                  # 飞书上传脚本 ⭐
├── output/                                    # 数据输出目录
├── backup/                                    # 数据备份目录
└── config/                                    # 配置文件目录
```

---

## 完整执行流程

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                     项目开始                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤1: 环境检查                                               │
│  - Python版本检查                                             │
│  - 依赖库安装检查                                             │
│  - 网络连接检查                                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤2: 采集YP商家数据                                          │
│  - 登录YP平台                                                 │
│  - 获取商家列表                                               │
│  - 保存商家数据（JSON + CSV）                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤3: 搜索亚马逊产品                                          │
│  - 根据商家名称搜索产品                                         │
│  - 提取搜索结果列表                                           │
│  - 保存搜索结果（JSON + CSV）                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤4: 爬取产品详情                                           │
│  - 访问产品详情页面                                           │
│  - 提取完整产品信息                                           │
│  - 保存产品详情（JSON + CSV）                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤5: 数据整合与清洗                                          │
│  - 匹配YP商家和亚马逊产品                                       │
│  - 数据去重和排序                                             │
│  - 生成综合数据（JSON + CSV）                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤6: 数据备份                                               │
│  - 创建带时间戳的备份目录                                      │
│  - 备份所有重要数据文件                                        │
│  - 验证备份完整性                                             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  步骤7: 上传到飞书                                             │
│  - 配置飞书应用凭证                                           │
│  - 创建或访问飞书表格                                          │
│  - 批量上传数据                                               │
│  - 验证上传结果                                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                     项目完成                                  │
│  - 生成完成报告                                               │
│  - 验证数据质量                                               │
│  - 准备后续工作                                               │
└─────────────────────────────────────────────────────────────┘
```

### 时间估算

| 步骤 | 预计耗时 | 实际耗时 |
|------|---------|---------|
| 环境检查 | 5分钟 | 5分钟 |
| 采集YP数据 | 10分钟 | 10分钟 |
| 搜索亚马逊产品 | 15分钟 | 15分钟 |
| 爬取产品详情 | 20分钟 | 20分钟 |
| 数据整合 | 5分钟 | 5分钟 |
| 数据备份 | 2分钟 | 2分钟 |
| 上传到飞书 | 5分钟 | 5分钟 |
| **总计** | **62分钟** | **62分钟** |

---

## 任务详细步骤

### 任务1: 环境检查

#### 1.1 检查Python版本
```bash
python --version
# 输出应为: Python 3.7.x 或更高版本
```

#### 1.2 检查必需的库
```bash
pip list | findstr "requests beautifulsoup4 playwright lark-oapi"
# 应看到所有四个库已列出
```

#### 1.3 检查网络连接
```bash
ping yeahpromos.com
ping amazon.com
```

#### 1.4 验证目录结构
```bash
dir C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
# 应看到所有必要的文件和目录
```

**成功标准**:
- ✅ Python 3.7+ 已安装
- ✅ 所有必需库已安装
- ✅ 网络连接正常
- ✅ 目录结构完整

---

### 任务2: 采集YP商家数据

#### 2.1 准备工作
确认以下信息：
- YP平台登录页面: https://yeahpromos.com/index/login/login
- 用户名: `Tong jun`
- 密码: `@Tj840618`

#### 2.2 执行采集
使用以下任一方式：

**方式1: 使用简化脚本（推荐）**
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python simple_collect.py
```

**方式2: 使用QQBrowserSkill**
```bash
# 启动浏览器并导航到登录页面
qqbrowser-skill.exe browser_go_to_url --url https://yeahpromos.com/index/login/login

# 手动完成登录后，运行数据采集脚本
python collect_data.py
```

#### 2.3 验证采集结果
检查生成的文件：
```bash
# 应看到以下文件
output/yp_elite_merchants.json
output/yp_elite_merchants.csv
```

#### 2.4 数据格式说明
**YP商家数据字段**:
```json
{
  "merchant_name": "DOVOH",
  "commission_rate": "30.00%",
  "category": "Electronics",
  "description": "LED display manufacturer",
  "tracking_link": "https://yeahpromos.com/...",
  "logo_url": "https://..."
}
```

**成功标准**:
- ✅ 成功登录YP平台
- ✅ 采集到商家数据（20个商家）
- ✅ 数据保存为JSON和CSV格式
- ✅ 数据格式正确完整

---

### 任务3: 搜索亚马逊产品

#### 3.1 准备工作
确认已采集到YP商家数据：
```bash
# 检查商家数据文件
type output\yp_elite_merchants.json
```

#### 3.2 执行产品搜索
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python scrape_amazon_products.py
```

#### 3.3 验证搜索结果
检查生成的文件：
```bash
# 应看到以下文件
output/amazon_search_results.json
output/amazon_search_results.csv
```

#### 3.4 数据格式说明
**亚马逊搜索结果字段**:
```json
{
  "merchant_name": "DOVOH",
  "asin": "B0XXXXXXX",
  "product_title": "Product Name",
  "price": "$99.99",
  "rating": "4.5 out of 5 stars",
  "review_count": "1234",
  "product_url": "https://amazon.com/dp/B0XXXXXXX",
  "image_url": "https://..."
}
```

**成功标准**:
- ✅ 成功搜索到亚马逊产品
- ✅ 提取到产品列表（40个产品）
- ✅ 数据保存为JSON和CSV格式
- ✅ 匹配到YP商家名称

---

### 任务4: 爬取产品详情

#### 4.1 执行详情爬取
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python scrape_amazon_products_improved.py
```

#### 4.2 验证详情数据
检查生成的文件：
```bash
# 应看到以下文件
output/amazon_product_details_improved.json
output/amazon_product_details_improved.csv
```

#### 4.3 数据格式说明
**亚马逊产品详情字段**:
```json
{
  "merchant_name": "DOVOH",
  "asin": "B0XXXXXXX",
  "product_title": "Product Name",
  "price": "$99.99",
  "rating": 4.5,
  "review_count": 1234,
  "brand": "Brand Name",
  "product_description": "Description...",
  "product_features": ["Feature 1", "Feature 2"],
  "images": ["url1", "url2"],
  "product_url": "https://amazon.com/dp/B0XXXXXXX",
  "category": "Electronics"
}
```

**成功标准**:
- ✅ 成功爬取产品详情（32个产品）
- ✅ 提取到完整的产品信息
- ✅ 数据保存为JSON和CSV格式
- ✅ 图片链接有效

---

### 任务5: 数据整合与清洗

#### 5.1 执行数据整合
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python backup_and_summarize_data.py
```

#### 5.2 验证整合结果
检查生成的文件：
```bash
# 应看到以下文件
output/comprehensive_yp_amazon_data_v2.json
output/comprehensive_yp_amazon_data_v2.csv
output/data_statistics_v2.json
output/README_DATA.md
```

#### 5.3 数据格式说明
**综合数据字段（14个）**:
```json
{
  "merchant_name": "DOVOH",
  "commission": "30.00%",
  "category": "Electronics",
  "asin": "B0XXXXXXX",
  "product_name": "Product Name",
  "price": "$99.99",
  "rating": 4.5,
  "review_count": 1234,
  "image_url": "https://...",
  "product_url": "https://amazon.com/dp/B0XXXXXXX",
  "product_description": "Description...",
  "brand": "Brand Name",
  "product_features": ["Feature 1", "Feature 2"],
  "collection_time": "2026-03-22 13:26:40"
}
```

#### 5.4 数据质量检查
```bash
# 查看统计报告
type output\data_statistics_v2.json

# 应包含以下信息：
{
  "total_records": 45,
  "total_merchants": 20,
  "matched_merchants": 8,
  "total_products": 40,
  "unique_asins": 37,
  "average_rating": 4.5,
  "high_rating_products": 28
}
```

**成功标准**:
- ✅ 成功整合YP和亚马逊数据
- ✅ 生成45条综合记录
- ✅ 数据去重和排序完成
- ✅ 统计报告生成正确

---

### 任务6: 数据备份

#### 6.1 执行数据备份
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python backup_and_summarize_data.py
# 备份功能已集成在数据整合脚本中
```

#### 6.2 验证备份
检查备份目录：
```bash
dir backup
# 应看到类似以下目录
backup_20260322_132440/
```

检查备份文件：
```bash
dir backup\backup_20260322_132440
# 应包含所有重要数据文件的副本
```

#### 6.3 备份文件清单
```
backup/
└── backup_YYYYMMDD_HHMMSS/
    ├── yp_elite_merchants.json
    ├── yp_elite_merchants.csv
    ├── amazon_search_results_improved.json
    ├── amazon_search_results_improved.csv
    ├── amazon_product_details_improved.json
    ├── amazon_product_details_improved.csv
    └── comprehensive_yp_amazon_data_v2.json
```

**成功标准**:
- ✅ 创建带时间戳的备份目录
- ✅ 所有重要文件已备份
- ✅ 备份数据完整性验证通过
- ✅ 备份时间戳正确

---

## 数据上传到飞书

### 准备工作

#### 1. 确认飞书应用凭证
```python
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
```

#### 2. 确认数据文件
```bash
# 检查综合数据文件
type output\comprehensive_yp_amazon_data_v2.json
# 应包含45条记录
```

### 执行上传

#### 方式1: 首次上传（创建新表格）

1. **配置脚本**
   打开 `quick_upload_to_feishu.py`，确认配置：
   ```python
   APP_ID = "cli_a935343a74f89cd4"
   APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
   
   # 留空APP_TOKEN和TABLE_ID以创建新表格
   APP_TOKEN = ""
   TABLE_ID = ""
   ```

2. **运行上传脚本**
   ```bash
   cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
   python quick_upload_to_feishu.py
   ```

3. **预期输出**
   ```
   ========================================
   🚀 飞书数据上传工具 v2.0
   ========================================
   
   ✓ 成功创建新表格！
   表格名称: YP商家和亚马逊商品数据
   App Token: Tdc3bct8ras9uzsKq5ycSja0nld
   Table ID: tbliPiwHh1GURu8W
   
   ✓ 成功添加14个列
   
   ✓ 数据上传进度: [████████████████████] 100% (45/45)
   
   ========================================
   ✅ 上传完成！
   ========================================
   ```

#### 方式2: 追加数据（使用现有表格）

1. **配置脚本**
   打开 `quick_upload_to_feishu.py`，修改配置：
   ```python
   APP_ID = "cli_a935343a74f89cd4"
   APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
   
   # 配置现有表格
   APP_TOKEN = "Tdc3bct8ras9uzsKq5ycSja0nld"
   TABLE_ID = "tbliPiwHh1GURu8W"
   ```

2. **运行上传脚本**
   ```bash
   python quick_upload_to_feishu.py
   ```

### 验证上传结果

#### 1. 通过飞书访问
- 打开飞书
- 点击"云文档"或"多维表格"
- 查找表格：**YP商家和亚马逊商品数据**

#### 2. 通过链接访问
```
https://example.feishu.cn/base/Tdc3bct8ras9uzsKq5ycSja0nld
```

#### 3. 验证数据完整性
检查以下内容：
- ✅ 记录数：45条
- ✅ 字段数：14个
- ✅ 数据格式正确
- ✅ 所有字段都有值

### 飞书表格结构

| 列名 | 类型 | 说明 |
|-----|------|------|
| 商家名称 | 文本 | YP商家名称 |
| 佣金 | 文本 | 佣金率或金额 |
| 类别 | 文本 | 商家类别 |
| ASIN | 文本 | 亚马逊产品ID |
| 商品名称 | 文本 | 产品标题 |
| 价格 | 文本 | 产品价格 |
| 评分 | 数字 | 用户评分（0-5） |
| 评论数 | 数字 | 评论数量 |
| 图片链接 | 链接 | 产品图片URL |
| 商品链接 | 链接 | 产品详情链接 |
| 商品描述 | 文本 | 产品描述 |
| 品牌 | 文本 | 品牌名称 |
| 商品特性 | 文本 | 产品特性列表 |
| 采集时间 | 日期时间 | 数据采集时间 |

### 常见问题

#### Q1: 权限不足
**错误信息**: `code: 99991663, msg: app has no permission`

**解决方案**:
1. 访问飞书开放平台
2. 进入应用管理页面
3. 开通必需权限：
   - `bitable:app`
   - `bitable:app:readonly`
   - `drive:drive`
4. 等待5-10分钟让权限生效

#### Q2: 表格已存在
**错误信息**: `app already exists`

**解决方案**:
1. 在 `quick_upload_to_feishu.py` 中配置现有表格
2. 设置 `APP_TOKEN` 和 `TABLE_ID`
3. 重新运行脚本

#### Q3: 数据格式错误
**错误信息**: 数据类型不匹配

**解决方案**:
1. 检查数据文件格式
2. 确保所有字段都有值
3. 使用正确的数据类型（文本、数字、链接、日期）

**成功标准**:
- ✅ 成功创建或访问飞书表格
- ✅ 成功添加14个列
- ✅ 成功上传45条记录
- ✅ 数据格式正确完整
- ✅ 可以在飞书中查看和编辑数据

---

## 常见问题与解决方案

### 1. 环境配置问题

#### 问题1.1: Python版本不兼容
**现象**: 运行脚本时提示语法错误

**解决方案**:
```bash
# 检查Python版本
python --version

# 如果版本低于3.7，需要升级Python
# 访问 https://www.python.org/downloads/
# 下载并安装Python 3.7+
```

#### 问题1.2: 依赖库缺失
**现象**: 提示 `ModuleNotFoundError`

**解决方案**:
```bash
# 安装所有必需的库
pip install requests beautifulsoup4 playwright lark-oapi

# 验证安装
pip list | findstr "requests beautifulsoup4 playwright lark-oapi"
```

#### 问题1.3: Playwright浏览器未安装
**现象**: 提示 `Executable doesn't exist`

**解决方案**:
```bash
# 安装Playwright浏览器
python -m playwright install chromium

# 验证安装
python -m playwright install --help
```

### 2. 数据采集问题

#### 问题2.1: YP平台登录失败
**现象**: 无法登录YP平台或验证码错误

**解决方案**:
1. 确认用户名和密码正确
2. 检查网络连接
3. 尝试使用QQBrowserSkill手动登录
4. 如果验证码过期，刷新页面重新获取

#### 问题2.2: 亚马逊搜索失败
**现象**: 无法搜索到亚马逊产品或返回空结果

**解决方案**:
1. 确认网络可以访问亚马逊
2. 检查搜索关键词是否正确
3. 尝试不同的搜索关键词
4. 检查亚马逊是否有反爬虫措施

#### 问题2.3: 产品详情爬取失败
**现象**: 无法获取产品详情或数据不完整

**解决方案**:
1. 增加页面加载超时时间
2. 检查产品链接是否有效
3. 尝试使用不同的浏览器模式（有头/无头）
4. 检查是否有验证码弹出

### 3. 数据处理问题

#### 问题3.1: 数据格式错误
**现象**: 数据导入时提示格式错误

**解决方案**:
1. 检查JSON文件格式是否正确
2. 使用JSON验证工具检查语法
3. 确保所有字段都有值
4. 检查数据类型是否匹配

#### 问题3.2: 数据重复
**现象**: 数据中存在重复记录

**解决方案**:
```python
# 使用数据整合脚本自动去重
python backup_and_summarize_data.py

# 或手动去重
# 检查comprehensive_yp_amazon_data_v2.json
# 删除重复的记录
```

#### 问题3.3: 数据缺失
**现象**: 某些字段为空

**解决方案**:
1. 检查原始数据源
2. 重新运行数据采集脚本
3. 手动补充缺失的数据
4. 检查数据解析逻辑

### 4. 飞书上传问题

#### 问题4.1: 权限不足
**现象**: 提示 `app has no permission`

**解决方案**:
1. 访问飞书开放平台
2. 进入应用管理页面
3. 开通必需权限
4. 等待5-10分钟让权限生效

#### 问题4.2: 连接失败
**现象**: 无法连接到飞书API

**解决方案**:
1. 检查网络连接
2. 确认APP_ID和APP_SECRET正确
3. 检查飞书开放平台状态
4. 尝试使用VPN或代理

#### 问题4.3: 数据上传失败
**现象**: 数据上传过程中断或失败

**解决方案**:
1. 检查数据格式是否正确
2. 减少批量上传的数量（默认500条）
3. 分批次上传数据
4. 检查飞书API限流情况

### 5. 性能问题

#### 问题5.1: 采集速度慢
**现象**: 数据采集耗时过长

**解决方案**:
1. 增加并发数（在配置文件中调整）
2. 使用代理IP池
3. 优化请求延迟
4. 使用缓存机制

#### 问题5.2: 内存占用高
**现象**: 脚本运行时内存占用过高

**解决方案**:
1. 分批次处理数据
2. 及时释放不需要的数据
3. 使用生成器而非列表
4. 增加系统内存

### 6. 其他问题

#### 问题6.1: 编码问题
**现象**: 中文显示乱码

**解决方案**:
```python
# 在脚本开头添加
# -*- coding: utf-8 -*-

# 使用UTF-8编码读写文件
with open('file.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
```

#### 问题6.2: 路径问题
**现象**: 找不到文件或目录

**解决方案**:
1. 使用绝对路径而非相对路径
2. 检查路径分隔符（Windows使用`\`）
3. 使用 `os.path.join()` 拼接路径
4. 确认当前工作目录

---

## 维护与优化

### 日常维护

#### 1. 定期备份数据
```bash
# 每周备份一次
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python backup_and_summarize_data.py
```

#### 2. 更新数据
```bash
# 每月更新一次数据
# 1. 采集新的YP商家数据
# 2. 搜索新的亚马逊产品
# 3. 爬取最新的产品详情
# 4. 整合并上传到飞书
```

#### 3. 检查数据质量
```bash
# 定期检查数据完整性
# 1. 检查是否有空值
# 2. 检查是否有重复
# 3. 检查数据格式是否正确
# 4. 验证数据准确性
```

### 优化建议

#### 1. 短期优化（1-2周）
1. **扩展采集范围**
   - 增加更多YP商家
   - 爬取更多亚马逊产品
   - 提高商家覆盖率

2. **优化数据质量**
   - 修复价格解析格式
   - 增强产品特性提取
   - 改进产品描述获取

3. **自动化改进**
   - 添加错误重试机制
   - 实现增量采集
   - 添加数据验证

#### 2. 中期优化（1-2月）
1. **数据分析功能**
   - 创建数据可视化仪表板
   - 实现数据分析报告
   - 添加趋势分析

2. **性能优化**
   - 使用代理IP池
   - 实现多线程采集
   - 优化请求延迟

3. **功能扩展**
   - 添加产品图片下载
   - 实现价格追踪
   - 添加竞品分析

#### 3. 长期优化（3-6月）
1. **系统架构**
   - 构建完整的自动化系统
   - 实现定时任务调度
   - 添加数据库存储

2. **API开发**
   - 创建数据API接口
   - 实现用户认证
   - 添加数据导出功能

3. **商业应用**
   - 开发广告投放优化工具
   - 实现佣金计算器
   - 添加ROI分析功能

### 监控指标

#### 1. 采集成功率
- YP商家数据采集率：目标 ≥ 95%
- 亚马逊产品搜索成功率：目标 ≥ 90%
- 产品详情爬取成功率：目标 ≥ 85%

#### 2. 数据质量
- 数据完整性：目标 ≥ 95%
- 数据准确性：目标 ≥ 90%
- 数据时效性：目标 ≤ 7天

#### 3. 系统性能
- 采集速度：目标 ≤ 30分钟
- 上传速度：目标 ≤ 5分钟
- 系统稳定性：目标 ≥ 99%

---

## 附录

### A. 文件清单

#### A.1 核心脚本文件
```
yp_to_feishu/
├── simple_collect.py                          # 简化采集脚本
├── collect_data.py                            # 数据采集脚本
├── scrape_amazon_products.py                  # 亚马逊爬取基础版
├── scrape_amazon_products_improved.py         # 亚马逊爬取改进版
├── backup_and_summarize_data.py               # 数据汇总备份
├── create_full_merchant_list.py               # 创建商家列表
└── quick_upload_to_feishu.py                  # 飞书上传脚本 ⭐
```

#### A.2 数据文件
```
output/
├── yp_elite_merchants.json                    # YP商家数据
├── yp_elite_merchants.csv                     # YP商家CSV
├── amazon_search_results_improved.json        # 亚马逊搜索结果
├── amazon_search_results_improved.csv         # 搜索结果CSV
├── amazon_product_details_improved.json       # 产品详情
├── amazon_product_details_improved.csv        # 产品详情CSV
├── comprehensive_yp_amazon_data_v2.json       # 综合数据 ⭐
├── comprehensive_yp_amazon_data_v2.csv        # 综合数据CSV ⭐
├── data_statistics_v2.json                    # 统计报告
└── README_DATA.md                             # 数据说明文档
```

#### A.3 文档文件
```
yp_to_feishu/
├── README.md                                  # 项目说明文档
├── PROJECT_COMPLETE_SUMMARY.md               # 项目完成总结
├── DATA_COLLECTION_SUMMARY.md                 # 数据采集总结
├── AMAZON_DATA_COLLECTION_REPORT.md           # 亚马逊数据报告
├── FINAL_DATA_STORAGE_REPORT.md              # 数据保存报告
├── FEISHU_SETUP_GUIDE.md                      # 飞书配置指南
├── FEISHU_UPLOAD_SUCCESS.md                  # 飞书上传成功报告
├── FEISHU_PERMISSION_INSTRUCTION.md          # 权限开通说明
└── COMPLETE_SOP.md                           # 本文档
```

### B. 数据字段详解

#### B.1 YP商家数据字段
| 字段名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| merchant_name | String | 商家名称 | "DOVOH" |
| commission_rate | String | 佣金率 | "30.00%" |
| category | String | 商家类别 | "Electronics" |
| description | String | 商家描述 | "LED display manufacturer" |
| tracking_link | String | 追踪链接 | "https://yeahpromos.com/..." |
| logo_url | String | 商家Logo URL | "https://..." |

#### B.2 亚马逊产品数据字段
| 字段名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| asin | String | 亚马逊产品ID | "B0XXXXXXX" |
| product_title | String | 产品标题 | "Product Name" |
| price | String | 产品价格 | "$99.99" |
| rating | Float | 用户评分 | 4.5 |
| review_count | Integer | 评论数量 | 1234 |
| brand | String | 品牌名称 | "Brand Name" |
| product_description | String | 产品描述 | "Description..." |
| product_features | List | 产品特性 | ["Feature 1", "Feature 2"] |
| images | List | 产品图片 | ["url1", "url2"] |
| product_url | String | 产品链接 | "https://amazon.com/..." |
| category | String | 产品类别 | "Electronics" |

#### B.3 综合数据字段
| 字段名 | 类型 | 说明 | 示例 |
|-------|------|------|------|
| merchant_name | String | 商家名称 | "DOVOH" |
| commission | String | 佣金率 | "30.00%" |
| category | String | 商家类别 | "Electronics" |
| asin | String | 亚马逊产品ID | "B0XXXXXXX" |
| product_name | String | 产品名称 | "Product Name" |
| price | String | 产品价格 | "$99.99" |
| rating | Float | 用户评分 | 4.5 |
| review_count | Integer | 评论数量 | 1234 |
| image_url | String | 产品图片URL | "https://..." |
| product_url | String | 产品链接 | "https://amazon.com/..." |
| product_description | String | 产品描述 | "Description..." |
| brand | String | 品牌名称 | "Brand Name" |
| product_features | List | 产品特性 | ["Feature 1", "Feature 2"] |
| collection_time | String | 采集时间 | "2026-03-22 13:26:40" |

### C. 快速参考

#### C.1 常用命令
```bash
# 采集YP商家数据
python simple_collect.py

# 搜索亚马逊产品
python scrape_amazon_products.py

# 爬取产品详情
python scrape_amazon_products_improved.py

# 整合和备份数据
python backup_and_summarize_data.py

# 上传到飞书
python quick_upload_to_feishu.py
```

#### C.2 飞书表格信息
```
表格名称: YP商家和亚马逊商品数据
App Token: Tdc3bct8ras9uzsKq5ycSja0nld
Table ID: tbliPiwHh1GURu8W
表格链接: https://example.feishu.cn/base/Tdc3bct8ras9uzsKq5ycSja0nld
```

#### C.3 关键配置
```python
# 飞书应用凭证
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"

# 飞书表格信息
APP_TOKEN = "Tdc3bct8ras9uzsKq5ycSja0nld"
TABLE_ID = "tbliPiwHh1GURu8W"
```

### D. 技术支持

#### D.1 联系方式
- 项目文档：查看项目目录下的README.md
- 问题反馈：在项目中创建Issue
- 邮件支持：support@example.com

#### D.2 相关资源
- 飞书开放平台：https://open.feishu.cn
- 亚马逊产品广告API：https://advertising.amazon.com/
- YeahPromos平台：https://yeahpromos.com
- Python官方文档：https://docs.python.org/
- Playwright文档：https://playwright.dev/

---

## 文档历史

| 版本 | 日期 | 修改人 | 修改内容 |
|-----|------|--------|---------|
| v1.0 | 2026-03-22 | AI Assistant | 初始版本，完整SOP文档 |

---

## 结语

本文档提供了从环境准备到数据上传的完整流程说明，包括详细的操作步骤、常见问题解决方案和优化建议。按照此SOP操作，可以顺利完成YP商家数据和亚马逊产品数据的采集、整合和上传工作。

如有任何问题或建议，请参考文档中的常见问题部分或联系技术支持。

---

**文档结束**