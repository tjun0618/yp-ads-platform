#!/usr/bin/env python3
"""
测试 YP API 的限流策略
"""
import requests
import time

TOKEN = '7951dc7484fa9f9d'
SITE_ID = '12002'
url = 'https://www.yeahpromos.com/index.php/index/apioffer/getoffer'
headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'token': TOKEN,
    'siteid': SITE_ID
}

def test_request():
    """Make a single API request and return success status"""
    try:
        data = {'page': 1, 'limit': 10}
        resp = requests.post(url, headers=headers, data=data, timeout=30)
        result = resp.json()
        
        if result.get('code') == 200:
            return True, len(result.get('data', {}).get('data', []))
        else:
            return False, result.get('msg', 'Unknown error')
    except Exception as e:
        return False, str(e)

print("=" * 60)
print("YP API 限流测试")
print("=" * 60)

# Test 1: Rapid requests
print("\n[测试1] 快速连续请求 (间隔 0.5 秒):")
for i in range(5):
    success, info = test_request()
    status = "OK" if success else f"FAIL: {info}"
    print(f"  请求 {i+1}: {status}")
    if not success:
        print("  -> 被限流了，停止测试")
        break
    time.sleep(0.5)

# Test 2: Wait and retry
print("\n[测试2] 等待 10 秒后重试:")
time.sleep(10)
success, info = test_request()
status = "OK" if success else f"FAIL: {info}"
print(f"  请求: {status}")

# Test 3: If failed, wait longer
if not success:
    print("\n[测试3] 等待 30 秒后重试:")
    time.sleep(30)
    success, info = test_request()
    status = "OK" if success else f"FAIL: {info}"
    print(f"  请求: {status}")

# Test 4: If still failed, wait 60s
if not success:
    print("\n[测试4] 等待 60 秒后重试:")
    time.sleep(60)
    success, info = test_request()
    status = "OK" if success else f"FAIL: {info}"
    print(f"  请求: {status}")

print("\n" + "=" * 60)
if success:
    print("结论: API 已恢复，可以继续采集")
else:
    print("结论: API 仍然限流，需要更长时间等待")
print("=" * 60)
