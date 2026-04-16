import json

# Load ASIN map
with open('output/asin_merchant_map.json', 'r') as f:
    asin_map = json.load(f)

print(f'Total ASINs in map: {len(asin_map)}')
print(f'Sample ASINs: {list(asin_map.keys())[:10]}')

# Target ASINs from Feishu
target_asins = [
    'B0GDXPNRD4', 'B0GL7QP2SF', 'B0C545BTQN', 'B0FNWMSTR8', 'B0BR6DL25V',
    'B0FF4PXHRN', 'B0GHSXZ9Q2', 'B0GHSW4VWY', 'B0BH9GBCFB', 'B0CQZ2HQBN'
]

found = []
for asin in target_asins:
    if asin in asin_map:
        found.append(asin)
        merchant = asin_map[asin].get('merchant_name', 'Unknown')
        print(f'Found: {asin} -> {merchant}')

print(f'\nFound {len(found)}/{len(target_asins)} target ASINs')

if len(found) == 0:
    print('\nNo matches yet. Need to scrape more merchants.')
    print('Current map covers first 50 merchants only.')
    print('Need to continue scraping the remaining 1550 merchants.')
