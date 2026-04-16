# -*- coding: utf-8 -*-
"""清除 amazon_product_details 中 title 为 NULL 的空数据记录"""
import mysql.connector

db = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = db.cursor()

cur.execute('SELECT COUNT(*) FROM amazon_product_details WHERE title IS NULL')
empty_count = cur.fetchone()[0]
print(f'准备删除 {empty_count} 条空数据（title=NULL）...')

cur.execute('DELETE FROM amazon_product_details WHERE title IS NULL')
db.commit()
print(f'已删除 {cur.rowcount} 条')

cur.execute('SELECT COUNT(*) FROM amazon_product_details')
remain = cur.fetchone()[0]
print(f'剩余有效记录: {remain} 条')

db.close()
