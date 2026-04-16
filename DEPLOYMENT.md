# YP to Feishu - 部署指南

## 📋 部署清单

### 开发环境
- ✅ Python 3.9+
- ✅ pip 包管理器
- ✅ Git（可选）
- ✅ IDE（VS Code / PyCharm）

### 服务账号
- ✅ 飞书开放平台账号
- ✅ YP 平台账号（如需要）

### 网络环境
- ✅ 可以访问 yeahpromos.com
- ✅ 可以访问 amazon.com
- ✅ 可以访问 open.feishu.cn

---

## 🔧 详细部署步骤

### 步骤 1：环境准备

#### 1.1 安装 Python

Windows:
```bash
# 下载 Python 3.9 或更高版本
# 访问: https://www.python.org/downloads/
# 安装时勾选 "Add Python to PATH"
```

macOS:
```bash
# 使用 Homebrew 安装
brew install python@3.9
```

Linux:
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.9 python3.9-venv
```

#### 1.2 创建虚拟环境（推荐）

```bash
# Windows
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

#### 1.3 安装依赖

```bash
pip install -r requirements.txt

# 安装 Playwright 浏览器
python -m playwright install chromium
```

---

### 步骤 2：配置飞书应用

#### 2.1 创建应用

1. 登录 https://open.feishu.cn
2. 进入"创建应用"页面
3. 选择"自建应用"
4. 填写应用信息：
   - 应用名称：YP数据同步工具
   - 应用描述：从 YP 平台采集商品数据同步到飞书
   - 应用图标：可选

#### 2.2 配置权限

在"权限管理"中添加以下权限：

**云文档权限**:
- `drive:drive:readonly`
- `drive:drive:write`

**电子表格权限**:
- `sheets:spreadsheet:readonly`
- `sheets:spreadsheet:write`
- `sheets:spreadsheet:comment`

#### 2.3 发布应用

1. 进入"版本管理与发布"
2. 点击"创建版本"，填写版本号（如 1.0.0）
3. 点击"申请发布"
4. 选择发布范围：
   - 企业内部使用：无需审核
   - 企业外发布：需要审核（本工具不需要）
5. 等待审核通过（通常即时）

#### 2.4 获取凭证

在"凭证与基础信息"页面获取：
- **App ID**: 格式如 `cli_xxxxxxxxx`
- **App Secret**: 格式如 `xxxxxxxxxxxx`

---

### 步骤 3：配置项目

#### 3.1 创建配置文件

```bash
# 复制配置模板
copy config\feishu_config.yaml config\feishu_config_local.yaml
```

#### 3.2 编辑配置文件

使用文本编辑器打开 `config/feishu_config_local.yaml`，填入你的凭证：

```yaml
feishu:
  app_id: "cli_1234567890abcdef"  # 替换为你的 App ID
  app_secret: "1234567890abcdef1234567890abcdef"  # 替换为你的 App Secret

  document:
    create_new: true
    folder_token: ""  # 可选：指定文件夹 Token
    title: "YP平台商家商品数据"
```

#### 3.3 测试配置

运行测试脚本验证配置：

```bash
python -c "from src.feishu.client import FeishuClient; print('✅ 飞书客户端导入成功')"
```

---

### 步骤 4：测试运行

#### 4.1 小规模测试

修改 `config/config.yaml`，限制采集数量：

```yaml
amazon:
  max_products_per_merchant: 5  # 仅测试 5 个商品
```

#### 4.2 运行程序

```bash
# Windows
run.bat

# 或使用命令行
python src/main.py
```

#### 4.3 验证结果

1. 检查 `output/` 目录是否生成数据文件
2. 检查飞书文档是否创建成功
3. 检查 `logs/app.log` 查看详细日志

---

### 步骤 5：生产部署

#### 5.1 调整配置

修改 `config/config.yaml` 为生产配置：

```yaml
amazon:
  headless: true  # 生产环境使用无头模式
  timeout: 120000  # 增加超时时间
  request_delay: 3  # 增加延迟避免封禁
  max_concurrent: 5  # 控制并发数
  max_products_per_merchant: 100  # 取消限制
```

#### 5.2 设置日志级别

```yaml
logging:
  level: "INFO"  # 生产环境使用 INFO 或 WARNING
```

#### 5.3 定期运行

**Windows 任务计划程序**:

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器（每天/每周）
4. 操作：启动程序
   - 程序：`python.exe` 的完整路径
   - 参数：`src\main.py`
   - 起始于：项目根目录

**Linux Cron**:

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天凌晨 2 点运行）
0 2 * * * cd /path/to/yp_to_feishu && /path/to/venv/bin/python src/main.py >> logs/cron.log 2>&1
```

---

## 🔒 安全配置

### 1. 环境变量

将敏感信息存储为环境变量：

```python
import os

app_id = os.getenv("FEISHU_APP_ID")
app_secret = os.getenv("FEISHU_APP_SECRET")
```

Windows:
```powershell
setx FEISHU_APP_ID "cli_xxxxxxxxx"
setx FEISHU_APP_SECRET "xxxxxxxxxxxx"
```

Linux/macOS:
```bash
export FEISHU_APP_ID="cli_xxxxxxxxx"
export FEISHU_APP_SECRET="xxxxxxxxxxxx"

# 添加到 ~/.bashrc 或 ~/.zshrc
```

### 2. 配置文件加密

使用 Python 的 `cryptography` 库加密配置：

```python
from cryptography.fernet import Fernet

# 加密
key = Fernet.generate_key()
cipher_suite = Fernet(key)
encrypted = cipher_suite.encrypt(b"your_secret")

# 解密
decrypted = cipher_suite.decrypt(encrypted)
```

### 3. 访问控制

- 确保飞书文档仅授权人员可访问
- 定期更换应用密钥
- 使用最小权限原则

---

## 📊 监控和日志

### 1. 日志配置

`config/config.yaml`:

```yaml
logging:
  level: "INFO"
  file: "logs/app.log"
  rotation: "100 MB"  # 日志轮转
  retention: "30 days"  # 保留 30 天
```

### 2. 错误通知

可以集成错误通知服务（如 Sentry）：

```python
import sentry_sdk

sentry_sdk.init(
    dsn="your_sentry_dsn",
    traces_sample_rate=1.0
)
```

### 3. 监控指标

建议监控：
- 采集成功率
- API 调用次数
- 数据完整性
- 运行时间

---

## 🔄 更新和维护

### 1. 依赖更新

```bash
# 查看过期包
pip list --outdated

# 更新所有包
pip install --upgrade -r requirements.txt

# 更新 Playwright 浏览器
python -m playwright install --with-deps chromium
```

### 2. 代码更新

```bash
# 拉取最新代码
git pull origin main

# 重新安装依赖
pip install -r requirements.txt

# 测试运行
python src/main.py
```

### 3. 数据备份

定期备份数据文件：

```bash
# 创建备份脚本
xcopy output\*.json backup\%date:~0,10%\ /Y /I
```

---

## 🐛 故障恢复

### 常见问题及解决方案

| 问题 | 原因 | 解决方案 |
|-----|------|---------|
| Python 找不到 | 未安装或未添加到 PATH | 重新安装并勾选"Add to PATH" |
| 依赖安装失败 | 网络问题或版本冲突 | 使用国内镜像源 |
| 飞书 API 失败 | 凭证错误或权限不足 | 检查 App ID/Secret 和权限配置 |
| 爬虫失败 | 反爬限制 | 增加延迟、使用代理、人工验证 |
| 数据写入失败 | 表格不存在或权限不足 | 检查飞书文档权限 |

### 回滚方案

如果更新后出现问题：

```bash
# 回滚到上一个版本
git log --oneline
git checkout <commit_hash>
```

---

## 📞 支持和帮助

### 官方文档
- 飞书开放平台: https://open.feishu.cn/document/
- Playwright 文档: https://playwright.dev/python/
- Python 文档: https://docs.python.org/3/

### 社区支持
- Stack Overflow: https://stackoverflow.com/questions/tagged/feishu
- GitHub Issues: 如果是开源项目，可以提交 Issue

---

## ✅ 部署检查清单

在完成部署前，请确认以下项目：

- [ ] Python 3.9+ 已安装并可运行
- [ ] 所有依赖包已安装
- [ ] Playwright 浏览器已安装
- [ ] 飞书应用已创建并发布
- [ ] 飞书应用权限已配置
- [ ] `feishu_config_local.yaml` 已创建并配置
- [ ] 测试运行成功
- [ ] 日志系统正常工作
- [ ] 定时任务已配置（如需要）
- [ ] 监控和告警已设置（如需要）
- [ ] 备份策略已制定
- [ ] 安全配置已完成
- [ ] 相关人员已培训

---

**部署完成后，请保留此文档以备后续维护使用。**
