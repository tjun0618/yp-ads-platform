import json

with open('output/asin_merchant_map.json', 'r') as f:
    asin_map = json.load(f)

# Check merchant_id types
mids = set()
for info in asin_map.values():
    mid = info.get('merchant_id')
    mids.add(mid)

print(f'Unique merchant IDs in map: {len(mids)}')
print(f'Sample IDs: {list(mids)[:10]}')
print(f'ID types: {set(type(m) for m in mids)}')

# Check merchants file
with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
    merchants = json.load(f)

print(f'\nMerchants in file: {len(merchants)}')
if merchants:
    mid = merchants[0].get('id')
    print(f'Sample merchant ID: {mid}')
    print(f'Type: {type(mid)}')
    
    # Check if first merchant ID is in scraped set
    print(f'\nIs first merchant scraped? {mid in mids}')
    print(f'Is str(mid) in scraped? {str(mid) in [str(m) for m in mids]}')
