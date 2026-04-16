"""
分析商户页面HTML，找出pid和ASIN的对应关系
"""
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

mid = "363372"  # TruSkin
url = "https://www.yeahpromos.com/index/offer/brand_detail?advert_id=" + mid + "&site_id=" + SITE_ID
resp = requests.get(url, cookies=COOKIES, headers=HEADERS, timeout=20)
html = resp.text

# Save HTML for analysis
with open("output/truskin_brand_detail.html", "w", encoding="utf-8") as f:
    f.write(html)

print("HTML saved to output/truskin_brand_detail.html")
print("HTML length:", len(html))

# Find patterns
print("\n=== Track ===")
tracks = re.findall(r"track=([a-f0-9]{16})", html)
print("Tracks found:", set(tracks))

print("\n=== ClipboardJS URLs ===")
clipboard_urls = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", html)
print("Count:", len(clipboard_urls))
for u in clipboard_urls[:5]:
    print(" ", u)

print("\n=== Product IDs (pid) ===")
pids = re.findall(r"pid=(\d+)", html)
print("Count:", len(set(pids)))
print("Sample:", pids[:5])

print("\n=== Amazon links ===")
amazon_links = re.findall(r"amazon\.com[^\"'\s]*", html)
print("Count:", len(amazon_links))
for l in amazon_links[:5]:
    print(" ", l)

print("\n=== ASIN patterns ===")
# Various ASIN patterns
patterns = [
    r"ASIN[=:\s]+([A-Z0-9]{10})",
    r"/dp/([A-Z0-9]{10})",
    r"asin[=:\s]+([A-Z0-9]{10})",
    r'"asin":\s*"([A-Z0-9]{10})"',
    r"data-asin[=:\s\"']+([A-Z0-9]{10})",
]
for pat in patterns:
    found = re.findall(pat, html, re.IGNORECASE)
    if found:
        print(f"Pattern {pat[:40]}: {found[:3]}")

print("\n=== Around pid in HTML ===")
# Find context around pid
for m in re.finditer(r"pid=(\d+)", html):
    start = max(0, m.start()-200)
    end = min(len(html), m.end()+200)
    context = html[start:end].replace("\n", " ").replace("\r", "")
    print(f"\npid={m.group(1)} context:")
    print(context[:300])
    print("---")
    break  # Just show first one
