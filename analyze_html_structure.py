"""
分析TruSkin HTML页面，提取pid和产品名称/图片的对应关系
"""
import re
import json

with open("output/truskin_brand_detail.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find all product card sections
# Look for product blocks - each product has a pid and some info
# Try to find section delimiters

# Find pid locations
pid_positions = [(m.group(1), m.start()) for m in re.finditer(r"pid=(\d+)", html)]
print(f"Total pids: {len(pid_positions)}")

# For first pid, look at 1000 chars before/after
if pid_positions:
    pid, pos = pid_positions[0]
    start = max(0, pos-1000)
    end = min(len(html), pos+500)
    section = html[start:end]
    
    print(f"\n=== Context around first pid={pid} ===")
    # Remove HTML tags for readability but keep structure
    # Just print raw to see structure
    print(section[:2000])

# Also check Amazon image links to understand structure
print("\n\n=== Amazon image pattern analysis ===")
amazon_imgs = [(m.group(), m.start()) for m in re.finditer(r"amazon\.com/images/I/[A-Za-z0-9]+\.jpg", html)]
print(f"Amazon images found: {len(amazon_imgs)}")
if amazon_imgs:
    img, img_pos = amazon_imgs[0]
    start = max(0, img_pos-500)
    end = min(len(html), img_pos+500)
    print(f"\nContext around first amazon image:")
    print(html[start:end][:1000])
