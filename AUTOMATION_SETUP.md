# YP 自动化采集系统配置指南

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    YP 自动化采集系统                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │  yp_auto_refresh │ ───→ │ new_approved_    │                │
│  │  .py (定时运行)   │      │ merchants.json   │                │
│  │  每6小时运行一次  │      │ (新商户列表)      │                │
│  └──────────────────┘      └────────┬─────────┘                │
│           │                          │                          │
│           ↓                          ↓                          │
│  ┌──────────────────┐      ┌──────────────────┐                │
│  │ us_merchants_    │      │ incremental_     │                │
│  │ clean.json       │ ←─── │ collect.py       │                │
│  │ (更新状态)        │      │ (自动触发采集)    │                │
│  └──────────────────┘      └────────┬─────────┘                │
│                                     │                          │
│                                     ↓                          │
│                          ┌──────────────────┐                │
│                          │ 飞书多维表格      │                │
│                          │ (自动追加数据)    │                │
│                          └──────────────────┘                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 文件说明

| 文件 | 功能 |
|------|------|
| `yp_auto_refresh.py` | 定时刷新商户状态，发现新通过商户 |
| `incremental_collect.py` | 增量采集新商户的商品数据 |
| `run_refresh.bat` | Windows 批处理，用于计划任务 |
| `new_approved_merchants.json` | 新通过商户列表（自动生成） |
| `refresh_log.json` | 刷新历史记录 |
| `incremental_state.json` | 增量采集状态 |

## 设置 Windows 计划任务

### 方法 1：使用任务计划程序 GUI

1. **打开任务计划程序**
   - 按 `Win + R`，输入 `taskschd.msc`，回车

2. **创建基本任务**
   - 右侧点击 "创建基本任务..."
   - 名称：`YP_Auto_Refresh_Merchants`
   - 描述：`每6小时自动刷新YP商户状态并采集新商户数据`

3. **设置触发器**
   - 选择 "每天"
   - 开始时间：`00:00:00`
   - 勾选 "重复任务间隔"
   - 设置为：`6 小时`
   - 持续时间：`1 天`

4. **设置操作**
   - 选择 "启动程序"
   - 程序/脚本：`c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\run_refresh.bat`

5. **完成**
   - 勾选 "打开属性对话框"
   - 点击 "完成"

6. **修改属性（重要）**
   - 在 "常规" 选项卡：
     - 勾选 "使用最高权限运行"
     - 配置：选择 "Windows 10"
   - 在 "条件" 选项卡：
     - 取消勾选 "只有在计算机使用交流电源时才启动"
   - 点击 "确定"

### 方法 2：使用 PowerShell 命令（管理员）

以管理员身份运行 PowerShell：

```powershell
$action = New-ScheduledTaskAction -Execute "c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu\run_refresh.bat"
$trigger = New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 365)
$settings = New-ScheduledTaskSettingsSet -RunOnlyIfNetworkAvailable -StartWhenAvailable
Register-ScheduledTask -TaskName "YP_Auto_Refresh_Merchants" -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force
```

## 工作流程

### 1. 定时刷新（每6小时）

```
yp_auto_refresh.py 执行流程：
1. 加载当前商户数据
2. 调用 YP API 获取最新商户列表
3. 对比新旧数据，找出新通过的商户
4. 保存更新后的商户数据
5. 记录刷新日志
6. 如果有新商户 → 触发增量采集
```

### 2. 增量采集（自动触发）

```
incremental_collect.py 执行流程：
1. 读取新商户列表
2. 连接调试 Chrome（需提前启动）
3. 逐个访问新商户的品牌页
4. 下载 Excel 或解析页面获取商品
5. 上传到飞书多维表格
6. 保存采集状态
```

## 监控和日志

### 查看刷新日志

```powershell
cd "c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu"
python -c "import json; d=json.load(open('output/refresh_log.json')); print(json.dumps(d[-3:], indent=2, ensure_ascii=False))"
```

### 查看增量采集状态

```powershell
cd "c:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu"
python -c "import json; d=json.load(open('output/incremental_state.json')); print(f\"已完成: {len(d['completed_mids'])} 个商户, 商品: {len(d['products'])} 条\")"
```

### 查看计划任务状态

```powershell
schtasks /query /tn "YP_Auto_Refresh_Merchants" /v
```

## 注意事项

1. **Chrome 必须保持运行**
   - 调试模式 Chrome 需要一直运行
   - 如果 Chrome 关闭，增量采集会失败
   - 建议设置 Chrome 开机自启

2. **YP 登录状态**
   - 如果 YP 登录过期，脚本会等待 60 秒后重试
   - 建议定期检查 Chrome 中的登录状态

3. **飞书表格**
   - 自动使用已有的飞书表格配置
   - 新数据会自动追加到现有表格

4. **手动触发**
   - 随时可以手动运行刷新：
     ```
     python yp_auto_refresh.py
     ```
   - 随时可以手动运行增量采集：
     ```
     python incremental_collect.py
     ```

## 故障排查

### 问题：计划任务没有运行

1. 检查任务是否启用：`schtasks /query /tn "YP_Auto_Refresh_Merchants"`
2. 查看上次运行时间和结果
3. 检查日志文件：`output/refresh_log.json`

### 问题：增量采集失败

1. 检查 Chrome 是否以调试模式运行
2. 检查 YP 是否已登录
3. 查看增量采集日志：`output/incremental_state.json`

### 问题：飞书上传失败

1. 检查飞书配置：`output/feishu_table_config.json`
2. 检查网络连接
3. 检查飞书应用权限

## 建议的运行频率

| 场景 | 建议频率 |
|------|----------|
| 新商户申请频繁 | 每 2-4 小时 |
| 正常运营 | 每 6-12 小时 |
| 低频检查 | 每天 1-2 次 |

当前设置为：**每 6 小时**
