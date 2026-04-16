# -*- coding: utf-8 -*-
"""查看刚写入的商品详情"""
import mysql.connector, json

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin', database='affiliate_marketing'
)
cur = conn.cursor(dictionary=True)
cur.execute("SELECT * FROM amazon_product_details WHERE asin = 'B0CPW78492'")
row = cur.fetchone()
if row:
    for k, v in row.items():
        if v and str(v).strip():
            val_str = str(v)[:200]
            print(f"{k:20s}: {val_str}")
        else:
            print(f"{k:20s}: (空)")
conn.close()
