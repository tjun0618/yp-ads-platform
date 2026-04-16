import mysql.connector
conn = mysql.connector.connect(
    host='localhost', port=3306, user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor()

cols_to_add = [
    ('ai_strategy_notes', 'TEXT NULL'),
    ('ai_generated', 'TINYINT(1) DEFAULT 0'),
]
for col, ddl in cols_to_add:
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema='affiliate_marketing' AND table_name='ads_plans' AND column_name=%s",
        (col,)
    )
    if cur.fetchone()[0] == 0:
        cur.execute(f'ALTER TABLE ads_plans ADD COLUMN {col} {ddl}')
        print(f'Added column: {col}')
    else:
        print(f'Already exists: {col}')

conn.commit()
conn.close()
print('Done.')
