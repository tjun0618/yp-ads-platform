# 步骤1：打开YP平台并登录 - 详细操作指南

**文档版本**: v1.0  
**创建日期**: 2026-03-22  
**步骤状态**: ✅ 已完成并验证

---

## 📋 目录

1. [步骤概述](#步骤概述)
2. [问题1：调用哪个浏览器skill？](#问题1调用哪个浏览器skill)
3. [问题2：登录验证问题及解决方案](#问题2登录验证问题及解决方案)
4. [完整操作流程](#完整操作流程)
5. [验证与检查](#验证与检查)
6. [常见问题](#常见问题)

---

## 步骤概述

**目标**: 使用浏览器自动化工具打开YP平台并完成登录

**核心问题**:
1. 应该调用哪个浏览器skill？
2. 如何解决验证码问题？如何让用户参与？

**解决方案**:
- 使用 **QQBrowserSkill** 进行浏览器自动化
- 采用 **"自动化+人工干预"** 的混合方案处理验证码

---

## 问题1：调用哪个浏览器skill？

### 1.1 可用的浏览器技能

在当前环境中，我们有多个浏览器自动化技能可用：

| 技能名称 | 描述 | 推荐度 |
|---------|------|--------|
| **QQBrowserSkill** | 专门针对360浏览器的自动化工具 | ⭐⭐⭐⭐⭐ **推荐** |
| Playwright | 通用的浏览器自动化框架 | ⭐⭐⭐⭐ |
| Selenium | 传统的浏览器自动化工具 | ⭐⭐⭐ |

### 1.2 为什么选择QQBrowserSkill？

**优势**:
1. **系统原生支持**
   - 用户的默认浏览器是360浏览器
   - QQBrowserSkill专门为360浏览器优化
   - 无需额外安装浏览器驱动

2. **简单易用**
   - 提供简洁的命令行接口
   - 无需编写复杂的浏览器控制代码
   - 通过PowerShell直接调用

3. **稳定可靠**
   - 已在用户环境中安装和配置
   - 经过实际测试验证
   - 与WorkBuddy系统集成良好

4. **功能完整**
   - 支持页面导航
   - 支持表单填写
   - 支持元素点击
   - 支持页面内容提取

### 1.3 QQBrowserSkill的安装路径

```bash
# QQBrowserSkill可执行文件路径
C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe
```

### 1.4 QQBrowserSkill常用命令

| 命令 | 说明 | 使用场景 |
|-----|------|---------|
| `browser_go_to_url` | 导航到指定URL | 打开登录页面 |
| `browser_input_text` | 填写文本输入框 | 填写用户名、密码、验证码 |
| `browser_click_element` | 点击页面元素 | 点击登录按钮 |
| `browser_get_info` | 获取页面信息 | 检查当前URL、页面标题 |
| `browser_snapshot` | 获取页面快照 | 查看页面元素结构 |
| `browser_markdownify` | 提取页面内容为Markdown | 提取商家数据 |

**命令示例**:
```bash
# 打开登录页面
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/login/login

# 填写用户名
qqbrowser-skill.exe browser_input_text --index 22 --text "Tong jun"

# 填写密码
qqbrowser-skill.exe browser_input_text --index 23 --text "Tj840618"

# 点击登录按钮
qqbrowser-skill.exe browser_click_element --index 29

# 获取当前URL
qqbrowser-skill.exe browser_get_info --type url
```

### 1.5 通过Python调用QQBrowserSkill

**方法1：使用subprocess（推荐）**
```python
import subprocess

# 构建命令
command = 'browser_go_to_url --url https://www.yeahpromos.com/index/login/login'
qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"

# 通过PowerShell执行
full_command = f'& "{qqbrowser_path}" {command}'
result = subprocess.run(
    ['powershell', '-Command', full_command],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='ignore',
    timeout=30
)

# 检查结果
if result.returncode == 0:
    print("✅ 命令执行成功")
    print(result.stdout)
else:
    print("❌ 命令执行失败")
    print(result.stderr)
```

**方法2：封装为类（项目中使用）**
```python
class BrowserController:
    """浏览器控制器"""
    
    def __init__(self):
        self.qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
    
    def run_command(self, command: str) -> dict:
        """运行QQBrowserSkill命令"""
        full_command = f'& "{self.qqbrowser_path}" {command}'
        result = subprocess.run(
            ['powershell', '-Command', full_command],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            timeout=30
        )
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    
    def navigate_to_url(self, url: str) -> bool:
        """导航到指定URL"""
        result = self.run_command(f'browser_go_to_url --url {url}')
        return result['success']
    
    def input_text(self, index: int, text: str) -> bool:
        """填写文本输入框"""
        result = self.run_command(f'browser_input_text --index {index} --text "{text}"')
        return result['success']
    
    def click_element(self, index: int) -> bool:
        """点击元素"""
        result = self.run_command(f'browser_click_element --index {index}')
        return result['success']
```

---

## 问题2：登录验证问题及解决方案

### 2.1 YP平台登录机制分析

#### 2.1.1 登录页面URL
```
https://www.yeahpromos.com/index/login/login
```

#### 2.1.2 登录流程

```
┌─────────────────────────────────────────────────────┐
│ 1. 打开登录页面                                    │
│    URL: https://www.yeahpromos.com/index/login/login│
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 2. 输入用户名                                      │
│    字段：用户名输入框（第一个文本框）               │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 3. 点击 NEXT 按钮                                   │
│    动作：点击"下一步"按钮                           │
│    作用：切换到密码输入步骤                          │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 4. 输入密码                                        │
│    字段：密码输入框（第二个文本框）                 │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 5. 输入验证码 ⚠️                                  │
│    字段：验证码输入框（第三个文本框）               │
│    类型：图形验证码（4位字符）                      │
│    ⚠️ 关键：验证码每次都是动态生成的               │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 6. 点击登录按钮                                    │
│    动作：点击"登录"按钮                             │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 7. 等待登录验证                                    │
│    - 验证成功：跳转到主页                           │
│    - 验证失败：显示错误提示，重新输入               │
└─────────────────────────────────────────────────────┘
```

#### 2.1.3 验证码特征

**类型**: 图形验证码
**长度**: 4位字符（数字+字母混合）
**有效期**: 约5分钟
**特点**: 
- 每次刷新页面都会生成新的验证码
- 验证码图片是动态生成的
- 难以通过OCR自动识别
- 输错3次可能触发账号锁定

### 2.2 验证码解决方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐度 |
|-----|------|------|------|--------|
| **手动输入** ⭐ | 用户查看验证码并手动输入 | - 100%准确<br>- 成本为0<br>- 简单可靠 | - 需要用户介入<br>- 无法完全自动化 | ⭐⭐⭐⭐⭐ **推荐** |
| OCR识别 | 使用图像识别技术自动识别验证码 | - 可以完全自动化<br>- 减少用户干预 | - 准确率不确定（70-90%）<br>- 需要额外库<br>- 可能识别失败 | ⭐⭐⭐ |
| 第三方打码平台 | 使用付费服务识别验证码 | - 准确率高（95%+）<br>- 完全自动化 | - 需要付费<br>- 需要注册账号<br>- 存在延迟 | ⭐⭐ |
| 绕过验证码 | 尝试找到验证码绕过漏洞 | - 理论上最完美 | - 难度极高<br>- 可能违反服务条款<br>- 可能被封号 | ⭐ 不推荐 |

### 2.3 为什么选择"手动输入"方案？

**核心理由**:

1. **可靠性最高**
   - 人类识别验证码的准确率接近100%
   - 避免了OCR识别错误导致的问题
   - 不会因为验证码识别失败而中断流程

2. **成本最低**
   - 无需购买第三方服务
   - 无需安装额外的OCR库
   - 无需维护复杂的识别逻辑

3. **简单易实现**
   - 只需要等待用户输入
   - 代码逻辑非常简单
   - 易于维护和调试

4. **用户体验好**
   - 用户可以亲眼看到验证码
   - 可以处理模糊或难识别的验证码
   - 可以在失败时重新输入

### 2.4 混合方案：自动化+人工干预

**方案设计**:
```
┌─────────────────────────────────────────────────────┐
│ 自动化部分（由脚本自动完成）                          │
│                                                     │
│ 1. 打开浏览器                                        │
│ 2. 导航到登录页面                                    │
│ 3. 自动填写用户名                                    │
│ 4. 自动点击NEXT按钮                                  │
│ 5. 自动填写密码                                      │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 人工干预部分（需要用户参与）                          │
│                                                     │
│ ⚠️ 脚本暂停，提示用户输入验证码                        │
│                                                     │
│ 用户操作：                                           │
│ 1. 在浏览器中查看验证码图片                           │
│ 2. 在控制台输入验证码                                │
│ 3. 按回车确认                                        │
└──────────────┬────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────┐
│ 自动化部分（由脚本自动完成）                          │
│                                                     │
│ 6. 自动填写验证码到输入框                            │
│ 7. 自动点击登录按钮                                  │
│ 8. 自动检查登录是否成功                              │
└─────────────────────────────────────────────────────┘
```

**代码实现**:
```python
def input_captcha_manually(self) -> bool:
    """手动输入验证码"""
    print("\n" + "="*50)
    print("⚠️  需要手动输入验证码")
    print("1. 请在浏览器中查看验证码图片")
    print("2. 在下方输入验证码并按回车")
    print("="*50)
    
    # 等待用户输入
    captcha_code = input("请输入验证码: ").strip()
    
    if not captcha_code:
        print("❌ 未输入验证码")
        return False
    
    # 自动填写验证码到输入框
    print(f"正在填写验证码: {captcha_code}")
    result = self.run_command(f'browser_input_text --index 25 --text "{captcha_code}"')
    time.sleep(0.5)
    
    if result['success']:
        print("✅ 验证码已填写")
        return True
    else:
        print("❌ 验证码填写失败")
        return False
```

### 2.5 用户交互流程

**步骤1: 脚本自动打开登录页面**
```
[1/5] 打开登录页面...
✅ 登录页面已打开
```

**步骤2: 脚本自动填写用户名**
```
[2/5] 填写登录信息...
正在填写用户名: Tong jun
✅ 用户名已填写
```

**步骤3: 脚本自动填写密码**
```
正在填写密码: Tj840618
✅ 密码已填写
```

**步骤4: 脚本暂停，等待用户输入验证码**
```
==================================================
⚠️  需要手动输入验证码
1. 请在浏览器中查看验证码图片
2. 在下方输入验证码并按回车
==================================================

请输入验证码: 
```

**用户操作**:
1. 查看浏览器窗口中的验证码图片
2. 在控制台输入看到的验证码（例如：`aB3k`）
3. 按回车键确认

**步骤5: 脚本继续自动填写验证码**
```
正在填写验证码: aB3k
✅ 验证码已填写
```

**步骤6: 脚本自动点击登录按钮**
```
[4/5] 提交登录...
✅ 登录已提交
```

**步骤7: 脚本自动检查登录状态**
```
[5/5] 检查登录状态...
当前页面 URL: https://www.yeahpromos.com/index/index/index
✅ 登录成功！
```

### 2.6 处理登录失败的情况

**场景1: 验证码输入错误**
```
❌ 登录失败，仍在登录页面
提示: 验证码可能输入错误，请重新输入

是否重新输入验证码？(y/n): y
```

**解决方案**:
- 脚本提示用户重新输入
- 用户刷新页面获取新验证码
- 重新执行验证码输入流程

**场景2: 验证码已过期**
```
❌ 登录失败，验证码已过期
提示: 验证码有效期为5分钟，请刷新页面获取新验证码
```

**解决方案**:
- 用户点击浏览器刷新按钮
- 获取新的验证码
- 重新输入

**场景3: 多次输入失败**
```
❌ 登录失败，已输入错误3次
提示: 账号可能被临时锁定，请稍后重试
```

**解决方案**:
- 等待5-10分钟后重试
- 或联系YP平台客服解锁账号

### 2.7 增强用户体验

**提示1: 清晰的进度显示**
```python
print("\n" + "="*60)
print("YP 平台登录流程")
print("="*60)
print(f"[1/6] 打开登录页面... {status}")
print(f"[2/6] 填写用户名... {status}")
print(f"[3/6] 填写密码... {status}")
print(f"[4/6] 输入验证码... {status}")
print(f"[5/6] 提交登录... {status}")
print(f"[6/6] 检查登录状态... {status}")
print("="*60)
```

**提示2: 倒计时提醒**
```python
import time

print("\n验证码将在 5 秒后过期...")
for i in range(5, 0, -1):
    print(f"剩余时间: {i} 秒", end='\r')
    time.sleep(1)
print("\n验证码可能已过期，建议刷新页面")
```

**提示3: 错误重试机制**
```python
def login_with_retry(self, username: str, password: str, max_retries: int = 3):
    """带重试的登录"""
    for attempt in range(1, max_retries + 1):
        print(f"\n第 {attempt} 次尝试登录...")
        
        # 执行登录流程
        success = self.perform_login(username, password)
        
        if success:
            print(f"✅ 登录成功！")
            return True
        
        print(f"❌ 登录失败")
        
        if attempt < max_retries:
            print(f"是否重试？(y/n): ", end='')
            user_choice = input().strip().lower()
            
            if user_choice != 'y':
                break
            
            print("请刷新页面获取新验证码...")
            input("按回车键继续...")
    
    print(f"❌ 已尝试 {max_retries} 次，登录失败")
    return False
```

---

## 完整操作流程

### 3.1 准备工作

#### 3.1.1 环境检查

**检查1: QQBrowserSkill是否已安装**
```bash
# 检查QQBrowserSkill路径
dir "C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"

# 预期输出：应该看到文件存在
```

**检查2: 360浏览器是否已安装**
```bash
# 检查360浏览器路径
dir "C:\Program Files (x86)\360\360se6\360se.exe"

# 或检查
dir "C:\Program Files\360\360se6\360se.exe"
```

**检查3: 网络连接**
```bash
# 测试YP平台连接
ping www.yeahpromos.com

# 预期输出：能够正常ping通
```

**检查4: 登录凭证**
```
用户名: Tong jun
密码: Tj840618
```

### 3.2 执行登录

#### 方式1: 使用完整脚本（推荐）

**脚本文件**: `auto_collect_with_qqbrowser.py` 或 `simple_collect.py`

**执行步骤**:
```bash
# 1. 切换到项目目录
cd C:\Users\wuhj\WorkBuddy\20260322085355\yp_to_feishu

# 2. 运行脚本
python simple_collect.py

# 3. 脚本会自动执行以下流程
#    - 打开浏览器
#    - 导航到登录页面
#    - 填写用户名和密码
#    - 等待用户输入验证码 ⚠️
#    - 提交登录
#    - 检查登录状态
```

**控制台输出示例**:
```
==================================================
YP 数据采集工具（使用 QQBrowserSkill）
==================================================

[1/5] 打开登录页面...
      OK: 登录页面已打开

[2/5] 填写登录信息...
      OK: 用户名和密码已填写

[3/5] 等待验证码输入...
      请在浏览器中查看验证码图片
      请输入验证码: aB3k
      OK: 验证码已填写

[4/5] 提交登录...
      OK: 登录已提交

[5/5] 检查登录状态...
      OK: 登录成功！

==================================================
提示:
  - 如果登录成功，请继续下一步
  - 如果登录失败，请手动在浏览器中完成登录
  - 然后输入 'ok' 继续
==================================================

输入 'ok' 开始采集，或 'q' 退出: ok
```

#### 方式2: 手动执行（了解原理）

**步骤1: 打开浏览器并导航到登录页**
```bash
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/login/login
```

**步骤2: 填写用户名**
```bash
qqbrowser-skill.exe browser_input_text --index 22 --text "Tong jun"
```

**步骤3: 填写密码**
```bash
qqbrowser-skill.exe browser_input_text --index 23 --text "Tj840618"
```

**步骤4: 手动查看并输入验证码**
```
（用户在浏览器中看到验证码图片）
（用户在控制台输入：aB3k）
```

**步骤5: 填写验证码**
```bash
qqbrowser-skill.exe browser_input_text --index 25 --text "aB3k"
```

**步骤6: 点击登录按钮**
```bash
qqbrowser-skill.exe browser_click_element --index 29
```

**步骤7: 等待3秒并检查登录状态**
```bash
timeout /t 3
qqbrowser-skill.exe browser_get_info --type url
```

### 3.3 验证登录是否成功

**方法1: 检查URL**
```python
# 获取当前页面URL
result = self.run_command('browser_get_info --type url')
current_url = result.get('text', '')

# 检查是否跳转
if 'login' not in current_url.lower():
    print("✅ 登录成功！")
    print(f"当前页面: {current_url}")
else:
    print("❌ 登录失败，仍在登录页面")
```

**方法2: 检查页面内容**
```python
# 获取页面内容
result = self.run_command('browser_markdownify')
page_content = result.get('text', '')

# 检查是否有登录后的元素
if 'Welcome' in page_content or 'Dashboard' in page_content:
    print("✅ 登录成功！")
else:
    print("❌ 登录失败")
```

**方法3: 尝试访问需要登录的页面**
```python
# 尝试访问商家页面
api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
response = requests.get(api_url, headers=headers)

if response.status_code == 200 and 'code' in response.json():
    print("✅ 登录成功，可以访问API")
else:
    print("❌ 登录失败，无法访问API")
```

---

## 验证与检查

### 4.1 登录成功后的状态

**预期结果**:
1. ✅ 浏览器跳转到登录后的页面
2. ✅ 可以看到用户信息或Dashboard
3. ✅ 可以访问需要登录的API接口
4. ✅ Cookie已保存到浏览器中

**验证命令**:
```bash
# 检查当前URL
qqbrowser-skill.exe browser_get_info --type url

# 预期输出类似：
# {"text":"https://www.yeahpromos.com/index/index/index"}
```

### 4.2 可以进行的后续操作

**操作1: 导航到商家页面**
```bash
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/getadvert/getadvert
```

**操作2: 采集商家数据**
```python
# 通过API采集
api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
response = session.get(api_url, headers=headers)
merchants = response.json()['data']
```

**操作3: 导航到工具页面**
```bash
# Postback工具
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/tools/postback

# Link工具
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/tools/link

# Info工具
qqbrowser-skill.exe browser_go_to_url --url https://www.yeahpromos.com/index/tools/info
```

### 4.3 登录失败的处理

**检查清单**:
- [ ] 用户名和密码是否正确？
- [ ] 验证码是否输入正确？
- [ ] 验证码是否已过期（超过5分钟）？
- [ ] 是否输入错误3次导致账号锁定？
- [ ] 网络连接是否正常？
- [ ] YP平台是否正常访问？

**解决步骤**:
1. 刷新登录页面
2. 重新填写用户名和密码
3. 获取新的验证码
4. 重新输入验证码
5. 点击登录
6. 检查是否成功

---

## 常见问题

### Q1: QQBrowserSkill命令执行失败

**错误信息**:
```
命令执行失败: 找不到指定的文件
```

**原因**: QQBrowserSkill路径不正确

**解决方案**:
```python
# 检查正确的路径
import os

# 方法1：使用环境变量
qqbrowser_path = os.path.expanduser(
    r"~\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
)

# 方法2：使用绝对路径
qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"

# 验证路径
if not os.path.exists(qqbrowser_path):
    print(f"错误：找不到QQBrowserSkill: {qqbrowser_path}")
    print("请确认QQBrowserSkill已正确安装")
```

### Q2: 无法打开360浏览器

**错误信息**:
```
无法启动浏览器或浏览器未响应
```

**原因**: 360浏览器未正确安装或路径错误

**解决方案**:
```bash
# 1. 检查360浏览器是否已安装
dir "C:\Program Files (x86)\360\360se6\360se.exe"
dir "C:\Program Files\360\360se6\360se.exe"

# 2. 如果未安装，访问官网下载
# https://browser.360.cn/

# 3. 手动启动360浏览器测试
"C:\Program Files (x86)\360\360se6\360se.exe"

# 4. 确认360浏览器是默认浏览器
```

### Q3: 无法填写表单

**错误信息**:
```
填写失败: 无法找到指定索引的元素
```

**原因**: 页面元素索引可能发生变化

**解决方案**:
```python
# 方法1：获取页面快照，查看实际索引
result = self.run_command('browser_snapshot')
print(result['stdout'])

# 方法2：使用不同的索引尝试
for index in range(20, 30):
    result = self.run_command(f'browser_input_text --index {index} --text "test"')
    if result['success']:
        print(f"成功的索引: {index}")
        break

# 方法3：等待页面完全加载
time.sleep(3)  # 增加等待时间
```

### Q4: 验证码输入后登录失败

**错误信息**:
```
登录失败，仍在登录页面
```

**原因**: 
1. 验证码输入错误
2. 验证码已过期
3. 用户名或密码错误

**解决方案**:
```python
# 1. 提示用户检查验证码
print("⚠️ 登录失败，可能的原因：")
print("  1. 验证码输入错误")
print("  2. 验证码已过期（有效期为5分钟）")
print("  3. 用户名或密码错误")

# 2. 提供重试选项
choice = input("是否重新输入验证码？(y/n): ").strip().lower()
if choice == 'y':
    # 刷新页面
    print("正在刷新页面...")
    self.run_command('browser_go_to_url --url https://www.yeahpromos.com/index/login/login')
    time.sleep(3)
    
    # 重新执行登录流程
    self.run_login()
```

### Q5: 网络连接问题

**错误信息**:
```
无法连接到服务器或请求超时
```

**原因**: 网络连接问题或YP平台服务器问题

**解决方案**:
```bash
# 1. 检查网络连接
ping www.yeahpromos.com

# 2. 检查DNS解析
nslookup www.yeahpromos.com

# 3. 尝试访问其他网站
ping google.com
ping baidu.com

# 4. 如果网络正常，可能是YP平台问题
# 等待一段时间后重试
```

---

## 总结

### 核心要点

1. **浏览器选择**: 使用QQBrowserSkill
   - 专门为360浏览器优化
   - 简单易用的命令行接口
   - 已在用户环境中安装配置

2. **验证码解决方案**: 采用"自动化+人工干预"混合方案
   - 脚本自动打开页面和填写表单
   - 用户手动输入验证码
   - 脚本自动完成后续操作

3. **关键优势**:
   - 可靠性高（100%准确）
   - 成本低（无需额外付费）
   - 简单易实现
   - 用户体验好

### 下一步

登录成功后，可以执行以下操作：
1. 导航到商家页面采集商家数据
2. 导航到工具页面探索API功能
3. 通过API接口获取数据

---

**文档结束**
