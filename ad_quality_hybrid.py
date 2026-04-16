# -*- coding: utf-8 -*-
"""
ad_quality_hybrid.py
===================
混合评分系统：硬编码规则 + Agent 评估

策略：
1. 先用硬编码规则快速筛选（毫秒级）
2. 规则评分 < 70 分：直接返回，需要修正
3. 规则评分 >= 70 分：调用 Agent 深度评估
4. 返回综合评分和建议

使用方法：
    from ad_quality_hybrid import HybridAdScorer

    scorer = HybridAdScorer()
    result = scorer.evaluate(ad_data, product_data, keywords)
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass

from ad_quality_scorer import AdQualityScorer, score_single_ad
from ad_quality_agent import AdQualityAgent, evaluate_ad_with_agent


@dataclass
class HybridEvaluationResult:
    """混合评估结果"""

    score: float = 0.0
    grade: str = ""
    rule_score: float = 0.0
    agent_score: float = 0.0
    used_agent: bool = False
    breakdown: Dict = None
    strengths: List[str] = None
    weaknesses: List[str] = None
    suggestions: List[str] = None
    compliance_issues: List[str] = None  # 合规问题（来自规则）

    def __post_init__(self):
        if self.breakdown is None:
            self.breakdown = {}
        if self.strengths is None:
            self.strengths = []
        if self.weaknesses is None:
            self.weaknesses = []
        if self.suggestions is None:
            self.suggestions = []
        if self.compliance_issues is None:
            self.compliance_issues = []


class HybridAdScorer:
    """混合广告评分器"""

    def __init__(self, agent_threshold: float = 70.0, agent_model: str = "kimi"):
        """
        初始化混合评分器

        Args:
            agent_threshold: 触发 Agent 评估的分数阈值
            agent_model: Agent 使用的模型
        """
        self.agent_threshold = agent_threshold
        self.rule_scorer = AdQualityScorer()
        self.agent = AdQualityAgent(model=agent_model)

    def evaluate(
        self,
        ad_data: Dict,
        product_data: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
        force_agent: bool = False,
    ) -> HybridEvaluationResult:
        """
        混合评估广告质量

        Args:
            ad_data: 广告数据
            product_data: 产品数据
            keywords: 目标关键词
            force_agent: 是否强制使用 Agent 评估

        Returns:
            HybridEvaluationResult: 评估结果
        """
        result = HybridEvaluationResult()

        # 1. 硬编码规则评分
        rule_result = self.rule_scorer.score_ad(ad_data, product_data, keywords)
        result.rule_score = rule_result.total_score

        # 提取合规问题
        result.compliance_issues = [
            s
            for s in rule_result.suggestions
            if any(kw in s for kw in ["字符", "敏感词", "禁用", "超长", "限制"])
        ]

        # 2. 决定是否使用 Agent
        if force_agent or result.rule_score >= self.agent_threshold:
            # 调用 Agent 深度评估
            agent_result = self.agent.evaluate_ad(ad_data, product_data, keywords)
            result.agent_score = agent_result.score
            result.used_agent = True

            # 综合评分：规则 30% + Agent 70%
            result.score = result.rule_score * 0.3 + result.agent_score * 0.7
            result.grade = self._get_grade(result.score)

            # 合并建议
            result.breakdown = {
                "相关性": round(agent_result.relevance, 1),
                "吸引力": round(agent_result.appeal, 1),
                "真实性": round(agent_result.authenticity, 1),
                "合规性": round(
                    (rule_result.compliance_score + agent_result.compliance) / 2, 1
                ),
                "转化潜力": round(agent_result.conversion, 1),
            }
            result.strengths = agent_result.strengths
            result.weaknesses = agent_result.weaknesses
            result.suggestions = agent_result.suggestions + result.compliance_issues

        else:
            # 仅使用规则评分
            result.agent_score = 0
            result.used_agent = False
            result.score = result.rule_score
            result.grade = self._get_grade(result.score)

            result.breakdown = {
                "相关性": round(rule_result.relevance_score, 1),
                "吸引力": round(rule_result.appeal_score, 1),
                "真实性": round(rule_result.authenticity_score, 1),
                "合规性": round(rule_result.compliance_score, 1),
                "转化潜力": round(rule_result.conversion_score, 1),
            }
            result.suggestions = rule_result.suggestions

        return result

    def _get_grade(self, score: float) -> str:
        """根据分数返回等级"""
        if score >= 90:
            return "A (优秀)"
        elif score >= 80:
            return "B (良好)"
        elif score >= 70:
            return "C (一般)"
        elif score >= 60:
            return "D (需改进)"
        else:
            return "F (不合格)"

    def batch_evaluate(
        self,
        ads: List[Dict],
        products: Optional[Dict[str, Dict]] = None,
        keywords_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict]:
        """
        批量评估

        Args:
            ads: 广告列表
            products: 产品字典 {asin: product_data}
            keywords_map: 关键词字典 {asin: [keywords]}

        Returns:
            评估结果列表
        """
        results = []

        for ad in ads:
            asin = ad.get("asin")
            product = products.get(asin) if products else None
            keywords = keywords_map.get(asin) if keywords_map else None

            result = self.evaluate(ad, product, keywords)

            results.append(
                {
                    "asin": asin,
                    "ad_id": ad.get("id"),
                    "score": round(result.score, 1),
                    "grade": result.grade,
                    "rule_score": result.rule_score,
                    "agent_score": result.agent_score,
                    "used_agent": result.used_agent,
                    "breakdown": result.breakdown,
                    "strengths": result.strengths,
                    "weaknesses": result.weaknesses,
                    "suggestions": result.suggestions,
                    "compliance_issues": result.compliance_issues,
                }
            )

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results


def evaluate_ad_hybrid(
    ad_data: Dict,
    product_data: Dict = None,
    keywords: List[str] = None,
    force_agent: bool = False,
) -> Dict:
    """
    混合评估广告质量（便捷函数）

    Example:
        result = evaluate_ad_hybrid(
            ad_data={"headlines": [...], "descriptions": [...]},
            product_data={"title": "...", "brand": "..."},
            keywords=["natural deodorant"],
            force_agent=False  # 规则评分 >= 70 才用 Agent
        )
        print(f"总分: {result['score']}")
        print(f"规则分: {result['rule_score']}, Agent分: {result['agent_score']}")
    """
    scorer = HybridAdScorer()
    result = scorer.evaluate(ad_data, product_data, keywords, force_agent)

    return {
        "score": round(result.score, 1),
        "grade": result.grade,
        "rule_score": result.rule_score,
        "agent_score": result.agent_score,
        "used_agent": result.used_agent,
        "breakdown": result.breakdown,
        "strengths": result.strengths,
        "weaknesses": result.weaknesses,
        "suggestions": result.suggestions,
        "compliance_issues": result.compliance_issues,
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
            "Made in USA",
            "Organic ingredients",
        ],
        "price": "$12.99",
        "rating": "4.2",
        "review_count": 652,
    }

    test_keywords = ["natural deodorant", "aluminum free deodorant"]

    print("=" * 70)
    print("混合评分系统测试")
    print("=" * 70)

    result = evaluate_ad_hybrid(test_ad, test_product, test_keywords)

    print(f"\n总分: {result['score']} / 100 ({result['grade']})")
    print(f"规则评分: {result['rule_score']}")
    print(f"Agent评分: {result['agent_score']}")
    print(f"使用Agent: {'是' if result['used_agent'] else '否'}")

    print("\n分项得分:")
    for k, v in result["breakdown"].items():
        print(f"  - {k}: {v}")

    if result["strengths"]:
        print("\n优点:")
        for s in result["strengths"]:
            print(f"  + {s}")

    if result["weaknesses"]:
        print("\n缺点:")
        for w in result["weaknesses"]:
            print(f"  - {w}")

    print("\n改进建议:")
    for s in result["suggestions"]:
        print(f"  -> {s}")

    if result["compliance_issues"]:
        print("\n合规问题:")
        for c in result["compliance_issues"]:
            print(f"  ! {c}")
