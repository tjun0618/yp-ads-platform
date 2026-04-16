# 长期 AI 团队建设 SOP

**适用场景**：需要多个 AI 成员长期协作、各自记忆、专业分工的项目  
**作者**：基于 WorkBuddy 团队模式实践，2026-03-27

---

## 核心认知：团队模式的本质

### 系统提供了什么

WorkBuddy 的团队模式提供三样东西：

1. **异步执行**：Sub-Agent 在后台并行工作，不阻塞主 Agent
2. **身份标识**：每个成员有唯一的 `name`，可以互相发消息
3. **历史持久化**：相同 `name` 的成员被多次召唤时，对话历史会恢复（respawn 机制）

### 系统没有提供什么

- ❌ 自动的专业知识注入（需要你手动在 prompt 里告诉成员去读哪些文件）
- ❌ 可靠的消息传递（Sub-Agent 发出的消息可能丢失）
- ❌ 成员间自动协调（需要主 Agent 主动调度）
- ❌ 长期目标追踪（需要通过文件系统手动维护）

---

## 三层记忆架构

```
┌─────────────────────────────────────────────────────────┐
│  Layer 3: 知识库（Skill，最稳定）                         │
│  存放：领域专业知识、SOP、API规范、规则约束               │
│  文件：{workspace}/.workbuddy/skills/{skill-name}/SKILL.md │
│  特点：静态，手动维护，注入到上下文                       │
├─────────────────────────────────────────────────────────┤
│  Layer 2: 长期记忆（MEMORY.md，高可靠）                  │
│  存放：配置、历史决策、成功经验、已知坑                   │
│  文件：{workspace}/.workbuddy/memory/{role}/MEMORY.md    │
│  特点：动态更新，每次启动读取，append-only for daily logs │
├─────────────────────────────────────────────────────────┤
│  Layer 1: 系统历史（teams 目录，依赖系统）               │
│  存放：对话记录，自动恢复                                 │
│  目录：{workspace}/.workbuddy/teams/{team_name}/         │
│  特点：自动管理，但不可直接控制内容                       │
└─────────────────────────────────────────────────────────┘
```

**黄金法则**：**Layer 2（MEMORY.md）是最可靠的跨 session 记忆**。不要依赖 Layer 1 的自动恢复，因为历史可能很长、噪音很多。

---

## 技能（Skill）设计原则

### 什么时候写技能

当以下内容需要被多个 Agent 共享时：
- 项目配置（数据库连接、API地址）
- 操作规范（文案字符限制、代码约定）
- 常用命令（脚本路径、调试步骤）
- 域知识（评分算法、业务逻辑）

### 技能文件结构

```yaml
---
name: skill-name
description: >
  一句话描述：什么角色在什么场景下加载此技能。
---

# 技能标题

## 角色定位（可选，针对特定角色）

## 核心知识点
（密度优先，去掉废话）

## SOP 流程
（步骤清晰，包含代码示例）

## 常见坑
（避免重复踩坑）
```

### 技能粒度

| 粒度 | 适用场景 | 示例 |
|------|---------|------|
| **全团队共享** | 项目背景、数据库、API | `affiliate-team` |
| **角色专属** | 该角色的工具、流程、约束 | `ops-agent`, `ads-copywriter` |
| **任务专属** | 临时性、一次性的深度知识 | 不用写技能，直接写 prompt |

---

## 成员 prompt 模板

每次召唤团队成员时，prompt 必须包含以下四段：

```
【身份】
你是 {name}，{team-name} 团队的 {role}。

【记忆初始化】
请读取你的记忆文件：{memory-path}/MEMORY.md
如果文件不存在，说明这是你第一次工作，直接开始即可。

【技能加载】
加载技能：{skill-1}（{why-you-need-it}）
加载技能：{skill-2}（{why-you-need-it}）

【今日任务】
{具体任务，尽量精确，包含验收标准}

【完成协议】
完成后：
1. 将工作结果写入 {memory-path}/{YYYY-MM-DD}.md
2. 如果有长期价值的发现，更新 {memory-path}/MEMORY.md
3. 创建完成信号文件：.workbuddy/teams/{team}/signals/{name}_done_{task}.txt
4. send_message 给 main，说明完成情况
```

---

## 主 Agent 调度策略

### 启动团队
```python
# 主 Agent 的 Task 工具调用示例
task(
    subagent_name="research_subagent",
    name="ops-monitor",           # 固定名 → 历史可恢复
    team_name="phase3-ops",       # 固定团队名
    mode="acceptEdits",           # 允许文件写入
    prompt="""...""",             # 见上方模板
    max_turns=20
)
```

### 检查完成状态（不依赖消息）
```python
import glob, os

def check_done(team, name, task):
    signal_file = f'.workbuddy/teams/{team}/signals/{name}_done_{task}.txt'
    return os.path.exists(signal_file)

# 定时轮询（比等消息可靠10倍）
for _ in range(10):  # 最多等10分钟
    if check_done('phase3-ops', 'data-scout', 'scrape_20260327'):
        print("data-scout 完成了！")
        break
    time.sleep(60)
```

### 团队重启（保留历史）
重启团队时，只要 `team_name` 相同，成员历史自动恢复。
不需要删除团队再重建，直接再次 `team_create` 或直接 `task()` 即可。

---

## 第三阶段运营团队配置

### 技能文件位置
```
{workspace}/.workbuddy/skills/
├── affiliate-team/SKILL.md     # 所有成员必须加载
├── ops-agent/SKILL.md          # ops-monitor 专用
├── ads-copywriter/SKILL.md     # ads-optimizer 专用
└── data-scout/SKILL.md         # data-scout 专用
```

### 记忆文件位置
```
{workspace}/.workbuddy/memory/
├── MEMORY.md                   # 主 Agent 长期记忆
├── ops/MEMORY.md               # ops-monitor 记忆
├── ads/MEMORY.md               # ads-optimizer 记忆
└── scout/MEMORY.md             # data-scout 记忆
```

### 信号文件约定
```
{workspace}/.workbuddy/teams/phase3-ops/signals/
└── {name}_done_{task}_{date}.txt
```

---

## 运营节奏建议

| 频率 | 谁做 | 做什么 |
|------|------|-------|
| 每天早上 | 你（主 Agent） | 询问 ops-monitor 系统状态 |
| 每天 | ops-monitor（计划任务） | 自动监控 + 日报 |
| 每周一 | data-scout | 完整数据采集 + 评分更新 |
| 每周三 | ads-optimizer | QS审查 + 低分广告重做 |
| 每周五 | 你（主 Agent） | 汇总本周数据，规划下周 |

---

## 已知限制与规避

| 限制 | 规避方法 |
|------|---------|
| 消息丢失率高 | 用文件信号替代消息确认 |
| Sub-Agent 上下文有限 | MEMORY.md 精简，只存高价值信息 |
| 历史对话噪音多 | 每次 prompt 主动提示"读 MEMORY.md 作为你的记忆基准" |
| 无法主动唤醒 | 主 Agent 定期（每次对话开始时）检查 signal 文件 |
