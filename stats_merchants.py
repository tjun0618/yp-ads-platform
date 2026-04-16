#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""查询 yp_merchants_full 表统计信息"""

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

    # 总记录数
    cursor.execute("SELECT COUNT(*) FROM yp_merchants_full")
    total = cursor.fetchone()[0]
    print(f"============================================================")
    print(f"YP 商户数据统计 - yp_merchants_full")
    print(f"============================================================")
    print(f"总商户数: {total:,}")

    # 按国家统计
    print(f"\nTop 10 国家 (按商户数量):")
    cursor.execute("SELECT country_code, COUNT(*) FROM yp_merchants_full GROUP BY country_code ORDER BY COUNT(*) DESC LIMIT 10")
    for row in cursor.fetchall():
        print(f"  {row[0] if row[0] else '(none)'}: {row[1]:,}")

    # 佣金率 >= 10% 统计
    cursor.execute("SELECT COUNT(*) FROM yp_merchants_full WHERE avg_payout >= 10")
    high_commission = cursor.fetchone()[0]
    print(f"\n佣金率 >= 10%: {high_commission:,} 个")

    # 平均佣金率
    cursor.execute("SELECT AVG(avg_payout) FROM yp_merchants_full WHERE avg_payout > 0")
    avg_commission = cursor.fetchone()[0]
    print(f"平均佣金率 (有佣金数据): {avg_commission:.2f}%")

    # 平均 Cookie 天数
    cursor.execute("SELECT AVG(cookie_days) FROM yp_merchants_full")
    avg_cookie = cursor.fetchone()[0]
    print(f"平均 Cookie 天数: {avg_cookie:.0f} 天")

    # 支持深度链接
    cursor.execute("SELECT COUNT(*) FROM yp_merchants_full WHERE is_deeplink = 'Yes'")
    deeplink = cursor.fetchone()[0]
    print(f"支持深度链接: {deeplink:,} 个")

    print(f"\n============================================================")
    conn.close()

if __name__ == "__main__":
    main()
