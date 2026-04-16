#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YP 登录 Skill - 使用 bb-browser 进行 YP 平台登录
支持会话保持，避免每次重新登录
"""

import subprocess
import json
import time
import re
from datetime import datetime


class YPLoginSkill:
    """YP 登录 Skill"""
    
    def __init__(self):
        self.yp_login_url = "https://www.yeahpromos.com/index/login/login"
        self.yp_main_url = "https://www.yeahpromos.com/index/index/index"
        self.username = "Tong jun"
        self.password = "Tj840618"
        self.tab_id = None
        self.login_status_file = "output/login_status.json"
    
    def run_bb_browser(self, args, capture_json=True):
        """运行 bb-browser 命令"""
        cmd = ["bb-browser"] + args
        
        try:
            # 使用 shell=True 来查找 bb-browser 命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=True
            )
            
            if result.returncode != 0:
                print(f"[错误] 命令执行失败: {' '.join(args)}")
                print(f"错误信息: {result.stderr}")
                return None
            
            if capture_json:
                # 尝试解析 JSON 输出
                output = result.stdout.strip()
                if output.startswith("{"):
                    return json.loads(output)
                return output
            
            return result.stdout
        
        except subprocess.TimeoutExpired:
            print(f"[错误] 命令超时: {' '.join(args)}")
            return None
        except Exception as e:
            print(f"[错误] 命令执行异常: {e}")
            return None
    
    def check_login_status(self):
        """检查登录状态"""
        print("\n" + "="*50)
        print("[检查] 检查登录状态...")
        print("="*50)
        
        # 获取当前 URL
        result = self.run_bb_browser(["get", "url"])
        
        if result and isinstance(result, dict) and "text" in result:
            current_url = result["text"]
            print(f"当前页面 URL: {current_url}")
            
            # 检查是否还在登录页面
            if "login" in current_url:
                print("[状态] 未登录，需要重新登录")
                return False
            else:
                print("[状态] 已登录")
                return True
        
        print("[状态] 无法确定登录状态")
        return False
    
    def open_login_page(self):
        """打开登录页面"""
        print("\n" + "="*50)
        print("[1/5] 打开 YP 登录页面...")
        print("="*50)
        
        result = self.run_bb_browser(["open", self.yp_login_url])
        
        if result and "Tab ID" in result:
            # 提取 Tab ID
            match = re.search(r"Tab ID: ([A-F0-9]+)", result)
            if match:
                self.tab_id = match.group(1)
                print(f"[成功] 页面已打开，Tab ID: {self.tab_id}")
                return True
        
        print("[失败] 打开页面失败")
        return False
    
    def take_screenshot(self):
        """截图"""
        print("\n[截图] 正在截图...")
        result = self.run_bb_browser(["screenshot"], capture_json=False)
        
        if result and "截图已保存" in result:
            # 提取截图路径
            match = re.search(r"截图已保存: (.+)", result)
            if match:
                screenshot_path = match.group(1).strip()
                print(f"[成功] 截图已保存: {screenshot_path}")
                return screenshot_path
        
        print("[失败] 截图失败")
        return None
    
    def fill_username(self):
        """填写用户名"""
        print("\n[填写] 正在填写用户名...")
        
        # 用户名输入框的 ref=16
        result = self.run_bb_browser(["fill", "16", self.username])
        
        if result:
            print(f"[成功] 用户名已填写: {self.username}")
            return True
        
        print("[失败] 用户名填写失败")
        return False
    
    def fill_password(self):
        """填写密码"""
        print("\n[填写] 正在填写密码...")
        
        # 密码输入框的 ref=17
        result = self.run_bb_browser(["fill", "17", self.password])
        
        if result:
            print("[成功] 密码已填写")
            return True
        
        print("[失败] 密码填写失败")
        return False
    
    def input_captcha_manually(self):
        """手动输入验证码"""
        print("\n" + "="*50)
        print("[警告] 需要手动输入验证码")
        print("="*50)
        print("1. 请查看浏览器窗口中的验证码图片")
        print("2. 在下方输入验证码并按回车")
        print("="*50)
        
        # 先截图，方便用户查看
        screenshot_path = self.take_screenshot()
        if screenshot_path:
            print(f"\n[提示] 截图已保存，您可以查看: {screenshot_path}")
        
        # 等待用户输入
        captcha_code = input("\n请输入验证码: ").strip()
        
        if not captcha_code:
            print("[失败] 未输入验证码")
            return False
        
        print(f"\n[填写] 正在填写验证码: {captcha_code}")
        
        # 验证码输入框的 ref=18
        result = self.run_bb_browser(["fill", "18", captcha_code])
        
        if result:
            print("[成功] 验证码已填写")
            return True
        
        print("[失败] 验证码填写失败")
        return False
    
    def click_login_button(self):
        """点击登录按钮"""
        print("\n[点击] 正在点击登录按钮...")
        
        # 登录按钮的 ref=21
        result = self.run_bb_browser(["click", "21"])
        
        if result:
            print("[成功] 登录按钮已点击")
            return True
        
        print("[失败] 点击登录按钮失败")
        return False
    
    def wait_for_login(self):
        """等待登录完成"""
        print("\n[等待] 等待页面跳转...")
        time.sleep(3)
        print("[成功] 等待完成")
        return True
    
    def save_login_status(self):
        """保存登录状态"""
        print("\n[保存] 保存登录状态...")
        
        login_status = {
            "login_time": datetime.now().isoformat(),
            "username": self.username,
            "login_success": True
        }
        
        try:
            with open(self.login_status_file, "w", encoding="utf-8") as f:
                json.dump(login_status, f, indent=2, ensure_ascii=False)
            print(f"[成功] 登录状态已保存: {self.login_status_file}")
            return True
        except Exception as e:
            print(f"[失败] 保存登录状态失败: {e}")
            return False
    
    def load_login_status(self):
        """加载登录状态"""
        try:
            with open(self.login_status_file, "r", encoding="utf-8") as f:
                login_status = json.load(f)
            return login_status
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"[警告] 加载登录状态失败: {e}")
            return None
    
    def navigate_to_main_page(self):
        """导航到主页"""
        print("\n[导航] 正在导航到主页...")
        
        result = self.run_bb_browser(["open", self.yp_main_url])
        
        if result:
            print("[成功] 已导航到主页")
            return True
        
        print("[失败] 导航到主页失败")
        return False
    
    def login(self):
        """执行完整的登录流程"""
        print("\n" + "="*50)
        print("YP 登录 Skill - 使用 bb-browser")
        print("="*50)
        print(f"用户名: {self.username}")
        print(f"登录页面: {self.yp_login_url}")
        print("="*50)
        
        try:
            # 步骤 1: 检查登录状态
            if self.check_login_status():
                print("\n[提示] 已登录，无需重新登录")
                # 导航到主页
                self.navigate_to_main_page()
                return True
            
            # 步骤 2: 打开登录页面
            if not self.open_login_page():
                return False
            
            # 步骤 3: 填写用户名
            if not self.fill_username():
                return False
            
            # 步骤 4: 填写密码
            if not self.fill_password():
                return False
            
            # 步骤 5: 手动输入验证码
            if not self.input_captcha_manually():
                return False
            
            # 步骤 6: 点击登录按钮
            if not self.click_login_button():
                return False
            
            # 步骤 7: 等待页面跳转
            if not self.wait_for_login():
                return False
            
            # 步骤 8: 检查登录状态
            if not self.check_login_status():
                print("\n[失败] 登录失败，仍在登录页面")
                return False
            
            # 步骤 9: 保存登录状态
            if not self.save_login_status():
                print("\n[警告] 保存登录状态失败，但登录成功")
            
            # 成功！
            print("\n" + "="*50)
            print("[成功] 登录成功！")
            print("="*50)
            print(f"1. 您现在可以使用 bb-browser 访问需要登录的页面")
            print(f"2. 登录状态已保存在 bb-browser 的浏览器中")
            print(f"3. 后续操作无需重新登录（除非会话过期）")
            print(f"4. 会话保持时间取决于 YP 平台的 Cookie 有效期")
            print("="*50)
            
            return True
        
        except KeyboardInterrupt:
            print("\n\n[警告] 用户中断操作")
            return False
        except Exception as e:
            print(f"\n\n[失败] 发生错误: {e}")
            return False
    
    def logout(self):
        """退出登录"""
        print("\n" + "="*50)
        print("[提示] YP 登录 Skill - 退出登录")
        print("="*50)
        print("注意: 此操作不会清除 bb-browser 的 Cookie")
        print("如需清除 Cookie，请使用: bb-browser tab close")
        print("="*50)


def main():
    """主函数"""
    import sys
    
    # 创建登录实例
    login_skill = YPLoginSkill()
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "check":
            # 检查登录状态
            if login_skill.check_login_status():
                print("\n[状态] 已登录")
                sys.exit(0)
            else:
                print("\n[状态] 未登录")
                sys.exit(1)
        
        elif command == "logout":
            # 退出登录
            login_skill.logout()
            sys.exit(0)
        
        else:
            print(f"[错误] 未知命令: {command}")
            print("可用命令: login, check, logout")
            sys.exit(1)
    
    # 默认执行登录
    if login_skill.login():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
