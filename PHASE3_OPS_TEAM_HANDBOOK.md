# 第三阶段：运营团队 — 启动手册

## 团队概述

第三阶段从"建设"转向"运营"：
- **第一阶段**（已完成）：基础设施 — 数据库、采集脚本、Flask 管理平台
- **第二阶段**（已完成）：广告系统 — 广告生成、QS评分、竞品分析、优化模块
- **第三阶段**（当前）：运营闭环 — 日常监控、广告优化、选品迭代、ROI追踪

---

## 团队成员配置

### 成员1：ops-monitor（运营监控员）
**专属技能**：`ops-agent`（系统健康、飞书推送、日报）  
**记忆文件**：`.workbuddy/memory/ops/MEMORY.md`  
**主要职责**：
- 每天检查系统健康状态（MySQL / Flask / 计划任务）
- 生成并推送日报
- 监控数据新鲜度，触发采集任务

**召唤提示词**：
```
你是 ops-monitor，联盟营销运营团队的系统监控员。
请读取你的记忆文件：C:\Users\wuhj\WorkBuddy\20260322085355\.workbuddy\memory\ops\MEMORY.md
加载技能：ops-agent（了解监控脚本和飞书配置）
加载技能：affiliate-team（了解项目全景和数据库结构）

今日任务：[具体任务描述]

完成后：
1. 将结果写入今日日志 .workbuddy/memory/ops/YYYY-MM-DD.md
2. 更新 MEMORY.md 中的相关配置
3. 发消息告知 main：任务完成，并说明做了什么
```

---

### 成员2：ads-optimizer（广告优化员）
**专属技能**：`ads-copywriter`（文案创作、QS优化）  
**记忆文件**：`.workbuddy/memory/ads/MEMORY.md`  
**主要职责**：
- 为高分商品制作广告文案
- 对现有广告进行 QS 评分分析
- 根据搜索词报告优化出价和文案

**召唤提示词**：
```
你是 ads-optimizer，联盟营销运营团队的广告优化员。
请读取你的记忆文件：C:\Users\wuhj\WorkBuddy\20260322085355\.workbuddy\memory\ads\MEMORY.md
加载技能：ads-copywriter（了解文案规范和QS优化方法）
加载技能：affiliate-team（了解项目结构和API）

今日任务：[具体任务描述]

完成后：
1. 将优化结果写入今日日志 .workbuddy/memory/ads/YYYY-MM-DD.md
2. 如果有新的高效文案模式，更新 MEMORY.md
3. 发消息告知 main：任务完成
```

---

### 成员3：data-scout（数据侦察员）
**专属技能**：`data-scout`（采集、评分、分析）  
**记忆文件**：`.workbuddy/memory/scout/MEMORY.md`  
**主要职责**：
- 定期执行数据采集脚本
- 更新商品 investment_score
- 挖掘新的高价值商品和商户

**召唤提示词**：
```
你是 data-scout，联盟营销运营团队的数据侦察员。
请读取你的记忆文件：C:\Users\wuhj\WorkBuddy\20260322085355\.workbuddy\memory\scout\MEMORY.md
加载技能：data-scout（了解采集脚本和评分算法）
加载技能：affiliate-team（了解数据库结构）

今日任务：[具体任务描述]

完成后：
1. 将采集结果写入今日日志 .workbuddy/memory/scout/YYYY-MM-DD.md
2. 如果发现新的高价值商户/商品，更新 MEMORY.md
3. 发消息告知 main：任务完成，数据概览
```

---

## 长期团队的核心机制

### 1. 持久化原理

WorkBuddy 团队模式的持久化依赖两层机制：

**系统级持久化（自动）**：
- 每个 Sub-Agent 的对话历史保存在 `{workspace}/.workbuddy/teams/{team_name}/` 目录
- 当同名成员再次被召唤（respawn）时，历史对话自动恢复
- 这意味着：只要使用相同的 `name` 参数召唤，成员就能"记得"之前的工作

**应用级持久化（主动维护）**：
- 每个成员有自己的 `.workbuddy/memory/{role}/MEMORY.md`
- 每次工作后必须 append 到今日日志文件
- **这是最可靠的记忆机制**，不依赖系统是否保存历史

### 2. 技能注入原理

技能（Skill）= 提前写好的专业知识 + SOP，以 Markdown 文件形式存储。

当 Agent 任务提示词中包含"加载技能：xxx"时，该技能的 SKILL.md 内容会被注入到上下文。

**项目级技能**（存放在 `{workspace}/.workbuddy/skills/`）：
- `affiliate-team`：全团队共享的基础知识
- `ops-agent`：运营监控专用知识
- `ads-copywriter`：广告文案专用知识
- `data-scout`：数据采集专用知识

### 3. 消息可靠性问题（已知限制）

Sub-Agent 发送 `send_message` 后，主 Agent 不一定能收到。

**改进方案（使用文件作为完成信号）**：
```python
# Sub-Agent 任务完成后，写入完成标记文件
with open('.workbuddy/teams/phase3/signals/{name}_done_{date}.txt', 'w') as f:
    f.write(f"completed: {task_summary}\n")
```

主 Agent 检查：
```python
import glob
signals = glob.glob('.workbuddy/teams/phase3/signals/*_done_*.txt')
```

---

## 日常运营工作流

### 每日例行任务（自动）

| 时间 | 任务 | 执行者 |
|------|------|--------|
| 06:00 | 更新 Top50 investment_score | 计划任务 |
| 08:00 | 生成日报 HTML | 计划任务 |
| 每5分钟 | 系统监控 | 计划任务 |

### 每日人工触发任务

召唤 ops-monitor 时，告知：
- 检查昨日日报内容
- 确认所有计划任务正常运行
- 如果有告警，分析原因并修复

### 每周任务

1. **data-scout**：完整数据采集（YP + Amazon + 关键词）
2. **ads-optimizer**：审查 QS < 60 的广告，重新生成
3. **ops-monitor**：清理7天前的临时文件

### 选品迭代节奏

每周由 data-scout 提交 Top 10 新商品候选，ads-optimizer 为其制作广告方案。

---

## 召唤模板（即用版）

### 快速运营检查

```
召唤 ops-monitor（团队名：phase3-ops）：

你是 ops-monitor。
读取记忆：.workbuddy/memory/ops/MEMORY.md
今日任务：检查系统健康并汇报
1. Flask 服务是否正常（GET http://localhost:5055/api/ads/scores）
2. 计划任务是否按时执行（schtasks /query /fo CSV | Select-String "Affiliate"）
3. 最新日报是否已生成（检查 logs/ 目录）
完成后写日志并 send_message 给 main。
```

### 为新商品制作广告

```
召唤 ads-optimizer（团队名：phase3-ops）：

你是 ads-optimizer。
读取记忆：.workbuddy/memory/ads/MEMORY.md
今日任务：为 ASIN=B0XXXXXXXX 制作完整广告方案
1. 通过 GET http://localhost:5055/api/ads/B0XXXXXXXX 查看现有方案
2. 查询关键词：SELECT keyword FROM google_suggest_keywords WHERE asin='B0XXXXXXXX' LIMIT 20
3. 生成 15条标题 + 4条描述 + 4条 Sitelink + 6条 Callout
4. 写入 ads_ads 表，调用 POST /api/ads/score/B0XXXXXXXX 打分
5. QS < 80 时继续优化直到达标
完成后写日志并 send_message 给 main。
```

### 数据采集

```
召唤 data-scout（团队名：phase3-ops）：

你是 data-scout。
读取记忆：.workbuddy/memory/scout/MEMORY.md
今日任务：执行完整数据采集并更新评分
1. 运行 python -X utf8 score_products.py --all
2. 查询新的高分商品：SELECT asin, investment_score FROM yp_us_products WHERE investment_score >= 60 ORDER BY investment_score DESC LIMIT 10
3. 检查这些商品是否已有广告方案（SELECT asin FROM ads_plans WHERE plan_status='completed'）
4. 将没有广告方案的高分商品 ASIN 列表报告给 main
完成后写日志并 send_message 给 main。
```

---

## 第三阶段 Roadmap

### P1 — 投放 ROI 追踪（最高优先级）
- 目标：从 Google Ads 导入实际花费和转化数据
- 输出：每个 ASIN 的 ROAS（广告支出回报率）
- 新增表：`google_ads_performance`（date, asin, spend, clicks, conversions）

### P2 — 自动选品优化
- 目标：基于实际 ROAS 反向优化 investment_score 权重
- 输出：更准确的商品优先级排序

### P3 — 飞书日报推送
- 目标：完善飞书 user_id 授权，实现真实推送
- 输出：每天早上收到运营日报消息

### P4 — 关键词出价建议
- 目标：根据竞品出价和商品 margin 自动建议 CPC 出价
- 输出：每个关键词的建议出价范围
