#!/usr/bin/env python3
import json

with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("First 10 merchants:")
for i, m in enumerate(data[:10]):
    mid = m.get("merchant_id") or m.get("mid") or m.get("id")
    name = m.get("merchant_name", "Unknown")
    name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
    print(f"  {i+1}. MID={mid}, Name={name_safe}")
