import requests
import re

cookies = {'PHPSESSID': '932a965dc80f3c5bc7fe2226771950fc'}
headers = {'User-Agent': 'Mozilla/5.0'}

url = 'https://www.yeahpromos.com/index/offer/brand_detail'
resp = requests.get(url, params={'advert_id': '363372', 'site_id': '12002'}, headers=headers, cookies=cookies)

print(f"Status: {resp.status_code}")
print(f"URL: {resp.url}")
print(f"Content length: {len(resp.text)}")

# Look for ASIN patterns (10 char alphanumeric)
asins = re.findall(r'[A-Z0-9]{10}', resp.text)
unique_asins = list(set(asins))[:20]
print(f"\nFound {len(set(asins))} unique ASIN-like patterns")
print("Sample:", unique_asins[:10])

# Look for amazon links
amazon_links = re.findall(r'https://www\.amazon\.com[^\'"\s]+', resp.text)
print(f"\nAmazon links found: {len(amazon_links)}")
for link in amazon_links[:5]:
    print(f"  {link}")

# Look for tracking links
tracking_links = re.findall(r"ClipboardJS\.copy\('([^']+)'\)", resp.text)
print(f"\nTracking links found: {len(tracking_links)}")
for link in tracking_links[:3]:
    print(f"  {link.replace('&amp;', '&')}")

# Save HTML sample for inspection
with open("output/truskin_page_debug.html", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("\nSaved full HTML to output/truskin_page_debug.html")
