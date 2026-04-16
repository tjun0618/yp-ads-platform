from bs4 import BeautifulSoup
import re

with open("output/truskin_brand_detail.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")
product_lines = soup.find_all("div", class_="product-line")
print("Product lines found:", len(product_lines))

for line in product_lines[:3]:
    asin_div = line.find("div", class_="asin-code")
    asin = asin_div.get_text(strip=True) if asin_div else None
    
    copy_btn = line.find("p", class_="adv-btn")
    tracking_url = None
    pid = None
    if copy_btn:
        onclick = copy_btn.get("onclick", "")
        # Extract URL from ClipboardJS.copy(...)
        pattern = r"ClipboardJS\.copy\('([^']+)'\)"
        url_match = re.search(pattern, onclick)
        if url_match:
            tracking_url = url_match.group(1).replace("&amp;", "&")
            pid_match = re.search(r"pid=(\d+)", tracking_url)
            pid = pid_match.group(1) if pid_match else None
    
    print("ASIN=" + str(asin) + ", pid=" + str(pid))
    print("  URL=" + str(tracking_url))
    print()
