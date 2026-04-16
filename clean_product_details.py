# -*- coding: utf-8 -*-
"""
清洗 amazon_product_details.product_details 字段中的 JS 代码脏数据
- 删除 key 为 "Customer Reviews" / "ASIN" 的条目
- 删除 value 中含 JS 特征（P.when、.execute、function(、onclick= 等）的条目
"""
import json
import re
import mysql.connector

DB_CONFIG = dict(host='localhost', user='root', password='admin',
                 database='affiliate_marketing', charset='utf8mb4')

JS_PATTERNS = re.compile(r'P\.when\(|\.execute\(|function\(|onclick=|addEventListener|<script', re.IGNORECASE)
SKIP_KEYS = {'customer reviews', 'asin'}


def clean_details(raw: str) -> tuple[str, int]:
    """返回 (清洗后JSON字符串, 删掉的条目数)"""
    try:
        d = json.loads(raw)
    except Exception:
        return raw, 0

    cleaned = {}
    removed = 0
    for k, v in d.items():
        if k.lower() in SKIP_KEYS:
            removed += 1
            continue
        if isinstance(v, str) and JS_PATTERNS.search(v):
            removed += 1
            continue
        cleaned[k] = v

    return json.dumps(cleaned, ensure_ascii=False), removed


def main():
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT asin, product_details FROM amazon_product_details WHERE product_details IS NOT NULL")
    rows = cur.fetchall()
    print(f"共 {len(rows)} 条记录需要检查...")

    updated = 0
    total_removed = 0
    for asin, raw in rows:
        new_val, removed = clean_details(raw)
        if removed > 0:
            cur.execute(
                "UPDATE amazon_product_details SET product_details=%s WHERE asin=%s",
                (new_val, asin)
            )
            updated += 1
            total_removed += removed
            print(f"  [{asin}] 清除 {removed} 个脏条目")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\n完成：更新 {updated} 条记录，共清除 {total_removed} 个脏条目")


if __name__ == '__main__':
    main()
