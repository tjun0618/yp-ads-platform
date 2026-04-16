import requests, time, sys

resp = requests.get('http://localhost:5055/api/generate_ai/B0FX34NS5K?llm=kimi', stream=True, timeout=20)
print(f'Status: {resp.status_code}')
print(f'Content-Type: {resp.headers.get("Content-Type")}')
sys.stdout.flush()

count = 0
start = time.time()
for line in resp.iter_lines(decode_unicode=True):
    elapsed = time.time() - start
    print(f'[{elapsed:.1f}s] {line}')
    sys.stdout.flush()
    count += 1
    if count > 20 or elapsed > 15:
        break
print(f'Total lines received: {count}')
