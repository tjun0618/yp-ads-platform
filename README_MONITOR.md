# YP Affiliate 平台运维监控系统

## 概述

本监控系统用于监控 YP Affiliate 平台的运行状态，包括数据库健康、服务可用性、数据新鲜度等，并提供每日运行报告。

## 文件列表

### 核心脚本
1. **monitor.py** - 系统监控脚本
   - 每5分钟运行一次
   - 监控：MySQL、Flask服务、磁盘空间、采集进程、数据新鲜度
   - 状态变化时发送飞书报警

2. **daily_report.py** - 日报生成脚本
   - 每天8点运行（建议）
   - 生成HTML格式日报
   - 内容包括：数据概览、今日待办、投放状态、系统健康

3. **一键启动监控.bat** - 监控启动脚本
   - 启动监控循环（每5分钟检查一次）
   - 显示实时监控日志

4. **一键生成日报.bat** - 日报生成脚本
   - 生成当日日报
   - 自动在浏览器中打开HTML报告

5. **一键启动Flask服务.bat** - Flask服务启动脚本
   - 启动 ads_manager.py 服务
   - 提供健康检查端点

### 支持文件
- `logs/` - 日志和报告目录
- `logs/monitor.log` - 监控日志
- `logs/monitor_state.json` - 监控状态历史
- `logs/daily_report_YYYY-MM-DD.html` - 每日报告

## 快速开始

### 1. 启动监控系统
```bash
# 方法1：双击运行
一键启动监控.bat

# 方法2：命令行运行
python -X utf8 monitor.py
```

### 2. 生成日报
```bash
# 方法1：双击运行
一键生成日报.bat

# 方法2：命令行运行
python -X utf8 daily_report.py
```

### 3. 启动Flask服务（可选）
```bash
# 双击运行
一键启动Flask服务.bat
```

## 监控内容

### 1. MySQL 数据库健康检查
- 连接测试
- 响应时间监控（>2秒报警）
- 数据新鲜度检查

### 2. Flask 服务健康检查
- HTTP GET http://localhost:5055/api/health
- 服务可用性监控
- 响应时间监控

### 3. 磁盘空间检查
- `output/` 目录大小监控
- 超过2GB报警

### 4. 采集脚本检查
- 检测 `scrape_amazon_details.py` 是否在运行
- 检测 `download_only.py` 是否在运行

### 5. 数据新鲜度检查
- `yp_products` 最近 scraped_at > 7天 → 警告
- `amazon_product_details` 最近 scraped_at > 3天 → 警告

## 日报内容

### 1. 数据概览
- `yp_products` 总数/昨日新增
- `amazon_product_details` 总数/昨日新增
- `ads_plans` 总数/昨日新增

### 2. 今日待办
- 没有广告方案的高价值商品（commission>8%, price>$30）Top 10
- SEMrush数据超30天未更新的商户 Top 5
- google_suggest_keywords超7天未更新的商户数量

### 3. 投放状态
- 最近一次数据更新时间
- KPI数据记录数量
- 投放表现监控

### 4. 系统健康
- MySQL状态
- Flask服务状态
- 磁盘使用情况

## 报警机制

### 飞书报警（待授权）
- 当前状态：仅打印日志，等待用户授权
- 授权后：状态从正常变异常时发送报警
- 避免刷屏：只在状态变化时发送

### 文件日志报警
- 所有检查结果记录到 `logs/monitor.log`
- 状态变化记录详细日志
- 滚动日志：最大5MB，保留5个备份

## 配置说明

### 数据库配置（monitor.py）
```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'database': 'affiliate_marketing',
    'user': 'root',
    'password': 'admin',
    'charset': 'utf8mb4',
}
```

### Flask服务配置
```python
FLASK_URL = "http://localhost:5055"
```

### 飞书配置（待授权）
```python
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_USER_ID = ""  # 待授权后填写
```

### 监控阈值
```python
MYSQL_TIMEOUT = 2.0      # 秒
DISK_WARNING_GB = 2.0    # GB
YP_FRESH_DAYS = 7        # yp_products 数据新鲜度阈值
AMAZON_FRESH_DAYS = 3    # amazon_product_details 数据新鲜度阈值
```

## 定时任务设置

### Windows 计划任务
1. **监控脚本**（每5分钟运行）
```powershell
# 创建计划任务
schtasks /create /tn "YP Monitor" /tr "C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\一键启动监控.bat" /sc minute /mo 5 /st 00:00 /ed 23:59
```

2. **日报脚本**（每天8点运行）
```powershell
# 创建计划任务
schtasks /create /tn "YP Daily Report" /tr "C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\一键生成日报.bat" /sc daily /st 08:00
```

### Linux crontab
```bash
# 监控脚本（每5分钟运行）
*/5 * * * * cd /path/to/yp_to_feishu && python -X utf8 monitor.py

# 日报脚本（每天8点运行）
0 8 * * * cd /path/to/yp_to_feishu && python -X utf8 daily_report.py
```

## 故障排除

### 常见问题
1. **MySQL连接失败**
   - 检查MySQL服务是否运行
   - 验证数据库配置（用户名/密码）

2. **Flask服务不可用**
   - 运行 `一键启动Flask服务.bat`
   - 检查端口5055是否被占用

3. **日报生成失败**
   - 检查数据库连接
   - 查看 `logs/daily_report.log` 获取详细错误信息

4. **飞书报警未发送**
   - 当前为待授权状态
   - 需要填写 `FEISHU_USER_ID` 并配置飞书应用权限

### 日志查看
```bash
# 监控日志
type logs\monitor.log

# 日报日志
type logs\daily_report.log

# 实时监控
python -X utf8 monitor.py
```

## 扩展功能

### 1. 飞书报警集成
1. 在飞书开放平台创建应用
2. 获取 `app_id` 和 `app_secret`
3. 获取用户 `user_id`
4. 更新 `monitor.py` 中的飞书配置

### 2. 邮件报警
- 可添加SMTP邮件报警功能
- 配置邮件服务器和收件人

### 3. 微信/钉钉报警
- 集成其他IM平台的Webhook
- 实现多渠道报警

### 4. 自定义监控项
- 添加新的数据库表监控
- 自定义报警阈值
- 扩展监控指标

## 注意事项

1. **首次运行**：会自动创建必要的目录和文件
2. **权限要求**：需要Python环境和MySQL访问权限
3. **依赖包**：需要 `psutil`、`mysql-connector-python`、`requests`
4. **文件权限**：确保有日志目录的写入权限
5. **网络访问**：需要访问本地MySQL和Flask服务

## 版本历史

### v1.0 (2026-03-27)
- 初始版本发布
- 基础监控功能
- HTML日报生成
- 飞书报警框架（待授权）
- Windows批处理脚本

## 技术支持

如有问题，请检查：
1. 日志文件：`logs/monitor.log`、`logs/daily_report.log`
2. Python依赖：`pip install psutil mysql-connector-python requests`
3. 数据库连接：确保MySQL服务运行且配置正确
4. 文件权限：确保有日志目录的写入权限