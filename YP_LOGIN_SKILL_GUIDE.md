# YP 登录 Skill - 使用指南

## 📋 Skill 概述

**Skill 名称**: yp_login_skill
**Skill 版本**: v1.0
**创建日期**: 2026-03-22
**Skill 类型**: 登录/会话管理
**技术方案**: bb-browser

### 核心功能
1. ✅ 使用 bb-browser 自动化登录 YP 平台
2. ✅ 支持会话保持，避免每次重新登录
3. ✅ 自动填写用户名和密码
4. ✅ 手动输入验证码（仅首次需要）
5. ✅ 自动检查登录状态
6. ✅ 保存登录状态到本地文件

---

## 🚀 快速开始

### 安装要求

#### 1. 安装 bb-browser
```bash
# 全局安装 bb-browser
npm install -g bb-browser

# 更新社区适配器
bb-browser site update

# 验证安装
bb-browser --version
```

#### 2. 安装 Python 依赖
```bash
# 切换到项目目录
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 无需额外依赖，仅使用标准库
```

### 使用方式

#### 方式 1: 使用 Python 脚本（推荐）
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 执行登录
python yp_login_skill.py

# 检查登录状态
python yp_login_skill.py check

# 退出登录
python yp_login_skill.py logout
```

#### 方式 2: 使用批处理脚本
```bash
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 执行登录
login_with_bb_browser.bat
```

---

## 📖 详细说明

### 命令参数

| 命令 | 说明 | 示例 |
|-----|------|------|
| `python yp_login_skill.py` | 执行登录 | `python yp_login_skill.py` |
| `python yp_login_skill.py check` | 检查登录状态 | `python yp_login_skill.py check` |
| `python yp_login_skill.py logout` | 退出登录 | `python yp_login_skill.py logout` |

---

### 登录流程

#### 首次登录（需要验证码）

```
==================================================
YP 登录 Skill - 使用 bb-browser
==================================================
用户名: Tong jun
登录页面: https://www.yeahpromos.com/index/login/login
==================================================

[检查] 检查登录状态...
当前页面 URL: https://www.yeahpromos.com/index/login/login
[状态] 未登录，需要重新登录

==================================================
[1/5] 打开 YP 登录页面...
==================================================
[成功] 页面已打开，Tab ID: C74465C42256C7BA23A8FC3AE2B5970C

[填写] 正在填写用户名...
[成功] 用户名已填写: Tong jun

[填写] 正在填写密码...
[成功] 密码已填写

==================================================
[警告] 需要手动输入验证码
==================================================
1. 请查看浏览器窗口中的验证码图片
2. 在下方输入验证码并按回车
==================================================

[截图] 正在截图...
[成功] 截图已保存: C:\Users\wuhj\AppData\Local\Temp\bb-screenshot-2026-03-22T09-11-52-000Z.png

[提示] 截图已保存，您可以查看: C:\Users\wuhj\AppData\Local\Temp\bb-screenshot-2026-03-22T09-11-52-000Z.png

请输入验证码: aB3k  ← 用户在这里手动输入

[填写] 正在填写验证码: aB3k
[成功] 验证码已填写

[点击] 正在点击登录按钮...
[成功] 登录按钮已点击

[等待] 等待页面跳转...
[成功] 等待完成

[检查] 检查登录状态...
当前页面 URL: https://www.yeahpromos.com/index/index/index
[状态] 已登录

[保存] 保存登录状态...
[成功] 登录状态已保存: output/login_status.json

==================================================
[成功] 登录成功！
==================================================
1. 您现在可以使用 bb-browser 访问需要登录的页面
2. 登录状态已保存在 bb-browser 的浏览器中
3. 后续操作无需重新登录（除非会话过期）
4. 会话保持时间取决于 YP 平台的 Cookie 有效期
==================================================
```

#### 后续登录（无需验证码）

```
==================================================
YP 登录 Skill - 使用 bb-browser
==================================================
用户名: Tong jun
登录页面: https://www.yeahpromos.com/index/login/login
==================================================

[检查] 检查登录状态...
当前页面 URL: https://www.yeahpromos.com/index/index/index
[状态] 已登录

[提示] 已登录，无需重新登录

[导航] 正在导航到主页...
[成功] 已导航到主页

==================================================
[提示] 您已经登录！
==================================================
1. 可以直接访问需要登录的页面
2. 无需重新登录
3. 会话保持有效
==================================================
```

---

### 检查登录状态

```bash
python yp_login_skill.py check
```

**输出示例**:
```
==================================================
[检查] 检查登录状态...
==================================================
当前页面 URL: https://www.yeahpromos.com/index/index/index
[状态] 已登录

[状态] 已登录
```

或

```
==================================================
[检查] 检查登录状态...
==================================================
当前页面 URL: https://www.yeahpromos.com/index/login/login
[状态] 未登录，需要重新登录

[状态] 未登录
```

---

### 退出登录

```bash
python yp_login_skill.py logout
```

**输出示例**:
```
==================================================
[提示] YP 登录 Skill - 退出登录
==================================================
注意: 此操作不会清除 bb-browser 的 Cookie
如需清除 Cookie，请使用: bb-browser tab close
==================================================
```

---

## 🔧 配置说明

### 账户配置

在 `yp_login_skill.py` 中修改以下配置：

```python
class YPLoginSkill:
    def __init__(self):
        self.yp_login_url = "https://www.yeahpromos.com/index/login/login"
        self.yp_main_url = "https://www.yeahpromos.com/index/index/index"
        self.username = "Tong jun"      # 修改为您的用户名
        self.password = "Tj840618"      # 修改为您的密码
        self.tab_id = None
        self.login_status_file = "output/login_status.json"
```

### 登录状态文件

登录状态保存在 `output/login_status.json` 文件中：

```json
{
  "login_time": "2026-03-22T17:20:00",
  "username": "Tong jun",
  "login_success": true
}
```

---

## 💡 使用技巧

### 技巧 1: 避免重复登录

在每次执行数据采集之前，先检查登录状态：

```python
from yp_login_skill import YPLoginSkill

# 创建登录实例
login_skill = YPLoginSkill()

# 检查登录状态
if not login_skill.check_login_status():
    # 未登录，执行登录
    login_skill.login()
else:
    # 已登录，直接进行数据采集
    print("已登录，开始数据采集...")
```

### 技巧 2: 集成到自动化脚本

将登录检查集成到数据采集脚本中：

```python
import sys
from yp_login_skill import YPLoginSkill

def main():
    # 检查登录状态
    login_skill = YPLoginSkill()
    if not login_skill.check_login_status():
        print("未登录，正在登录...")
        if not login_skill.login():
            print("登录失败，退出")
            sys.exit(1)
    
    # 已登录，开始数据采集
    print("已登录，开始数据采集...")
    # ... 数据采集代码 ...

if __name__ == "__main__":
    main()
```

### 技巧 3: 定期检查会话保持

定期检查会话是否仍然有效：

```python
import time
from yp_login_skill import YPLoginSkill

def check_session_periodically():
    login_skill = YPLoginSkill()
    
    while True:
        is_logged_in = login_skill.check_login_status()
        print(f"会话状态: {'有效' if is_logged_in else '已失效'}")
        
        # 每小时检查一次
        time.sleep(3600)

if __name__ == "__main__":
    check_session_periodically()
```

---

## 📊 页面元素映射

### YP 登录页面元素

| 元素 | ref 值 | 说明 |
|-----|--------|------|
| 用户名输入框 | 16 | "User" |
| 密码输入框 | 17 | "Password" |
| 验证码输入框 | 18 | "Verify" |
| 登录按钮 | 21 | "Go" |
| 忘记密码链接 | 22 | "Forgot password" |

---

## ⚠️ 注意事项

### 1. 验证码问题
- ⚠️ 首次登录需要手动输入验证码
- ✅ 后续登录无需验证码（如果会话保持有效）
- ⚠️ 如果会话过期，需要重新输入验证码

### 2. 会话保持时长
- ⚠️ 会话保持时长取决于 YP 平台的 Cookie 有效期
- ⚠️ 需要实际测试确定会话保持时长
- ✅ 建议定期检查登录状态

### 3. 多浏览器实例
- ⚠️ 每个 bb-browser 浏览器实例的会话是独立的
- ⚠️ 关闭浏览器后，会话可能丢失
- ✅ 建议保持浏览器实例运行

### 4. 安全性
- ⚠️ 登录凭证保存在脚本中
- ⚠️ 不要将脚本分享给他人
- ✅ 建议使用环境变量存储密码

---

## 🐛 常见问题

### 问题 1: bb-browser 未找到

**错误信息**:
```
[错误] 命令执行失败: bb-browser
```

**解决方案**:
```bash
# 全局安装 bb-browser
npm install -g bb-browser

# 验证安装
bb-browser --version
```

---

### 问题 2: 登录失败

**错误信息**:
```
[失败] 登录失败，仍在登录页面
```

**解决方案**:
1. 检查用户名和密码是否正确
2. 检查验证码是否输入正确
3. 检查网络连接是否正常
4. 使用 `bb-browser get url` 检查当前页面

---

### 问题 3: 会话过期

**错误信息**:
```
[状态] 未登录，需要重新登录
```

**解决方案**:
```bash
# 重新登录
python yp_login_skill.py
```

---

### 问题 4: 截图失败

**错误信息**:
```
[失败] 截图失败
```

**解决方案**:
1. 检查临时目录是否有写入权限
2. 检查磁盘空间是否充足
3. 重试登录流程

---

## 📚 相关文档

- **完整SOP v2.0**: `COMPLETE_SOP_V2.md`
- **bb-browser测试指南**: `BB_BROWSER_TEST_GUIDE.md`
- **会话保持测试报告**: `SESSION_PERSISTENCE_TEST_REPORT.md`
- **浏览器方案对比**: `BROWSER_SKILL_COMPARISON.md`

---

## 🎯 总结

### 核心优势

1. ✅ **会话保持** - 一次登录，长期使用
2. ✅ **自动化** - 自动填写表单，减少人工操作
3. ✅ **简单易用** - 命令行接口，易于集成
4. ✅ **可靠稳定** - 基于成熟的 bb-browser 框架

### 适用场景

- ✅ 定期数据采集
- ✅ 长期自动化运行
- ✅ 无需人工值守的自动化任务
- ✅ 集成到定时任务系统

### 与 QQBrowserSkill 对比

| 对比维度 | QQBrowserSkill | yp_login_skill (bb-browser) |
|---------|----------------|---------------------------|
| 登录方式 | 每次都需要重新登录 | ✅ 一次登录，长期使用 |
| 验证码问题 | 每次都需要手动输入 | ✅ 首次需要，后续不需要 |
| 自动化程度 | ⭐⭐⭐☆☆ 半自动化 | ✅ ⭐⭐⭐⭐⭐ 全自动化 |
| 数据提取 | 需要自己解析 HTML | ✅ 可以直接执行 JavaScript |
| 多页面访问 | 每次都是新会话 | ✅ 会话状态共享 |

---

**创建日期**: 2026-03-22
**最后更新**: 2026-03-22
**文档版本**: v1.0
