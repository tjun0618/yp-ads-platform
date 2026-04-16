#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出 affiliate_marketing 数据库所有表及结构"""

import mysql.connector

# MySQL 数据库配置
MYSQL_CONFIG = dict(
    host='localhost',
    port=3306,
    user='root',
    password='admin',
    database='affiliate_marketing',
    charset='utf8mb4'
)

def main():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    print("============================================================")
    print("数据库: affiliate_marketing")
    print("============================================================")

    # 列出所有表
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]

    print(f"\n共有 {len(tables)} 个表:\n")
    for t in tables:
        print(f"  - {t}")

    # 显示每个表结构
    print("\n============================================================")
    print("每个表结构:")
    print("============================================================")

    for table in tables:
        print(f"\n* {table}:")
        cursor.execute(f"DESCRIBE {table}")
        cols = cursor.fetchall()
        for c in cols:
            field = c[0]
            typ = c[1]
            key = c[3]
            pk_mark = " (PK)" if key == "PRI" else ""
            print(f"  {field:<24} {typ:<18} {pk_mark}")

    conn.close()
    print("\n============================================================")

if __name__ == "__main__":
    main()
