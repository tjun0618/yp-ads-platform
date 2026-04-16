#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 US 商户数据统计"""
import mysql.connector

def main():
    c = mysql.connector.connect(
        host='localhost',
        user='root',
        password='admin',
        database='affiliate_marketing'
    )
    cur = c.cursor()

    # 总记录数
    cur.execute('SELECT COUNT(*) FROM yp_merchants')
    total = cur.fetchone()[0]

    # US 商户统计
    cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE country LIKE 'US%'")
    us_total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE country LIKE 'US%' AND status = 'APPROVED'")
    us_approved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE country LIKE 'US%' AND status = 'UNAPPLIED'")
    us_unapplied = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM yp_merchants WHERE country LIKE 'US%' AND status = 'PENDING'")
    us_pending = cur.fetchone()[0]

    # 查看 country 字段的分布
    cur.execute("SELECT country, COUNT(*) as cnt FROM yp_merchants WHERE country IS NOT NULL GROUP BY country ORDER BY cnt DESC LIMIT 10")
    countries = cur.fetchall()

    cur.close()
    c.close()

    print("=" * 50)
    print("商户管理页面 - US 商户数据统计")
    print("=" * 50)
    print(f"\n数据库总记录数: {total}")
    print(f"\nUS 商户总数: {us_total}")
    print(f"  - APPROVED (已批准): {us_approved}")
    print(f"  - UNAPPLIED (未申请): {us_unapplied}")
    print(f"  - PENDING (审批中): {us_pending}")
    print(f"  - 其他状态: {us_total - us_approved - us_unapplied - us_pending}")

    print("\n" + "-" * 50)
    print("国家/地区分布 (Top 10):")
    print("-" * 50)
    for country, cnt in countries:
        print(f"  {country}: {cnt}")

    print("\n" + "=" * 50)
    print("数据准确性评估:")
    print("=" * 50)
    if us_total > 0:
        print(f"✓ US 商户占比: {us_total/total*100:.1f}%")
        print(f"✓ 已批准商户: {us_approved/us_total*100:.1f}%")
        print(f"✓ 未申请商户: {us_unapplied/us_total*100:.1f}%")
    else:
        print("✗ 暂无 US 商户数据")

if __name__ == '__main__':
    main()
