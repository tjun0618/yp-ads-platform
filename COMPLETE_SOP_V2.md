# YP商家数据和亚马逊产品采集项目 - 完整SOP v2.0

**文档版本**: v2.0
**创建日期**: 2026-03-22
**最后更新**: 2026-03-22
**项目状态**: ✅ 生产就绪
**更新内容**: 使用 bb-browser 进行登录，支持会话保持

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

### v2.0 更新内容
- ✅ 使用 bb-browser 进行登录（替代 QQBrowserSkill）
- ✅ 支持会话保持，避免每次重新登录
- ✅ 减少验证码输入次数
- ✅ 提高自动化程度

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
- **Node.js版本**: Node.js 18+（用于 bb-browser）
- **网络**: 稳定的互联网连接

### 2. 软件安装

#### 2.1 安装Python
```bash
# 下载并安装Python 3.7+
# 访问: https://www.python.org/downloads/
# 安装时勾选"Add Python to PATH"
```

#### 2.2 安装Node.js
```bash
# 下载并安装Node.js 18+
# 访问: https://nodejs.org/
# 下载LTS版本并安装
```

#### 2.3 安装bb-browser
```bash
# 全局安装bb-browser
npm install -g bb-browser

# 更新社区适配器
bb-browser site update

# 验证安装
bb-browser --version
```

#### 2.4 安装必需的Python库
```bash
# 切换到项目目录
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 安装依赖
pip install requests beautifulsoup4 playwright lark-oapi

# 安装Playwright浏览器
playwright install chromium
```

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
├── collect_yp_data.py              # YP数据采集脚本
├── scrape_amazon_products.py       # 亚马逊产品爬取脚本
├── quick_upload_to_feishu.py      # 飞书上传脚本
├── yp_login_skill.py               # YP登录Skill（新增）
├── login_with_bb_browser.py        # bb-browser登录脚本
├── login_with_bb_browser.bat       # 批处理登录脚本
├── output/                         # 数据输出目录
│   ├── yp_merchants.json
│   ├── amazon_search_results.json
│   └── amazon_product_details.json
└── docs/                          # 文档目录
    ├── COMPLETE_SOP_V2.md         # 本文档
    ├── BROWSER_SKILL_COMPARISON.md
    ├── BB_BROWSER_TEST_GUIDE.md
    └── SESSION_PERSISTENCE_TEST_REPORT.md
```

---

## 完整执行流程

### 流程图

```
┌─────────────────────────────────────────────────────────┐
│ 步骤1: 环境检查                                      │
│ - 验证Python、Node.js、bb-browser安装                 │
│ - 验证飞书配置                                       │
│ - 验证目录结构                                       │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤2: 登录YP平台 ⭐（v2.0更新）                     │
│ - 使用yp_login_skill.py进行首次登录                    │
│ - 手动输入验证码（仅首次需要）                        │
│ - bb-browser保存登录状态（Cookie）                     │
│ - 后续操作无需重新登录                                │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤3: 采集YP商家数据                                 │
│ - 使用bb-browser访问商家列表页面                      │
│ - 使用JavaScript提取商家数据                          │
│ - 保存为JSON格式                                     │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤4: 搜索亚马逊产品                                 │
│ - 使用商家名称在亚马逊搜索产品                        │
│ - 保存搜索结果                                       │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤5: 爬取产品详情                                   │
│ - 访问每个产品的详情页                                │
│ - 提取详细信息（价格、评分、评论数等）                │
│ - 保存为JSON格式                                     │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤6: 数据整合与清洗                                 │
│ - 整合YP商家和亚马逊产品数据                         │
│ - 数据清洗和格式化                                    │
│ - 保存为CSV和JSON格式                                │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤7: 数据备份                                       │
│ - 备份原始数据                                       │
│ - 备份整合后的数据                                   │
│ - 备份配置文件                                       │
└──────────────┬────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│ 步骤8: 上传到飞书                                      │
│ - 使用飞书API上传数据                                 │
│ - 验证上传结果                                       │
│ - 记录上传日志                                       │
└─────────────────────────────────────────────────────────┘
```

### 时间估算

| 步骤 | 预计时间 | 说明 |
|-----|---------|------|
| 步骤1: 环境检查 | 5分钟 | 首次执行 |
| 步骤2: 登录YP平台 | 10分钟 | 首次需要验证码，后续1分钟 |
| 步骤3: 采集YP商家数据 | 15分钟 | 20个商家 |
| 步骤4: 搜索亚马逊产品 | 20分钟 | 40个产品搜索 |
| 步骤5: 爬取产品详情 | 30分钟 | 32个产品详情 |
| 步骤6: 数据整合与清洗 | 10分钟 | 数据处理 |
| 步骤7: 数据备份 | 5分钟 | 备份操作 |
| 步骤8: 上传到飞书 | 10分钟 | API上传 |
| **总计** | **105分钟** | 首次执行 |
| **后续执行** | **95分钟** | 无需重新登录 |

---

## 任务详细步骤

### 任务1: 环境检查

#### 准备工作
- 确保Python、Node.js已安装
- 确保bb-browser已安装
- 确保飞书配置已完成

#### 执行命令
```bash
# 检查Python版本
python --version

# 检查Node.js版本
node --version

# 检查bb-browser版本
bb-browser --version

# 验证bb-browser适配器
bb-browser site list
```

#### 验证方法
- Python版本 >= 3.7
- Node.js版本 >= 18
- bb-browser版本 >= 0.10.0
- bb-browser适配器数量 > 0

#### 成功标准
- ✅ 所有工具版本符合要求
- ✅ bb-browser可以正常工作
- ✅ 目录结构正确

---

### 任务2: 登录YP平台 ⭐（v2.0更新）

#### 准备工作
- 确保已安装bb-browser
- 准备好YP账户信息
- 首次登录需要手动输入验证码

#### 执行命令

**方式1: 使用Python脚本（推荐）**
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python yp_login_skill.py
```

**方式2: 使用批处理脚本**
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
login_with_bb_browser.bat
```

#### 详细步骤

**首次登录（需要验证码）**:
1. 运行登录脚本
2. 脚本自动打开YP登录页面
3. 脚本自动填写用户名和密码
4. ⚠️ 脚本暂停，提示用户手动输入验证码
5. 用户查看验证码图片，输入验证码
6. 脚本自动填写验证码并点击登录按钮
7. 登录成功后，bb-browser保存登录状态（Cookie）

**后续登录（无需验证码）**:
1. 运行登录脚本
2. 脚本检查是否已有登录状态
3. 如果有登录状态，直接跳转到登录后页面
4. 如果登录状态过期，重新执行首次登录流程

#### 验证方法
```bash
# 检查当前页面URL
bb-browser get url

# 预期输出（登录成功）:
# https://www.yeahpromos.com/index/index/index

# 预期输出（未登录）:
# https://www.yeahpromos.com/index/login/login
```

#### 成功标准
- ✅ 当前URL不包含"login"
- ✅ 可以访问受保护页面
- ✅ 登录状态已保存

---

### 任务3: 采集YP商家数据

#### 准备工作
- 确保已登录YP平台
- 准备好商家列表页面URL

#### 执行命令
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python collect_yp_data.py
```

#### 数据字段
```python
{
    "merchant_name": "商家名称",
    "commission": "佣金比例",
    "category": "类别",
    "description": "描述"
}
```

#### 验证方法
```bash
# 查看采集的数据
type output\yp_merchants.json

# 检查数据完整性
python -c "import json; data=json.load(open('output/yp_merchants.json')); print(f'采集商家数: {len(data)}')"
```

#### 成功标准
- ✅ 采集商家数 > 0
- ✅ 所有字段完整
- ✅ JSON格式正确

---

### 任务4: 搜索亚马逊产品

#### 准备工作
- 确保YP商家数据已采集
- 准备好亚马逊搜索URL

#### 执行命令
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python scrape_amazon_products.py
```

#### 数据字段
```python
{
    "merchant_name": "商家名称",
    "product_title": "产品标题",
    "product_url": "产品链接",
    "price": "价格",
    "rating": "评分",
    "review_count": "评论数",
    "image_url": "产品图片"
}
```

#### 验证方法
```bash
# 查看搜索结果
type output\amazon_search_results.json

# 检查数据完整性
python -c "import json; data=json.load(open('output/amazon_search_results.json')); print(f'搜索结果数: {len(data)}')"
```

#### 成功标准
- ✅ 搜索结果数 > 0
- ✅ 所有字段完整
- ✅ JSON格式正确

---

### 任务5: 爬取产品详情

#### 准备工作
- 确保搜索结果已获取
- 准备好产品详情页URL列表

#### 执行命令
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python scrape_amazon_products.py --details
```

#### 数据字段
```python
{
    "product_title": "产品标题",
    "price": "价格",
    "rating": "评分",
    "review_count": "评论数",
    "product_url": "产品链接",
    "image_url": "产品图片",
    "brand": "品牌",
    "product_features": "产品特性"
}
```

#### 验证方法
```bash
# 查看产品详情
type output\amazon_product_details.json

# 检查数据完整性
python -c "import json; data=json.load(open('output/amazon_product_details.json')); print(f'产品详情数: {len(data)}')"
```

#### 成功标准
- ✅ 产品详情数 > 0
- ✅ 所有字段完整
- ✅ JSON格式正确

---

### 任务6: 数据整合与清洗

#### 准备工作
- 确保YP商家数据已采集
- 确保亚马逊产品详情已爬取

#### 执行命令
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python integrate_data.py
```

#### 数据字段
```python
{
    "merchant_name": "商家名称",
    "commission": "佣金",
    "category": "类别",
    "asin": "ASIN",
    "product_name": "商品名称",
    "price": "价格",
    "rating": "评分",
    "review_count": "评论数",
    "image_url": "图片链接",
    "product_url": "商品链接",
    "description": "商品描述",
    "brand": "品牌",
    "features": "商品特性",
    "collection_time": "采集时间"
}
```

#### 验证方法
```bash
# 查看整合后的数据
type output\integrated_data.json

# 检查数据完整性
python -c "import json; data=json.load(open('output/integrated_data.json')); print(f'综合数据数: {len(data)}')"
```

#### 成功标准
- ✅ 综合数据数 > 0
- ✅ 所有字段完整
- ✅ JSON格式正确

---

### 任务7: 数据备份

#### 准备工作
- 确保所有数据已生成

#### 执行命令
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 创建备份目录
mkdir backup\%date:~0,10%

# 备份所有数据
copy output\*.json backup\%date:~0,10%\
copy output\*.csv backup\%date:~0,10%\
```

#### 验证方法
```bash
# 检查备份文件
dir backup\%date:~0,10%\
```

#### 成功标准
- ✅ 所有数据文件已备份
- ✅ 备份文件完整

---

### 任务8: 上传到飞书

#### 准备工作
- 确保整合后的数据已生成
- 确保飞书应用配置已完成

#### 执行命令

**首次上传（创建新表格）**:
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python quick_upload_to_feishu.py
```

**追加数据（使用现有表格）**:
```bash
python quick_upload_to_feishu.py --append
```

#### 飞书表格结构

| 字段名 | 字段类型 | 说明 |
|-------|---------|------|
| 商家名称 | 文本 | YP商家名称 |
| 佣金 | 数字 | 佣金比例 |
| 类别 | 文本 | 商家类别 |
| ASIN | 文本 | 亚马逊产品ASIN |
| 商品名称 | 文本 | 亚马逊商品标题 |
| 价格 | 货币 | 商品价格 |
| 评分 | 数字 | 商品评分 |
| 评论数 | 数字 | 商品评论数 |
| 图片链接 | URL | 商品图片链接 |
| 商品链接 | URL | 商品详情链接 |
| 商品描述 | 文本 | 商品描述 |
| 品牌 | 文本 | 商品品牌 |
| 商品特性 | 文本 | 商品特性 |
| 采集时间 | 日期 | 数据采集时间 |

#### 验证方法
```bash
# 查看上传结果
type upload_result.json

# 预期输出:
# {
#   "success": true,
#   "uploaded_count": 45,
#   "table_id": "tbliPiwHh1GURu8W"
# }
```

#### 成功标准
- ✅ 上传成功
- ✅ 数据条数正确
- ✅ 所有字段完整

---

## 数据上传到飞书

### 首次上传

#### 步骤1: 准备数据
```bash
# 确保整合后的数据文件存在
ls output/integrated_data.json
```

#### 步骤2: 配置飞书应用
```python
# 在quick_upload_to_feishu.py中配置
APP_ID = "cli_a935343a74f89cd4"
APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
```

#### 步骤3: 执行上传
```bash
python quick_upload_to_feishu.py
```

#### 步骤4: 验证上传
- 访问飞书多维表格
- 检查数据是否正确上传
- 验证字段完整性

### 追加数据

#### 步骤1: 准备新数据
```bash
# 确保新的整合数据文件存在
ls output/integrated_data.json
```

#### 步骤2: 执行追加上传
```bash
python quick_upload_to_feishu.py --append
```

#### 步骤3: 验证追加
- 访问飞书多维表格
- 检查新数据是否追加成功
- 验证数据条数是否增加

### 常见问题

#### 问题1: 上传失败
**原因**: 飞书应用配置错误

**解决方案**:
1. 检查APP_ID和APP_SECRET是否正确
2. 检查网络连接是否正常
3. 检查飞书应用权限是否开通

#### 问题2: 数据格式错误
**原因**: 数据字段不匹配

**解决方案**:
1. 检查数据字段是否完整
2. 检查字段类型是否正确
3. 检查数据格式是否符合要求

#### 问题3: 上传速度慢
**原因**: 网络延迟或数据量大

**解决方案**:
1. 检查网络连接
2. 批量上传数据
3. 使用异步上传

---

## 常见问题与解决方案

### 环境配置问题

#### 问题1: bb-browser无法找到
**原因**: bb-browser未安装或未添加到PATH

**解决方案**:
```bash
# 全局安装bb-browser
npm install -g bb-browser

# 验证安装
bb-browser --version

# 如果仍然无法找到，重启命令行
```

#### 问题2: Python版本过低
**原因**: Python版本 < 3.7

**解决方案**:
```bash
# 下载并安装Python 3.7+
# 访问: https://www.python.org/downloads/
```

#### 问题3: 依赖库安装失败
**原因**: pip安装失败

**解决方案**:
```bash
# 升级pip
python -m pip install --upgrade pip

# 使用国内镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple requests beautifulsoup4
```

### 数据采集问题

#### 问题1: 登录失败
**原因**: 验证码输入错误或登录信息错误

**解决方案**:
1. 检查用户名和密码是否正确
2. 检查验证码是否输入正确
3. 使用 `bb-browser get url` 检查登录状态

#### 问题2: 会话过期
**原因**: Cookie有效期已过

**解决方案**:
```bash
# 重新登录
python yp_login_skill.py
```

#### 问题3: 数据采集不完整
**原因**: 网络问题或页面结构变化

**解决方案**:
1. 检查网络连接
2. 检查页面结构是否变化
3. 增加重试机制

### 数据处理问题

#### 问题1: JSON解析失败
**原因**: JSON格式错误

**解决方案**:
```bash
# 验证JSON格式
python -m json.tool output/yp_merchants.json
```

#### 问题2: 数据重复
**原因**: 多次采集导致数据重复

**解决方案**:
```python
# 使用去重逻辑
data = list({item['asin']: item for item in data}.values())
```

#### 问题3: 字段缺失
**原因**: 数据采集不完整

**解决方案**:
```python
# 添加默认值
item.setdefault('brand', 'Unknown')
```

### 飞书上传问题

#### 问题1: 权限不足
**原因**: 飞书应用权限未开通

**解决方案**:
1. 检查飞书应用权限配置
2. 重新开通所需权限
3. 重新生成APP_SECRET

#### 问题2: 表格不存在
**原因**: 表格ID错误或表格已被删除

**解决方案**:
1. 检查表格ID是否正确
2. 使用首次上传创建新表格
3. 更新表格ID配置

#### 问题3: 上传失败
**原因**: 网络问题或API限流

**解决方案**:
1. 检查网络连接
2. 添加重试机制
3. 分批上传数据

---

## 维护与优化

### 日常维护

#### 每日检查
- 检查数据采集是否成功
- 检查登录状态是否有效
- 检查飞书上传是否成功

#### 每周备份
- 备份所有采集的数据
- 备份配置文件
- 备份日志文件

#### 每月更新
- 更新Python依赖库
- 更新bb-browser
- 更新飞书API

### 优化建议

#### 短期优化（1-2周）
1. 优化数据采集速度
2. 添加错误重试机制
3. 完善日志记录

#### 中期优化（1-2月）
1. 实现增量采集
2. 添加数据验证
3. 优化内存使用

#### 长期优化（3-6月）
1. 实现分布式采集
2. 添加数据分析功能
3. 实现实时监控

### 监控指标

#### 采集成功率
- 目标: > 95%
- 监控方法: 每日统计采集成功次数
- 告警阈值: < 90%

#### 数据质量
- 目标: 字段完整率 > 95%
- 监控方法: 每日验证数据完整性
- 告警阈值: < 90%

#### 系统性能
- 目标: 响应时间 < 5秒
- 监控方法: 监控采集时间
- 告警阈值: > 10秒

---

## 附录

### 文件清单

#### 核心脚本
- `yp_login_skill.py` - YP登录Skill（新增）
- `collect_yp_data.py` - YP数据采集脚本
- `scrape_amazon_products.py` - 亚马逊产品爬取脚本
- `quick_upload_to_feishu.py` - 飞书上传脚本
- `integrate_data.py` - 数据整合脚本

#### 数据文件
- `output/yp_merchants.json` - YP商家数据
- `output/amazon_search_results.json` - 亚马逊搜索结果
- `output/amazon_product_details.json` - 亚马逊产品详情
- `output/integrated_data.json` - 整合后的数据

#### 文档文件
- `COMPLETE_SOP_V2.md` - 完整SOP v2.0（本文档）
- `BROWSER_SKILL_COMPARISON.md` - 浏览器方案对比
- `BB_BROWSER_TEST_GUIDE.md` - bb-browser测试指南
- `SESSION_PERSISTENCE_TEST_REPORT.md` - 会话保持测试报告

### 数据字段详解

#### YP商家数据
| 字段名 | 类型 | 说明 |
|-------|------|------|
| merchant_name | String | 商家名称 |
| commission | String | 佣金比例 |
| category | String | 商家类别 |
| description | String | 商家描述 |

#### 亚马逊产品数据
| 字段名 | 类型 | 说明 |
|-------|------|------|
| asin | String | 产品ASIN |
| product_title | String | 产品标题 |
| price | String | 产品价格 |
| rating | Float | 产品评分 |
| review_count | Integer | 评论数 |
| image_url | String | 产品图片URL |
| product_url | String | 产品详情URL |
| brand | String | 产品品牌 |
| features | String | 产品特性 |

#### 综合数据
| 字段名 | 类型 | 说明 |
|-------|------|------|
| merchant_name | String | 商家名称 |
| commission | String | 佣金比例 |
| category | String | 商家类别 |
| asin | String | 产品ASIN |
| product_name | String | 产品标题 |
| price | String | 产品价格 |
| rating | Float | 产品评分 |
| review_count | Integer | 评论数 |
| image_url | String | 产品图片URL |
| product_url | String | 产品详情URL |
| description | String | 产品描述 |
| brand | String | 产品品牌 |
| features | String | 产品特性 |
| collection_time | DateTime | 采集时间 |

### 快速参考

#### 常用命令
```bash
# 登录YP平台
python yp_login_skill.py

# 采集YP商家数据
python collect_yp_data.py

# 搜索亚马逊产品
python scrape_amazon_products.py

# 上传到飞书
python quick_upload_to_feishu.py

# 检查登录状态
bb-browser get url
```

#### 飞书表格信息
- **App ID**: `cli_a935343a74f89cd4`
- **App Secret**: `EqnC0zcv1CF9A2h849z8geK8RmfRRfiE`
- **表格链接**: https://example.feishu.cn/base/Tdc3bct8ras9uzsKq5ycSja0nld
- **Table ID**: `tbliPiwHh1GURu8W`

#### 关键配置
```python
# YP登录配置
YP_USERNAME = "Tong jun"
YP_PASSWORD = "Tj840618"
YP_LOGIN_URL = "https://www.yeahpromos.com/index/login/login"

# 亚马逊搜索配置
AMAZON_BASE_URL = "https://www.amazon.com/s?k={query}"
AMAZON_PRODUCT_URL = "https://www.amazon.com/dp/{asin}"

# 飞书API配置
FEISHU_API_BASE = "https://open.feishu.cn/open-apis/bitable/v1/apps/{app_id}/tables/{table_id}/records"
```

### 技术支持

#### 相关资源
- bb-browser文档: https://github.com/epiral/bb-browser
- Python文档: https://docs.python.org/3/
- 飞书开放平台: https://open.feishu.cn/

#### 常见问题
1. **如何检查登录状态？**
   ```bash
   bb-browser get url
   ```

2. **如何重新登录？**
   ```bash
   python yp_login_skill.py
   ```

3. **如何查看采集的数据？**
   ```bash
   type output\integrated_data.json
   ```

4. **如何备份数据？**
   ```bash
   copy output\*.json backup\
   ```

---

## 更新日志

### v2.0 (2026-03-22)
- ✅ 使用bb-browser进行登录（替代QQBrowserSkill）
- ✅ 支持会话保持，避免每次重新登录
- ✅ 减少验证码输入次数
- ✅ 提高自动化程度
- ✅ 添加yp_login_skill.py登录脚本
- ✅ 更新环境准备步骤
- ✅ 更新登录流程说明

### v1.0 (2026-03-22)
- ✅ 初始版本
- ✅ 完整的项目SOP
- ✅ 所有8个任务详细步骤
- ✅ 飞书上传指南
- ✅ 常见问题与解决方案

---

**文档维护**: WorkBuddy Assistant
**最后更新**: 2026-03-22
**下次审核**: 2026-04-22
