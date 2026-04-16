import json

with open('output/asin_merchant_map.json', 'r') as f:
    asin_map = json.load(f)

# Check first 5 entries
print("First 5 ASIN entries:")
for i, (asin, info) in enumerate(list(asin_map.items())[:5]):
    mid = info.get('merchant_id')
    name = info.get('merchant_name', 'Unknown')
    name_safe = name.encode('ascii', 'ignore').decode('ascii') if name else 'Unknown'
    print(f"  {asin}: mid={mid}, name={name_safe}")

# Count unique merchant IDs
mids = set(info.get('merchant_id') for info in asin_map.values())
print(f"\nUnique merchant IDs: {len(mids)}")
print(f"Sample IDs: {list(mids)[:10]}")

# Check if None is in the set
if None in mids:
    print("\nWARNING: Some entries have None as merchant_id!")
    none_count = sum(1 for info in asin_map.values() if info.get('merchant_id') is None)
    print(f"Entries with None merchant_id: {none_count}")
