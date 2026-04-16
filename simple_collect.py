"""
使用 QQBrowserSkill 自动化采集 YP 平台商家数据（简化版）
"""

import subprocess
import json
import time
import requests
from pathlib import Path
from typing import Dict, List


class SimpleYPDataCollector:
    """简化的 YP 数据采集器"""
    
    def __init__(self, base_url: str = "https://www.yeahpromos.com"):
        self.base_url = base_url
        self.qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
        self.merchant_data = []
        
    def run_command(self, command: str) -> str:
        """运行 QQBrowserSkill 命令并返回输出"""
        try:
            full_command = f'& "{self.qqbrowser_path}" {command}'
            result = subprocess.run(
                ['powershell', '-Command', full_command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            return result.stdout
        except Exception as e:
            print(f"命令执行错误: {e}")
            return ""
    
    def open_login_page(self) -> bool:
        """打开登录页面"""
        print("[1/5] 打开登录页面...")
        output = self.run_command('browser_go_to_url --url https://www.yeahpromos.com/index/login/login')
        time.sleep(3)
        
        if 'Successfully' in output or 'Navigated' in output:
            print("      OK: 登录页面已打开")
            return True
        return False
    
    def fill_credentials(self, username: str, password: str) -> bool:
        """填写用户名和密码"""
        print("[2/5] 填写登录信息...")
        
        # 填写用户名（索引 22）
        output1 = self.run_command(f'browser_input_text --index 22 --text "{username}"')
        time.sleep(0.5)
        
        # 填写密码（索引 23）
        output2 = self.run_command(f'browser_input_text --index 23 --text "{password}"')
        time.sleep(0.5)
        
        if 'Success' in output1 and 'Success' in output2:
            print("      OK: 用户名和密码已填写")
            return True
        return False
    
    def input_captcha(self) -> bool:
        """输入验证码"""
        print("[3/5] 等待验证码输入...")
        print("      请在浏览器中查看验证码图片")
        
        captcha = input("      请输入验证码: ").strip()
        
        if not captcha:
            print("      ERROR: 未输入验证码")
            return False
        
        # 填写验证码（索引 25）
        output = self.run_command(f'browser_input_text --index 25 --text "{captcha}"')
        time.sleep(0.5)
        
        if 'Success' in output:
            print("      OK: 验证码已填写")
            return True
        return False
    
    def submit_form(self) -> bool:
        """提交表单"""
        print("[4/5] 提交登录...")
        
        # 点击登录按钮（索引 29）
        output = self.run_command('browser_click_element --index 29')
        time.sleep(3)
        
        if 'clicked' in output.lower():
            print("      OK: 登录已提交")
            return True
        return False
    
    def check_login(self) -> bool:
        """检查登录状态"""
        print("[5/5] 检查登录状态...")
        
        output = self.run_command('browser_get_info --type url')
        
        if 'login' not in output.lower():
            print("      OK: 登录成功！")
            return True
        else:
            print("      WARNING: 仍在登录页面，可能登录失败")
            return False
    
    def collect_data_via_api(self) -> List[Dict]:
        """通过 API 采集数据"""
        print("\n[采集] 正在采集商家数据...")
        
        try:
            # 尝试访问商家 API
            api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
            session = requests.Session()
            
            # 设置 headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = session.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == 1:
                    merchants = data.get('data', [])
                    print(f"      OK: 成功获取 {len(merchants)} 个商家")
                    return merchants
                else:
                    print(f"      ERROR: API 返回错误 - {data.get('msg')}")
                    return []
            else:
                print(f"      ERROR: HTTP {response.status_code}")
                return []
                
        except Exception as e:
            print(f"      ERROR: {e}")
            return []
    
    def save_data(self, data: List[Dict], output_dir: str = "output") -> bool:
        """保存数据"""
        if not data:
            print("\n[保存] 没有数据可保存")
            return False
        
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 保存 JSON
            json_file = output_path / "yp_merchants.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"\n[保存] JSON 文件: {json_file}")
            
            # 保存 CSV
            csv_file = output_path / "yp_merchants.csv"
            import csv
            
            all_keys = set()
            for item in data:
                all_keys.update(item.keys())
            fieldnames = list(all_keys)
            
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(data)
            
            print(f"[保存] CSV 文件: {csv_file}")
            return True
            
        except Exception as e:
            print(f"\n[保存] 错误: {e}")
            return False
    
    def run(self, username: str, password: str) -> bool:
        """执行完整流程"""
        print("\n" + "="*50)
        print("YP 数据采集工具（使用 QQBrowserSkill）")
        print("="*50 + "\n")
        
        # 步骤 1-5: 登录
        if not self.open_login_page():
            return False
        
        if not self.fill_credentials(username, password):
            return False
        
        if not self.input_captcha():
            return False
        
        if not self.submit_form():
            return False
        
        self.check_login()
        
        # 提示：用户可以手动在浏览器中完成操作
        print("\n" + "="*50)
        print("提示:")
        print("  - 如果登录成功，请继续下一步")
        print("  - 如果登录失败，请手动在浏览器中完成登录")
        print("  - 然后输入 'ok' 继续")
        print("="*50)
        
        user_input = input("\n输入 'ok' 开始采集，或 'q' 退出: ").strip().lower()
        
        if user_input != 'ok':
            print("用户取消")
            return False
        
        # 采集数据
        merchants = self.collect_data_via_api()
        
        if not merchants:
            print("\n尝试通过浏览器页面采集...")
            # 备用方案：从浏览器页面提取数据
            print("请手动导航到商家页面，然后输入 'ok'")
            input("按回车继续...")
            
            # 尝试导航到商家页面
            print("正在导航到商家页面...")
            self.run_command('browser_go_to_url --url https://www.yeahpromos.com/index/getadvert/getadvert')
            time.sleep(3)
            
            # 获取页面内容
            output = self.run_command('browser_markdownify')
            print("页面内容已获取，但需要手动解析")
            return False
        
        # 保存数据
        self.save_data(merchants)
        
        # 显示统计
        print(f"\n{'='*50}")
        print("采集完成！")
        print(f"{'='*50}")
        print(f"商家数量: {len(merchants)}")
        
        if merchants:
            print(f"\n第一个商家信息:")
            for key, value in list(merchants[0].items())[:5]:
                print(f"  {key}: {str(value)[:50]}")
        
        return True


def main():
    """主函数"""
    USERNAME = "Tong jun"
    PASSWORD = "Tj840618"
    
    collector = SimpleYPDataCollector()
    success = collector.run(USERNAME, PASSWORD)
    
    if success:
        print("\n[成功] 采集任务完成！")
    else:
        print("\n[失败] 采集任务未完成")
    
    print("\n浏览器仍保持打开状态，可以手动操作")
    input("按回车键退出...")


if __name__ == "__main__":
    main()
