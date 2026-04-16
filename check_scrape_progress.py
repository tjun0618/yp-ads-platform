import json

with open("output/web_scrape_state.json", "r", encoding="utf-8") as f:
    state = json.load(f)
print("State:", state)

with open("output/asin_merchant_map.json", "r", encoding="utf-8") as f:
    asin_map = json.load(f)
print("ASIN map size:", len(asin_map))
if asin_map:
    items = list(asin_map.items())[:3]
    for asin, info in items:
        name = info.get("merchant_name", "")
        print("  " + asin + ": mid=" + str(info.get("merchant_id")) + ", name=" + name[:30])
        print("  tracking_url=" + str(info.get("tracking_url", ""))[:80])
