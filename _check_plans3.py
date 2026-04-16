import mysql.connector, json

conn = mysql.connector.connect(
    host='localhost', user='root', password='admin',
    database='affiliate_marketing', charset='utf8mb4'
)
cur = conn.cursor(dictionary=True)
asin = 'B0FX34NS5K'

# 看 ai_strategy_notes 完整内容
cur.execute("SELECT ai_strategy_notes FROM ads_plans WHERE asin=%s", (asin,))
row = cur.fetchone()
notes_raw = row['ai_strategy_notes']
print(f'ai_strategy_notes length: {len(str(notes_raw))}')
print(f'Type: {type(notes_raw)}')

if isinstance(notes_raw, str):
    try:
        notes = json.loads(notes_raw)
    except:
        notes = notes_raw
elif isinstance(notes_raw, dict):
    notes = notes_raw
else:
    notes = notes_raw

if isinstance(notes, dict):
    print('Keys:', list(notes.keys()))
    # 打印结构
    for k, v in notes.items():
        if isinstance(v, (list, dict)):
            print(f'  {k}: [{type(v).__name__} len={len(v)}]')
            if isinstance(v, list) and v:
                print(f'    first item keys: {list(v[0].keys()) if isinstance(v[0], dict) else str(v[0])[:100]}')
        else:
            print(f'  {k}: {str(v)[:200]}')
else:
    print('Content (first 2000 chars):')
    print(str(notes)[:2000])

conn.close()
