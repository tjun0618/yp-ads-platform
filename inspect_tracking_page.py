"""深度测试 tracking_url：检查响应头、尝试带 Cookie、查看完整响应"""
import requests

url = "https://yeahpromos.com/index/index/openurlproduct?track=1571c8c1f6b0a14a&pid=242"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# 1. 不跟随跳转，看原始响应头
resp = requests.get(url, headers=headers, allow_redirects=False, timeout=15)
print("=== 不跟随跳转 ===")
print(f"状态码: {resp.status_code}")
print(f"响应头 Location: {resp.headers.get('Location', 'N/A')}")
print(f"响应头 Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
print(f"响应体长度: {len(resp.text)}")
print(f"响应体: {repr(resp.text[:500])}")
print()
print("所有响应头:")
for k, v in resp.headers.items():
    print(f"  {k}: {v}")
