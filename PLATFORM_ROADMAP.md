# 联盟营销广告平台 — 功能演进路线图

> 制定日期：2026-03-27  
> 负责人：AI 自主研发（重大决策询问用户）  
> 平台入口：http://localhost:5055  
> 主文件：`yp_to_feishu/ads_manager.py`

---

## 阶段一：近期完善（Week 1-2，2026-03-27 起）

### ✅ 已完成
- [x] YP 数据采集（YP API + 网页全量）
- [x] Amazon 商品详情采集
- [x] SEMrush 竞品数据采集
- [x] Google Suggest 关键词采集
- [x] 广告生成系统（5 Campaign + RSA 结构）
- [x] 商户作战室（一页整合 5 步工作流）
- [x] 推广链接一键复制 + 直达 Amazon 按钮
- [x] 用户评论完整展示

### 🚧 Week 1（当前执行中）

#### P1 — 广告优化模块（最高优先级）[进行中]
**目标**：上传 Google Ads 后台导出的搜索词报告，自动分析并输出优化建议。

功能点：
- 新增"📈 投放优化"导航 Tab
- 支持上传 Google Ads CSV/Excel（搜索词报告 + 关键词效果报告）
- 自动解析列：Search term / Impressions / Clicks / CTR / CPC / Conversions / Cost
- 分析引擎：
  - 高点击低转化词 → 建议加否定关键词
  - 高转化低曝光词 → 建议提升出价 / 扩展匹配
  - QS < 5 → 建议优化对应广告文案
  - 高意图完全匹配词 → 建议新建专属 Ad Group
- 针对每个 ASIN 现有广告方案输出具体修改建议
- KPI 仪表盘：目标 ROAS / CPA / CTR vs 实际数据，红绿灯指示

数据库新表：
- `ads_search_term_reports`：上传的报告数据
- `ads_optimization_suggestions`：系统生成的优化建议
- `ads_kpi_targets`：用户设置的 KPI 目标

#### P2 — 广告质量评分系统（QS 自动打分）
**目标**：对每条广告自动评分，优先投高质量广告。

评分维度（满分 100）：
- 关键词密度（标题含目标关键词）：30分
- CTA 明确性（含 Buy/Get/Save/Shop/Try 等动词）：20分
- 情感词命中（Free/Best/Top/Proven/Guaranteed 等）：20分
- 字符利用率（标题≥25/30，描述≥75/90）：20分
- 唯一性（与同 ASIN 其他变体的重复度）：10分

新增字段：`ads_ads.quality_score`（0-100）

#### P3 — 竞品文案参考库
**目标**：将 SEMrush 采集的竞品 Ad Copies 结构化，AI 生成广告时自动引用。

功能点：
- 解析 `semrush_competitor_data.ad_copies` JSON
- 提取：标题模式 / CTA 词汇 / 价格诉求 / 情感词 / USP 结构
- 新增"竞品参考库"页面，支持按类别浏览
- 广告生成时自动拉取同类别 Top 竞品文案作为 AI 上下文

---

### 🗓 Week 2

#### P4 — 商品选品评分（投放价值分）
综合评估每个商品的投放潜力，输出 0-100 的"投放价值分"。

评分算法：
```
价值分 = 
  佣金率(%) × 商品价格($) × 0.3     # 单次转化佣金价值
+ min(评论数/1000, 1) × 20          # 市场验证（评论越多越好，上限20分）
+ 评分(1-5) × 4                     # 商品质量（4.5星=18分）
+ SEMrush付费流量热度 × 0.15        # 竞对愿意花钱=市场有利可图
+ min(cookie天数/30, 1) × 10        # Cookie越长越好
```

新增字段：`yp_us_products.investment_score`

#### P5 — 否定关键词智能推荐 + UTM 追踪标记
- 基于商品类别 + Amazon 评论高频无关词，自动推荐否定关键词
- 为每个广告变体生成唯一 UTM 参数（utm_campaign/utm_content/utm_term）

---

## 阶段二：中期新增（Week 3-4）

#### P6 — 预算追踪 + ROI 计算器
输入：广告费 + 点击数 + 转化数 + 佣金比例 + 商品均价  
输出：ROAS / 预估佣金收入 / 利润率 / 盈亏状态

#### P7 — 日报 / 周报自动生成
定时任务（每天 8:00 AM）：
- 汇总：新增商品数 / 广告方案数 / 待投放 ASIN / 数据需更新的商户
- 生成 HTML 日报页面
- 推送飞书消息

---

## 阶段三：远期 Agent 化（Month 1-2）

### Agent 架构设计

```
┌─────────────────────────────────────────────────┐
│              Ops Monitor Agent                  │  ← 总裁判，KPI考核
│          (每日巡逻 + 每周报告)                    │
└──────────┬──────────┬──────────┬────────────────┘
           │          │          │          │
    ┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌──▼──────────┐
    │ Data    │ │Product  │ │  Ad    │ │Performance  │
    │Collector│ │Analyst  │ │Creator │ │ Optimizer   │
    └─────────┘ └─────────┘ └────────┘ └─────────────┘
```

### 各 Agent 职责 + KPI

| Agent | 职责 | KPI 指标 |
|-------|------|----------|
| Data Collector | 定期检测数据新鲜度，自动触发采集 | 数据新鲜度≥95%，采集成功率≥90% |
| Product Analyst | 每日输出 Top 20 潜力商品清单 | 推荐商品实际转化率，未投放高价值品检出率 |
| Ad Creator | 自动为未投放商品生成广告方案，检测过时文案 | QS均分≥70，方案合规率100%，生成速度<5min/ASIN |
| Performance Optimizer | 解析投放数据，输出优化建议，KPI报警 | 优化建议采纳率，CTR/CPA改善幅度 |
| Ops Monitor | 监控系统健康，考核其他Agent，生成周报 | 系统可用率≥99%，日报准时率100% |

### Agent KPI 数据库
```sql
CREATE TABLE agent_kpi (
    id INT AUTO_INCREMENT PRIMARY KEY,
    agent_name VARCHAR(50),
    metric_name VARCHAR(100),
    metric_value FLOAT,
    target_value FLOAT,
    status ENUM('green','yellow','red'),
    recorded_at DATETIME
);
```

### 服务拆分规划（系统做大后）
```
gateway        :5055  ← 统一入口，反代以下服务（当前阶段保持单体）
data-service   :5001  ← 采集 + MySQL 读写 API
ads-service    :5002  ← 广告生成 + 广告管理
analytics-service :5003  ← 效果分析 + 报告生成
agent-service  :5004  ← Agent 调度 + KPI 管理
```

---

## 进度追踪

| 功能 | 状态 | 完成日期 | 备注 |
|------|------|----------|------|
| 广告优化模块 | ✅ 已完成 | 2026-03-27 | P1 最高优先 |
| 广告质量评分 | ⏳ 待开始 | 预计 2026-03-29 | |
| 竞品文案参考库 | ⏳ 待开始 | 预计 2026-03-30 | |
| 商品选品评分 | ⏳ 待开始 | 预计 2026-04-01 | |
| 否定词推荐+UTM | ⏳ 待开始 | 预计 2026-04-02 | |
| 预算追踪ROI | ⏳ 待开始 | 预计 2026-04-05 | |
| 日报周报 | ⏳ 待开始 | 预计 2026-04-07 | |
| Agent化架构 | ⏳ 待开始 | 预计 2026-04-20 | 分步实施 |
| 服务拆分 | ⏳ 待开始 | 预计 2026-05-01 | 最后阶段 |

---

> 本文档由 AI 自动维护，每完成一个功能模块自动更新状态。
> 重大决策节点会主动询问用户意见。
