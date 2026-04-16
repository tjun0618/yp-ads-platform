import requests
import json

# Feishu config
FEISHU_APP_ID = "cli_a935343a74f89cd4"
FEISHU_APP_SECRET = "EqnC0zcv1CF9A2h849z8geK8RmfRRfiE"
FEISHU_APP_TOKEN = "VgOiblBCKac38ZsNx9acHpCGnQb"
TABLE_OFFERS = "tblMCbaHhP88sgeS"

def get_feishu_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET})
    return resp.json().get("tenant_access_token")

def get_feishu_offers(token):
    """Get all offers from Feishu"""
    offers = []
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_APP_TOKEN}/tables/{TABLE_OFFERS}/records"
    headers = {"Authorization": f"Bearer {token}"}
    
    has_more = True
    page_token = None
    
    while has_more:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
            
        resp = requests.get(url, headers=headers, params=params)
        result = resp.json()
        
        if result.get("code") == 0:
            items = result["data"]["items"]
            for item in items:
                fields = item.get("fields", {})
                offers.append({
                    "asin": fields.get("ASIN"),
                    "product_name": fields.get("Product Name", ""),
                    "category": fields.get("Category", ""),
                    "amazon_link": fields.get("Amazon Link", "")
                })
            
            has_more = result["data"].get("has_more", False)
            page_token = result["data"].get("page_token")
        else:
            break
    
    return offers

def extract_brand_from_name(name):
    """Extract brand from product name"""
    if not name:
        return None
    # Brand is usually the first word
    parts = name.split()
    if parts:
        return parts[0]
    return None

def main():
    print("=" * 70)
    print("分析飞书表格中的商品")
    print("=" * 70)
    
    # Get Feishu token
    token = get_feishu_token()
    if not token:
        print("[ERROR] Failed to get Feishu token")
        return
    
    # Get offers
    print("\n获取飞书商品数据...")
    offers = get_feishu_offers(token)
    print(f"  共 {len(offers)} 个商品")
    
    if not offers:
        return
    
    # Analyze categories
    categories = {}
    brands = {}
    
    for offer in offers:
        # Category
        cat = offer.get("category", "Unknown")
        categories[cat] = categories.get(cat, 0) + 1
        
        # Brand
        brand = extract_brand_from_name(offer.get("product_name", ""))
        if brand:
            brands[brand] = brands.get(brand, 0) + 1
    
    # Print categories
    print("\n" + "-" * 70)
    print("商品类别分布:")
    print("-" * 70)
    for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:15]:
        print(f"  {cat}: {count} 个")
    
    # Print brands
    print("\n" + "-" * 70)
    print("品牌分布 (Top 20):")
    print("-" * 70)
    for brand, count in sorted(brands.items(), key=lambda x: -x[1])[:20]:
        print(f"  {brand}: {count} 个")
    
    # Print sample ASINs
    print("\n" + "-" * 70)
    print("样本商品 (前 10 个):")
    print("-" * 70)
    for offer in offers[:10]:
        name = offer.get("product_name", "")[:40]
        asin = offer.get("asin", "N/A")
        cat = offer.get("category", "N/A")
        print(f"  [{asin}] {name}...")
        print(f"      类别: {cat}")

if __name__ == "__main__":
    main()
