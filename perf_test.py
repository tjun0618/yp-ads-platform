"""
验证优化效果：实际测量各接口响应时间
"""
import urllib.request
import time
import json

BASE = "http://localhost:5055"

tests = [
    ("首页 /", "/"),
    ("商品列表 API", "/api/merchant_products?merchant_id=DOVOH"),
    ("商品管理 API", "/api/products?size=50"),
    ("商户作战室", "/api/merchant_room/DOVOH"),
    ("QS仪表板", "/api/qs/dashboard"),
    ("竞品商户", "/api/competitor/merchants"),
]

print("=" * 65)
print(f"{'接口':<30} {'状态':>6} {'耗时(ms)':>10} {'结果':>8}")
print("=" * 65)

for name, path in tests:
    url = BASE + path
    t0 = time.time()
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            body = r.read()
            elapsed_ms = (time.time() - t0) * 1000
            status = r.status
            ct = r.headers.get('Content-Type', '')
            if 'json' in ct:
                data = json.loads(body)
                if isinstance(data, dict):
                    extra = f"ok={data.get('ok', data.get('success', '?'))}"
                else:
                    extra = f"items={len(data)}"
            else:
                extra = f"html,{len(body)}B"
    except Exception as e:
        elapsed_ms = (time.time() - t0) * 1000
        status = 'ERR'
        extra = str(e)[:30]
    
    flag = "✅" if elapsed_ms < 500 else ("⚠️ " if elapsed_ms < 2000 else "❌")
    print(f"{flag} {name:<28} {str(status):>6} {elapsed_ms:>10.0f}ms  {extra}")

print("=" * 65)
print("说明: <500ms=优秀 | 500-2000ms=可接受 | >2000ms=需优化")
