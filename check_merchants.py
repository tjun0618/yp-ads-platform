#!/usr/bin/env python3
import json

with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total merchants: {len(data)}')
if data:
    m = data[0]
    mid = m.get('mid') or m.get('id') or m.get('advert_id')
    name = m.get('merchant_name') or m.get('name', 'Unknown')
    print(f'First merchant MID: {mid}')
    print(f'First merchant Name: {name.encode("ascii", "ignore").decode("ascii")}')
    print(f'Keys: {list(m.keys())}')
