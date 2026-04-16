# 2026-03-26 工作复盘报告

> 整理时间：2026-03-26 23:54
> 作者：AI 助手（协同用户完成）

---

## 一、今日工作全景

今天围绕"亚马逊联盟营销 Google Ads 投放系统"完成了两大板块的工作：

**板块 A：Google Ads 广告创作系统从零搭建（上午—下午）**

从数据库表设计、广告生成脚本、到 Flask Web UI，完整交付了一套可运行的 Ads 管理平台。

**板块 B：ads_manager.py 网站加载失败故障排查与修复（下午—深夜）**

网站上线后出现"一直加载中"，经历了多轮排查，最终彻底修复，响应时间从 24+ 秒降至 0.002 秒。

---

## 二、板块 A：广告创作系统搭建

### 2.1 完成内容

**数据库层（4张表，三层广告结构）**

| 表名 | 层次 | 存储内容 |
|------|------|---------|
| `ads_plans` | 方案汇总 | 每个 ASIN 一条，记录 campaign/ad_group/ad 数量、方案状态 |
| `ads_campaigns` | Campaign 层 | 5个购买旅程阶段（Brand / Problem-Awareness / Solution-Evaluation / Feature-Exploration / Purchase-Decision） |
| `ads_ad_groups` | Ad Group 层 | 关键词 JSON、否定词 JSON、CPC 出价 |
| `ads_ads` | Ad 层 | 15 标题 + 5 描述 + Sitelinks + Callouts + Structured Snippet + 三阶段出价策略 |

**核心脚本**

- `create_ads_tables.py`：一键建表
- `generate_ads.py`：按需为指定 ASIN 生成完整广告方案写入 DB
- `ads_manager.py`：Flask Web UI（端口 5055），含商品浏览、广告制作、Amazon 采集、广告详情展示
- `build_us_cache.py`：构建 `yp_us_products` 物化缓存表

**验证结果**

- ASIN B09G1Z83GM 生成 5 Campaign / 6 Ad Group / 7 Ads
- 全部 15 标题 ≤30 字符，5 描述 ≤90 字符，合规率 100%
- Flask 接口响应 200 OK，41,562 字节，0.002 秒

### 2.2 关键设计决策

- 广告按需制作（不预批量），节省存储，灵活性高
- 物化表 `yp_us_products` 预过滤 US 商户，每 ASIN 唯一，消灭运行时 GROUP BY
- Web UI 支持"一键采集Amazon"（商品无详情时显示），闭环了数据采集流程

---

## 三、板块 B：故障排查复盘（重点）

### 3.1 故障时间线

```
14:xx  ads_manager.py 启动，浏览器访问 http://localhost:5055
      → 页面停在"加载中"，无任何数据展示

15:xx  第一轮排查：怀疑是 Flask 后端报错
      → 后端日志无异常，HTTP 200 OK，有响应体
      → 结论：后端正常，问题在前端 JS

16:xx  第二轮排查：怀疑是 JS 逻辑错误
      → 用 node --check 检查，发现 SyntaxError（行号 47）
      → 找到根因：onclick 里用了 Python \'，输出裸引号，JS 引号嵌套冲突

17:xx  修复引号问题后重启，页面仍然卡住（不同原因）
      → 此时 build_us_cache.py 尚未成功运行，物化表为空
      → Flask 启动检查显示提示页面（非加载错误）

18:xx  运行 build_us_cache.py 报错：Column count doesn't match
      → 原因：INSERT 未显式指定列名，表结构变更后列数不匹配

19:xx  修复列名后重新运行 build_us_cache.py
      → 新报错：Duplicate entry for UNIQUE(asin)
      → 原因：yp_merchants 里 merchant_name 有重复条目（Generic:11条、Lepro:7条等）
             JOIN 时同一 ASIN 出现多行，违反 UNIQUE 约束

21:xx  采用双层去重方案：
      yp_merchants 按 merchant_name GROUP BY MIN(id)
      yp_products 按 asin GROUP BY MIN(id)
      → build_us_cache.py 成功，329,202 行，约 27 秒完成

22:xx  ads_manager.py 查询改为直接查 yp_us_products
      → 响应时间从 24+ 秒降至 0.002 秒
      → 所有问题全部解决
```

### 3.2 根本原因分析（5-Why）

**问题：页面一直加载中**

| Why | 原因 |
|-----|------|
| Why 1 | 浏览器 JS 执行失败，导致数据请求从未发出 |
| Why 2 | `<script>` 块存在 SyntaxError，脚本整体无法执行 |
| Why 3 | onclick 内联事件中用了 `\'`，Python 输出为裸单引号，在 JS 字符串上下文中造成引号嵌套冲突 |
| Why 4 | **写 Python 后端生成 HTML/JS 时，没有区分"Python 转义"和"JS/HTML 输出"的边界** |
| Why 5 | 缺乏"前端 JS 嵌在 Python 字符串里"的规范，以及调试意识（后端 200 就停止排查） |

**问题：build_us_cache.py 重复 ASIN**

| Why | 原因 |
|-----|------|
| Why 1 | INSERT 插入时触发 UNIQUE asin 冲突 |
| Why 2 | 同一 ASIN 在 JOIN 后出现多行 |
| Why 3 | `yp_merchants` 存在多条 merchant_name 相同的记录，JOIN 时产生笛卡尔积 |
| Why 4 | 数据库建表时没有对 merchant_name 做唯一约束，导致脏数据积累 |
| Why 5 | 数据入库时缺乏去重检查（YP API 分批下发，重复商户名没有被过滤） |

---

## 四、经验总结与规则沉淀

### 规则 1：Python 生成 HTML/JS 的引号铁律

**禁止在 Python 三引号字符串中用 `\'` 嵌入 JS 字符串引号。**

Python 的 `\'` 是 Python 转义，输出到 HTML/JS 里变成裸引号，立刻破坏 JS 语法。

**正确做法：**

```python
# ❌ 危险 — 输出 selectCat('ALL',this)，引号冲突
html += '<div onclick="selectCat(\'ALL\',this)">全部</div>'

# ✅ 安全 — 用 data 属性传值，避免 onclick 内字符串
html += '<div data-cat="ALL" onclick="selectCatByEl(this)">全部</div>'
# JS 里：function selectCatByEl(el){ const cat = el.getAttribute('data-cat'); }
```

---

### 规则 2：前端"加载中"必须先检查 JS 语法

当页面停在加载状态时，**不要只看后端日志**。标准排查流程：

```bash
# Step 1：确认后端是否正常
curl -I http://localhost:5055/products    # 看 HTTP 状态码

# Step 2：提取页面 JS，用 Node 检查语法（5秒定位根因）
python -c "
import urllib.request, re
html = urllib.request.urlopen('http://localhost:5055/products').read().decode()
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
open('_check.js','w').write('\n'.join(scripts))
"
node --check _check.js
# → 直接输出错误行号，精准定位
```

---

### 规则 3：MySQL INSERT 必须显式指定列名

**禁止使用 `INSERT INTO table VALUES (...)` 不指定列名的写法。**

表结构一旦变更（加列、调整顺序），不指定列名的 INSERT 会立刻报 "Column count doesn't match"，且极难诊断。

```sql
-- ❌ 危险
INSERT INTO yp_us_products VALUES (1, 'B001', ...);

-- ✅ 安全
INSERT INTO yp_us_products (product_id, asin, product_name, price, ...)
VALUES (1, 'B001', ...);
```

---

### 规则 4：JOIN 前必须检查外键字段的唯一性

**任何 JOIN 操作前，先确认 JOIN 条件字段在两侧是否唯一。** 字段非唯一时 JOIN 会产生笛卡尔积，下游 UNIQUE 约束必然爆炸。

```sql
-- 诊断命令：检查 merchant_name 是否有重复
SELECT merchant_name, COUNT(*) cnt
FROM yp_merchants
GROUP BY merchant_name
HAVING cnt > 1
ORDER BY cnt DESC
LIMIT 10;
```

如果存在重复，JOIN 之前必须先去重：

```sql
-- 用子查询取 MIN(id) 去重
JOIN (
    SELECT MIN(id) AS id, merchant_name
    FROM yp_merchants WHERE country LIKE 'US -%'
    GROUP BY merchant_name
) mu ON p.merchant_name = mu.merchant_name
```

---

### 规则 5：物化表是高并发 Flask 的标配

**超过 10 万行的复杂 JOIN + GROUP BY 查询，绝不放在 HTTP 请求路径上。**

应预先构建物化表（物化视图），将查询结果缓存到独立表，服务层直接读缓存。

| 维度 | 实时 JOIN | 物化表 |
|------|----------|--------|
| 查询时间 | 24+ 秒 | 0.002 秒 |
| 可靠性 | 依赖运行时锁/并发 | 独立，可加 UNIQUE INDEX |
| 代价 | 零 | 每次数据更新后需重建（~27s） |

**物化表重建触发时机：yp_products 大批量新增后，手动运行 `python build_us_cache.py`。**

---

### 规则 6：后端 200 ≠ 前端正常

这条是今天最值得铭记的教训：

> **HTTP 200 只证明服务器成功把 HTML 发出去了，不等于前端 JS 能正常执行。**

前端 JS 报错时，后端看不到任何异常。排查前端问题必须：
1. 打开浏览器开发者工具 → Console 标签
2. 或用 `node --check` 离线检查提取出来的 JS
3. **不要只看后端日志就下"后端没问题"的结论**

---

## 五、今日工作量统计

| 类别 | 内容 | 数量 |
|------|------|------|
| 新建脚本 | create_ads_tables.py / generate_ads.py / build_us_cache.py | 3个 |
| 重大改写 | ads_manager.py（完整路由重构）/ build_us_cache.py（去重逻辑）| 2个 |
| 数据库表 | ads_plans / ads_campaigns / ads_ad_groups / ads_ads / yp_us_products | 5张 |
| 物化表行数 | yp_us_products | 329,202 行 |
| 性能提升 | 24s → 0.002s | 12,000x |
| 快捷启动 bat | 一键启动Ads管理界面.bat | 1个 |

---

## 六、明日待办事项

1. **测试更多 ASIN 生成广告** —— 找 3~5 个高佣金 ASIN（≥10%），验证 generate_ads.py 对不同品类的适配情况
2. **Google Suggest 关键词采集** —— 运行 `scrape_google_suggest_browser.py` 对 7,457 个 US 商户采集关键词，填充 `ads_merchant_keywords`
3. **广告投放实操** —— 在 Google Ads 控制台新建广告系列，按系统生成的方案手动导入一个测试广告
4. **SEMrush 竞争对手数据** —— 每天额度 2000 积分，可采集约 40 个商户，选高优先级的先跑

---

*本文档由 AI 助手自动整理，记录于 2026-03-26 工作结束时。*
