"""
捕获 YP 页面加载时的所有网络请求（不过滤），找真实 API
"""
from playwright.sync_api import sync_playwright
import json, time

PHPSESSID = "932a965dc80f3c5bc7fe2226771950fc"

PAGES = [
    ("brands", "https://yeahpromos.com/index/offer/brands"),
    ("advert_index", "https://yeahpromos.com/index/advert/index"),
    ("report_performance", "https://yeahpromos.com/index/offer/report_performance?start_date=2026-03-01&end_date=2026-03-23&site_id=12002&dim=CampaignId"),
    ("brand_detail_nortiv8", "https://yeahpromos.com/index/offer/brand_detail?advert_id=362548"),
    ("offer_index", "https://yeahpromos.com/index/offer/index"),
]

all_results = {}

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        context.add_cookies([
            {"name": "PHPSESSID", "value": PHPSESSID, "domain": "yeahpromos.com", "path": "/"},
            {"name": "user_id", "value": "2864", "domain": "yeahpromos.com", "path": "/"},
            {"name": "user_name", "value": "Tong Jun", "domain": "yeahpromos.com", "path": "/"},
            {"name": "think_lang", "value": "zh-cn", "domain": "yeahpromos.com", "path": "/"},
        ])
        
        for page_name, page_url in PAGES:
            print(f"\n{'='*60}")
            print(f"[{page_name}] {page_url}")
            print('='*60)
            
            page_requests = []
            
            page = context.new_page()
            
            def capture_response(response):
                url = response.url
                status = response.status
                ct = response.headers.get("content-type", "")
                
                # 跳过静态资源
                skip_ext = ['.css', '.js', '.png', '.jpg', '.gif', '.ico', '.woff', '.ttf', '.svg', '.webp']
                if any(url.endswith(x) or f'{x}?' in url for x in skip_ext):
                    return
                
                # 记录所有 yeahpromos.com 的请求
                if "yeahpromos.com" in url and url != page_url:
                    entry = {"url": url, "status": status, "content_type": ct[:50]}
                    
                    if "json" in ct:
                        try:
                            body = response.json()
                            entry["json"] = body
                            print(f"  [JSON] {url}")
                            print(f"         status={status}, keys={list(body.keys()) if isinstance(body, dict) else type(body).__name__}")
                        except:
                            pass
                    elif "spreadsheet" in ct or "excel" in ct:
                        try:
                            body = response.body()
                            entry["excel_size"] = len(body)
                            print(f"  [EXCEL] {url} ({len(body)} bytes)")
                        except:
                            pass
                    elif "html" not in ct:  # 非 HTML 的其他类型
                        print(f"  [{ct[:20]}] {url}")
                    
                    page_requests.append(entry)
            
            page.on("response", capture_response)
            
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=25000)
                final_url = page.url
                
                if "login" in final_url:
                    print("  => Login redirect! Session expired.")
                    page.close()
                    continue
                
                print(f"  => Loaded: {final_url}")
                print(f"  => Title: {page.title()}")
                
                # 等待异步请求
                time.sleep(3)
                
                # 获取页面嵌入的 JSON 数据
                inline_data = page.evaluate("""() => {
                    const scripts = Array.from(document.querySelectorAll('script:not([src])'));
                    const data = [];
                    for (const s of scripts) {
                        const t = s.textContent.trim();
                        if (t.length > 100) {
                            // 查找 JSON 对象
                            const jsonMatches = t.match(/\{[^{}]{50,}\}/g) || [];
                            for (const m of jsonMatches.slice(0, 5)) {
                                try {
                                    const parsed = JSON.parse(m);
                                    data.push({source: 'inline_script', data: parsed});
                                } catch(e) {}
                            }
                            // 查找 API 端点
                            const apiMatches = t.match(/\/index\/[a-z_\/]+/g) || [];
                            if (apiMatches.length > 0) {
                                data.push({source: 'api_in_script', apis: [...new Set(apiMatches)]});
                            }
                        }
                    }
                    return data;
                }""")
                
                if inline_data:
                    print(f"  Inline script data ({len(inline_data)} items):")
                    for item in inline_data:
                        print(f"    {item}")
                
                # 保存 HTML 以便后续分析
                html = page.content()
                with open(f'output/page_{page_name}.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"  HTML saved: output/page_{page_name}.html ({len(html)} chars)")
                
                all_results[page_name] = {
                    "url": page_url,
                    "final_url": final_url,
                    "requests": page_requests,
                    "inline_data": inline_data
                }
                
            except Exception as e:
                print(f"  Error: {e}")
            finally:
                page.close()
        
        browser.close()
    
    # 保存完整结果
    with open('output/all_page_requests.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nAll results saved to output/all_page_requests.json")

if __name__ == '__main__':
    run()
