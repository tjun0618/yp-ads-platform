# -*- coding: utf-8 -*-
"""
ad_quality_scorer.py
====================
广告质量自动评分系统

评估维度：
1. 相关性 (Relevance) - 关键词覆盖、产品匹配
2. 吸引力 (Appeal) - 痛点、差异化、社会证明
3. 真实性 (Authenticity) - 内容真实性
4. 合规性 (Compliance) - 字符限制、禁用词
5. 转化潜力 (Conversion) - CTA、信任元素

使用方法：
    from ad_quality_scorer import AdQualityScorer

    scorer = AdQualityScorer()
    result = scorer.score_ad(ad_data, product_data, keywords)
    print(result['total_score'])  # 0-100
    print(result['suggestions'])  # 改进建议
"""

import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class QualityScore:
    """质量评分结果"""

    total_score: float = 0.0
    relevance_score: float = 0.0
    appeal_score: float = 0.0
    authenticity_score: float = 0.0
    compliance_score: float = 0.0
    conversion_score: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


class AdQualityScorer:
    """广告质量评分器"""

    # Google Ads 禁用词/敏感词
    BANNED_WORDS = [
        "best",
        "#1",
        "number one",
        "guaranteed",
        "free",
        "click here",
        "buy now",
        "limited time",
        "act now",
        "最好",
        "第一",
        "保证",
        "免费",
        "点击这里",
    ]

    # 行动号召词（正面）
    CTA_WORDS = [
        "shop",
        "buy",
        "order",
        "get",
        "try",
        "discover",
        "find",
        "explore",
        "save",
        "enjoy",
        "experience",
        "购买",
        "选购",
        "立即",
        "发现",
    ]

    # 痛点词
    PAIN_POINT_WORDS = [
        "sensitive",
        "irritation",
        "dry",
        "oily",
        "acne",
        "aging",
        "wrinkle",
        "dull",
        "damaged",
        "fragile",
        "敏感",
        "干燥",
        "油腻",
        "痘痘",
        "衰老",
        "皱纹",
    ]

    # 差异化卖点词
    DIFFERENTIATION_WORDS = [
        "organic",
        "natural",
        "vegan",
        "cruelty-free",
        "usa made",
        "handmade",
        "sustainable",
        "eco-friendly",
        "non-gmo",
        "有机",
        "天然",
        "素食",
        "无残忍",
        "美国制造",
    ]

    # 社会证明词
    SOCIAL_PROOF_WORDS = [
        "stars",
        "reviews",
        "rated",
        "bestseller",
        "top rated",
        "award",
        "certified",
        "trusted",
        "recommended",
        "星",
        "评论",
        "畅销",
        "认证",
        "推荐",
    ]

    def __init__(self):
        pass

    def score_ad(
        self,
        ad_data: Dict,
        product_data: Optional[Dict] = None,
        keywords: Optional[List[str]] = None,
    ) -> QualityScore:
        """
        评估广告质量

        Args:
            ad_data: 广告数据，包含 headlines, descriptions 等
            product_data: 产品数据，包含 bullet_points, title 等
            keywords: 目标关键词列表

        Returns:
            QualityScore: 评分结果
        """
        result = QualityScore()

        # 提取广告文本
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

        all_text = " ".join(headline_texts + description_texts).lower()

        # 1. 相关性评分 (0-20分)
        result.relevance_score, rel_suggestions = self._score_relevance(
            headline_texts, description_texts, all_text, product_data, keywords
        )
        result.suggestions.extend(rel_suggestions)

        # 2. 吸引力评分 (0-25分)
        result.appeal_score, appeal_suggestions = self._score_appeal(
            headline_texts, description_texts, all_text, product_data
        )
        result.suggestions.extend(appeal_suggestions)

        # 3. 真实性评分 (0-15分)
        result.authenticity_score, auth_suggestions = self._score_authenticity(
            all_text, product_data
        )
        result.suggestions.extend(auth_suggestions)

        # 4. 合规性评分 (0-20分)
        result.compliance_score, comp_suggestions = self._score_compliance(
            headlines, descriptions, all_text
        )
        result.suggestions.extend(comp_suggestions)

        # 5. 转化潜力评分 (0-20分)
        result.conversion_score, conv_suggestions = self._score_conversion(
            headline_texts, description_texts, all_text, ad_data
        )
        result.suggestions.extend(conv_suggestions)

        # 计算总分
        result.total_score = (
            result.relevance_score
            + result.appeal_score
            + result.authenticity_score
            + result.compliance_score
            + result.conversion_score
        )

        # 生成详细报告
        result.details = {
            "headline_count": len(headline_texts),
            "description_count": len(description_texts),
            "total_chars": len(all_text),
            "has_final_url": bool(ad_data.get("final_url")),
        }

        return result

    def _score_relevance(
        self,
        headlines: List[str],
        descriptions: List[str],
        all_text: str,
        product_data: Optional[Dict],
        keywords: Optional[List[str]],
    ) -> Tuple[float, List[str]]:
        """相关性评分 (0-20分)"""
        score = 10.0  # 基础分
        suggestions = []

        # 关键词覆盖 (最多+5分)
        if keywords:
            covered = 0
            for kw in keywords[:10]:
                if kw.lower() in all_text:
                    covered += 1
            coverage = covered / min(len(keywords), 10)
            score += coverage * 5

            if coverage < 0.5:
                suggestions.append(
                    f"关键词覆盖率仅 {coverage * 100:.0f}%，建议在广告中包含更多目标关键词"
                )

        # 产品匹配 (最多+5分)
        if product_data:
            product_title = (
                product_data.get("title") or product_data.get("product_name") or ""
            ).lower()
            bullet_points = product_data.get("bullet_points") or ""
            if isinstance(bullet_points, list):
                bullet_points = " ".join(bullet_points)
            bullet_points = bullet_points.lower()

            # 检查品牌名是否出现
            brand = product_data.get("brand") or ""
            if brand and brand.lower() in all_text:
                score += 2
            elif brand:
                suggestions.append(f"广告中未包含品牌名 '{brand}'")

            # 检查核心产品词是否出现
            if product_title:
                core_words = [w for w in product_title.split() if len(w) > 3][:5]
                matched = sum(1 for w in core_words if w in all_text)
                if matched >= 3:
                    score += 3
                elif matched < 2:
                    suggestions.append("广告与产品标题的匹配度较低，建议增加产品核心词")

        return min(score, 20), suggestions

    def _score_appeal(
        self,
        headlines: List[str],
        descriptions: List[str],
        all_text: str,
        product_data: Optional[Dict],
    ) -> Tuple[float, List[str]]:
        """吸引力评分 (0-25分)"""
        score = 10.0  # 基础分
        suggestions = []

        # 痛点切入 (最多+5分)
        pain_points_found = sum(1 for word in self.PAIN_POINT_WORDS if word in all_text)
        if pain_points_found >= 2:
            score += 5
        elif pain_points_found == 1:
            score += 2
        else:
            suggestions.append(
                "广告未触及用户痛点，建议添加如 '敏感肌适用'、'无刺激' 等痛点词"
            )

        # 差异化卖点 (最多+5分)
        diff_found = sum(1 for word in self.DIFFERENTIATION_WORDS if word in all_text)
        if diff_found >= 3:
            score += 5
        elif diff_found >= 1:
            score += 3
        else:
            suggestions.append(
                "广告缺乏差异化卖点，建议添加如 '有机认证'、'美国制造'、'素食友好' 等"
            )

        # 社会证明 (最多+5分)
        social_proof_found = sum(
            1 for word in self.SOCIAL_PROOF_WORDS if word in all_text
        )
        if social_proof_found >= 2:
            score += 5
        elif social_proof_found == 1:
            score += 2
        else:
            suggestions.append("广告缺少社会证明，建议添加评分、评论数或认证信息")

        # 标题吸引力 (最多+5分)
        if headlines:
            # 检查是否有数字（数字更吸引眼球）
            has_number = any(re.search(r"\d", h) for h in headlines)
            # 检查是否有问号（问题式标题）
            has_question = any("?" in h for h in headlines)
            # 检查是否有情感词
            emotion_words = [
                "amazing",
                "incredible",
                "perfect",
                "love",
                "great",
                "best",
            ]
            has_emotion = any(
                any(e in h.lower() for e in emotion_words) for h in headlines
            )

            if has_number:
                score += 2
            if has_question:
                score += 1
            if has_emotion:
                score += 2

        return min(score, 25), suggestions

    def _score_authenticity(
        self, all_text: str, product_data: Optional[Dict]
    ) -> Tuple[float, List[str]]:
        """真实性评分 (0-15分)"""
        score = 12.0  # 默认较高，除非发现问题
        suggestions = []

        # 检查是否有夸大宣传
        exaggeration_words = [
            "miracle",
            "instant",
            "overnight",
            "permanent",
            "cure",
            "奇迹",
            "瞬间",
            "永久",
            "治愈",
        ]
        for word in exaggeration_words:
            if word in all_text:
                score -= 3
                suggestions.append(f"广告中包含夸大词汇 '{word}'，可能违反广告政策")

        # 检查是否有虚假承诺
        fake_promises = [
            "100%",
            "guaranteed results",
            "works for everyone",
            "100%",
            "保证效果",
            "对所有人都有效",
        ]
        for phrase in fake_promises:
            if phrase in all_text:
                score -= 5
                suggestions.append(f"广告中包含虚假承诺 '{phrase}'，建议删除")

        # 如果有产品数据，检查功能声明是否与产品一致
        if product_data:
            bullet_points = product_data.get("bullet_points") or ""
            if isinstance(bullet_points, list):
                bullet_points = " ".join(bullet_points)

            # 简单检查：如果广告声称了产品没有的功能
            # 这里可以扩展更复杂的逻辑
            pass

        return max(score, 0), suggestions

    def _score_compliance(
        self, headlines: List[dict], descriptions: List[dict], all_text: str
    ) -> Tuple[float, List[str]]:
        """合规性评分 (0-20分)"""
        score = 15.0  # 基础分
        suggestions = []

        # 字符限制检查 (最多-10分)
        headline_over = 0
        desc_over = 0

        for h in headlines:
            text = h.get("text", "") if isinstance(h, dict) else str(h)
            chars = h.get("chars", len(text)) if isinstance(h, dict) else len(text)
            if chars > 30:
                headline_over += 1
                score -= 2

        for d in descriptions:
            text = d.get("text", "") if isinstance(d, dict) else str(d)
            chars = d.get("chars", len(text)) if isinstance(d, dict) else len(text)
            if chars > 90:
                desc_over += 1
                score -= 2

        if headline_over > 0:
            suggestions.append(f"有 {headline_over} 个标题超过30字符限制")
        if desc_over > 0:
            suggestions.append(f"有 {desc_over} 个描述超过90字符限制")

        # 禁用词检查 (每个-3分)
        banned_found = []
        for word in self.BANNED_WORDS:
            if word.lower() in all_text:
                banned_found.append(word)
                score -= 3

        if banned_found:
            suggestions.append(
                f"广告中包含敏感词: {', '.join(banned_found[:3])}，可能被拒审"
            )

        # 格式检查
        # 全大写过多
        upper_ratio = sum(1 for c in all_text if c.isupper()) / max(len(all_text), 1)
        if upper_ratio > 0.5:
            score -= 3
            suggestions.append("广告大写字母过多，建议使用正常大小写")

        # 特殊符号过多
        special_chars = sum(1 for c in all_text if c in "!@#$%^&*(){}[]|\\:;<>?/~")
        if special_chars > 10:
            score -= 2
            suggestions.append("广告中特殊符号过多，可能影响可读性")

        return max(score, 0), suggestions

    def _score_conversion(
        self,
        headlines: List[str],
        descriptions: List[str],
        all_text: str,
        ad_data: Dict,
    ) -> Tuple[float, List[str]]:
        """转化潜力评分 (0-20分)"""
        score = 10.0  # 基础分
        suggestions = []

        # CTA 检查 (最多+5分)
        cta_found = sum(1 for word in self.CTA_WORDS if word in all_text)
        if cta_found >= 2:
            score += 5
        elif cta_found == 1:
            score += 3
        else:
            suggestions.append(
                "广告缺少明确的行动号召，建议添加 'Shop Now'、'Buy'、'Order' 等"
            )

        # 品牌信任 (最多+3分)
        if ad_data.get("display_url"):
            score += 1
        else:
            suggestions.append("建议设置显示网址以增强信任感")

        # 链接有效性
        if ad_data.get("final_url"):
            score += 2
        else:
            suggestions.append("广告缺少最终链接，无法引导用户")

        # 价格信息 (最多+2分，但也可能扣分)
        has_price = bool(re.search(r"\$\d+", all_text))
        if has_price:
            score += 2

        # 促销信息 (最多+2分)
        promo_words = ["save", "discount", "off", "sale", "deal", "free shipping"]
        has_promo = any(word in all_text for word in promo_words)
        if has_promo:
            score += 2

        return min(score, 20), suggestions

    def get_grade(self, score: float) -> str:
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

    def batch_score(
        self,
        ads: List[Dict],
        products: Optional[Dict[str, Dict]] = None,
        keywords_map: Optional[Dict[str, List[str]]] = None,
    ) -> List[Dict]:
        """
        批量评分

        Args:
            ads: 广告列表
            products: 产品字典 {asin: product_data}
            keywords_map: 关键词字典 {asin: [keywords]}

        Returns:
            评分结果列表
        """
        results = []

        for ad in ads:
            asin = ad.get("asin")
            product = products.get(asin) if products else None
            keywords = keywords_map.get(asin) if keywords_map else None

            score = self.score_ad(ad, product, keywords)

            results.append(
                {
                    "asin": asin,
                    "ad_id": ad.get("id"),
                    "total_score": score.total_score,
                    "grade": self.get_grade(score.total_score),
                    "relevance": score.relevance_score,
                    "appeal": score.appeal_score,
                    "authenticity": score.authenticity_score,
                    "compliance": score.compliance_score,
                    "conversion": score.conversion_score,
                    "suggestions": score.suggestions,
                }
            )

        # 按分数排序
        results.sort(key=lambda x: x["total_score"], reverse=True)

        return results


# 便捷函数
def score_single_ad(
    ad_data: Dict, product_data: Dict = None, keywords: List[str] = None
) -> Dict:
    """
    评估单个广告

    Example:
        result = score_single_ad(
            ad_data={"headlines": [...], "descriptions": [...]},
            product_data={"title": "...", "bullet_points": [...]},
            keywords=["organic deodorant", "natural deodorant"]
        )
        print(f"总分: {result['total_score']}")
        print(f"等级: {result['grade']}")
        print("建议:", result['suggestions'])
    """
    scorer = AdQualityScorer()
    score = scorer.score_ad(ad_data, product_data, keywords)

    return {
        "total_score": round(score.total_score, 1),
        "grade": scorer.get_grade(score.total_score),
        "breakdown": {
            "相关性": round(score.relevance_score, 1),
            "吸引力": round(score.appeal_score, 1),
            "真实性": round(score.authenticity_score, 1),
            "合规性": round(score.compliance_score, 1),
            "转化潜力": round(score.conversion_score, 1),
        },
        "suggestions": score.suggestions,
        "details": score.details,
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
        "final_url": "https://amazon.com/dp/test",
        "display_url": "amazon.com",
    }

    test_product = {
        "title": "Beauty by Earth Natural Deodorant - Aluminum Free",
        "brand": "Beauty by Earth",
        "bullet_points": [
            "Aluminum free formula",
            "Made in USA with organic ingredients",
            "Perfect for sensitive skin",
        ],
    }

    test_keywords = [
        "natural deodorant",
        "aluminum free deodorant",
        "organic deodorant",
    ]

    result = score_single_ad(test_ad, test_product, test_keywords)

    print("=" * 50)
    print("广告质量评估报告")
    print("=" * 50)
    print(f"总分: {result['total_score']} / 100")
    print(f"等级: {result['grade']}")
    print("\n分项得分:")
    for k, v in result["breakdown"].items():
        print(f"  - {k}: {v}")
    print("\n改进建议:")
    for s in result["suggestions"]:
        print(f"  - {s}")
