"""
终极诊断：用 curl 直接测量 Flask 响应时间
排查是 Flask 本身慢还是 perf 脚本测量问题
"""
import subprocess, time

urls = [
    ('http://localhost:5055/', '首页'),
    ('http://localhost:5055/qs_dashboard', '/qs_dashboard'),
    ('http://localhost:5055/competitor_ads', '/competitor_ads'),
    ('http://localhost:5055/api/products?page=1', '/api/products'),
    ('http://localhost:5055/api/merchants?page=1', '/api/merchants'),
]

print('=== curl 直接计时（排除 Python HTTP 客户端干扰）===')
import os
# 检查 curl 是否可用
try:
    result = subprocess.run(['curl', '--version'], capture_output=True, timeout=5)
    has_curl = result.returncode == 0
except:
    has_curl = False

if has_curl:
    for url, label in urls:
        result = subprocess.run(
            ['curl', '-s', '-o', os.devnull, '-w', '%{time_total}', url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            ms = float(result.stdout.strip()) * 1000
            status = "✅" if ms < 500 else ("⚠️" if ms < 2000 else "❌")
            print(f'{status} [{ms:8.1f}ms] {label}')
else:
    print('curl 不可用，用 urllib 测量')

print()
print('=== urllib 逐一测量（等待前一个完全完成再测下一个）===')
import urllib.request

for url, label in urls:
    # 连续测5次，取中位数
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        try:
            r = urllib.request.urlopen(url, timeout=15)
            r.read()
            ms = (time.perf_counter()-t0)*1000
            times.append(ms)
        except Exception as e:
            times.append(-1)
        time.sleep(0.1)
    
    valid = sorted([x for x in times if x > 0])
    if valid:
        best = valid[0]
        median = valid[len(valid)//2]
        status = "✅" if best < 500 else ("⚠️" if best < 2000 else "❌")
        print(f'{status} [{best:8.1f}ms best / {median:8.1f}ms median] {label}')
    else:
        print(f'❌ ERROR: {label}')
    time.sleep(0.5)  # 给 Flask 休息

print()
print('完成')
