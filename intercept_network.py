"""
用 Playwright 打开 YP 关键页面，注入 Cookie，
监听所有 XHR/Fetch 请求，输出真实 API 端点
"""
import subprocess
import sys
import json
import time

# 检查 playwright 是否安装
try:
    from playwright.sync_api import sync_playwright
    print("[OK] playwright already installed")
except ImportError:
    print("Installing playwright...")
    subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)
    from playwright.sync_api import sync_playwright

PHPSESSID = "932a965dc80f3c5bc7fe2226771950fc"

PAGES_TO_VISIT = [
    "https://yeahpromos.com/index/offer/brands",
    "https://yeahpromos.com/index/advert/index",
    "https://yeahpromos.com/index/offer/report_performance?start_date=2026-03-01&end_date=2026-03-23&site_id=12002&dim=CampaignId",
    "https://yeahpromos.com/index/offer/brand_detail?advert_id=362548",
]

captured_requests = []

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # 注入 cookies
        context.add_cookies([
            {"name": "PHPSESSID", "value": PHPSESSID, "domain": "yeahpromos.com", "path": "/"},
            {"name": "user_id", "value": "2864", "domain": "yeahpromos.com", "path": "/"},
            {"name": "user_name", "value": "Tong%20Jun", "domain": "yeahpromos.com", "path": "/"},
            {"name": "think_lang", "value": "zh-cn", "domain": "yeahpromos.com", "path": "/"},
        ])
        
        page = context.new_page()
        
        # 监听所有网络请求
        api_calls = []
        
        def on_request(request):
            url = request.url
            method = request.method
            # 只记录 XHR/Fetch 或 JSON 相关的请求
            if any(x in url for x in ['/api/', '/index/api', '/json', 'get', 'list', 'search', 'export', 'query']):
                api_calls.append({
                    'url': url,
                    'method': method,
                    'resource_type': request.resource_type,
                    'headers': dict(request.headers),
                    'post_data': request.post_data
                })
        
        def on_response(response):
            url = response.url
            status = response.status
            content_type = response.headers.get('content-type', '')
            
            # 记录所有 JSON 和 Excel 响应
            if ('json' in content_type or 'spreadsheet' in content_type or 'excel' in content_type):
                try:
                    if 'json' in content_type:
                        body = response.json()
                        # 只记录有实际数据的响应
                        if body and body != {} and not (isinstance(body, dict) and body.get('status') == 302):
                            captured_requests.append({
                                'url': url,
                                'status': status,
                                'content_type': content_type,
                                'response_keys': list(body.keys()) if isinstance(body, dict) else type(body).__name__,
                                'response_preview': str(body)[:200]
                            })
                            print(f"  [JSON] {url}")
                            print(f"         Keys: {list(body.keys()) if isinstance(body, dict) else type(body).__name__}")
                    else:
                        captured_requests.append({
                            'url': url,
                            'status': status,
                            'content_type': content_type,
                            'response_keys': 'EXCEL/BINARY',
                            'response_preview': f'Binary data, {len(response.body())} bytes'
                        })
                        print(f"  [EXCEL] {url}")
                except Exception as e:
                    pass
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        for page_url in PAGES_TO_VISIT:
            print(f"\n{'='*60}")
            print(f"Visiting: {page_url}")
            print('='*60)
            try:
                page.goto(page_url, wait_until="networkidle", timeout=30000)
                current_url = page.url
                print(f"  Final URL: {current_url}")
                
                # 检查是否重定向到登录页
                if 'login' in current_url:
                    print("  => Redirected to login page (session expired)")
                    continue
                
                title = page.title()
                print(f"  Page title: {title}")
                
                # 等待一秒让异步请求完成
                time.sleep(2)
                
                # 尝试滚动页面触发懒加载
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
                
                # 截图保存
                screenshot_name = page_url.split('/')[-1].split('?')[0] or 'index'
                page.screenshot(path=f'output/intercept_{screenshot_name}.png')
                print(f"  Screenshot saved: output/intercept_{screenshot_name}.png")
                
            except Exception as e:
                print(f"  Error: {e}")
        
        browser.close()
    
    print(f"\n{'='*60}")
    print(f"CAPTURED {len(captured_requests)} API CALLS")
    print('='*60)
    for req in captured_requests:
        print(f"\n  URL: {req['url']}")
        print(f"  Content-Type: {req['content_type']}")
        print(f"  Keys/Type: {req['response_keys']}")
        print(f"  Preview: {req['response_preview'][:100]}")
    
    # 保存结果
    with open('output/intercepted_apis.json', 'w', encoding='utf-8') as f:
        json.dump(captured_requests, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to output/intercepted_apis.json")

if __name__ == '__main__':
    run()
