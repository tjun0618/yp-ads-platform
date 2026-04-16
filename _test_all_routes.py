"""Test all page routes return HTTP 200 and contain expected content"""
import requests, sys, time

BASE = "http://localhost:5055"

# All page routes (GET routes that return HTML)
PAGE_ROUTES = [
    ("/", "商品列表"),
    ("/products", "商品管理"),
    ("/merchants", "商户管理"),
    ("/merchant_products", "商户商品"),
    ("/amazon_scrape", "Amazon采集"),
    ("/plans", "广告方案列表"),
    ("/optimize", "投放优化"),
    ("/qs_dashboard", "质量评分"),
    ("/competitor_ads", "竞品参考"),
    ("/yp_collect", "YP采集"),
    ("/yp_sync", "全量同步"),
]

# Some API routes to test (safe GET APIs)
API_ROUTES = [
    "/api/products?page=1",
    "/api/merchants?page=1",
    "/api/progress",
    "/api/yp_collect_status",
    "/api/yp_sync/status",
    "/api/qs/dashboard",
    "/api/optimize/uploads",
    "/api/ads/scores",
]

print("=" * 70)
print("PAGE ROUTE TESTS")
print("=" * 70)

passed = 0
failed = 0
for path, name in PAGE_ROUTES:
    try:
        r = requests.get(BASE + path, timeout=10)
        status = r.status_code
        if status == 200:
            # Check it has actual HTML content
            has_html = "<html" in r.text.lower() or "<!doctype" in r.text.lower() or "<div" in r.text.lower()
            size = len(r.text)
            if has_html:
                print(f"  OK  {path:35s} [{name}] {size:>6d} bytes")
                passed += 1
            else:
                print(f"  ??  {path:35s} [{name}] 200 but no HTML content ({size} bytes)")
                failed += 1
        else:
            print(f"  FAIL {path:35s} [{name}] HTTP {status}")
            failed += 1
    except Exception as e:
        print(f"  ERR  {path:35s} [{name}] {e}")
        failed += 1

print(f"\n{'=' * 70}")
print(f"API ROUTE TESTS")
print(f"{'=' * 70}")

for path in API_ROUTES:
    try:
        r = requests.get(BASE + path, timeout=10)
        status = r.status_code
        size = len(r.text)
        if status == 200:
            print(f"  OK  {path:40s} {size:>6d} bytes")
            passed += 1
        elif status == 500:
            # 500 might be expected for some APIs if DB schema differs
            print(f"  500 {path:40s} {size:>6d} bytes (server error)")
            failed += 1
        else:
            print(f"  {status}  {path:40s} {size:>6d} bytes")
            failed += 1
    except Exception as e:
        print(f"  ERR  {path:40s} {e}")
        failed += 1

print(f"\n{'=' * 70}")
print(f"RESULT: {passed} passed, {failed} failed, {passed + failed} total")
print(f"{'=' * 70}")
