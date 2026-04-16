import json

# Check merchants data
with open('output/merchants_data.json', 'r', encoding='utf-8') as f:
    merchants = json.load(f)

print(f'Merchants in file: {len(merchants)}')

# Check full collect state
try:
    with open('output/full_collect_state.json', 'r') as f:
        state = json.load(f)
    print(f"Full collect merchants_page: {state.get('merchants_page', 0)}")
    print(f"Total merchants collected: {state.get('total_merchants', 0)}")
except Exception as e:
    print(f'No full_collect_state.json: {e}')

# Check ASIN map
try:
    with open('output/asin_merchant_map.json', 'r') as f:
        asin_map = json.load(f)
    print(f'ASIN map entries: {len(asin_map)}')
except:
    print('No ASIN map')
