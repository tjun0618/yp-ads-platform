import sys
sys.path.insert(0, '.')
from routes_collect import _parse_keywords_ocr, _parse_adcopy_ocr

# 用实际 OCR 数据测试
organic_ocr = """EBAAERRRA 32,360

RRA b= 43] HE
true classic &} N 1
true classictees) (c) N 1
trueclassic EF} N 1
true classicts... & (c) N 1
true classics Ej N 1
"""

paid_ocr = """EBA 82

RRA j
true classic Fj

fresh clean threads EF}

fresh clean threads EF}

fresh clean threads EF}

fresh clean threads EF}
"""

adcopy_ocr = """MFT SHA 82
Comfort You Can Feel - Better Fitting T Fresh Tees - The Best T-Shirts - Other Save Up to 65% Off Everything - True Fresh Tees - The Perfect T-Shirt
Shirts Brands VS True Classic Classic T-Shirt https://www.trueclassictees.com> [7
https://www.trueclassictees.com [4 https://www.trueclassictees.com> [%%] https://www.trueclassictees.com> [ -- men's> basics
Hate Shirts That Shrink? Upgrade To mens Bases men s>asits The first and only t-shirt to crack the
Premium Quality Basics Built For The first and only t-shirt to crack the President's Day Sale: Save Up to 65% code on a perfect fit for guys of all
Everyday Wear. Shop. Discover The code on a perfect fit for guys of all Off Everything. The first and only t-shirt sizes. Elevate your style game with True
Ultimate Fit. Unlock Exclusive Savings sizes. We produce premium fitted, to crack the code on a perfect fit for Classic - Trusted by 4 Million+ fashion-
On Premium Men's Wardrobe buttery soft crew neck tees for men, at guys of all sizes. Super Soft Premium forward Men! Super Soft Premium
Essentials. wallet friendly prices. Low Price Point. Blend. Fitted, Not Baggy or Boxy. Low Blend.

Fitted, Not Baggy or Boxy. Super Soft Price Point. Types: T-Shirts, Crew Neck,

Premium Blend. Types: T-Shirts, Crew V-Neck, Pocket, Long Sleeve.

Neck, V-Neck, Pocket, Long Sleeve.
"""

print("=== Organic Keywords ===")
org_kw = _parse_keywords_ocr(organic_ocr)
for kw in org_kw:
    print("  keyword=%s volume=%s raw=%s" % (kw["keyword"], kw["volume"], kw["raw"]))

print()
print("=== Paid Keywords ===")
paid_kw = _parse_keywords_ocr(paid_ocr)
for kw in paid_kw:
    print("  keyword=%s volume=%s raw=%s" % (kw["keyword"], kw["volume"], kw["raw"]))

print()
print("=== Ad Copies ===")
ads = _parse_adcopy_ocr(adcopy_ocr, "trueclassictees.com")
for i, ad in enumerate(ads):
    print("  Ad %d: headline=%s" % (i+1, ad["headline"]))
    for d in ad["descriptions"]:
        print("    desc: %s" % d[:80])
