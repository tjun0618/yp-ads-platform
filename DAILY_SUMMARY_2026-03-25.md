# 今日工作总结 — 2026-03-25

---

## 一、今天做了什么

| 时间 | 事项 | 结果 |
|------|------|------|
| 02:41 | `fetch_amazon_urls.py` 全量解析完成 | 292,717 条 amazon_url 写入 MySQL |
| 早上 | `download_only.py` Excel 解析 bug 修复 | 38 个失败商户重新下载成功 |
| 08:37 | `download_only.py` v4 重构上线 | state.json 从 152MB 缩减到 22KB，OOM 根治 |
| 14:00 | `scrape_amazon_details.py` 调试完成 | 亚马逊商品详情采集脚本上线，开始全量采集 |
| 16:33 | 语言切换方式改造 | 从 URL 参数改为全局语言偏好设置 |
| 17:13 | 规格参数 JS 脏数据清洗 | 116 条存量数据清洗，225 个脏条目清除 |
| 17:59 | 项目整体架构梳理报告 | 生成 `PROJECT_ARCHITECTURE_REPORT.md` |

---

## 二、踩过的坑

### 坑1：openpyxl 报 "File is not a zip file"

**现象**：`download_only.py` 下载 Excel 后解析失败，`openpyxl.load_workbook()` 报错。

**根因**：Playwright `expect_download()` 在下载超时时会捕获到一个**不完整的文件**，文件头不是 `PK`（ZIP 格式），而是 HTML 错误页或截断数据。`openpyxl` 遇到这种文件直接抛异常。

**正确做法**：
```python
# 在解析前先校验文件头
with open(filepath, 'rb') as f:
    magic = f.read(2)
if magic != b'PK':
    return None  # 不是合法 xlsx，触发兜底逻辑
```

**经验**：任何通过浏览器自动化下载的文件，都要先做文件头魔数校验，不能无脑调解析库。

---

### 坑2：state.json 膨胀到 152MB 导致 OOM

**现象**：下载脚本运行一段时间后进程被系统 Kill，state.json 文件异常巨大。

**根因**：早期版本把每个商户的所有商品数据也存进 state.json（用于恢复），随着商户增多，这个文件线性膨胀，最终撑爆内存。

**正确做法**：
```python
# 断点续传 state 只存"已完成的ID列表"，不存数据本体
state = {
    "completed_mids": [...],  # 只有几KB，永不膨胀
    "failed_mids":    [...],
}
# 数据本体实时写入目标文件（Excel/DB），不经过内存缓存
```

**经验**：断点续传 state 文件的设计原则——**只存进度标记，不存数据**。数据要实时落盘，不要在内存里攒批。

---

### 坑3：PowerShell 中 errorlevel 判断失效

**现象**：`.bat` 文件里用 `if %errorlevel% neq 0` 判断 Chrome 是否启动失败，结果始终判断为"成功"。

**根因**：PowerShell 脚本里 `%errorlevel%` 行为与 CMD 不同，某些命令即使失败也不修改 `errorlevel`，导致判断失效。

**正确做法**：改用 `netstat` 直接检测端口是否监听：
```batch
netstat -an | findstr ":9222" >nul 2>&1
if %errorlevel% equ 0 (echo Chrome 调试端口已开启) else (echo 启动失败)
```

**经验**：在 bat/PowerShell 混合环境中，检测服务是否就绪，用**端口检测**比依赖 errorlevel 更可靠。

---

### 坑4：YP Service Worker 拦截亚马逊页面请求

**现象**：用 Playwright 已打开 YP 平台的浏览器 Tab 直接 `goto("amazon.com/...")` 时，页面内容异常——不是标准亚马逊页面，像是被拦截后返回了奇怪内容。

**根因**：YP 平台注册了 Service Worker，这个 Service Worker 的作用域会影响到**同一 BrowserContext 下的新导航**，导致 amazon.com 的请求被它拦截处理。

**正确做法**：
```python
# 不复用已有 Tab，用 ctx.new_page() 创建全新独立 Tab
page = ctx.new_page()
page.goto("https://www.amazon.com/...")
```

**经验**：用 Playwright 同时操作多个不同域名网站时，**为每个目标域名创建独立的 Page（Tab）**，避免 Service Worker / Cookie 的相互污染。

---

### 坑5：亚马逊语言问题 — URL 参数 vs 账户设置

**现象**：在商品 URL 后追加 `?language=en_US` 参数，某些页面依然显示中文内容。

**根因**：亚马逊的语言优先级是：**账户偏好设置 > URL 参数**。如果账户已经设置了某语言，URL 参数不生效。更根本的是：如果账户已设为英语，根本不需要追加参数。

**正确做法**：初始化时访问一次 `/customer-preferences/edit`，确认 `en_US` 已选中并 Save，之后所有页面自动英语，无需在每个 URL 后追加参数。

**经验**：对于有账户系统的网站，**通过账户设置做全局配置**比在每个 URL 上打补丁更稳定，也更干净。

---

### 坑6：亚马逊规格参数混入 JS 代码

**现象**：`product_details` 字段的 `Customer Reviews` 条目的 value 是 `P.when('A', 'ready').execute(function(A)...` 这样的 JS 代码。

**根因**：亚马逊部分表格行的 `<td>` 里嵌入了动态渲染脚本，`text_content()` 会把脚本文本也一起提取出来。

**正确做法**：
```python
JS_PATTERNS = re.compile(r'P\.when\(|\.execute\(|function\(|onclick=', re.IGNORECASE)
SKIP_KEYS = {'customer reviews', 'asin'}

def _is_clean(k, v):
    if k.lower() in SKIP_KEYS:
        return False
    if JS_PATTERNS.search(v):
        return False
    return True
```

**经验**：采集结构化网页数据时，对提取到的文本内容要做**合法性校验**，特别是 value 字段长度异常、含 JS 关键词等情况，要过滤掉。采集完成后还要设计**存量清洗脚本**，支持对已入库数据的补丁式修复。

---

### 坑7：约 30% ASIN 为 404（商品已下架）

**现象**：批量采集时大量 ASIN 返回 "Page Not Found"。

**误判过程**：最初以为是访问方式问题（YP 追踪链接 vs 直链）、或者是语言设置导致的重定向，排查了好几个方向。

**真正根因**：YP 平台的商品数据库更新滞后，大量商品在亚马逊早已下架，但 YP 还保留着记录。这是数据质量问题，不是技术问题。

**正确做法**：脚本检测到 404 时标记 `__404__` 跳过，不重试，不污染数据库。

**经验**：遇到大量失败时，先分清是**技术问题**（网络/权限/selector 失效）还是**数据质量问题**（源数据本身就是脏的）。排查顺序：先验证少量样本的真实情况，再做结论。

---

## 三、可以沉淀复用的经验

### 通用经验

**① 断点续传的标准设计模式**
```
state.json = {已完成ID集合, 失败ID集合, 最后更新时间}
```
- state 只存标记，不存数据本体
- 写入使用 tmp + rename 原子操作，防止写一半崩溃
- 每处理 N 个立即保存一次（不要等全部完成才保存）

**② 文件下载后必须做完整性校验**
```python
# xlsx 文件头魔数
with open(path, 'rb') as f:
    if f.read(2) != b'PK':
        return None  # 文件不完整，触发重新下载
```
- Excel（xlsx）= ZIP，文件头为 `PK`
- PDF 文件头为 `%PDF`
- 图片 PNG 为 `\x89PNG`

**③ 多线程并发 + 批量处理的标准模板**
```python
# 分批从 DB 取数，并发处理，实时回写
BATCH_SIZE = 1000
CONCURRENCY = 30
with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    futures = {pool.submit(process, item): item for item in batch}
    for f in as_completed(futures):
        result = f.result()
        # 立即写 DB，不攒批
```

**④ 服务就绪检测用端口而非 errorlevel**
```batch
:wait_loop
netstat -an | findstr ":9222" >nul 2>&1
if %errorlevel% neq 0 (
    timeout /t 2 >nul
    goto wait_loop
)
echo 服务已就绪
```

---

### Playwright 相关经验

**⑤ 多域名场景：每个域名用独立 Tab**
```python
# 操作 A 网站时用 page_a，操作 B 网站时用 page_b
# 不混用，避免 Service Worker / Cookie 污染
ctx = playwright.chromium.connect_over_cdp("http://localhost:9222")
page_yp = ctx.pages[0]       # 已有的 YP Tab
page_amz = ctx.new_page()    # 新建独立 Tab 给亚马逊用
```

**⑥ 用账户偏好设置做全局配置，比 URL 参数更稳定**
适用于：语言设置、配送地址、货币单位等所有账户级别的偏好。
做法：脚本启动时执行一次初始化，全局设好，后续所有页面自动生效。

**⑦ 多 selector 回退策略**
亚马逊页面结构频繁变动，关键字段要备多个 selector：
```python
for sel in ['#productTitle', 'h1.a-size-large', 'h1#title']:
    try:
        val = page.locator(sel).first.text_content(timeout=3000)
        if val and val.strip():
            data['title'] = val.strip()
            break
    except Exception:
        pass
```

**⑧ 调试 Chrome 连接的标准模式**
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]  # 复用已有 context（含登录态）
    page = ctx.new_page()
    # ...
```

---

### 数据采集质量经验

**⑨ 对 text_content() 提取的内容做 JS 代码检测**
```python
JS_PATTERNS = re.compile(r'P\.when\(|\.execute\(|function\(|onclick=', re.IGNORECASE)
if JS_PATTERNS.search(value):
    skip_this_field()
```
适用于：任何有动态渲染的网站（亚马逊、京东、淘宝等）。

**⑩ 采集脚本必须有存量修复能力**
每个采集脚本配套一个 `clean_xxx.py`，用于：
- 对已入库数据做字段清洗
- 补采缺失字段
- 修复 selector 更新后的历史数据

**⑪ 数据来源优先级：网页端 > API**
当平台同时提供 API 和网页端时，如果 API 数据质量有问题（混入非目标市场数据），优先用网页端数据。
原因：网页端展示的是用户实际看到的数据，更准确；API 可能返回后台全量数据，包含未过滤的全球数据。

---

## 四、明天可以继续的事项

1. **确认全量采集进度** — `scrape_amazon_details.py` 在独立 CMD 窗口里跑着，明早检查进度
2. **评估有效数据比例** — 统计 `amazon_product_details` 中真正采集成功的条数，排除 404 下架的
3. **Google Ads 文案创作** — 挑选评分高（≥4.0）、评论多（≥100）、佣金率高的商品，用 Bullet Points + 标题生成广告文案

---

*总结生成时间：2026-03-25 18:08*
