#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
为yp_us_products表添加investment_score字段
"""

import mysql.connector
from mysql.connector import Error

def add_investment_score_column():
    """添加investment_score字段到yp_us_products表"""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            port=3306,
            database='affiliate_marketing',
            user='root',
            password='admin',
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        # 检查字段是否存在
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'affiliate_marketing' AND TABLE_NAME = 'yp_us_products' AND COLUMN_NAME = 'investment_score'")
        exists = cursor.fetchone()
        
        if exists:
            print("investment_score字段已存在")
        else:
            # 添加字段
            cursor.execute("ALTER TABLE yp_us_products ADD COLUMN investment_score FLOAT DEFAULT 0 COMMENT '投放价值分0-100'")
            conn.commit()
            print("investment_score字段添加成功")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Error as e:
        print(f"添加字段失败: {e}")
        return False

def update_build_us_cache():
    """更新build_us_cache.py脚本，在INSERT语句中包含investment_score字段"""
    try:
        with open('build_us_cache.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找INSERT语句
        if 'INSERT INTO yp_us_products' in content:
            # 检查INSERT语句是否包含investment_score
            if 'investment_score' not in content:
                # 找到INSERT语句的位置
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'INSERT INTO yp_us_products' in line:
                        # 查看INSERT语句的字段列表
                        insert_line = line
                        # 在字段列表中添加investment_score
                        if 'VALUES' in insert_line:
                            # 提取字段列表部分
                            fields_part = insert_line.split('VALUES')[0]
                            # 添加investment_score字段
                            if fields_part.endswith(','):
                                fields_part += ' investment_score'
                            else:
                                fields_part += ', investment_score'
                            # 重新构建INSERT语句
                            new_insert_line = fields_part + insert_line.split('VALUES')[1]
                            lines[i] = new_insert_line
                            print("已更新INSERT语句，添加investment_score字段")
                            break
        
                # 写入更新后的内容
                with open('build_us_cache.py', 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
        
        print("build_us_cache.py更新完成")
        return True
        
    except Exception as e:
        print(f"更新build_us_cache.py失败: {e}")
        return False

if __name__ == "__main__":
    print("开始为yp_us_products表添加investment_score字段...")
    
    # 添加字段到数据库
    if add_investment_score_column():
        print("数据库字段添加成功")
    else:
        print("数据库字段添加失败")
    
    # 更新build_us_cache.py脚本
    if update_build_us_cache():
        print("脚本更新成功")
    else:
        print("脚本更新失败")
    
    print("任务完成")