"""
使用 QQBrowserSkill 自动化采集 YP 平台商家数据

流程：
1. 打开浏览器并导航到 YP 登录页
2. 自动填写用户名和密码
3. 提示用户输入验证码
4. 完成登录
5. 采集所有商家数据
6. 解析追踪链接
7. 爬取亚马逊商品数据
8. 保存到本地文件
"""

import subprocess
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
import re
import sys
import io

# 设置控制台编码为 UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='ignore')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='ignore')


class YPDataCollector:
    """YP 平台数据采集器"""
    
    def __init__(self, base_url: str = "https://www.yeahpromos.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
        self.cookies = {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        }
        self.merchant_data = []
        
    def run_qqbrowser_command(self, command: str) -> Dict:
        """运行 QQBrowserSkill 命令"""
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
            
            if result.returncode != 0:
                print(f"命令执行失败: {result.stderr}")
                return {'success': False, 'error': result.stderr}
            
            # 解析 JSON 结果
            output = result.stdout
            json_match = re.search(r'\[RESULT\]\s*(\{.*?\})', output, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group(1))
                return {'success': True, 'data': result_json}
            
            return {'success': True, 'raw_output': output}
            
        except Exception as e:
            print(f"执行 QQBrowserSkill 命令时出错: {e}")
            return {'success': False, 'error': str(e)}
    
    def navigate_to_login_page(self) -> bool:
        """导航到登录页面"""
        print("正在导航到 YP 登录页面...")
        result = self.run_qqbrowser_command('browser_go_to_url --url https://www.yeahpromos.com/index/index/merchantlogin')
        
        if result['success']:
            print("✅ 成功打开登录页面")
            time.sleep(2)  # 等待页面加载
            return True
        else:
            print(f"❌ 打开登录页面失败: {result.get('error', '未知错误')}")
            return False
    
    def fill_login_form(self, username: str, password: str) -> bool:
        """填写登录表单"""
        print("正在填写登录表单...")
        
        # 获取页面快照以获取元素索引
        snapshot_result = self.run_qqbrowser_command('browser_snapshot')
        time.sleep(1)
        
        # 填写用户名（第一个文本输入框）
        print(f"填写用户名: {username}")
        result1 = self.run_qqbrowser_command(f'browser_input_text --index 0 --text "{username}"')
        time.sleep(0.5)
        
        # 填写密码（第二个文本输入框）
        print(f"填写密码: {password}")
        result2 = self.run_qqbrowser_command(f'browser_input_text --index 1 --text "{password}"')
        time.sleep(0.5)
        
        if result1['success'] and result2['success']:
            print("✅ 表单填写完成")
            return True
        else:
            print("❌ 表单填写失败")
            return False
    
    def input_captcha_manually(self) -> bool:
        """手动输入验证码"""
        print("\n" + "="*50)
        print("⚠️  需要手动输入验证码")
        print("1. 请在浏览器中查看验证码图片")
        print("2. 输入验证码并按回车")
        print("="*50)
        
        captcha_code = input("请输入验证码: ").strip()
        
        if not captcha_code:
            print("❌ 未输入验证码")
            return False
        
        # 填写验证码（第三个文本输入框）
        print(f"填写验证码: {captcha_code}")
        result = self.run_qqbrowser_command(f'browser_input_text --index 2 --text "{captcha_code}"')
        time.sleep(0.5)
        
        if result['success']:
            print("✅ 验证码填写完成")
            return True
        else:
            print("❌ 验证码填写失败")
            return False
    
    def submit_login(self) -> bool:
        """提交登录"""
        print("正在提交登录...")
        
        # 点击登录按钮（索引通常在最后一个或倒数第二个）
        result = self.run_qqbrowser_command('browser_click_element --index 3')
        time.sleep(3)  # 等待登录处理
        
        if result['success']:
            print("✅ 登录按钮已点击")
            return True
        else:
            print("❌ 点击登录按钮失败")
            return False
    
    def check_login_success(self) -> bool:
        """检查登录是否成功"""
        print("检查登录状态...")
        result = self.run_qqbrowser_command('browser_get_info --type url')
        
        if result['success']:
            current_url = result['data'].get('text', '')
            print(f"当前页面 URL: {current_url}")
            
            # 检查是否跳转到登录后的页面
            if 'login' not in current_url.lower():
                print("✅ 登录成功！")
                return True
            else:
                print("❌ 登录失败，仍在登录页面")
                return False
        else:
            print("❌ 无法检查登录状态")
            return False
    
    def navigate_to_merchant_page(self) -> bool:
        """导航到商家页面"""
        print("正在导航到商家页面...")
        result = self.run_qqbrowser_command('browser_go_to_url --url https://www.yeahpromos.com/index/getadvert/getadvert')
        time.sleep(3)
        
        if result['success']:
            print("✅ 成功打开商家页面")
            return True
        else:
            print("❌ 打开商家页面失败")
            return False
    
    def extract_merchant_data(self) -> List[Dict]:
        """从页面提取商家数据"""
        print("正在提取商家数据...")
        
        # 获取页面内容
        result = self.run_qqbrowser_command('browser_markdownify')
        
        if not result['success']:
            print("❌ 获取页面内容失败")
            return []
        
        # 尝试从 API 获取数据（更可靠的方式）
        try:
            api_url = "https://www.yeahpromos.com/index/getadvert/getadvert"
            response = self.session.get(api_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('code') == 1:
                    merchants = data.get('data', [])
                    print(f"✅ 成功获取 {len(merchants)} 个商家数据")
                    
                    self.merchant_data = merchants
                    return merchants
                else:
                    print(f"❌ API 返回错误: {data.get('msg', '未知错误')}")
                    return []
            else:
                print(f"❌ API 请求失败，状态码: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"❌ 获取商家数据时出错: {e}")
            return []
    
    def save_merchant_data(self, output_dir: str = "output") -> bool:
        """保存商家数据到文件"""
        try:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # 保存为 JSON 格式
            json_file = output_path / "yp_merchants.json"
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(self.merchant_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 商家数据已保存到: {json_file}")
            
            # 保存为 CSV 格式（便于查看）
            if self.merchant_data:
                csv_file = output_path / "yp_merchants.csv"
                import csv
                
                # 获取所有字段名
                all_keys = set()
                for merchant in self.merchant_data:
                    all_keys.update(merchant.keys())
                fieldnames = list(all_keys)
                
                with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(self.merchant_data)
                
                print(f"✅ 商家数据已保存到: {csv_file}")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存数据时出错: {e}")
            return False
    
    def run_collection(self, username: str, password: str) -> bool:
        """执行完整的数据采集流程"""
        print("\n" + "="*60)
        print("YP 平台数据自动化采集工具")
        print("="*60 + "\n")
        
        # 步骤 1: 导航到登录页
        if not self.navigate_to_login_page():
            return False
        
        # 步骤 2: 填写表单
        if not self.fill_login_form(username, password):
            return False
        
        # 步骤 3: 手动输入验证码
        if not self.input_captcha_manually():
            return False
        
        # 步骤 4: 提交登录
        if not self.submit_login():
            return False
        
        # 步骤 5: 检查登录状态
        if not self.check_login_success():
            print("\n提示: 登录可能失败，请检查浏览器中的错误信息")
            input("\n按回车键继续尝试采集数据...")
        
        # 步骤 6: 导航到商家页面
        if not self.navigate_to_merchant_page():
            return False
        
        # 步骤 7: 提取商家数据
        merchants = self.extract_merchant_data()
        
        if not merchants:
            print("\n提示: 可能需要等待浏览器完全加载，或手动导航到商家页面")
            input("请手动导航到商家页面后按回车键继续...")
            merchants = self.extract_merchant_data()
        
        # 步骤 8: 保存数据
        if merchants:
            self.save_merchant_data()
            
            # 显示统计信息
            print(f"\n{'='*60}")
            print("采集完成！")
            print(f"{'='*60}")
            print(f"商家数量: {len(merchants)}")
            
            if merchants:
                print(f"\n示例商家数据:")
                sample = merchants[0]
                for key, value in sample.items():
                    if isinstance(value, str) and len(value) > 50:
                        value = value[:50] + "..."
                    print(f"  {key}: {value}")
            
            return True
        else:
            print("❌ 未能获取商家数据")
            return False


def main():
    """主函数"""
    # 登录凭证
    USERNAME = "Tong jun"
    PASSWORD = "Tj840618"
    
    # 创建采集器实例
    collector = YPDataCollector()
    
    # 执行采集
    success = collector.run_collection(USERNAME, PASSWORD)
    
    if success:
        print("\n✅ 采集任务完成！")
    else:
        print("\n❌ 采集任务失败")
        print("提示: 您可以手动在浏览器中完成登录和数据采集")
    
    # 保持浏览器打开，方便用户查看
    input("\n按回车键关闭程序...")


if __name__ == "__main__":
    main()
