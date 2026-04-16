"""单接口精准计时：消除串行等待带来的假2秒"""
import urllib.request, time

def http_get(url):
    req = urllib.request.urlopen(url, timeout=15)
    data = req.read()
    return len(data)

print('=== 单接口独立计时（消除串行干扰）===')
print()

# 每个接口单独测3次，取最快
for url, label in [
    ('http://localhost:5055/', '首页 /'),
    ('http://localhost:5055/api/products?page=1', '/api/products?page=1'),
    ('http://localhost:5055/api/merchants?page=1', '/api/merchants?page=1'),
    ('http://localhost:5055/qs_dashboard', '/qs_dashboard'),
    ('http://localhost:5055/competitor_ads', '/competitor_ads'),
    ('http://localhost:5055/api/merchant_room/363047', '/api/merchant_room/363047'),
]:
    times = []
    for i in range(3):
        t0 = time.perf_counter()
        try:
            size = http_get(url)
            ms = (time.perf_counter()-t0)*1000
            times.append(ms)
        except Exception as e:
            times.append(-1)
        time.sleep(0.05)  # 短暂间隔
    
    valid = [x for x in times if x > 0]
    if valid:
        best = min(valid)
        avg = sum(valid)/len(valid)
        status = "✅" if best < 500 else ("⚠️" if best < 2000 else "❌")
        print(f'{status} {label:40s} 最快={best:.0f}ms  平均={avg:.0f}ms')
    else:
        print(f'❌ {label:40s} ERROR')

print()
print('说明: <500ms=优秀 | 500-2000ms=可接受 | >2000ms=需优化')
