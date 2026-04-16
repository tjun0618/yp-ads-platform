# 第二阶段开发运维团队 — 启动手册

**团队名称**：`phase2-dev`  
**用途**：亚马逊联盟营销管理平台（ads_manager.py）长期迭代开发与运维  
**工作目录**：`C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\`

---

## 团队成员

| 成员名 | 角色 | 专属 Skill | 记忆文件 |
|--------|------|-----------|---------|
| `backend-engineer` | 后端工程师 | `backend-engineer` | `.workbuddy/memory/backend/MEMORY.md` |
| `frontend-engineer` | 前端工程师 | `frontend-engineer` | `.workbuddy/memory/frontend/MEMORY.md` |
| `devops-engineer` | 运维工程师 | `devops-engineer` | `.workbuddy/memory/devops/MEMORY.md` |

**共享 Skill（所有成员必须加载）**：`platform-dev-team`

---

## 快速召唤模板

### 召唤后端工程师

```
请加载 platform-dev-team 和 backend-engineer 技能，
读取 .workbuddy/memory/backend/MEMORY.md，
然后执行以下任务：

[任务描述]
```

### 召唤前端工程师

```
请加载 platform-dev-team 和 frontend-engineer 技能，
读取 .workbuddy/memory/frontend/MEMORY.md，
然后执行以下任务：

[任务描述]
```

### 召唤运维工程师

```
请加载 platform-dev-team 和 devops-engineer 技能，
读取 .workbuddy/memory/devops/MEMORY.md，
然后执行以下任务：

[任务描述]
```

### 召唤全团队（并行）

```
[在新对话中用 Task 工具并行召唤，team_name="phase2-dev"]

Task 1 — backend-engineer:
  name: "backend-engineer"
  team_name: "phase2-dev"
  prompt: "加载 platform-dev-team 和 backend-engineer 技能，读取记忆文件，执行：[后端任务]"

Task 2 — frontend-engineer:
  name: "frontend-engineer"
  team_name: "phase2-dev"
  prompt: "加载 platform-dev-team 和 frontend-engineer 技能，读取记忆文件，执行：[前端任务]"

Task 3 — devops-engineer:
  name: "devops-engineer"
  team_name: "phase2-dev"
  prompt: "加载 platform-dev-team 和 devops-engineer 技能，读取记忆文件，执行：[运维任务]"
```

---

## 任务分配指南

### 哪些任务给后端工程师
- Flask 新路由开发（/new_feature）
- 数据库表结构变更、新建表
- 采集脚本（scrape_*.py）的修改和调试
- 广告生成算法（generate_ads.py）优化
- JSON API 接口开发
- 性能问题排查（SQL 慢查询）

### 哪些任务给前端工程师
- 新页面 UI 实现（render_template_string）
- 现有页面交互优化（按钮、弹窗、Toast）
- 数据可视化（Chart.js 图表）
- 用户体验改进（Loading 状态、错误提示）
- 响应式布局调整

### 哪些任务给运维工程师
- Windows 计划任务（新增/修改/删除）
- 监控阈值调整（monitor.py）
- 日志分析（flask_err.txt 报错排查）
- 数据备份和恢复
- 磁盘清理、调试文件整理
- sync_merchants.py 脚本实现（最高优先级）

---

## 迭代开发工作流

### 标准功能开发流程
```
1. 需求明确 → 分配给对应角色
2. 后端先行 → backend-engineer 开发 API/路由
3. 前端接入 → frontend-engineer 开发 UI
4. 运维验收 → devops-engineer 检查部署状态
5. 写入信号 → {member}_done_{task_id}.txt
6. 更新记忆 → 各自 MEMORY.md 追加工作日志
```

### Hotfix 流程（紧急修复）
```
1. 确认问题 → devops-engineer 分析日志
2. 定位代码 → backend-engineer 或 frontend-engineer 修复
3. 快速验证 → 访问 http://localhost:5055 确认
4. 记录根因 → 追加到对应 MEMORY.md
```

---

## 当前迭代待办（Backlog）

### P0（最高优先级）
- [ ] **sync_merchants.py 实现**：AffiliateMerchantSync 计划任务的核心脚本
  - 负责：devops-engineer + backend-engineer
  - 功能：定期从 YP API 同步商户数据到 MySQL

### P1（高优先级）
- [ ] **飞书告警 user_id 配置**：让 monitor.py 真正能推送告警
  - 负责：devops-engineer
  - 前置：用户提供飞书 user_id
- [ ] **首页骨架屏**：改善大数据量时的加载体验
  - 负责：frontend-engineer

### P2（中优先级）
- [ ] **ads_manager.py 拆分**：按功能模块拆分为 Flask Blueprint
  - 负责：backend-engineer
  - 风险：高，需完整测试
- [ ] **广告文案一键复制**：广告详情页增加复制按钮
  - 负责：frontend-engineer

### P3（低优先级）
- [ ] **调试文件清理**：整理 `_test_*.py`、`debug_*.py`、`_check_*.py`
  - 负责：devops-engineer
- [ ] **移动端适配**：最小支持 768px
  - 负责：frontend-engineer

---

## 长期记忆维护规则

### 每次工作后必须
1. 将本次关键决策、踩坑、代码位置追加到自己的 `MEMORY.md`
2. 写入任务完成信号：`.workbuddy/teams/phase2-dev/signals/{name}_done_{task}.txt`
3. 如果修改了数据库结构或新增了重要路由，同步更新 `platform-dev-team/SKILL.md`

### 每月定期维护
1. 将 30 天前的日志条目从 MEMORY.md 蒸馏为摘要
2. 删除已完成任务的信号文件
3. 归档调试脚本到 `_archive/` 目录

---

## 团队协作与主 Agent 关系

- 主 Agent（你正在对话的 AI）是**产品经理 + 架构师**角色
- 主 Agent 负责：需求拆解、任务分配、成果验收、最终决策
- 团队成员负责：专业领域内的具体执行
- **消息传递不可靠**，以文件系统（信号文件）为唯一完成确认
- 主 Agent 可以直接检查信号文件来确认成员完成状态

---

*创建时间：2026-03-27*  
*下次更新：每次重大迭代完成后*
