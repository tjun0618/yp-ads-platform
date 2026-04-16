# YP 平台商户商品采集完整 SOP

> 版本：v1.0 | 更新时间：2026-03-24 | 适用场景：批量采集 YP US 商户商品数据并写入飞书

---

## 概述

本 SOP 涵盖从登录 YP 平台，到获取商户列表、采集商品数据、写入飞书多维表格的完整流程。

### 核心链路

```
登录 YP → 启动调试模式 Chrome → 脚本连接浏览器 → 遍历 US 商户 → 
抓取 brand_detail 页面商品 → 解析 ASIN + 投放链接 → 写入飞书
```

### 关键参数

| 参数 | 值 |
|------|-----|
| Site ID | `12002` |
| 登录 URL | `https://www.yeahpromos.com/index/login/login` |
| 品牌页 URL | `https://www.yeahpromos.com/index/offer/brand_detail?advert_id={mid}&site_id=12002` |
| US APPROVED 商户数 | 3,727 个 |
| 飞书 App Token | `VgOiblBCKac38ZsNx9acHpCGnQb` |
| 飞书 Table ID | `tblMCbaHhP88sgeS` |

---

## 阶段一：环境准备

### 1.1 确认脚本目录

```
工作目录：c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\
```

关键文件：

| 文件 | 用途 |
|------|------|
| `output/us_merchants_clean.json` | US 商户列表（3,727 个 APPROVED） |
| `scrape_no_wait.py` | 页面解析抓取脚本 |
| `download_merchant_products.py` | Excel 下载抓取脚本（推荐） |
| `output/scrape_state_manual.json` | 断点续传状态文件 |
| `output/us_merchants_products.json` | 抓取结果输出 |

### 1.2 安装依赖

```powershell
pip install playwright openpyxl requests
playwright install chromium
```

---

## 阶段二：启动调试模式 Chrome 并登录

> **核心原因**：YP 有反爬机制，Playwright 自动操作的浏览器无法正常输入账号密码（会被清空）。必须用调试模式连接到真实 Chrome 实例。

### 2.1 启动调试模式 Chrome

打开 **PowerShell** 或 **CMD**，运行：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\wuhj\Chrome_Debug"
```

**说明：**
- `--remote-debugging-port=9222`：开启调试端口，供 Playwright 连接
- `--user-data-dir`：使用独立用户数据目录（不影响日常 Chrome）
- 启动成功后控制台会显示：`DevTools listening on ws://127.0.0.1:9222/...`

### 2.2 在调试模式 Chrome 中登录 YP

1. 调试模式 Chrome 启动后，在地址栏输入：
   ```
   https://www.yeahpromos.com/index/login/login
   ```
2. **手动输入**账号密码（注意：这个浏览器是全新的，没有书签和历史记录）
3. 登录成功后，确认页面跳转到 YP 后台（Offers 或 Advert 页面）
4. **保持 Chrome 窗口打开，不要关闭**

> ⚠️ **注意**：每次关闭调试模式 Chrome 后，需要重新执行 2.1 和 2.2 步骤

---

## 阶段三：运行抓取脚本

### 方案 A：页面解析（推荐，全量）

适用场景：抓取所有 APPROVED US 商户的商品和投放链接

```powershell
cd "c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu"
python -X utf8 scrape_no_wait.py
```

**脚本逻辑：**
1. 连接调试模式 Chrome（`http://localhost:9222`）
2. 遍历 `output/us_merchants_clean.json` 中的 3,727 个 APPROVED 商户
3. 访问每个商户的 `brand_detail` 页面，分页遍历所有页
4. 解析 HTML 中的 `ASIN`（`<div class="asin-code">`）和投放链接（`ClipboardJS.copy('...')`）
5. 实时保存断点状态到 `output/scrape_state_manual.json`

**断点续传：** 脚本会自动跳过已完成的商户，中断后直接重新运行即可继续

**检测登录失效：** 如遇 `Login name cannot be empty`，等待 30 秒后重试

### 方案 B：Excel 下载（单商户精准）

适用场景：单个商户全量数据，或 Download Products 按钮可用时

```powershell
python -X utf8 download_merchant_products.py
```

**脚本逻辑：**
1. 连接调试模式 Chrome
2. 访问商户 brand_detail 页面
3. 查找并点击 "Download Products" 按钮
4. 读取下载的 `.xlsx` 文件（字段：ASIN, Product Name, Category, Commission, Price, Tracking Link）
5. 解析后保存到 JSON

---

## 阶段四：解析数据格式

### brand_detail 页面关键字段

| 数据 | 来源 | 说明 |
|------|------|------|
| ASIN | `<div class="asin-code">XXXXXXXXXX</div>` | 10位亚马逊商品编号 |
| 投放链接 | `ClipboardJS.copy('https://yeahpromos.com/index/index/openurlproduct?track=xxx&pid=xxx')` | 完整的带追踪参数的链接 |
| Track Token | 从投放链接中提取 `track=` 参数 | 商户级别，同一商户所有商品相同 |
| PID | 从投放链接中提取 `pid=` 参数 | 商品级别唯一标识 |

### 投放链接格式

```
https://yeahpromos.com/index/index/openurlproduct?track={track_token}&pid={product_id}
```

### Excel 下载字段（列顺序）

| 列 | 字段 |
|----|------|
| A | ASIN |
| B | Product Name |
| C | Category |
| D | Commission (%) |
| E | Price (USD) |
| F | Tracking Link |

---

## 阶段五：数据写入飞书

### 飞书配置

```python
APP_ID     = 'cli_a935343a74f89cd4'
APP_SECRET = 'EqnC0zcv1CF9A2h849z8geK8RmfRRfiE'
APP_TOKEN  = 'VgOiblBCKac38ZsNx9acHpCGnQb'
TABLE_ID   = 'tblMCbaHhP88sgeS'
```

### 飞书表格字段映射

| 飞书字段 | 数据来源 |
|---------|---------|
| ASIN | 抓取/Excel 的 asin |
| Product Name | product_name |
| Price (USD) | price |
| Payout (%) | commission |
| Category Name | category |
| Merchant ID | merchant_id |
| Merchant Name | merchant_name |
| Tracking URL | tracking_url / tracking_link |
| Track Token | track |
| Amazon Link | `https://www.amazon.com/dp/{ASIN}` |
| Collected At | scraped_at |

### 写入脚本

数据采集完成后，运行：

```powershell
python -X utf8 upload_to_feishu.py
```

> 脚本会自动去重（按 ASIN），避免重复写入

---

## 阶段六：常见问题处理

### Q1：脚本提示"连接失败 ECONNREFUSED"

**原因：** 调试模式 Chrome 没有启动，或已关闭

**解决：** 重新执行阶段二的 2.1 步骤启动 Chrome

---

### Q2：脚本提示"未登录 Login name cannot be empty"

**原因：** Chrome 中 YP Session 已过期

**解决：**
1. 在调试模式 Chrome 中重新访问 `https://www.yeahpromos.com/index/login/login`
2. 手动登录
3. 脚本等待 30 秒后会自动重试

---

### Q3：调试模式 Chrome 登录时输入框被清空

**原因：** YP 的反爬机制检测到自动化浏览器

**解决：** 使用 `--user-data-dir` 参数启动的 Chrome 是真实浏览器，应该可以正常输入。如果仍然被清空，尝试：
1. 先点击一下页面空白处
2. 等待 2 秒后再输入
3. 或者用键盘一个字一个字输入（不要粘贴）

---

### Q4：抓取速度很慢

**原因：** 每页需要等待页面加载

**优化：**
- 减小 `time.sleep()` 值（建议 0.3 ~ 0.5 秒，不要太小以免被封）
- 先处理商品数量少的商户（1页），积累完成数量
- 大商户（如 NORTIV 8 有 183 页）放到最后

---

### Q5：断点续传如何工作

脚本每完成一个商户就写入 `output/scrape_state_manual.json`。重新运行脚本时，会自动读取此文件，跳过已完成的商户。

**手动重置：** 删除 `output/scrape_state_manual.json` 即可从头开始

---

## 完整运行命令汇总

```powershell
# 步骤 1：启动调试模式 Chrome（每次抓取前都要执行）
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\wuhj\Chrome_Debug"

# 步骤 2：在新打开的 Chrome 中手动登录 YP
# 访问：https://www.yeahpromos.com/index/login/login

# 步骤 3：切换到工作目录，运行抓取脚本
cd "c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu"
python -X utf8 scrape_no_wait.py

# 步骤 4：抓取完成后，上传飞书
python -X utf8 upload_to_feishu.py
```

---

## 数据质量说明

| 数据来源 | 质量 | 说明 |
|---------|------|------|
| brand_detail 页面解析 | ⭐⭐⭐⭐⭐ | 100% 准确，只含 US 站商品，投放链接有效 |
| Excel Download Products | ⭐⭐⭐⭐⭐ | 最准确，字段更完整（含价格、类别） |
| YP API（getoffer） | ⭐⭐ | 混入全球站商品，商户归属不可靠 |

**推荐优先使用 brand_detail 页面解析**，配合 Excel Download 获取完整字段。
