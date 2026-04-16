#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 bb-browser 登录 YP 平台
"""

import subprocess
import time
import json
import os
from pathlib import Path


class YPLoginWithBBBrowser:
    """使用 bb-browser 登录 YP 平台"""
    
    def __init__(self):
        self.yp_url = "https://www.yeahpromos.com/index/login/login"
        self.username = "Tong jun"
        self.password = "Tj840618"
        self.tab_id = None
    
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
    
    def open_login_page(self):
        """打开登录页面"""
        print("\n" + "="*50)
        print("[1/5] 打开 YP 登录页面...")
        print("="*50)
        
        result = self.run_bb_browser(["open", self.yp_url])
        
        if result and "Tab ID" in result:
            # 提取 Tab ID
            import re
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
            import re
            match = re.search(r"截图已保存: (.+)", result)
            if match:
                screenshot_path = match.group(1).strip()
                print(f"✅ 截图已保存: {screenshot_path}")
                return screenshot_path
        
        print("❌ 截图失败")
        return None
    
    def fill_username(self):
        """填写用户名"""
        print("\n[填写] 正在填写用户名...")
        
        # 用户名输入框的 ref=16
        result = self.run_bb_browser(["fill", "16", self.username])
        
        if result:
            print(f"✅ 用户名已填写: {self.username}")
            return True
        
        print("❌ 用户名填写失败")
        return False
    
    def fill_password(self):
        """填写密码"""
        print("\n[填写] 正在填写密码...")
        
        # 密码输入框的 ref=17
        result = self.run_bb_browser(["fill", "17", self.password])
        
        if result:
            print("✅ 密码已填写")
            return True
        
        print("❌ 密码填写失败")
        return False
    
    def input_captcha_manually(self):
        """手动输入验证码"""
        print("\n" + "="*50)
        print("⚠️  需要手动输入验证码")
        print("="*50)
        print("1. 请查看浏览器窗口中的验证码图片")
        print("2. 在下方输入验证码并按回车")
        print("="*50)
        
        # 先截图，方便用户查看
        screenshot_path = self.take_screenshot()
        if screenshot_path:
            print(f"\n📸 截图已保存，您可以查看: {screenshot_path}")
        
        # 等待用户输入
        captcha_code = input("\n请输入验证码: ").strip()
        
        if not captcha_code:
            print("❌ 未输入验证码")
            return False
        
        print(f"\n[填写] 正在填写验证码: {captcha_code}")
        
        # 验证码输入框的 ref=18
        result = self.run_bb_browser(["fill", "18", captcha_code])
        
        if result:
            print("✅ 验证码已填写")
            return True
        
        print("❌ 验证码填写失败")
        return False
    
    def click_login_button(self):
        """点击登录按钮"""
        print("\n[点击] 正在点击登录按钮...")
        
        # 登录按钮的 ref=21
        result = self.run_bb_browser(["click", "21"])
        
        if result:
            print("✅ 登录按钮已点击")
            return True
        
        print("❌ 点击登录按钮失败")
        return False
    
    def check_login_status(self):
        """检查登录状态"""
        print("\n[检查] 正在检查登录状态...")
        
        # 等待页面跳转
        time.sleep(3)
        
        # 获取当前 URL
        result = self.run_bb_browser(["get", "url"])
        
        if result and isinstance(result, dict) and "text" in result:
            current_url = result["text"]
            print(f"当前页面 URL: {current_url}")
            
            # 检查是否还在登录页面
            if "login" in current_url:
                print("❌ 登录失败，仍在登录页面")
                return False
            else:
                print("✅ 登录成功！已跳转到登录后页面")
                return True
        
        print("⚠️  无法确定登录状态")
        return False
    
    def login(self):
        """执行完整的登录流程"""
        print("\n" + "="*50)
        print("YP 平台登录（使用 bb-browser）")
        print("="*50)
        
        try:
            # 步骤 1: 打开登录页面
            if not self.open_login_page():
                return False
            
            # 步骤 2: 填写用户名
            if not self.fill_username():
                return False
            
            # 步骤 3: 填写密码
            if not self.fill_password():
                return False
            
            # 步骤 4: 手动输入验证码
            if not self.input_captcha_manually():
                return False
            
            # 步骤 5: 点击登录按钮
            if not self.click_login_button():
                return False
            
            # 步骤 6: 检查登录状态
            if not self.check_login_status():
                return False
            
            # 成功！
            print("\n" + "="*50)
            print("🎉 登录成功！")
            print("="*50)
            print(f"✅ 您现在可以使用 bb-browser 访问需要登录的页面")
            print(f"✅ 登录状态已保存在 bb-browser 的浏览器中")
            print(f"✅ 下次调用 bb-browser 命令时会自动使用这个登录状态")
            
            return True
        
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断操作")
            return False
        except Exception as e:
            print(f"\n\n❌ 发生错误: {e}")
            return False


def main():
    """主函数"""
    login = YPLoginWithBBBrowser()
    login.login()


if __name__ == "__main__":
    main()
