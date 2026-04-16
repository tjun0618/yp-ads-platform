import requests

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 尝试不同页面
urls = [
    "https://www.yeahpromos.com/index/offer/advertList",
    "https://www.yeahpromos.com/index/offer/offerList",
    "https://www.yeahpromos.com/index/user/index",
    "https://www.yeahpromos.com/index/affiliate/advertList",
]

for url in urls:
    try:
        resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=15)
        print(f"URL: {url}")
        print(f"  Status: {resp.status_code}, Len: {len(resp.text)}")
        print(f"  Final: {resp.url}")
        # print first 300 chars
        print(f"  Content: {resp.text[:200]}")
        print()
    except Exception as e:
        print(f"  Error: {e}")
