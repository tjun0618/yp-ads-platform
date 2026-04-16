import requests
import re
import json

COOKIES = {
    "PHPSESSID": "932a965dc80f3c5bc7fe2226771950fc",
    "user_id": "2864",
    "user_name": "Tong%20Jun",
    "think_lang": "zh-cn"
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
SITE_ID = "12002"

# Test with a few merchants
test_mids = [
    ("363372", "TruSkin"),
    ("362247", "Physicians Choice"),
    ("200000", "Test"),
]

for mid, name in test_mids:
    url = "https://www.yeahpromos.com/index/offer/brand_detail?advert_id=" + mid + "&site_id=" + SITE_ID
    resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=20)
    
    html = resp.text
    track_match = re.search(r"track=([a-f0-9]{16})", html)
    clipboard_urls = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
    asins = re.findall(r"asin=([A-Z0-9]{10})", html)
    
    track = track_match.group(1) if track_match else None
    print(name + " (MID=" + mid + "):")
    print("  Status=" + str(resp.status_code) + ", Track=" + str(track))
    print("  ClipboardJS URLs: " + str(len(clipboard_urls)))
    print("  ASINs found: " + str(len(asins)))
    if clipboard_urls:
        print("  Sample URL: " + clipboard_urls[0][:100])
    print()
