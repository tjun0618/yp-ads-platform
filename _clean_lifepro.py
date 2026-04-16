import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    port=3306,
    user="root",
    password="admin",
    database="affiliate_marketing",
    charset="utf8mb4",
)
cur = conn.cursor()

# 清理 Lifepro 的所有旧关键词
cur.execute("DELETE FROM ads_merchant_keywords WHERE merchant_id = '362137'")
conn.commit()
print(f"Deleted {cur.rowcount} old keywords for Lifepro")

# 重新查询
cur.execute("SELECT COUNT(*) FROM ads_merchant_keywords WHERE merchant_id = '362137'")
print(f"Remaining: {cur.fetchone()[0]}")

conn.close()
