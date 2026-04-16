# YP to Feishu - 快速开始指南

## 🎯 5 分钟快速部署

### 前置要求

- Python 3.9 或更高版本
- 飞书账号
- 可以访问 YeahPromos 和亚马逊的网络环境

---

## 第 1 步：安装依赖 (1 分钟)

```bash
# 进入项目目录
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 安装依赖包
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

---

## 第 2 步：配置飞书应用 (3 分钟)

### 2.1 创建飞书应用

1. 访问 https://open.feishu.cn
2. 登录后点击"创建应用"
3. 选择"自建应用"，填写应用名称（如"YP数据同步"）
4. 创建完成后，记录下 **App ID** 和 **App Secret**

### 2.2 配置应用权限

在应用管理页面，找到"权限管理"，添加以下权限：

- `drive:drive:readonly`
- `drive:drive:write`
- `sheets:spreadsheet:readonly`
- `sheets:spreadsheet:write`

### 2.3 发布应用

1. 找到"版本管理与发布"
2. 点击"创建版本"
3. 点击"申请发布"
4. 选择"企业内部使用"，完成发布

---

## 第 3 步：配置项目 (1 分钟)

1. 复制配置文件模板：
   ```bash
   copy config\feishu_config.yaml config\feishu_config_local.yaml
   ```

2. 编辑 `config\feishu_config_local.yaml`，填入你的飞书凭证：

   ```yaml
   feishu:
     app_id: "cli_xxxxxxxxx"  # 替换为你的 App ID
     app_secret: "xxxxxxxxxxxx"  # 替换为你的 App Secret

     document:
       create_new: true
       folder_token: ""
       title: "YP平台商家商品数据"
   ```

---

## 第 4 步：运行程序 (1 分钟)

### 方式 A：使用批处理文件（推荐）

双击运行 `run.bat` 即可。

### 方式 B：命令行运行

```bash
python src\main.py
```

---

## 📊 预期输出

程序会依次执行 4 个阶段：

```
============================================================
Phase 1: Collecting merchants from YP platform...
============================================================
✅ Phase 1 completed: 150 merchants collected

============================================================
Phase 2: Parsing tracking links...
============================================================
✅ Phase 2 completed: 142 valid links

============================================================
Phase 3: Scraping Amazon products...
============================================================
✅ Phase 3 completed: 142 products scraped

============================================================
Phase 4: Processing data and syncing to Feishu...
============================================================
📊 Dataset statistics:
   total_products: 142
   total_merchants: 142
   avg_price: 89.99
   avg_rating: 4.3
📤 Syncing to Feishu...
✅ Phase 4 completed: 142 products synced to Feishu
```

程序完成后，数据将自动写入到你的飞书文档中。

---

## 📂 生成的文件

### 输出文件（output/ 目录）

- `merchants_raw_YYYYMMDD_HHMMSS.json` - YP 商家原始数据
- `links_parsed_YYYYMMDD_HHMMSS.json` - 解析后的链接数据
- `products_raw_YYYYMMDD_HHMMSS.json` - 亚马逊商品原始数据
- `dataset_final_YYYYMMDD_HHMMSS.json` - 最终处理后的数据集

### 日志文件（logs/ 目录）

- `app.log` - 运行日志

---

## 🔍 验证数据

1. 打开飞书应用
2. 查找标题为"YP平台商家商品数据"的表格
3. 确认数据是否正确写入

表格应包含以下列：
- 商家名称
- 商品ASIN
- 商品名称
- 价格
- 佣金率
- 评分
- 评论数
- 商品描述
- 追踪链接
- 采集时间

---

## ⚙️ 常见配置调整

### 1. 调整爬取速度

编辑 `config/config.yaml`：

```yaml
amazon:
  request_delay: 3  # 增加延迟，降低被封风险
  max_concurrent: 3  # 减少并发数
```

### 2. 使用无头模式（后台运行）

```yaml
amazon:
  headless: true  # 不显示浏览器窗口
```

### 3. 数据过滤

编辑 `src/main.py`，在 `process_and_sync_to_feishu` 方法中添加：

```python
# 只保留评分大于 4.0 的商品
dataset = self.data_processor.filter_products(
    dataset,
    min_rating=4.0
)
```

---

## 🐛 故障排查

### 问题 1：找不到 Python

**错误信息**：`未找到 Python，请先安装 Python 3.9+`

**解决方案**：
1. 从 https://www.python.org 下载安装 Python 3.9+
2. 安装时勾选"Add Python to PATH"
3. 重启命令行窗口

### 问题 2：飞书 API 调用失败

**错误信息**：`Failed to get token` 或 `Failed to create spreadsheet`

**解决方案**：
1. 确认 App ID 和 App Secret 正确
2. 确认应用已发布
3. 确认已添加所需权限
4. 检查网络连接

### 问题 3：亚马逊爬取失败

**错误信息**：`Failed to scrape product` 或页面加载超时

**解决方案**：
1. 增加超时时间：`config/config.yaml` 中修改 `timeout`
2. 增加 `request_delay` 降低请求频率
3. 暂时关闭 headless 模式查看浏览器行为
4. 检查是否有验证码或反爬限制

### 问题 4：YP API 返回空数据

**错误信息**：`No merchants found`

**解决方案**：
1. 确认网络可以访问 YP 平台
2. 检查 API 端点是否正确
3. 可能需要登录 YP 平台获取认证（需要在代码中添加 cookie 处理）

---

## 📞 获取帮助

1. 查看完整文档：`README.md`
2. 查看架构设计：`ARCHITECTURE.md`
3. 查看日志文件：`logs/app.log`
4. 飞书开放平台文档：https://open.feishu.cn/document/

---

## ⚠️ 重要提示

1. **遵守平台规则**
   - 遵守 YP 平台和亚马逊的使用条款
   - 不要过度频繁请求，避免被封禁

2. **数据安全**
   - 不要将 `feishu_config_local.yaml` 提交到版本控制
   - 定期更换飞书应用密钥

3. **合规使用**
   - 本工具仅供学习研究使用
   - 商业使用前请确保符合相关法律法规

---

## 🚀 下一步

成功运行后，你可以：

1. **定期更新数据**
   - 设置定时任务自动运行脚本
   - 实现增量更新机制

2. **数据分析**
   - 使用飞书表格的数据分析功能
   - 导出数据进行进一步分析

3. **自定义处理**
   - 修改 `src/data/processor.py` 添加自定义数据处理逻辑
   - 修改列定义和数据字段

4. **集成到现有系统**
   - 将数据同步到你的 CRM 或数据库
   - 实现自动化工作流

---

**祝你使用愉快！** 🎉
