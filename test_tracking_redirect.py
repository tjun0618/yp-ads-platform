"""测试 tracking_url 跳转行为，看能否通过 requests 直接获取最终 Amazon URL"""
import requests

test_urls = [
    "https://yeahpromos.com/index/index/openurlproduct?track=1571c8c1f6b0a14a&pid=242",
    "https://yeahpromos.com/index/index/openurlproduct?track=1571c8c1f6b0a14a&pid=359",
    "https://yeahpromos.com/index/index/openurlproduct?track=1571c8c1f6b0a14a&pid=1329",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

session = requests.Session()

for url in test_urls:
    print(f"\n[测试] {url}")
    try:
        resp = session.get(url, headers=headers, allow_redirects=True, timeout=15)
        print(f"  状态码: {resp.status_code}")
        print(f"  最终 URL: {resp.url}")
        print(f"  跳转历史: {[r.url for r in resp.history]}")
        is_amazon = "amazon.com" in resp.url
        print(f"  是亚马逊链接: {is_amazon}")
    except Exception as e:
        print(f"  错误: {e}")
