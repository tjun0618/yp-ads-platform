import time, requests

s = requests.Session()

t0 = time.perf_counter()
r = s.get('http://127.0.0.1:5055/api/merchants?tab=approved&page=1&size=50')
ms = (time.perf_counter()-t0)*1000

print(f'HTTP状态: {r.status_code}')
print(f'响应时间: {ms:.0f}ms')
print(f'Content-Type: {r.headers.get("Content-Type","?")}')

if r.status_code == 200:
    try:
        data = r.json()
        print(f'total: {data.get("total")}')
        print(f'pages: {data.get("pages")}')
        print(f'items count: {len(data.get("items", []))}')
        print(f'summary: {data.get("summary")}')
        if data.get("items"):
            print(f'第一条: {list(data["items"][0].keys())}')
    except Exception as e:
        print(f'JSON解析失败: {e}')
        print(f'响应前500字: {r.text[:500]}')
else:
    print(f'非200响应，内容: {r.text[:800]}')

# 再测一次看是否有缓存加速
t0 = time.perf_counter()
r2 = s.get('http://127.0.0.1:5055/api/merchants?tab=approved&page=1&size=50')
ms2 = (time.perf_counter()-t0)*1000
print(f'\n第二次请求: {ms2:.0f}ms  (HTTP {r2.status_code})')

# 测商户管理主页 HTML
t0 = time.perf_counter()
r3 = s.get('http://127.0.0.1:5055/merchants')
ms3 = (time.perf_counter()-t0)*1000
print(f'/merchants 页面: {ms3:.0f}ms  ({len(r3.content)//1024}KB, HTTP {r3.status_code})')
