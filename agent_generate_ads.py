# -*- coding: utf-8 -*-
"""
agent_generate_ads.py
=====================
使用 Agent + Google Ads 技能生成广告方案

用法:
    python -X utf8 agent_generate_ads.py --asin B0XXXXX [--force]

流程:
    1. 从数据库获取产品信息
    2. 读取 Google Ads 技能文件
    3. 调用 Agent 生成广告方案
    4. 解析结果并写入数据库
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 添加当前目录到 path
BASE_DIR = Path(os.path.abspath(__file__)).parent
sys.path.insert(0, str(BASE_DIR))

import mysql.connector

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4",
}

# Google Ads 技能路径
SKILL_PATH = Path(r"D:\workspace\claws\google-ads-skill\SKILL-Google-Ads.md")
REFS_DIR = Path(r"D:\workspace\claws\google-ads-skill\references")


def get_product_info(asin: str) -> dict:
    """从数据库获取产品信息"""
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    # 获取商品基本信息
    cur.execute(
        """
        SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
               p.merchant_name, p.yp_merchant_id,
               a.title as amz_title, a.brand, a.rating, a.review_count,
               a.bullet_points, a.description, a.availability, a.category_path,
               a.main_image_url
        FROM yp_us_products p
        LEFT JOIN amazon_product_details a ON p.asin = a.asin
        WHERE p.asin = %s LIMIT 1
    """,
        (asin,),
    )
    product = cur.fetchone()

    if not product:
        conn.close()
        return None

    # 获取商户关键词
    merchant_id = str(product.get("yp_merchant_id") or "")
    brand_keywords = []
    if merchant_id:
        cur.execute(
            "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s",
            (merchant_id,),
        )
        brand_keywords = [r["keyword"] for r in cur.fetchall()]

    conn.close()

    product["brand_keywords"] = brand_keywords
    return product


def build_agent_prompt(product: dict) -> str:
    """构建 Agent 的 prompt"""

    # 读取技能文件
    skill_content = ""
    if SKILL_PATH.exists():
        with open(SKILL_PATH, "r", encoding="utf-8") as f:
            skill_content = f.read()

    # 读取参考文件
    refs_content = ""
    ref_files = [
        "product-category-analyzer.md",
        "keyword-engine.md",
        "negative-keywords.md",
        "copy-generator.md",
        "qa-checker.md",
    ]
    for ref_file in ref_files:
        ref_path = REFS_DIR / ref_file
        if ref_path.exists():
            with open(ref_path, "r", encoding="utf-8") as f:
                refs_content += f"\n\n---\n\n## {ref_file}\n\n{f.read()}"

    # 构建产品信息
    product_info = f"""
## 产品信息

- **ASIN**: {product["asin"]}
- **商品名称**: {product.get("amz_title") or product.get("product_name", "未知")}
- **品牌**: {product.get("brand") or "未知"}
- **价格**: ${product.get("price") or "0"}
- **佣金率**: {product.get("commission") or "0%"}
- **评分**: {product.get("rating") or "无"} ({product.get("review_count") or 0} 评价)
- **类目**: {product.get("category_path") or "未知"}
- **库存状态**: {product.get("availability") or "未知"}
- **品牌关键词**: {", ".join(product.get("brand_keywords", [])[:10]) or "无"}

### 产品卖点
{product.get("bullet_points") or "暂无"}

### 产品描述
{(product.get("description") or "暂无")[:500]}
"""

    prompt = f"""
# 任务：为以下产品生成 Google Ads 广告方案

请严格按照 SKILL-Google-Ads.md 技能文件中的 10 步工作流程执行，为产品生成完整的广告方案。

{product_info}

---

# 技能文件内容

{skill_content}

---

# 参考文件

{refs_content}

---

# 输出要求

请按照技能文件的要求，逐步执行并生成完整的广告方案。

最后请以 JSON 格式输出（用于程序解析）：

```json
{{
  "product_analysis": {{
    "category": "产品品类",
    "type": "痛点驱动型/礼品驱动型/效果驱动型",
    "brand_awareness": "高/中/低",
    "commission_per_sale": 1.5,
    "target_cpa": 1.0,
    "recommended_campaigns": 3
  }},
  "profitability": {{
    "break_even_cpa": 2.0,
    "safe_target_cpa": 1.4,
    "feasibility": "可行/中等风险/高风险",
    "warning": "可选的警告信息"
  }},
  "campaigns": [
    {{
      "name": "Campaign名称",
      "budget_daily": 10,
      "bid_strategy": "Manual CPC / Max Conversions / Target CPA",
      "ad_groups": [
        {{
          "name": "Ad Group名称",
          "keywords": [
            {{"kw": "关键词", "match": "E", "chars": 15}}
          ],
          "negative_keywords": ["否定词"],
          "headlines": [
            {{"text": "标题内容", "chars": 25}}
          ],
          "descriptions": [
            {{"text": "描述内容", "chars": 85}}
          ]
        }}
      ],
      "campaign_negative_keywords": ["系列级否定词"]
    }}
  ],
  "account_negative_keywords": ["账户级否定词"],
  "sitelinks": [
    {{"text": "链接文字", "desc1": "描述1", "desc2": "描述2"}}
  ],
  "callouts": ["卖点1", "卖点2"],
  "structured_snippets": {{
    "header": "类型",
    "values": ["值1", "值2"]
  }},
  "qa_report": {{
    "price_consistency": "PASS",
    "ad_group_duplicates": "PASS",
    "keyword_authenticity": "PASS",
    "template_residue": "PASS",
    "negative_keyword_fit": "PASS",
    "char_format": "PASS"
  }}
}}
```

请开始生成广告方案。
"""
    return prompt


def parse_and_save(asin: str, result_text: str, force: bool = False) -> dict:
    """解析 Agent 输出并保存到数据库"""

    # 尝试提取 JSON
    json_match = None
    if "```json" in result_text:
        start = result_text.find("```json") + 7
        end = result_text.find("```", start)
        if end > start:
            json_match = result_text[start:end].strip()
    elif "```" in result_text:
        start = result_text.find("```") + 3
        end = result_text.find("```", start)
        if end > start:
            json_match = result_text[start:end].strip()

    if not json_match:
        # 尝试直接解析
        try:
            # 找到第一个 { 和最后一个 }
            start = result_text.find("{")
            end = result_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_match = result_text[start:end]
        except:
            pass

    if not json_match:
        return {"success": False, "error": "无法从输出中提取 JSON"}

    try:
        data = json.loads(json_match)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"JSON 解析失败: {e}"}

    # 保存到数据库
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)

    try:
        # 检查是否已存在
        cur.execute("SELECT id FROM ads_plans WHERE asin=%s", (asin,))
        exists = cur.fetchone()

        if exists and not force:
            conn.close()
            return {"success": False, "error": "方案已存在，使用 --force 覆盖"}

        # 解析数据
        campaigns = data.get("campaigns", [])
        campaign_count = len(campaigns)
        ad_group_count = sum(len(c.get("ad_groups", [])) for c in campaigns)
        ad_count = ad_group_count * 3  # 假设每组 3 个广告变体

        product_analysis = data.get("product_analysis", {})
        target_cpa = product_analysis.get("target_cpa", 0)

        # 获取商品信息
        cur.execute(
            "SELECT merchant_name FROM yp_us_products WHERE asin=%s LIMIT 1", (asin,)
        )
        prod = cur.fetchone()
        merchant_name = prod["merchant_name"] if prod else ""

        # 获取 merchant_id
        cur.execute(
            "SELECT yp_merchant_id FROM yp_us_products WHERE asin=%s LIMIT 1", (asin,)
        )
        prod2 = cur.fetchone()
        merchant_id = str(prod2["yp_merchant_id"]) if prod2 else ""

        if exists:
            # 更新
            cur.execute(
                """
                UPDATE ads_plans SET
                    merchant_id = %s,
                    merchant_name = %s,
                    plan_status = 'completed',
                    campaign_count = %s,
                    ad_group_count = %s,
                    ad_count = %s,
                    target_cpa = %s,
                    ai_strategy_notes = %s,
                    updated_at = NOW()
                WHERE asin = %s
            """,
                (
                    merchant_id,
                    merchant_name,
                    campaign_count,
                    ad_group_count,
                    ad_count,
                    target_cpa,
                    json.dumps(data.get("product_analysis", {}), ensure_ascii=False),
                    asin,
                ),
            )
            plan_id = exists["id"]
        else:
            # 插入
            cur.execute(
                """
                INSERT INTO ads_plans (
                    asin, merchant_id, merchant_name, plan_status,
                    campaign_count, ad_group_count, ad_count, target_cpa,
                    ai_strategy_notes, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, 'completed',
                    %s, %s, %s, %s,
                    %s, NOW(), NOW()
                )
            """,
                (
                    asin,
                    merchant_id,
                    merchant_name,
                    campaign_count,
                    ad_group_count,
                    ad_count,
                    target_cpa,
                    json.dumps(data.get("product_analysis", {}), ensure_ascii=False),
                ),
            )
            plan_id = cur.lastrowid

        # 删除旧的 campaigns, ad_groups, ads
        if exists:
            cur.execute(
                "DELETE FROM ads_ads WHERE ad_group_id IN (SELECT id FROM ads_ad_groups WHERE campaign_id IN (SELECT id FROM ads_campaigns WHERE asin=%s))",
                (asin,),
            )
            cur.execute(
                "DELETE FROM ads_ad_groups WHERE campaign_id IN (SELECT id FROM ads_campaigns WHERE asin=%s)",
                (asin,),
            )
            cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))

        # 插入新的 campaigns
        for camp in campaigns:
            cur.execute(
                """
                INSERT INTO ads_campaigns (asin, name, budget_daily, bid_strategy, negative_keywords)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (
                    asin,
                    camp.get("name", ""),
                    camp.get("budget_daily", 10),
                    camp.get("bid_strategy", "Manual CPC"),
                    json.dumps(
                        camp.get("campaign_negative_keywords", []), ensure_ascii=False
                    ),
                ),
            )
            camp_id = cur.lastrowid

            # 插入 ad_groups
            for ag in camp.get("ad_groups", []):
                cur.execute(
                    """
                    INSERT INTO ads_ad_groups (campaign_id, name, keywords, negative_keywords)
                    VALUES (%s, %s, %s, %s)
                """,
                    (
                        camp_id,
                        ag.get("name", ""),
                        json.dumps(ag.get("keywords", []), ensure_ascii=False),
                        json.dumps(ag.get("negative_keywords", []), ensure_ascii=False),
                    ),
                )
                ag_id = cur.lastrowid

                # 插入 ads (3 个变体)
                headlines = ag.get("headlines", [])
                descriptions = ag.get("descriptions", [])

                for variant in range(3):
                    # 选择对应的标题和描述
                    hl = headlines[variant % len(headlines)] if headlines else {}
                    desc = (
                        descriptions[variant % len(descriptions)]
                        if descriptions
                        else {}
                    )

                    cur.execute(
                        """
                        INSERT INTO ads_ads (ad_group_id, variant, headlines, descriptions, all_chars_valid)
                        VALUES (%s, %s, %s, %s, 1)
                    """,
                        (
                            ag_id,
                            variant + 1,
                            json.dumps([hl], ensure_ascii=False),
                            json.dumps([desc], ensure_ascii=False),
                        ),
                    )

        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"success": False, "error": str(e)}

    conn.close()

    return {
        "success": True,
        "campaigns": campaign_count,
        "ad_groups": ad_group_count,
        "ads": ad_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Agent 生成广告方案")
    parser.add_argument("--asin", required=True, help="ASIN")
    parser.add_argument("--force", action="store_true", help="强制覆盖")
    args = parser.parse_args()

    print(f"[INFO] 开始处理 ASIN: {args.asin}")

    # 1. 获取产品信息
    print("[Step 1] 获取产品信息...")
    product = get_product_info(args.asin)
    if not product:
        print(f"[ERROR] 找不到 ASIN {args.asin}")
        sys.exit(1)

    print(
        f"  - 商品: {product.get('amz_title') or product.get('product_name', '')[:50]}"
    )
    print(
        f"  - 价格: ${product.get('price', 'N/A')} | 佣金: {product.get('commission', 'N/A')}"
    )

    # 2. 构建 prompt
    print("[Step 2] 构建 Agent prompt...")
    prompt = build_agent_prompt(product)

    # 保存 prompt 供调试
    prompt_file = BASE_DIR / f"_agent_prompt_{args.asin}.md"
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"  - Prompt 已保存: {prompt_file}")

    # 3. 调用 Agent (这里需要实际的 Agent 实现)
    print("[Step 3] 调用 Agent 生成广告方案...")
    print("  - 注意: 当前版本需要手动调用 Agent")
    print(f"  - 请使用以下 prompt 调用 Agent:")
    print(f"    {prompt_file}")

    # TODO: 实际的 Agent 调用
    # 这里可以调用 Task 工具或其他 Agent 实现

    print()
    print("[完成] Prompt 已生成，请手动调用 Agent 或等待集成完成")


if __name__ == "__main__":
    main()
