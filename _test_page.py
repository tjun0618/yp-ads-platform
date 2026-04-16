import requests

# Test the merchant room page
resp = requests.get("http://localhost:5055/merchant_room/363312")
html = resp.text

# Check for the specific pattern we fixed
if "onclick=\"downloadPlan(''" in html:
    print("ERROR: Still has broken onclick pattern")
else:
    print("OK: onclick pattern is correct")

# Check line 576 area
lines = html.split("\n")
print(f"\nTotal lines: {len(lines)}")
print("\n=== Line 576 ===")
if len(lines) > 575:
    print(f"{lines[575][:200]}")
