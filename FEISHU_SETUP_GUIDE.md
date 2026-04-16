# 飞书配置和上传指南

## 📋 前置准备

### 1. 创建飞书应用

#### 步骤1: 登录飞书开放平台
访问：https://open.feishu.cn/

#### 步骤2: 创建应用
1. 点击"创建应用"
2. 选择"企业自建应用"
3. 填写应用信息：
   - 应用名称：YP数据上传（可自定义）
   - 应用描述：上传YP商家和亚马逊商品数据

#### 步骤3: 获取凭证
1. 进入应用详情页
2. 点击左侧"凭证与基础信息"
3. 记录以下信息：
   - **App ID** (cli_xxxxxxxxx)
   - **App Secret** (xxxxxxxxxxxx)

### 2. 配置应用权限

#### 必需权限
在"权限管理"中开通以下权限：

**多维表格权限**：
- `bitable:app` - 读取多维表格
- `bitable:app:readonly` - 只读多维表格
- `drive:drive` - 获取文件

**文件权限**：
- `drive:drive:readonly` - 只读云空间文件

#### 步骤：
1. 点击"权限管理" -> "权限配置"
2. 搜索并勾选上述权限
3. 点击"批量申请权限"
4. 在飞书工作台中批准权限请求

---

## ⚙️ 配置上传脚本

### 方式1：直接修改脚本（快速测试）

编辑 `upload_to_feishu.py` 文件，找到以下部分：

```python
# 配置信息（请替换为真实的飞书凭证）
APP_ID = "cli_xxxxxxxxx"  # 请替换为您的飞书应用ID
APP_SECRET = "xxxxxxxxxxxx"  # 请替换为您的飞书应用密钥
```

替换为您的真实凭证：
```python
APP_ID = "cli_1234567890abcdef"  # 您的App ID
APP_SECRET = "abcdefghijklmnopqrstuvwxyz123456"  # 您的App Secret
```

### 方式2：使用配置文件（推荐）

#### 步骤1：创建本地配置文件
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\config
copy feishu_config.yaml feishu_config_local.yaml
```

#### 步骤2：编辑本地配置文件
打开 `feishu_config_local.yaml`，填入您的凭证：

```yaml
# 飞书应用凭证
feishu:
  app_id: "cli_1234567890abcdef"  # 替换为您的App ID
  app_secret: "abcdefghijklmnopqrstuvwxyz123456"  # 替换为您的App Secret

  # 文档配置
  document:
    create_new: true  # 是否创建新文档
    folder_token: ""  # 文件夹 Token (可选)
    title: "YP平台商家商品数据"  # 文档标题
```

---

## 🚀 运行上传脚本

### 基本用法

```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python upload_to_feishu.py
```

### 脚本功能

1. **自动选择数据文件**
   - 优先使用：`output/comprehensive_yp_amazon_data_v2.json`
   - 备选使用：`output/comprehensive_yp_amazon_data_v2.csv`

2. **创建新表格**
   - 首次运行会自动创建新的多维表格
   - 表格名称：`YP商家和亚马逊商品数据`

3. **自动添加列**
   - 根据数据自动创建表格列
   - 包含：商家名称、佣金、ASIN、商品名称、价格、评分等

4. **批量上传**
   - 支持批量上传多条记录
   - 每批最多500条

### 预期输出

```
============================================================
  飞书数据上传工具
============================================================

[信息] 使用JSON文件: comprehensive_yp_amazon_data_v2.json
[信息] 读取到 45 条记录

[开始] 上传45条数据到飞书...
[步骤1] 创建多维表格...
[成功] 表格已创建，Token: bascxxxxx
[步骤2] 创建数据表...
[成功] 数据表已创建，ID: tblxxxxx
[步骤3] 添加表格列...
  [OK] 已添加列: 商家名称
  [OK] 已添加列: 佣金
  [OK] 已添加列: ASIN
  [OK] 已添加列: 商品名称
  [OK] 已添加列: 价格
  [OK] 已添加列: 评分
  [OK] 已添加列: 评论数
  [OK] 已添加列: 图片链接
  [OK] 已添加列: 商品链接
  [OK] 已添加列: 商品描述
  [OK] 已添加列: 品牌
[步骤4] 上传数据...
  [进度] 已上传 45/45 条记录

============================================================
  上传完成！
============================================================

[链接] https://example.feishu.cn/base/bascxxxxx

[提示] 您可以点击上面的链接在飞书中查看数据
```

---

## 📊 数据字段说明

上传到飞书的数据包含以下字段：

| 字段名称 | 数据来源 | 类型 | 说明 |
|---------|---------|------|------|
| 商家名称 | YP商家数据 | 文本 | 商家名称 |
| 佣金 | YP商家数据 | 文本 | 佣金率或金额 |
| 类别 | YP商家数据 | 文本 | 商家类别 |
| ASIN | 亚马逊产品 | 文本 | 亚马逊产品ID |
| 商品名称 | 亚马逊产品 | 文本 | 产品标题 |
| 价格 | 亚马逊产品 | 数字 | 产品价格 |
| 评分 | 亚马逊产品 | 数字 | 用户评分 |
| 评论数 | 亚马逊产品 | 数字 | 评论数量 |
| 图片链接 | 亚马逊产品 | 文本 | 产品图片URL |
| 商品链接 | 亚马逊产品 | URL | 产品详情链接 |
| 商品描述 | 亚马逊产品 | 文本 | 产品描述 |
| 品牌 | 亚马逊产品 | 文本 | 品牌名称 |
| 商品特性 | 亚马逊产品 | 文本 | 产品特性列表 |
| 采集时间 | 自动生成 | 日期时间 | 数据采集时间 |

---

## ⚠️ 常见问题

### 1. 权限不足

**错误信息**：`权限不足 (permission_denied)`

**解决方案**：
1. 检查应用是否开通了所有必需权限
2. 确保已在飞书工作台中批准权限请求
3. 等待几分钟让权限生效

### 2. App ID或App Secret错误

**错误信息**：`应用凭证无效`

**解决方案**：
1. 确认从飞书开放平台复制的凭证是否完整
2. 检查是否有多余的空格或换行符
3. 重新生成App Secret（在凭证页面）

### 3. 网络连接问题

**错误信息**：`连接超时` 或 `网络错误`

**解决方案**：
1. 检查网络连接是否正常
2. 如果使用代理，请配置代理设置
3. 稍后重试

### 4. 数据格式错误

**错误信息**：`数据格式不正确`

**解决方案**：
1. 确保数据文件存在且格式正确
2. 检查JSON文件是否为有效的JSON格式
3. 检查CSV文件编码是否为UTF-8

---

## 🔄 使用现有表格

如果您想将数据追加到已存在的飞书表格：

### 步骤1：获取表格Token

1. 打开飞书多维表格
2. 从URL中获取app_token，例如：
   - URL：`https://example.feishu.cn/base/bascxxxxx`
   - app_token：`bascxxxxx`

### 步骤2：获取表格ID

1. 打开表格后，点击右上角"..." -> "查看表格信息"
2. 记录表格ID（table_id）

### 步骤3：修改脚本

编辑 `upload_to_feishu.py`，取消注释并填入：

```python
# 使用现有表格
APP_TOKEN = "bascxxxxxxxxxxxxx"  # 您的表格app_token
TABLE_ID = "tblxxxxxxxxxxxxx"  # 您的表格table_id

# 注释掉创建新表格的逻辑
# return self.create_new_bitable(data, table_name)
# 改用：
# return self.append_to_existing_bitable(APP_TOKEN, TABLE_ID, data)
```

---

## 📚 参考文档

- [飞书开放平台](https://open.feishu.cn/)
- [多维表格API文档](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table/list)
- [Python SDK文档](https://github.com/larksuite/oapi-sdk-python)

---

## 💡 使用技巧

### 1. 定期更新数据

可以设置定时任务定期运行上传脚本：

```bash
# Windows 任务计划程序
# 添加任务：每天早上8点运行 python upload_to_feishu.py
```

### 2. 数据去重

如果需要避免重复上传，可以在脚本中添加去重逻辑：

```python
# 检查ASIN是否已存在
existing_records = get_existing_records(app_token, table_id)
new_data = [item for item in data if item['amazon_asin'] not in existing_records]
```

### 3. 数据同步

可以创建双向同步，将飞书中的修改同步到本地：

```python
# 从飞书读取数据
records = fetch_records_from_feishu(app_token, table_id)

# 保存到本地
save_to_local(records, 'output/updated_data.json')
```

---

## 📞 获取帮助

如果遇到问题：

1. 查看飞书开放平台文档
2. 检查错误日志中的详细信息
3. 确认网络连接和权限配置
4. 联系飞书技术支持

---

**祝您使用愉快！** 🎉
