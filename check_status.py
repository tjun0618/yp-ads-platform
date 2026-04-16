import json

# Check full collect state
state_file = 'output/full_collect_state.json'
merchants_file = 'output/merchants_data.json'

try:
    with open(state_file, 'r') as f:
        state = json.load(f)
    print('Full collect state:')
    print(f"  merchants_page: {state.get('merchants_page', 0)}")
    print(f"  total_merchants: {state.get('total_merchants', 0)}")
except Exception as e:
    print(f'No full_collect_state.json: {e}')

# Check ASIN map
try:
    with open('output/asin_merchant_map.json', 'r') as f:
        asin_map = json.load(f)
    print(f"\nASIN map: {len(asin_map)} entries")
    if asin_map:
        print(f"Sample ASINs: {list(asin_map.keys())[:5]}")
except Exception as e:
    print(f'No ASIN map found: {e}')

# Check merchants data
try:
    with open(merchants_file, 'r', encoding='utf-8') as f:
        merchants = json.load(f)
    print(f"\nMerchants data: {len(merchants)} entries")
    if merchants:
        print(f"First merchant: {merchants[0].get('name', merchants[0].get('merchant_name', 'Unknown'))}")
except Exception as e:
    print(f'No merchants data: {e}')
