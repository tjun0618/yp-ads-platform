"""
解析 Elite Pick 页面的商家数据（改进版）
"""

import json
import re
from pathlib import Path


def parse_elite_merchants(content: str):
    """解析 Elite Pick 页面的商家数据"""
    merchants = []
    
    # 查找所有商家条目的模式
    # 观察到的格式:
    # [47]<input adv_id[];checkbox;356364/>
    # [48]<img />
    # [49]<div OlliePets_US/>
    # MID: 356364
    # USD 34.50
    
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 查找复选框行（格式: [47]<input adv_id[];checkbox;356364/>）
        checkbox_match = re.search(r'\[\d+\]<input\s+adv_id\[\];checkbox;(\d+)/>', line)
        
        if checkbox_match:
            merchant_id = checkbox_match.group(1)
            
            # 在接下来的行中查找商家信息
            name = ""
            mid = ""
            commission = ""
            
            # 查找商家名称（<div NAME/> 格式）
            for j in range(i+1, min(i+5, len(lines))):
                name_match = re.search(r'<div\s+([^/>]+)/>', lines[j])
                if name_match:
                    potential_name = name_match.group(1).strip()
                    # 过滤掉明显不是名称的内容
                    if len(potential_name) > 2 and not potential_name.startswith('MID'):
                        name = potential_name
                        break
            
            # 查找 MID 和佣金
            for j in range(i, min(i+10, len(lines))):
                # 查找 MID
                mid_match = re.search(r'MID:\s*(\d+)', lines[j])
                if mid_match:
                    mid = mid_match.group(1)
                
                # 查找佣金（多种格式）
                # 格式: USD 34.50, 6.00%, € 1.33, 15.00%, etc.
                comm_line = lines[j]
                
                # 百分比格式
                percent_match = re.search(r'([\d.,]+)%', comm_line)
                if percent_match:
                    commission = percent_match.group(1) + "%"
                
                # 金额格式
                if not commission:
                    amount_match = re.search(r'(USD|EUR|GBP|\$|€)\s*([\d.,]+)', comm_line)
                    if amount_match:
                        commission = amount_match.group(1) + " " + amount_match.group(2)
            
            # 如果没有找到佣金，尝试其他模式
            if not commission:
                for j in range(i, min(i+10, len(lines))):
                    # 查找纯数字（可能是佣金）
                    if re.search(r'^[\d.,]+$', lines[j].strip()) and not lines[j].strip().startswith('['):
                        commission = lines[j].strip()
                        break
            
            # 保存商家数据（至少有名称或ID）
            if name or merchant_id:
                merchant = {
                    'merchant_id': merchant_id,
                    'name': name or f"Merchant_{merchant_id}",
                    'mid': mid or merchant_id,
                    'commission': commission or "N/A"
                }
                merchants.append(merchant)
                if len(merchants) <= 10:
                    print(f"提取: {name or 'Unknown'} - {commission}")
        
        i += 1
    
    return merchants


def main():
    print("开始解析商家数据...\n")
    
    # 读取页面内容
    try:
        with open('page_content.txt', 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("错误: 找不到 page_content.txt 文件")
        return
    
    print(f"页面内容长度: {len(content)} 字符\n")
    
    # 解析商家数据
    merchants = parse_elite_merchants(content)
    
    print(f"\n共解析 {len(merchants)} 个商家\n")
    
    if merchants:
        # 保存为 JSON
        output_dir = Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        json_file = output_dir / "yp_elite_merchants.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(merchants, f, ensure_ascii=False, indent=2)
        print(f"已保存: {json_file}")
        
        # 保存为 CSV
        csv_file = output_dir / "yp_elite_merchants.csv"
        import csv
        
        all_keys = set()
        for m in merchants:
            all_keys.update(m.keys())
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=sorted(all_keys))
            writer.writeheader()
            writer.writerows(merchants)
        
        print(f"已保存: {csv_file}")
        
        # 显示前20个商家
        print(f"\n前20个商家:")
        for i, m in enumerate(merchants[:20], 1):
            print(f"  {i}. {m.get('name', 'N/A')} - {m.get('commission', 'N/A')}")
        
        # 统计信息
        print(f"\n商家总数: {len(merchants)}")
        
        # 去重
        unique_merchants = {}
        for m in merchants:
            key = m['merchant_id']
            if key not in unique_merchants:
                unique_merchants[key] = m
        
        print(f"去重后商家数: {len(unique_merchants)}")
        
        # 保存去重后的数据
        unique_list = list(unique_merchants.values())
        with open(output_dir / "yp_elite_merchants_unique.json", 'w', encoding='utf-8') as f:
            json.dump(unique_list, f, ensure_ascii=False, indent=2)
        print(f"已保存去重数据: {output_dir / 'yp_elite_merchants_unique.json'}")


if __name__ == "__main__":
    main()
