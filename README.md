# YP to Feishu - 使用指南

## 📖 项目简介

本项目从 YeahPromos (YP) 平台获取所有商家信息，通过追踪链接爬取亚马逊商品数据，并自动同步到飞书文档。

## ✨ 主要功能

1. ✅ 从 YP Monetization API 获取所有商家列表
2. ✅ 自动解析追踪链接，提取亚马逊商品 URL
3. ✅ 批量爬取亚马逊商品信息（名称、价格、ASIN、评分、评论数等）
4. ✅ 数据清洗、去重、排序
5. ✅ 自动创建飞书表格并写入数据

## 🚀 快速开始

### 1. 安装依赖

```bash
cd yp_to_feishu
pip install -r requirements.txt
```

### 2. 配置飞书应用

#### 步骤 1：创建飞书应用

1. 登录 [飞书开放平台](https://open.feishu.cn)
2. 创建应用（应用类型选择"自建应用"）
3. 获取 App ID 和 App Secret

#### 步骤 2：配置权限

为应用添加以下权限：
- `drive:drive:readonly` - 读取云文档权限
- `drive:drive:write` - 写入云文档权限
- `sheets:spreadsheet:readonly` - 读取电子表格
- `sheets:spreadsheet:write` - 写入电子表格

#### 步骤 3：配置文件

复制 `config/feishu_config.yaml` 为 `config/feishu_config_local.yaml`，填入你的凭证：

```yaml
feishu:
  app_id: "cli_xxxxxxxxx"  # 替换为你的 App ID
  app_secret: "xxxxxxxxxxxx"  # 替换为你的 App Secret

  document:
    create_new: true
    folder_token: ""  # 可选：指定文件夹
    title: "YP平台商家商品数据"
```

### 3. 运行程序

```bash
python src/main.py
```

## 📊 数据流程

```
YP API → 解析链接 → 亚马逊爬虫 → 数据处理 → 飞书文档
```

### 阶段说明

#### 阶段 1：采集商家数据
- 从 YP Monetization API 获取商家列表
- 数据包括：商家名称、佣金率、追踪链接、描述
- 自动保存到 `output/merchants_raw_YYYYMMDD_HHMMSS.json`

#### 阶段 2：解析追踪链接
- 解析 YP 追踪链接，提取亚马逊商品 URL
- 提取 ASIN
- 自动保存到 `output/links_parsed_YYYYMMDD_HHMMSS.json`

#### 阶段 3：爬取亚马逊商品
- 使用 Playwright 批量爬取商品数据
- 数据包括：名称、价格、评分、评论数、描述、图片等
- 自动保存到 `output/products_raw_YYYYMMDD_HHMMSS.json`

#### 阶段 4：处理和同步
- 数据清洗、去重、排序
- 创建飞书表格
- 批量写入数据

## 📁 项目结构

```
yp_to_feishu/
├── config/
│   ├── config.yaml              # 主配置文件
│   ├── feishu_config.yaml        # 飞书配置模板
│   └── feishu_config_local.yaml # 飞书配置（需自行创建）
├── src/
│   ├── yp_api/
│   │   ├── merchant_collector.py # YP 商家采集器
│   │   └── link_parser.py       # 链接解析器
│   ├── amazon/
│   │   └── crawler.py           # 亚马逊爬虫
│   ├── feishu/
│   │   └── client.py            # 飞书客户端
│   ├── data/
│   │   └── processor.py         # 数据处理器
│   └── main.py                   # 主程序
├── output/                       # 输出目录
├── logs/                         # 日志目录
├── requirements.txt
├── ARCHITECTURE.md              # 架构设计文档
└── README.md                    # 本文档
```

## ⚙️ 配置说明

### 主配置文件 (config/config.yaml)

```yaml
# YP 平台配置
yp:
  api_base: "https://yeahpromos.com"
  merchant_api: "/index/getadvert/getadvert"
  rate_limit: 10  # 每分钟请求限制
  timeout: 30  # 请求超时时间(秒)

# 亚马逊爬虫配置
amazon:
  headless: false  # 是否使用无头浏览器（建议先用 false 测试）
  timeout: 60000  # 页面加载超时(毫秒)
  request_delay: 2  # 请求间隔(秒)
  max_concurrent: 5  # 最大并发数
  max_products_per_merchant: 100
```

### 飞书配置文件 (config/feishu_config_local.yaml)

```yaml
feishu:
  app_id: "cli_xxxxxxxxx"  # 必填：飞书应用 ID
  app_secret: "xxxxxxxxxxxx"  # 必填：飞书应用密钥

  document:
    create_new: true
    folder_token: ""  # 可选：文件夹 token
    title: "YP平台商家商品数据"  # 文档标题
```

## 📝 飞书表格结构

数据将写入以下列：

| 列名 | 说明 | 类型 |
|-----|------|------|
| 商家名称 | YP 平台商家名称 | 文本 |
| 商品ASIN | 亚马逊商品 ID | 文本 |
| 商品名称 | 亚马逊商品标题 | 文本 |
| 价格 | 商品价格 | 数字 |
| 货币 | 货币类型 | 文本 |
| 佣金率 | YP 佣金率 | 文本 |
| 评分 | 商品评分 | 数字 |
| 评论数 | 评论数量 | 数字 |
| 品牌 | 商品品牌 | 文本 |
| 类别 | 商品类目 | 文本 |
| 商品描述 | 商品描述 | 文本 |
| 追踪链接 | YP 追踪链接 | 链接 |
| 采集时间 | 数据采集时间 | 日期时间 |

## 🔧 高级配置

### 调整爬取速度

在 `config/config.yaml` 中修改：

```yaml
amazon:
  request_delay: 3  # 增加延迟（秒）
  max_concurrent: 3  # 减少并发数
```

### 使用无头模式

```yaml
amazon:
  headless: true  # 后台运行，不显示浏览器
```

### 数据过滤

在 `src/main.py` 中的 `process_and_sync_to_feishu` 方法中添加：

```python
# 过滤价格
dataset = self.data_processor.filter_products(
    dataset,
    min_price=10,
    max_price=1000
)

# 过滤评分
dataset = self.data_processor.filter_products(
    dataset,
    min_rating=4.0
)
```

## 🐛 常见问题

### 1. YP API 返回空数据

- 检查 API 端点是否正确
- 查看日志文件 `logs/app.log` 了解详细错误
- 可能需要先登录 YP 平台获取认证 cookie

### 2. 亚马逊爬取失败

- 确保网络可以访问亚马逊
- 尝试关闭 headless 模式查看浏览器行为
- 增加 request_delay 和 timeout
- 检查是否有验证码弹出

### 3. 飞书写入失败

- 确认飞书应用已添加必要权限
- 检查 App ID 和 App Secret 是否正确
- 查看 API 限流情况

### 4. 安装 Playwright 失败

```bash
# 安装 Playwright 浏览器
python -m playwright install chromium
```

## 📈 性能优化

### 1. 并发控制

根据网络和机器性能调整：

```yaml
amazon:
  max_concurrent: 5  # 建议范围 3-10
```

### 2. 缓存机制

启用 Redis 缓存避免重复爬取（需要自行实现）

### 3. 增量更新

只更新有变化的商品，减少 API 调用

## 🔒 安全建议

1. **不要提交凭证到代码仓库**
   - `config/feishu_config_local.yaml` 应添加到 `.gitignore`

2. **使用环境变量**
   ```python
   app_id = os.getenv("FEISHU_APP_ID")
   ```

3. **定期更新密钥**
   - 飞书应用密钥应定期轮换

## 📞 支持

如有问题，请查看：
- 日志文件：`logs/app.log`
- 架构文档：`ARCHITECTURE.md`
- 飞书开放平台文档：https://open.feishu.cn/document/

## 📄 许可证

本项目仅供学习研究使用。请遵守 YP 平台和亚马逊的使用条款。
