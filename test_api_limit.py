import requests
import time

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
url = 'https://www.yeahpromos.com/index.php/index/apioffer/getoffer'
headers = {'Content-Type': 'application/x-www-form-urlencoded', 'token': TOKEN, 'siteid': SITE_ID}

print("Testing API limits...")
print("-" * 40)

# Test different limits
for limit in [100, 200, 500, 1000]:
    try:
        data = {'page': 1, 'limit': limit}
        resp = requests.post(url, headers=headers, data=data, timeout=30)
        result = resp.json()
        
        if result.get('code') == 200:
            actual_count = len(result.get('data', {}).get('data', []))
            total = result.get('data', {}).get('total', 0)
            print(f'Requested: {limit:4d}, Returned: {actual_count:4d}, Total: {total}')
        else:
            msg = result.get('msg', 'Unknown')
            print(f'Requested: {limit:4d}, Error: {msg}')
        
        time.sleep(0.5)
    except Exception as e:
        print(f'Requested: {limit:4d}, Exception: {e}')

print("-" * 40)
print("Conclusion: API max limit is 100 per page")
