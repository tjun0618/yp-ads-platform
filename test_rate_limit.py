#!/usr/bin/env python3
"""
测试 YP API 的限流上限
"""
import requests
import time
import json

TOKEN = "7951dc7484fa9f9d"
HEADERS = {"token": TOKEN}
SITE_ID = "12002"

def test_api_call():
    """Make a single API call and return success status"""
    url = "https://www.yeahpromos.com/index/apioffer/getoffer"
    params = {"site_id": SITE_ID, "page": 1, "limit": 10}
    
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                if data.get("status") == "SUCCESS":
                    return True, "OK"
                else:
                    return False, f"API_ERROR: {data.get('msg', 'Unknown')}"
            except:
                return False, "JSON_PARSE_ERROR"
        else:
            return False, f"HTTP_{resp.status_code}"
    except Exception as e:
        return False, f"EXCEPTION: {e}"

def test_burst_requests(count, delay_ms=0):
    """Test burst of requests"""
    print(f"\n测试连续发送 {count} 个请求 (间隔 {delay_ms}ms)...")
    
    success_count = 0
    fail_count = 0
    first_fail = None
    
    for i in range(count):
        success, msg = test_api_call()
        
        if success:
            success_count += 1
            print(f"  [{i+1}/{count}] OK")
        else:
            fail_count += 1
            if first_fail is None:
                first_fail = msg
            print(f"  [{i+1}/{count}] FAIL: {msg}")
        
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
    
    print(f"\n结果: 成功 {success_count}/{count}, 失败 {fail_count}/{count}")
    if first_fail:
        print(f"首次失败原因: {first_fail}")
    
    return success_count == count

def test_with_intervals():
    """Test different intervals"""
    print("=" * 60)
    print("YP API 限流测试")
    print("=" * 60)
    
    # Test 1: Burst without delay
    print("\n【测试1】连续快速发送 20 个请求")
    test_burst_requests(20, delay_ms=0)
    
    time.sleep(2)  # Cool down
    
    # Test 2: 100ms interval
    print("\n【测试2】间隔 100ms 发送 20 个请求")
    test_burst_requests(20, delay_ms=100)
    
    time.sleep(2)
    
    # Test 3: 200ms interval
    print("\n【测试3】间隔 200ms 发送 20 个请求")
    test_burst_requests(20, delay_ms=200)
    
    time.sleep(2)
    
    # Test 4: 500ms interval
    print("\n【测试4】间隔 500ms 发送 20 个请求")
    test_burst_requests(20, delay_ms=500)
    
    time.sleep(2)
    
    # Test 5: Find minimum safe interval
    print("\n【测试5】寻找最小安全间隔...")
    for interval in [50, 100, 150, 200, 250, 300]:
        print(f"\n测试间隔 {interval}ms:")
        success = test_burst_requests(10, delay_ms=interval)
        if success:
            print(f"  ✓ {interval}ms 是安全间隔")
            break
        time.sleep(2)

def test_sustained_rate():
    """Test sustained rate over time"""
    print("\n" + "=" * 60)
    print("【测试6】持续速率测试 (1分钟)")
    print("=" * 60)
    
    interval = 0.3  # 300ms
    duration = 60  # 1 minute
    count = int(duration / interval)
    
    print(f"间隔: {interval*1000:.0f}ms, 预计发送: {count} 个请求")
    
    success_count = 0
    fail_count = 0
    
    for i in range(count):
        success, msg = test_api_call()
        
        if success:
            success_count += 1
        else:
            fail_count += 1
            print(f"  [{i+1}] FAIL: {msg}")
        
        if (i + 1) % 10 == 0:
            print(f"  进度: {i+1}/{count}, 成功: {success_count}, 失败: {fail_count}")
        
        time.sleep(interval)
    
    print(f"\n结果: 成功 {success_count}/{count}, 失败: {fail_count}")
    print(f"成功率: {success_count/count*100:.1f}%")

def main():
    test_with_intervals()
    
    # Ask if user wants to run sustained test
    print("\n" + "=" * 60)
    response = input("是否运行1分钟持续速率测试? (y/n): ")
    if response.lower() == 'y':
        test_sustained_rate()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
    print("\n建议:")
    print("  - 如果 100-200ms 间隔测试通过, 建议日常使用 300ms 间隔")
    print("  - 如果 200-300ms 间隔测试通过, 建议日常使用 500ms 间隔")
    print("  - 批量采集时建议添加更长的间隔 (1-2秒)")

if __name__ == "__main__":
    main()
