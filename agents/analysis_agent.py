# -*- coding: utf-8 -*-
"""
agents/analysis_agent.py
=========================
分析 Agent

功能:
- 数据分析工作流
- 广告效果分析
- 商品表现分析
- 报告生成
"""

import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Union,
)

from .base_agent import (
    AgentMessage,
    AgentState,
    BaseAgent,
    MessageType,
    ToolResult,
)


class AnalysisType(Enum):
    """分析类型"""

    AD_PERFORMANCE = "ad_performance"
    PRODUCT_PERFORMANCE = "product_performance"
    MERCHANT_PERFORMANCE = "merchant_performance"
    KEYWORD_ANALYSIS = "keyword_analysis"


class AnalysisAgent(BaseAgent):
    """
    分析 Agent

    职责:
    - 分析广告效果
    - 分析商品表现
    - 分析商户数据
    - 生成洞察报告
    """

    def __init__(self, **kwargs):
        """初始化分析 Agent"""
        super().__init__(agent_id="analyst", **kwargs)

        # 支持的分析类型
        self._analysis_types = self._config.get("analysis_types", [])

        # 输出格式
        self._output_format = self._config.get("output_format", "markdown")

        self.logger.info("AnalysisAgent initialized")

    def detect_analysis_type(self, task: str) -> AnalysisType:
        """
        检测分析类型

        Args:
            task: 任务描述

        Returns:
            分析类型
        """
        task_lower = task.lower()

        if "广告" in task or "ad" in task_lower:
            return AnalysisType.AD_PERFORMANCE
        elif "商品" in task or "产品" in task or "product" in task_lower:
            return AnalysisType.PRODUCT_PERFORMANCE
        elif "商户" in task or "merchant" in task_lower:
            return AnalysisType.MERCHANT_PERFORMANCE
        elif "关键词" in task or "keyword" in task_lower:
            return AnalysisType.KEYWORD_ANALYSIS
        else:
            return AnalysisType.PRODUCT_PERFORMANCE

    async def analyze_ad_performance(
        self, asin: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        分析广告效果

        Args:
            asin: 产品 ASIN (可选，不指定则分析全部)
            days: 分析天数

        Returns:
            分析结果
        """
        self.logger.info(f"Analyzing ad performance: asin={asin}, days={days}")

        # 查询广告方案
        where_clause = f"WHERE asin = '{asin}'" if asin else ""

        result = await self.execute_tool(
            "db_query",
            sql=f"""
                SELECT 
                    id,
                    asin,
                    plan_json,
                    status,
                    created_at,
                    updated_at
                FROM ads_plans
                {where_clause}
                ORDER BY created_at DESC
            """,
        )

        ads_plans = result.data if result.success else []

        # 分析数据
        analysis = {
            "period": f"过去 {days} 天",
            "total_plans": len(ads_plans),
            "status_distribution": {},
            "recommendations": [],
        }

        # 统计状态分布
        for plan in ads_plans:
            status = plan.get("status", "unknown")
            analysis["status_distribution"][status] = (
                analysis["status_distribution"].get(status, 0) + 1
            )

        # 生成建议
        if analysis["status_distribution"].get("draft", 0) > 0:
            analysis["recommendations"].append(
                {
                    "type": "action",
                    "message": f"有 {analysis['status_distribution']['draft']} 个广告方案处于草稿状态，建议尽快发布",
                }
            )

        return analysis

    async def analyze_product_performance(
        self, asin: Optional[str] = None, brand: Optional[str] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """
        分析商品表现

        Args:
            asin: 产品 ASIN
            brand: 品牌名称
            limit: 返回数量

        Returns:
            分析结果
        """
        self.logger.info(f"Analyzing product performance: asin={asin}, brand={brand}")

        conditions = []
        if asin:
            conditions.append(f"asin = '{asin}'")
        if brand:
            conditions.append(f"brand = '{brand}'")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        # 查询产品数据
        result = await self.execute_tool(
            "db_query",
            sql=f"""
                SELECT 
                    asin,
                    product_name,
                    price,
                    rating,
                    review_count,
                    brand,
                    category,
                    created_at
                FROM yp_products
                {where_clause}
                ORDER BY rating DESC, review_count DESC
                LIMIT {limit}
            """,
        )

        products = result.data if result.success else []

        # 计算统计信息
        analysis = {
            "total_products": len(products),
            "avg_rating": 0,
            "avg_price": 0,
            "avg_reviews": 0,
            "top_products": [],
            "brand_distribution": {},
            "insights": [],
        }

        if products:
            ratings = [p.get("rating", 0) or 0 for p in products]
            prices = [p.get("price", 0) or 0 for p in products]
            reviews = [p.get("review_count", 0) or 0 for p in products]

            analysis["avg_rating"] = (
                round(sum(ratings) / len(ratings), 2) if ratings else 0
            )
            analysis["avg_price"] = round(sum(prices) / len(prices), 2) if prices else 0
            analysis["avg_reviews"] = (
                round(sum(reviews) / len(reviews), 0) if reviews else 0
            )

            # Top 产品
            analysis["top_products"] = sorted(
                products,
                key=lambda x: (x.get("rating", 0) or 0, x.get("review_count", 0) or 0),
                reverse=True,
            )[:5]

            # 品牌分布
            for p in products:
                b = p.get("brand", "Unknown")
                analysis["brand_distribution"][b] = (
                    analysis["brand_distribution"].get(b, 0) + 1
                )

            # 生成洞察
            if analysis["avg_rating"] >= 4.0:
                analysis["insights"].append(
                    {
                        "type": "positive",
                        "message": f"平均评分较高 ({analysis['avg_rating']}⭐)，产品整体质量良好",
                    }
                )

            if analysis["avg_price"] > 50:
                analysis["insights"].append(
                    {
                        "type": "info",
                        "message": f"平均价格 ${analysis['avg_price']}，属于中高价位产品",
                    }
                )

        return analysis

    async def analyze_merchant_performance(
        self, merchant_id: Optional[str] = None, limit: int = 20
    ) -> Dict[str, Any]:
        """
        分析商户表现

        Args:
            merchant_id: 商户 ID
            limit: 返回数量

        Returns:
            分析结果
        """
        self.logger.info(f"Analyzing merchant performance: merchant_id={merchant_id}")

        where_clause = f"WHERE merchant_id = '{merchant_id}'" if merchant_id else ""

        # 查询商户数据
        result = await self.execute_tool(
            "db_query",
            sql=f"""
                SELECT 
                    merchant_id,
                    merchant_name,
                    status,
                    commission_rate,
                    product_count,
                    created_at
                FROM yp_merchants
                {where_clause}
                ORDER BY product_count DESC
                LIMIT {limit}
            """,
        )

        merchants = result.data if result.success else []

        analysis = {
            "total_merchants": len(merchants),
            "status_distribution": {},
            "avg_commission": 0,
            "top_merchants": [],
            "recommendations": [],
        }

        if merchants:
            # 状态分布
            for m in merchants:
                status = m.get("status", "unknown")
                analysis["status_distribution"][status] = (
                    analysis["status_distribution"].get(status, 0) + 1
                )

            # 平均佣金
            commissions = [m.get("commission_rate", 0) or 0 for m in merchants]
            analysis["avg_commission"] = (
                round(sum(commissions) / len(commissions), 2) if commissions else 0
            )

            # Top 商户
            analysis["top_merchants"] = merchants[:5]

            # 建议
            approved = analysis["status_distribution"].get("approved", 0)
            if approved > 0:
                analysis["recommendations"].append(
                    {
                        "type": "positive",
                        "message": f"有 {approved} 个已通过审核的商户可以开始投放",
                    }
                )

        return analysis

    async def analyze_keywords(
        self, brand: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        """
        分析关键词

        Args:
            brand: 品牌名称
            limit: 返回数量

        Returns:
            分析结果
        """
        self.logger.info(f"Analyzing keywords: brand={brand}")

        where_clause = f"WHERE brand_name = '{brand}'" if brand else ""

        result = await self.execute_tool(
            "db_query",
            sql=f"""
                SELECT 
                    keyword,
                    brand_name,
                    search_volume,
                    competition,
                    source
                FROM brand_keywords
                {where_clause}
                ORDER BY search_volume DESC
                LIMIT {limit}
            """,
        )

        keywords = result.data if result.success else []

        analysis = {
            "total_keywords": len(keywords),
            "brands": set(),
            "top_keywords": [],
            "keyword_categories": {},
            "opportunities": [],
        }

        if keywords:
            # 收集品牌
            for kw in keywords:
                if kw.get("brand_name"):
                    analysis["brands"].add(kw["brand_name"])

            analysis["brands"] = list(analysis["brands"])

            # Top 关键词
            analysis["top_keywords"] = keywords[:10]

            # 发现机会
            for kw in keywords:
                search_vol = kw.get("search_volume", 0) or 0
                competition = kw.get("competition", "") or ""

                if search_vol > 1000 and competition in ["low", "medium"]:
                    analysis["opportunities"].append(
                        {
                            "keyword": kw.get("keyword"),
                            "search_volume": search_vol,
                            "competition": competition,
                            "reason": "高搜索量，低竞争",
                        }
                    )

        return analysis

    async def generate_report(
        self, analysis_type: AnalysisType, data: Dict[str, Any]
    ) -> str:
        """
        生成报告

        Args:
            analysis_type: 分析类型
            data: 分析数据

        Returns:
            Markdown 格式报告
        """
        report_lines = [
            f"# {analysis_type.value.replace('_', ' ').title()} 分析报告",
            f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        ]

        if analysis_type == AnalysisType.PRODUCT_PERFORMANCE:
            report_lines.extend(
                [
                    "## 概览\n",
                    f"- 总产品数: {data.get('total_products', 0)}",
                    f"- 平均评分: {data.get('avg_rating', 0)} ⭐",
                    f"- 平均价格: ${data.get('avg_price', 0)}",
                    f"- 平均评论数: {data.get('avg_reviews', 0)}\n",
                    "## Top 产品\n",
                ]
            )

            for i, p in enumerate(data.get("top_products", []), 1):
                report_lines.append(
                    f"{i}. **{p.get('product_name', 'N/A')}**\n"
                    f"   - ASIN: {p.get('asin', 'N/A')}\n"
                    f"   - 评分: {p.get('rating', 'N/A')} ⭐\n"
                    f"   - 价格: ${p.get('price', 'N/A')}\n"
                )

            if data.get("insights"):
                report_lines.append("\n## 洞察\n")
                for insight in data["insights"]:
                    report_lines.append(f"- {insight.get('message', '')}")

        elif analysis_type == AnalysisType.MERCHANT_PERFORMANCE:
            report_lines.extend(
                [
                    "## 概览\n",
                    f"- 总商户数: {data.get('total_merchants', 0)}",
                    f"- 平均佣金: {data.get('avg_commission', 0)}%\n",
                    "## 状态分布\n",
                ]
            )

            for status, count in data.get("status_distribution", {}).items():
                report_lines.append(f"- {status}: {count}")

        elif analysis_type == AnalysisType.KEYWORD_ANALYSIS:
            report_lines.extend(
                [
                    "## 概览\n",
                    f"- 总关键词数: {data.get('total_keywords', 0)}",
                    f"- 品牌数: {len(data.get('brands', []))}\n",
                    "## Top 关键词\n",
                ]
            )

            for i, kw in enumerate(data.get("top_keywords", []), 1):
                report_lines.append(
                    f"{i}. {kw.get('keyword', 'N/A')} "
                    f"(搜索量: {kw.get('search_volume', 'N/A')})\n"
                )

            if data.get("opportunities"):
                report_lines.append("\n## 发现机会\n")
                for opp in data["opportunities"][:5]:
                    report_lines.append(
                        f"- **{opp.get('keyword')}**: {opp.get('reason')}\n"
                    )

        return "\n".join(report_lines)

    async def execute(
        self, task: str, context: Optional[Dict[str, Any]] = None, stream: bool = True
    ) -> Union[str, Generator[AgentMessage, None, None]]:
        """
        执行分析任务

        Args:
            task: 任务描述
            context: 执行上下文
            stream: 是否流式输出

        Returns:
            执行结果或消息流
        """
        self.state = AgentState.RUNNING
        ctx = context or {}

        self.logger.info(f"Executing analysis task: {task}")

        # 检测分析类型
        analysis_type = self.detect_analysis_type(task)

        if stream:
            yield AgentMessage(
                type=MessageType.THINKING,
                content=f"检测到分析类型: {analysis_type.value}",
            )

        # 执行分析
        data = {}

        if analysis_type == AnalysisType.AD_PERFORMANCE:
            asin = ctx.get("asin")
            days = ctx.get("days", 30)

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content="正在分析广告效果..."
                )

            data = await self.analyze_ad_performance(asin, days)

        elif analysis_type == AnalysisType.PRODUCT_PERFORMANCE:
            asin = ctx.get("asin")
            brand = ctx.get("brand")

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content="正在分析商品表现..."
                )

            data = await self.analyze_product_performance(asin, brand)

        elif analysis_type == AnalysisType.MERCHANT_PERFORMANCE:
            merchant_id = ctx.get("merchant_id")

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content="正在分析商户表现..."
                )

            data = await self.analyze_merchant_performance(merchant_id)

        elif analysis_type == AnalysisType.KEYWORD_ANALYSIS:
            brand = ctx.get("brand")

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content="正在分析关键词..."
                )

            data = await self.analyze_keywords(brand)

        # 生成报告
        if stream:
            yield AgentMessage(type=MessageType.THINKING, content="正在生成报告...")

        report = await self.generate_report(analysis_type, data)

        # 保存报告
        report_path = ctx.get(
            "report_path",
            f"output/analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        )
        await self.execute_tool("file_write", path=report_path, content=report)

        self.state = AgentState.COMPLETED

        if stream:
            # 返回报告内容
            for line in report.split("\n"):
                yield AgentMessage(type=MessageType.TEXT, content=line + "\n")

            yield AgentMessage(
                type=MessageType.TEXT, content=f"\n报告已保存到: {report_path}\n"
            )
            yield AgentMessage(type=MessageType.DONE, content="")
