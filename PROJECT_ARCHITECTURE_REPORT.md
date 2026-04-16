# 亚马逊联盟营销数据采集项目 — 整体架构梳理报告

> 更新时间：2026-03-25  
> 项目目录：`C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\`  
> 数据库：MySQL `affiliate_marketing`（localhost:3306）

---

## 一、项目总体目标

本项目是一套**亚马逊联盟营销（Amazon Affiliate Marketing）全链路数据采集与投放体系**，核心目标是：

1. 从 YeahPromos（YP）联盟平台采集商户、商品、分类等基础数据
2. 清洗筛选出**美国市场**的有效商户和商品
3. 将商品的 YP 追踪链接解析为**亚马逊商品直链**
4. 通过 Playwright 浏览器自动化，从亚马逊采集**商品详细信息**（标题、价格、评分、Bullet Points、规格参数等）
5. 将全部数据沉淀到 MySQL 数据库，并同步到飞书多维表格，供 Google Ads 广告文案创作使用

---

## 二、整体数据流向图

```
YP 平台（yeahpromos.com）
      │
      ├─── API 接口（REST）
      │       ├── 类别 API    → yp_categories（148条）
      │       ├── 商户 API    → yp_merchants（9,997条）
      │       └── 商品 API    → yp_products（初始数据）
      │
      └─── 网页端（Playwright 浏览器自动化）
              └── brand_detail 页面 Download Products
                      → YP_products.xlsx（302,229条）
                              │
                              ▼
                    import_to_mysql.py / sync_excel_to_mysql.py
                              │
                              ▼
              MySQL: yp_products（289,640条）
                    字段：merchant_name, merchant_id, asin,
                          product_name, category, price,
                          commission, tracking_url, amazon_url
                              │
                              ▼
                    fetch_amazon_urls.py（解析追踪链接）
                    HTTP GET tracking_url，读响应头 refresh
                              │
                              ▼
              yp_products.amazon_url 全量写入（292,717条）
              格式：https://www.amazon.com/dp/ASIN?maas=...
                              │
                              ▼
                    scrape_amazon_details.py
                    （Playwright 连接调试 Chrome）
                              │
                              ▼
              MySQL: amazon_product_details（采集中）
                    字段：asin, title, brand, price, rating,
                          review_count, bullet_points, description,
                          product_details, category_path,
                          top_reviews, keywords
                              │
                              ▼
              飞书多维表格（YP商家和亚马逊商品数据）
              App Token: Tdc3bct8ras9uzsKq5ycSja0nld
```

---

## 三、第一阶段：登录 YP 平台

### 登录方式

YP 平台（`https://www.yeahpromos.com`）采用两种访问凭证：

| 凭证类型 | 用途 | 获取方式 |
|---------|------|---------|
| API Token | 调用 REST API | 固定值 `7951dc7484fa9f9d`，写在脚本常量中 |
| Browser Cookie | 访问网页端、下载 Excel | 通过已登录的 Chrome 浏览器提取 |

### 调试 Chrome 启动

所有需要网页操作的脚本（`download_only.py`、`scrape_amazon_details.py`），都依赖**调试模式 Chrome**：

```bash
"C:\Program Files\Google\Chrome\Application\chrome.exe"
  --remote-debugging-port=9222
  --user-data-dir="C:\Users\wuhj\Chrome_Debug"
```

快捷工具：`启动调试Chrome.bat` — 自动关闭残留进程并以调试模式重新启动。

脚本通过 Playwright 连接：`playwright.connect_over_cdp("http://localhost:9222")`，**复用已登录的 Chrome 会话**，无需重新登录。

---

## 四、第二阶段：从 YP 平台采集三类基础数据

### 4.1 类别数据（Categories）

**脚本**：`collect_categories.py`  
**API 端点**：`GET https://www.yeahpromos.com/index/apioffer/getcategory?token=TOKEN`  
**特殊点**：Category API 的 token 放在 URL 参数里（与其他 API 不同，其他 API 的 token 放在 HTTP Header）

```
请求方式：GET 参数 token
返回数据：类别 ID + 类别名称
采集结果：148 条类别
存储位置：MySQL yp_categories 表 + output/categories_data.json
```

### 4.2 商户数据（Merchants）

**脚本**：`collect_merchants.py`  
**API 端点**：`GET https://www.yeahpromos.com/index/getadvert/getadvert`  
**认证**：HTTP Header `{"token": "7951dc7484fa9f9d"}`  
**参数**：`site_id=12002`，支持分页（`page`、`limit`），`elite=0` 获取全量，`elite=1` 仅精英商户

```
请求方式：Header token + 分页参数
返回数据：商户名、商户ID(mid)、国家、佣金率、Cookie天数、状态等
采集结果：9,997 条商户
存储位置：MySQL yp_merchants 表 + output/merchants_data.json
                              + output/merchants_mid_list.json（含 mid 列表）
```

**关键字段说明**：
- `mid`：商户在 YP 平台的唯一 ID，后续所有关联操作均依赖此字段
- `status`：`APPROVED`（已申请审批通过）/ `UNAPPLIED`（未申请）/ `PENDING`（审批中）
- `country`：商户所在国家，用于后续美国商户筛选

### 4.3 商品数据（Offers）

YP 商品数据有**两个数据源**，质量差异显著：

#### 数据源 A：Offers API（质量差，已废弃）

**脚本**：`collect_offers.py`  
**API 端点**：`GET https://www.yeahpromos.com/index/apioffer/getoffer`  
**问题**：API 混入全球站点数据（EUR/CAD），价格单位混乱，不区分美国市场。  
**结论**：诊断报告（`DIAGNOSIS_REPORT.md`）建议废弃此数据源。

#### 数据源 B：网页端 Download Products（主力数据源）

**脚本**：`download_only.py`（v4 版本）  
**技术原理**：Playwright 浏览器自动化，登录 YP 网页后，逐个访问每个商户的 `brand_detail` 页面（`/index/offer/brand_detail?advert_id={mid}&page=N`），点击 **Download Products** 按钮下载 Excel 文件

```
采集流程：
  1. 从 merchants_mid_list.json 加载全部 MID 列表
  2. 逐个商户访问 brand_detail 页面
  3. 点击 Download Products 下载 xlsx 文件
  4. openpyxl 解析 Excel，提取：
     merchant_name, merchant_id, asin, product_name,
     category, price, commission, tracking_link
  5. 追加写入 D:\workspace\YP_products.xlsx
  6. 断点续传：output/download_state.json 记录已完成 MID

采集结果：302,229 条（涵盖 3,727 个商户）
输出文件：D:\workspace\YP_products.xlsx
```

**核心技术点**：
- v4 版本彻底解决 OOM 问题：state.json 只存商户 ID 列表（几 KB），商品数据不进内存，处理完立即写 Excel
- 文件头魔数校验（`PK` 字节）防止下载不完整的 xlsx 被解析
- 定时任务：每 30 分钟增量同步（`sync_excel_to_mysql.py`），计划任务名 `YP Full Auto Collect`

---

## 五、第三阶段：美国商户筛选与全量商品抓取

### 5.1 美国商户筛选

**脚本**：`analyze_us_merchants.py`  
**筛选逻辑**：从 `merchants_mid_list.json` 中过滤 `country` 字段包含 `"United States"` 的商户

```python
us_merchants = [m for m in all_merchants if 'United States' in m.get('country', '')]
```

**筛选结果**：
- 全平台商户：10,020 个
- 美国商户（US）：其中一批，按状态分为 APPROVED（已可投放）和 UNAPPLIED
- 输出文件：`output/us_merchants_clean.json`

### 5.2 全量网页端抓取 ASIN 与投放链接

**脚本**：`scrape_all_merchants_web.py`  
**目标**：为每个商户建立 `ASIN → 投放链接` 的完整映射

**技术原理**：
- 使用已登录 Chrome 的 Cookie（`PHPSESSID`、`user_id` 等）
- HTTP GET 请求（`requests` 库，非 Playwright）访问 `brand_detail` 页面
- BeautifulSoup 解析 HTML，提取 `div.asin-code` 获取 ASIN，提取投放链接

```
采集结果：
  - 覆盖 10,020 个商户
  - ASIN 映射总量：96,794 个
  - 含投放链接的：53,165 个（APPROVED 商户）
  - 输出文件：output/asin_merchant_map.json
```

**投放链接格式**：
```
https://yeahpromos.com/index/index/openurlproduct?track={track}&pid={pid}
```
说明：`track` 字段只有 APPROVED 商户才有值，UNAPPLIED 商户商品虽可见但无投放链接。

---

## 六、第四阶段：Excel 导入 MySQL

**脚本**：`import_to_mysql.py`（全量导入）/ `sync_excel_to_mysql.py`（增量同步）  
**数据源**：`D:\workspace\YP_products.xlsx`  
**目标表**：MySQL `affiliate_marketing.yp_products`

```
导入逻辑：
  - 批量读取 Excel（每批 2,000 行，控制内存）
  - INSERT ... ON DUPLICATE KEY UPDATE（以 ASIN 为主键，幂等写入）
  - 字段映射：merchant_name, merchant_id, asin, product_name,
              category, price, commission, tracking_url, scraped_at

最终数据量：289,640 条
```

**计划任务**（`sync_excel_to_mysql.py`）：每 30 分钟自动同步 Excel 新增数据至 MySQL。

---

## 七、第五阶段：tracking_url → Amazon URL 解析

**脚本**：`fetch_amazon_urls.py`  
**目标**：将 `yp_products` 表中的 `tracking_url`（YP 投放追踪链接）解析为**亚马逊商品直链**，写入 `amazon_url` 字段

**技术原理**：
YP 投放链接的跳转机制是通过 HTTP 响应头的 `Refresh` 字段实现的（非 301/302 重定向）：
```
HTTP Response Header:
  Refresh: 0;url=https://www.amazon.com/dp/B09G1Z83GM?maas=maas_adg_api_...&tag=maas
```

脚本用 `requests.get(tracking_url, allow_redirects=False)` 获取响应头，用正则提取 URL：
```python
refresh = headers.get("refresh", "")
m = re.search(r'url=(.+)', refresh, re.IGNORECASE)
amazon_url = m.group(1).strip()
```

```
并发配置：30 线程并发，每批 1,000 条，失败重试 2 次
采集结果：处理 292,720 条，成功 292,717 条，失败 3 条
耗时：190.9 分钟
解析后 URL 格式：https://www.amazon.com/dp/{ASIN}?maas=maas_adg_api_...&tag=maas
```

**重要结论**：`amazon_url` 字段存的是**亚马逊直链**（带 `maas` 联盟追踪参数，但不经过 YP 服务器），后续 Playwright 直接访问此 URL，效率高、不需要 YP 登录态。

---

## 八、第六阶段：从亚马逊采集商品详细信息

**脚本**：`scrape_amazon_details.py`  
**快捷启动**：`一键启动Amazon详情采集.bat`  
**目标表**：MySQL `affiliate_marketing.amazon_product_details`

### 8.1 前置初始化（`setup_language_and_address`）

脚本启动后执行一次性初始化，确保后续所有页面语言正确：

**步骤 1 — 切换配送地址到中国**：
- 访问 `https://www.amazon.com`，点击配送地址组件
- 找到 `#GLUXCountryList`，选择 `CN`（中国）
- 目的：避免"商品无法发货到美国"等地区限制干扰

**步骤 2 — 全局设置英语**：
- 访问 `/customer-preferences/edit`（语言偏好设置页）
- 确认 `value=en_US` 的单选按钮已选中
- 点击 `#icp-save-button` 保存
- 目的：确保所有商品页面显示英文内容，供广告文案使用

> 关键技术点：必须用 `ctx.new_page()` 创建新 Tab，不能复用已打开 YP 平台的 Tab。原因：YP 的 Service Worker 会拦截请求，导致亚马逊页面内容异常。

### 8.2 商品详情采集（`scrape_product`）

对每个 ASIN 执行以下采集流程：

```
1. page.goto(amazon_url)  访问商品页面
2. 检查是否跳到验证码/登录页（captcha/signin）
3. 检查页面 title 是否含 "page not found"（商品下架 → 标记 __404__）
4. 多 selector 回退策略依次采集：
   ┌─────────────────────────────────────────────┐
   │ 字段         │ 主 Selector                  │
   ├─────────────────────────────────────────────┤
   │ 标题         │ #productTitle                │
   │ 品牌         │ #bylineInfo                  │
   │ 价格         │ .a-price.apex-price-to-pay-value .a-offscreen │
   │ 原价         │ .a-price.a-text-price .a-offscreen │
   │ 评分         │ #acrPopover                  │
   │ 评论数       │ #acrCustomerReviewText       │
   │ 库存状态     │ #availability span           │
   │ Bullet Points│ #feature-bullets .a-list-item│
   │ 商品描述     │ #productDescription p        │
   │ 规格参数     │ #productDetails_techSpec_section_1 tr │
   │ 分类路径     │ #wayfinding-breadcrumbs_feature_div a │
   │ Top 评论     │ [data-hook="review"]         │
   └─────────────────────────────────────────────┘
5. 关键词：从标题+Bullet Points 自动提取（空格分词 + 去停用词）
6. INSERT INTO amazon_product_details ... ON DUPLICATE KEY UPDATE
```

### 8.3 规格参数脏数据过滤

亚马逊 `product_details` 表格中的 `Customer Reviews` 和 `ASIN` 字段值含有 JS 代码（`P.when(...).execute(...)`）：

**处理方式**：`_is_clean(k, v)` 函数过滤：
- 黑名单字段：`customer reviews`、`asin`
- JS 特征正则：`P\.when\(|\.execute\(|function\(|onclick=`

**存量清洗**：`clean_product_details.py` — 对已入库的 116 条数据清洗，共清除 225 个脏条目。

### 8.4 运行模式

```bash
# 增量模式（默认，只处理未采集的 ASIN）
python -X utf8 scrape_amazon_details.py

# 单 ASIN 测试
python -X utf8 scrape_amazon_details.py --asin B09G1Z83GM

# 限制条数（测试用）
python -X utf8 scrape_amazon_details.py --limit 100

# 全量重采（覆盖更新）
python -X utf8 scrape_amazon_details.py --refetch
```

---

## 九、数据存储架构

### MySQL 数据库（`affiliate_marketing`）

| 表名 | 行数 | 核心字段 | 用途 |
|------|------|---------|------|
| `yp_categories` | 148 | category_id, category_name | YP 商品分类 |
| `yp_merchants` | 9,997 | mid, name, country, avg_payout, cookie_days, status | 商户基础信息 |
| `yp_products` | 289,640 | asin, merchant_name, merchant_id, product_name, category, price, commission, tracking_url, amazon_url | 商品与投放链接 |
| `amazon_product_details` | 采集中 | asin, title, brand, price, rating, review_count, bullet_points, description, product_details, category_path, top_reviews, keywords | 亚马逊商品详情 |

### 文件存储（`yp_to_feishu/output/`）

| 文件 | 内容 |
|------|------|
| `categories_data.json` | 148 条类别原始数据 |
| `merchants_data.json` | 全量商户数据 |
| `merchants_mid_list.json` | 商户 MID 列表（含国家、状态） |
| `us_merchants_clean.json` | 美国商户清洗结果 |
| `asin_merchant_map.json` | ASIN→投放链接映射（96,794条） |
| `download_state.json` | 下载断点续传状态（已完成/失败 MID） |
| `download_log.txt` | 下载进度日志 |
| `fetch_amazon_urls.log` | URL 解析日志 |

### 飞书多维表格

| 表格 | App Token | 用途 |
|------|-----------|------|
| Offers 表 | `VgOiblBCKac38ZsNx9acHpCGnQb` | 8,401 条商品（早期数据） |
| YP商家和亚马逊商品数据 | `Tdc3bct8ras9uzsKq5ycSja0nld` | 45 条精选商品，含亚马逊详情 |

---

## 十、调用的技术能力（技能）

| 技能 | 具体技术 | 应用场景 |
|------|---------|---------|
| **Playwright 浏览器自动化** | `playwright.sync_api`，CDP 连接已登录 Chrome | YP 品牌页下载 Excel、亚马逊商品详情采集 |
| **HTTP 请求与解析** | `requests` + BeautifulSoup + `re` | YP REST API 调用、tracking_url 解析、网页 HTML 解析 |
| **多线程并发** | `ThreadPoolExecutor`（30线程） | `fetch_amazon_urls.py` 并发解析 29 万条链接 |
| **MySQL 数据库操作** | `mysql-connector-python`，批量 INSERT + ON DUPLICATE KEY UPDATE | 所有数据的持久化存储 |
| **Excel 文件操作** | `openpyxl`，追加写入（避免全量重写） | YP 产品数据的本地缓存与增量写入 |
| **飞书开放平台 API** | 飞书 Bitable API，Bearer Token 认证 | 数据同步到飞书多维表格 |
| **JSON 断点续传** | state.json 记录进度，程序崩溃后从断点继续 | `download_only.py`、`scrape_all_merchants_web.py` |
| **数据清洗** | 正则过滤、黑名单字段、JS特征检测 | 规格参数脏数据清洗 |

---

## 十一、快捷启动工具汇总

| 工具 | 功能 |
|------|------|
| `启动调试Chrome.bat` | 关闭残留 Chrome → 以调试模式（端口9222）重启 |
| `一键启动YP下载.bat` | 检测 Chrome 调试端口 → 显示断点进度 → 启动 download_only.py |
| `一键启动Amazon详情采集.bat` | 检测 Chrome → 启动 scrape_amazon_details.py |
| `一键增量同步.bat` | 运行 sync_excel_to_mysql.py |
| `run_full_collect.bat` | 全量数据采集流程 |

---

## 十二、整体数据流水线（完整版）

```
步骤1  启动调试Chrome.bat
       └─ Chrome 以调试模式启动（端口9222）
       └─ 手动登录 YP 平台

步骤2  collect_categories.py      → yp_categories（148条）
       collect_merchants.py        → yp_merchants（9,997条）
                                   → output/merchants_mid_list.json

步骤3  analyze_us_merchants.py     → output/us_merchants_clean.json
       （从10,020商户中筛选美国商户）

步骤4  scrape_all_merchants_web.py → output/asin_merchant_map.json
       （网页端抓取96,794个ASIN及投放链接）

步骤5  一键启动YP下载.bat
       └─ download_only.py         → D:\workspace\YP_products.xlsx（302,229条）
       └─ import_to_mysql.py       → yp_products（289,640条）

步骤6  fetch_amazon_urls.py        → yp_products.amazon_url（292,717条解析完成）
       （30线程并发，190分钟完成全量解析）

步骤7  一键启动Amazon详情采集.bat
       └─ scrape_amazon_details.py → amazon_product_details（采集中）
          ├─ 初始化：配送地址CN + 语言en_US
          ├─ 逐条访问 amazon_url
          ├─ 采集：标题/品牌/价格/评分/Bullets/描述/规格/评论/关键词
          └─ 写入 MySQL

步骤8  quick_upload_to_feishu.py   → 飞书多维表格
       （精选商品数据同步飞书，供广告文案使用）
```

---

## 十三、已知问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 约30%的ASIN为404（商品下架） | YP 平台数据更新滞后，下架商品未清理 | 脚本自动标记 `__404__`，跳过不重试 |
| API 数据混入 EUR/CAD 价格 | YP API 不区分市场，返回全球数据 | 以网页端 Download Products 数据为主 |
| 多语言评论混入（德语/意大利语） | kwmobile 等欧洲品牌的全球买家评论 | 仅影响 top_reviews，不影响核心字段 |
| state.json OOM（曾达152MB） | 早期版本将所有商品数据存入 state | v4 重构：state 只存 MID 列表 |
| 规格参数混入 JS 代码 | 亚马逊动态渲染，`P.when(...)` 污染 | `_is_clean()` 过滤 + 存量 `clean_product_details.py` 清洗 |
| YP Service Worker 拦截亚马逊请求 | Service Worker 注册在 YP Tab 上 | 用 `ctx.new_page()` 创建独立 Tab |

---

*报告生成时间：2026-03-25 17:59*
