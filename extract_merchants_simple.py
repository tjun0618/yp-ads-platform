"""
简单商家数据提取器 - 直接从当前浏览器页面提取
"""

import subprocess
import json
import re
from pathlib import Path


def run_qqbrowser_command(command: str) -> str:
    """运行 QQBrowserSkill 命令"""
    qqbrowser_path = r"C:\Users\wuhj\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts\qqbrowser-skill.exe"
    
    try:
        full_command = f'& "{qqbrowser_path}" {command}'
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
        print(f"错误: {e}")
        return ""


def main():
    print("\n开始提取商家数据...")
    
    # 获取当前页面快照
    print("正在获取页面内容...")
    output = run_qqbrowser_command('browser_snapshot')
    
    if not output:
        print("错误: 无法获取页面内容")
        return
    
    # 解析商家数据
    merchants = []
    
    # 查找所有商家条目
    # 模式：input checkbox + merchant_id, 然后是商家名称
    lines = output.split('\n')
    
    current_merchant = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 查找复选框行，提取 merchant_id
        if 'adv_id[]' in line and 'checkbox' in line:
            id_match = re.search(r'adv_id\[\];checkbox;(\d+)', line)
            if id_match:
                merchant_id = id_match.group(1)
                current_merchant = {'merchant_id': merchant_id}
                
                # 在接下来的几行中查找商家名称
                for j in range(i+1, min(i+5, len(lines))):
                    name_match = re.search(r'<a\s+([^>]+)/>', lines[j])
                    if name_match and 'checkbox' not in lines[j]:
                        name = name_match.group(1).strip()
                        current_merchant['name'] = name
                        break
                
                # 继续查找 Rating, Commission, MID, Country
                for j in range(i, min(i+15, len(lines))):
                    if 'Rating:' in lines[j]:
                        # Rating 在下一行
                        if j+1 < len(lines):
                            rating = lines[j+1].strip()
                            current_merchant['rating'] = rating
                    
                    if 'Commission:' in lines[j]:
                        # 查找 Commission 值
                        for k in range(j, min(j+3, len(lines))):
                            comm_match = re.search(r'<span\s+([^/>]+)/>', lines[k])
                            if comm_match:
                                commission = comm_match.group(1)
                                current_merchant['commission'] = commission
                                break
                    
                    if 'MID' in lines[j] and ':' in lines[j]:
                        mid_match = re.search(r':\s*(\d+)', lines[j])
                        if mid_match:
                            mid = mid_match.group(1)
                            current_merchant['mid'] = mid
                    
                    # Country 通常是两个字母的代码
                    country_match = re.search(r'\b([A-Z]{2})\b', lines[j])
                    if country_match and country_match.group(1) not in ['NEW', 'OK', 'USD', 'EUR', 'GBP']:
                        current_merchant['country'] = country_match.group(1)
                
                if 'name' in current_merchant:
                    merchants.append(current_merchant)
                    print(f"找到: {current_merchant['name']} - {current_merchant.get('commission', 'N/A')}")
        
        i += 1
    
    print(f"\n共提取 {len(merchants)} 个商家")
    
    if merchants:
        # 保存数据
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON
        json_file = output_dir / "yp_merchants.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merchants, f, ensure_ascii=False, indent=2)
        print(f"\n已保存: {json_file}")
        
        # CSV
        csv_file = output_dir / "yp_merchants.csv"
        import csv
        
        all_keys = set()
        for m in merchants:
            all_keys.update(m.keys())
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(merchants)
        
        print(f"已保存: {csv_file}")
        
        # 显示前10个
        print(f"\n前10个商家:")
        for i, m in enumerate(merchants[:10], 1):
            print(f"  {i}. {m.get('name', 'N/A')} - {m.get('commission', 'N/A')}")
    
    return merchants


if __name__ == "__main__":
    merchants = main()
    print(f"\n完成！共 {len(merchants)} 个商家")
    input("\n按回车键退出...")
