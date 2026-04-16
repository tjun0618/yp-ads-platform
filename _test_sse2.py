import requests, time, sys

resp = requests.get('http://localhost:5055/api/generate_ai/B0FX34NS5K?llm=kimi', stream=True, timeout=60)
print(f'Status: {resp.status_code}', flush=True)

count = 0
start = time.time()
has_thinking = False
for line in resp.iter_lines(decode_unicode=True):
    elapsed = time.time() - start
    if 'thinking' in line and 'text' in line and len(line) > 50:
        has_thinking = True
        print(f'[{elapsed:.1f}s] THINKING chunk (len={len(line)})', flush=True)
    elif line:
        print(f'[{elapsed:.1f}s] {line[:100]}', flush=True)
    count += 1
    if elapsed > 30:
        print(f'Timeout after 30s', flush=True)
        break

print(f'Total lines: {count}, has_thinking: {has_thinking}', flush=True)
