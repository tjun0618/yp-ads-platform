# -*- coding: utf-8 -*-
"""
ad_quality_agent.py
===================
使用 LLM Agent 进行广告质量评估

相比硬编码规则，Agent 可以：
1. 理解语义和上下文
2. 评估创意和情感吸引力
3. 给出具体的改进建议
4. 适应不同行业/产品类型

使用方法：
    from ad_quality_agent import AdQualityAgent

    agent = AdQualityAgent()
    result = agent.evaluate_ad(ad_data, product_data, keywords)
    print(result['score'])  # 0-100
    print(result['suggestions'])  # 改进建议
"""

import os
import json
import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AgentEvaluationResult:
    """Agent 评估结果"""

    score: float = 0.0
    grade: str = ""
    relevance: float = 0.0
    appeal: float = 0.0
    authenticity: float = 0.0
    compliance: float = 0.0
    conversion: float = 0.0
    strengths: List[str] = None
    weaknesses: List[str] = None
    suggestions: List[str] = None
    raw_response: str = ""

    def __post_init__(self):
        if self.strengths is None:
            self.strengths = []
        if self.weaknesses is None:
            self.weaknesses = []
        if self.suggestions is None:
            self.suggestions = []


class AdQualityAgent:
    """广告质量评估 Agent"""

    EVALUATION_PROMPT = """You are an expert Google Ads quality evaluator with 10+ years of experience in Amazon affiliate marketing.

Evaluate the following Google Ads ad for an Amazon affiliate product. Be strict but fair.

## Product Information
- Title: {product_title}
- Brand: {brand}
- Category: {category}
- Key Features: {bullet_points}
- Price: {price}
- Rating: {rating}

## Target Keywords
{keywords}

## Ad Content
### Headlines (max 30 chars each):
{headlines}

### Descriptions (max 90 chars each):
{descriptions}

## Evaluation Criteria (100 points total)

1. **Relevance (20 points)**: Does the ad match the product and keywords?
   - Are target keywords naturally incorporated?
   - Does it accurately represent the product?
   - Is the brand name mentioned?

2. **Appeal (25 points)**: Will users want to click?
   - Does it address user pain points?
   - Are there unique selling points (USPs)?
   - Is there social proof (ratings, reviews)?
   - Is the language engaging and emotional?

3. **Authenticity (15 points)**: Is the ad truthful?
   - No exaggerated claims ("miracle", "instant", "overnight")
   - No false promises
   - Accurate product representation

4. **Compliance (20 points)**: Does it follow Google Ads policies?
   - Headlines ≤ 30 characters
   - Descriptions ≤ 90 characters
   - No prohibited words ("best", "#1", "guaranteed", "free" in misleading context)
   - No excessive capitalization or symbols

5. **Conversion Potential (20 points)**: Will users take action?
   - Clear call-to-action (CTA)
   - Trust elements (brand, certification)
   - Urgency or incentive (without being misleading)

## Output Format

Return ONLY valid JSON (no markdown, no code fences):

```json
{{
  "score": 75,
  "grade": "C",
  "breakdown": {{
    "relevance": 15,
    "appeal": 20,
    "authenticity": 12,
    "compliance": 15,
    "conversion": 13
  }},
  "strengths": [
    "Brand name prominently featured",
    "Clear value proposition"
  ],
  "weaknesses": [
    "Missing social proof",
    "Generic description"
  ],
  "suggestions": [
    "Add rating or review count for social proof",
    "Include a specific benefit instead of generic claims",
    "Add urgency element like 'Shop Now' or 'Limited Stock'"
  ]
}}
```

Grade scale: A (90+), B (80-89), C (70-79), D (60-69), F (<60)

Be specific in your suggestions. Focus on actionable improvements."""

    def __init__(self, model: str = "kimi", api_key: str = None):
        """
        初始化 Agent

        Args:
            model: 使用的模型 ("kimi" 或 "qianfan")
            api_key: API 密钥（可选，默认从环境变量读取）
        """
        self.model = model
        self.api_key = api_key or os.environ.get("KIMI_API_KEY", "")
        if not self.api_key:
            raise ValueError("请设置环境变量 KIMI_API_KEY")

    def evaluate_ad(
        self,
        ad_data: Dict,
        product_data: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
    ) -> AgentEvaluationResult:
        """
        使用 Agent 评估广告质量

        Args:
            ad_data: 广告数据
            product_data: 产品数据
            keywords: 目标关键词

        Returns:
            AgentEvaluationResult: 评估结果
        """
        # 提取广告内容
        headlines = ad_data.get("headlines", [])
        descriptions = ad_data.get("descriptions", [])

        if isinstance(headlines, str):
            try:
                headlines = json.loads(headlines)
            except:
                headlines = [{"text": headlines}]

        if isinstance(descriptions, str):
            try:
                descriptions = json.loads(descriptions)
            except:
                descriptions = [{"text": descriptions}]

        headline_texts = [
            h.get("text", "") if isinstance(h, dict) else str(h) for h in headlines
        ]
        description_texts = [
            d.get("text", "") if isinstance(d, dict) else str(d) for d in descriptions
        ]

        # 构建评估 prompt
        prompt = self._build_prompt(
            headlines=headline_texts,
            descriptions=description_texts,
            product_data=product_data or {},
            keywords=keywords or [],
        )

        # 调用 LLM
        response = self._call_llm(prompt)

        # 解析结果
        result = self._parse_response(response)
        result.raw_response = response

        return result

    def _build_prompt(
        self,
        headlines: List[str],
        descriptions: List[str],
        product_data: Dict,
        keywords: List[str],
    ) -> str:
        """构建评估 prompt"""

        product_title = (
            product_data.get("title")
            or product_data.get("amz_title")
            or product_data.get("product_name", "Unknown Product")
        )
        brand = product_data.get("brand", "Unknown Brand")
        category = product_data.get("category_path", "General")
        bullet_points = product_data.get("bullet_points", [])
        if isinstance(bullet_points, str):
            bullet_points = [bullet_points]
        bullet_points_str = (
            "\n".join([f"- {bp}" for bp in bullet_points[:5]])
            if bullet_points
            else "Not available"
        )
        price = product_data.get("price", "N/A")
        rating = f"{product_data.get('rating', 'N/A')} ({product_data.get('review_count', 0)} reviews)"

        keywords_str = (
            "\n".join([f"- {kw}" for kw in keywords[:10]])
            if keywords
            else "Not specified"
        )

        headlines_str = "\n".join(
            [f'{i + 1}. "{h}" ({len(h)} chars)' for i, h in enumerate(headlines)]
        )
        descriptions_str = "\n".join(
            [f'{i + 1}. "{d}" ({len(d)} chars)' for i, d in enumerate(descriptions)]
        )

        return self.EVALUATION_PROMPT.format(
            product_title=product_title,
            brand=brand,
            category=category,
            bullet_points=bullet_points_str,
            price=price,
            rating=rating,
            keywords=keywords_str,
            headlines=headlines_str,
            descriptions=descriptions_str,
        )

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        import requests

        if self.model == "kimi":
            return self._call_kimi(prompt)
        elif self.model == "qianfan":
            return self._call_qianfan(prompt)
        else:
            return self._call_kimi(prompt)

    def _call_kimi(self, prompt: str) -> str:
        """调用 Kimi API"""
        import requests

        try:
            resp = requests.post(
                "https://api.moonshot.cn/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "moonshot-v1-8k",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,  # 低温度，更稳定
                    "max_tokens": 1000,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f'{{"error": "API call failed: {str(e)}"}}'

    def _call_qianfan(self, prompt: str) -> str:
        """调用千帆 API"""
        import requests

        try:
            # 千帆 API 调用
            access_token = os.environ.get("QIANFAN_ACCESS_TOKEN", "")
            if not access_token:
                return '{"error": "QIANFAN_ACCESS_TOKEN not set"}'

            resp = requests.post(
                f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={access_token}",
                headers={"Content-Type": "application/json"},
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", "")
        except Exception as e:
            return f'{{"error": "API call failed: {str(e)}"}}'

    def _parse_response(self, response: str) -> AgentEvaluationResult:
        """解析 LLM 响应"""
        result = AgentEvaluationResult()

        try:
            # 尝试提取 JSON
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
            else:
                data = json.loads(response)

            result.score = float(data.get("score", 0))
            result.grade = data.get("grade", "F")

            breakdown = data.get("breakdown", {})
            result.relevance = float(breakdown.get("relevance", 0))
            result.appeal = float(breakdown.get("appeal", 0))
            result.authenticity = float(breakdown.get("authenticity", 0))
            result.compliance = float(breakdown.get("compliance", 0))
            result.conversion = float(breakdown.get("conversion", 0))

            result.strengths = data.get("strengths", [])
            result.weaknesses = data.get("weaknesses", [])
            result.suggestions = data.get("suggestions", [])

        except json.JSONDecodeError:
            # JSON 解析失败，返回默认值
            result.score = 0
            result.grade = "F"
            result.suggestions = ["Failed to parse evaluation result"]

        return result


def evaluate_ad_with_agent(
    ad_data: Dict,
    product_data: Dict = None,
    keywords: List[str] = None,
    model: str = "kimi",
) -> Dict:
    """
    使用 Agent 评估广告质量（便捷函数）

    Example:
        result = evaluate_ad_with_agent(
            ad_data={"headlines": [...], "descriptions": [...]},
            product_data={"title": "...", "brand": "..."},
            keywords=["natural deodorant", "organic"],
            model="kimi"
        )
        print(f"总分: {result['score']}")
        print(f"优点: {result['strengths']}")
        print(f"建议: {result['suggestions']}")
    """
    agent = AdQualityAgent(model=model)
    evaluation = agent.evaluate_ad(ad_data, product_data, keywords)

    return {
        "score": evaluation.score,
        "grade": evaluation.grade,
        "breakdown": {
            "相关性": evaluation.relevance,
            "吸引力": evaluation.appeal,
            "真实性": evaluation.authenticity,
            "合规性": evaluation.compliance,
            "转化潜力": evaluation.conversion,
        },
        "strengths": evaluation.strengths,
        "weaknesses": evaluation.weaknesses,
        "suggestions": evaluation.suggestions,
        "raw_response": evaluation.raw_response,
    }


if __name__ == "__main__":
    # 测试示例
    test_ad = {
        "headlines": [
            {"text": "Beauty by Earth Deodorant", "chars": 25},
            {"text": "Aluminum Free Formula", "chars": 21},
            {"text": "4.2 Stars 652 Reviews", "chars": 21},
        ],
        "descriptions": [
            {
                "text": "Natural magnesium deodorant for all-day odor protection. Shop now at Amazon.",
                "chars": 75,
            },
        ],
    }

    test_product = {
        "title": "Beauty by Earth Natural Deodorant - Aluminum Free",
        "brand": "Beauty by Earth",
        "bullet_points": [
            "Aluminum free formula",
            "Made in USA with organic ingredients",
            "Perfect for sensitive skin",
        ],
        "price": "$12.99",
        "rating": "4.2",
        "review_count": 652,
    }

    test_keywords = [
        "natural deodorant",
        "aluminum free deodorant",
        "organic deodorant",
    ]

    print("=" * 60)
    print("Agent 广告质量评估")
    print("=" * 60)

    result = evaluate_ad_with_agent(test_ad, test_product, test_keywords)

    print(f"\n总分: {result['score']} / 100 ({result['grade']})")
    print("\n分项得分:")
    for k, v in result["breakdown"].items():
        print(f"  - {k}: {v}")

    print("\n优点:")
    for s in result["strengths"]:
        print(f"  + {s}")

    print("\n缺点:")
    for w in result["weaknesses"]:
        print(f"  - {w}")

    print("\n改进建议:")
    for s in result["suggestions"]:
        print(f"  → {s}")
