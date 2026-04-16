# Test template rendering
import sys

sys.path.insert(0, ".")
import ads_manager
from flask import Flask, render_template_string

app = Flask(__name__)
with app.app_context():
    result = render_template_string(ads_manager.MERCHANT_ROOM_HTML, merchant_id="12345")

    # Check for the specific pattern we fixed
    if "onclick=\"downloadPlan(''" in result:
        print("ERROR: Still has broken onclick pattern")
    else:
        print("Template renders OK - no broken onclick pattern")

    # Check line 576 area
    lines = result.split("\n")
    for i, line in enumerate(lines):
        if "downloadPlan" in line and "onclick" in line:
            print(f"\nLine {i + 1}: {line[:120]}")

    print(f"\nTotal result length: {len(result)} chars")
