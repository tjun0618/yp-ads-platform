import mysql.connector
c = mysql.connector.connect(host='localhost', user='root', password='admin', database='affiliate_marketing')
cur = c.cursor()
cur.execute("DELETE FROM amazon_product_details WHERE asin='B0CPW78492'")
c.commit()
print(f"已删除 {cur.rowcount} 条测试记录")
c.close()
