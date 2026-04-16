"""
从 YP 商家页面提取商家数据
"""

import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict


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


def parse_merchants_from_page(page_content: str) -> List[Dict]:
    """从页面内容中解析商家数据"""
    merchants = []
    
    # 查找所有商家条目
    # 模式: <input adv_id[];checkbox;ID/><a NAME/>...
    pattern = r'<input\s+adv_id\[\];checkbox;(\d+)/>.*?<a\s+([^>]+)/>.*?Rating:.*?([^\n]+).*?Commission:.*?<span\s+([^/>]+)/>.*?MID.*?:\s*(\d+).*?([A-Z]{2})'
    
    matches = re.findall(pattern, page_content, re.DOTALL)
    
    for match in matches:
        merchant_id, name, rating, commission, mid, country = match
        
        merchant = {
            'merchant_id': merchant_id,
            'name': name.strip(),
            'rating': rating.strip(),
            'commission': commission.strip(),
            'mid': mid,
            'country': country.strip()
        }
        
        merchants.append(merchant)
    
    return merchants


def main():
    print("\n" + "="*60)
    print("YP 商家数据提取工具")
    print("="*60 + "\n")
    
    # 滚动到页面底部以加载所有数据
    print("[1/3] 正在滚动页面以加载所有商家...")
    run_qqbrowser_command('browser_scroll_to_top')
    import time
    time.sleep(1)
    
    # 多次滚动以确保加载所有内容
    for i in range(5):
        print(f"      滚动 {i+1}/5...")
        run_qqbrowser_command('browser_scroll_down')
        time.sleep(1)
    
    # 滚动到底部
    run_qqbrowser_command('browser_scroll_to_bottom')
    time.sleep(2)
    
    print("[2/3] 正在提取页面内容...")
    
    # 获取页面 Markdown 内容
    output = run_qqbrowser_command('browser_markdownify')
    
    if not output:
        print("      ERROR: 无法获取页面内容")
        return False
    
    # 提取商家数据
    print("[3/3] 正在解析商家数据...")
    merchants = parse_merchants_from_page(output)
    
    print(f"      成功提取 {len(merchants)} 个商家数据")
    
    if not merchants:
        print("\n      警告: 未能解析商家数据")
        print("      尝试手动解析...")
        
        # 备用解析方法
        merchants = []
        lines = output.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 查找复选框行
            if 'adv_id[]' in line and 'checkbox' in line:
                # 提取 merchant_id
                id_match = re.search(r'adv_id\[\];checkbox;(\d+)', line)
                if id_match:
                    merchant_id = id_match.group(1)
                    
                    # 查找商家名称（下一个或几个行）
                    for j in range(i+1, min(i+10, len(lines))):
                        if '<a' in lines[j] and lines[j].strip().endswith('/>'):
                            name = re.sub(r'<a\s+([^>]+)/>', r'\1', lines[j])
                            name = name.strip()
                            break
                    else:
                        name = "Unknown"
                    
                    # 查找 Rating
                    rating = ""
                    for j in range(i, min(i+15, len(lines))):
                        if 'Rating:' in lines[j]:
                            rating_match = re.search(r'Rating:.*?([A-Z]+|[0-9.]+)', lines[j+1] if j+1 < len(lines) else '')
                            if rating_match:
                                rating = rating_match.group(1)
                            break
                    
                    # 查找 Commission
                    commission = ""
                    for j in range(i, min(i+20, len(lines))):
                        if 'Commission:' in lines[j]:
                            comm_match = re.search(r'Commission:.*?<span\s+([^/>]+)/>', lines[j:j+5], re.DOTALL)
                            if comm_match:
                                commission = comm_match.group(1)
                            break
                    
                    merchant = {
                        'merchant_id': merchant_id,
                        'name': name,
                        'rating': rating,
                        'commission': commission
                    }
                    
                    merchants.append(merchant)
                    print(f"      找到商家: {merchant_id} - {name}")
            
            i += 1
        
        print(f"      手动解析完成，共 {len(merchants)} 个商家")
    
    if merchants:
        # 保存数据
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON
        json_file = output_dir / "yp_merchants.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merchants, f, ensure_ascii=False, indent=2)
        print(f"\n[保存] JSON 文件: {json_file}")
        
        # CSV
        csv_file = output_dir / "yp_merchants.csv"
        import csv
        
        all_keys = set()
        for m in merchants:
            all_keys.update(m.keys())
        fieldnames = sorted(all_keys)
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(merchants)
        
        print(f"[保存] CSV 文件: {csv_file}")
        
        # 显示统计
        print(f"\n{'='*60}")
        print("提取完成！")
        print(f"{'='*60}")
        print(f"商家总数: {len(merchants)}")
        
        if merchants:
            print(f"\n前5个商家:")
            for i, m in enumerate(merchants[:5], 1):
                print(f"  {i}. {m.get('name', 'N/A')} - {m.get('commission', 'N/A')}")
        
        return True
    else:
        print("\n错误: 未能提取任何商家数据")
        return False


if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n[成功] 数据提取完成！")
    else:
        print("\n[失败] 数据提取失败")
    
    input("\n按回车键退出...")
