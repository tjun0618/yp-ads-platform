# -*- coding: utf-8 -*-
"""
agents/ad_agent.py
==================
广告创作 Agent

功能:
- 继承 base_agent
- 实现广告生成工作流
- 支持 Google Ads 技能
"""

import json
import logging
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


class AdAgent(BaseAgent):
    """
    广告创作 Agent

    基于 Google Ads 技能生成广告方案

    工作流:
    1. 获取产品信息
    2. 获取 Amazon 数据
    3. 获取品牌关键词
    4. 执行技能生成广告
    5. 保存广告方案
    """

    def __init__(self, **kwargs):
        """初始化广告创作 Agent"""
        super().__init__(agent_id="ad_creator", **kwargs)

        # 工作流步骤
        self._workflow = self._config.get("workflow", [])

        # 输出格式
        self._output_format = self._config.get("output_format", "json")

        self.logger.info("AdAgent initialized")

    def get_workflow_steps(self) -> List[Dict[str, Any]]:
        """获取工作流步骤"""
        return self._workflow

    async def query_product(self, asin: str) -> Dict[str, Any]:
        """
        查询产品信息

        Args:
            asin: Amazon ASIN

        Returns:
            产品信息
        """
        sql = f"""
            SELECT 
                asin,
                product_name,
                price,
                rating,
                review_count,
                brand,
                category,
                amazon_url
            FROM yp_products
            WHERE asin = '{asin}'
            LIMIT 1
        """

        result = await self.execute_tool("db_query", sql=sql)

        if result.success and result.data:
            return result.data[0]

        return {}

    async def query_amazon_details(self, asin: str) -> Dict[str, Any]:
        """
        查询 Amazon 详情

        Args:
            asin: Amazon ASIN

        Returns:
            Amazon 详情
        """
        sql = f"""
            SELECT 
                asin,
                title,
                price,
                rating,
                review_count,
                bullet_points,
                description,
                image_url,
                availability
            FROM amazon_product_details
            WHERE asin = '{asin}'
            LIMIT 1
        """

        result = await self.execute_tool("db_query", sql=sql)

        if result.success and result.data:
            return result.data[0]

        return {}

    async def query_brand_keywords(self, brand: str) -> List[str]:
        """
        查询品牌关键词

        Args:
            brand: 品牌名称

        Returns:
            关键词列表
        """
        sql = f"""
            SELECT keyword
            FROM brand_keywords
            WHERE brand_name = '{brand}'
            ORDER BY search_volume DESC
            LIMIT 20
        """

        result = await self.execute_tool("db_query", sql=sql)

        if result.success and result.data:
            return [row.get("keyword", "") for row in result.data]

        return []

    async def generate_ads_with_skill(
        self,
        product_info: Dict[str, Any],
        amazon_details: Dict[str, Any],
        keywords: List[str],
    ) -> Dict[str, Any]:
        """
        使用技能生成广告

        Args:
            product_info: 产品信息
            amazon_details: Amazon 详情
            keywords: 关键词列表

        Returns:
            广告方案
        """
        # 加载技能提示词
        skill_content = self.load_skill("google-ads-v5.0")

        # 构建输入数据
        input_data = {
            "asin": product_info.get("asin", ""),
            "product_name": product_info.get("product_name")
            or amazon_details.get("title", ""),
            "price": product_info.get("price") or amazon_details.get("price", 0),
            "commission": "5%",  # 默认佣金
            "rating": product_info.get("rating") or amazon_details.get("rating", 0),
            "review_count": product_info.get("review_count")
            or amazon_details.get("review_count", 0),
            "brand": product_info.get("brand", ""),
            "category_path": product_info.get("category", ""),
            "bullet_points": amazon_details.get("bullet_points", []),
            "brand_keywords": keywords,
        }

        # 调用 LLM 生成广告
        # 这里是占位实现，实际需要调用千帆 API
        ads_plan = await self._call_llm_for_ads(skill_content, input_data)

        return ads_plan

    async def _call_llm_for_ads(
        self, skill_prompt: str, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用 LLM 生成广告（占位实现）

        Args:
            skill_prompt: 技能提示词
            input_data: 输入数据

        Returns:
            生成的广告方案
        """
        # 实际实现需要调用千帆 API
        # 这里返回占位数据

        self.logger.info(f"Calling LLM with model: {self.model}")

        # 模拟生成的广告方案
        return {
            "product_analysis": {
                "name": input_data.get("product_name", ""),
                "category": input_data.get("category_path", ""),
                "price": input_data.get("price", 0),
                "commission": input_data.get("commission", "5%"),
                "rating": input_data.get("rating", 0),
                "review_count": input_data.get("review_count", 0),
            },
            "profitability": {
                "estimated_cpc": 0.5,
                "estimated_conversion_rate": 0.03,
                "estimated_roi": 2.5,
                "recommendation": "建议投放",
            },
            "campaigns": [
                {
                    "name": f"{input_data.get('brand', '')} - 品牌词",
                    "type": "Search",
                    "budget": 10,
                    "ad_groups": [
                        {
                            "name": "核心品牌词",
                            "keywords": input_data.get("brand_keywords", [])[:5],
                            "ads": [
                                {
                                    "headline1": f"官方{input_data.get('brand', '')}产品",
                                    "headline2": f"仅${input_data.get('price', 0)}起",
                                    "description": f"Amazon精选，{input_data.get('rating', 0)}星好评，免费配送",
                                }
                            ],
                        }
                    ],
                }
            ],
            "account_negative_keywords": ["免费", "下载", "教程"],
            "qa_report": {
                "passed": True,
                "checks": [
                    {"id": "price_consistency", "status": "pass"},
                    {"id": "char_format", "status": "pass"},
                ],
            },
        }

    async def save_ads_plan(self, asin: str, ads_plan: Dict[str, Any]) -> bool:
        """
        保存广告方案

        Args:
            asin: Amazon ASIN
            ads_plan: 广告方案

        Returns:
            是否成功
        """
        # 保存到数据库
        result = await self.execute_tool(
            "db_write",
            table="ads_plans",
            data={
                "asin": asin,
                "plan_json": json.dumps(ads_plan, ensure_ascii=False),
                "status": "draft",
                "created_at": "NOW()",
            },
            mode="upsert",
        )

        return result.success

    async def execute(
        self, task: str, context: Optional[Dict[str, Any]] = None, stream: bool = True
    ) -> Union[str, Generator[AgentMessage, None, None]]:
        """
        执行广告创作任务

        Args:
            task: 任务描述
            context: 执行上下文
            stream: 是否流式输出

        Returns:
            执行结果或消息流
        """
        self.state = AgentState.RUNNING
        ctx = context or {}

        self.logger.info(f"Executing ad creation task: {task}")

        # 从上下文或任务中提取 ASIN
        asin = ctx.get("asin")
        if not asin:
            # 尝试从任务文本中提取 ASIN
            import re

            match = re.search(r"[A-Z0-9]{10}", task)
            if match:
                asin = match.group()

        if not asin:
            self.state = AgentState.FAILED
            error_msg = "无法识别产品 ASIN，请提供有效的 ASIN"
            if stream:
                yield AgentMessage(type=MessageType.ERROR, content=error_msg)
                yield AgentMessage(type=MessageType.DONE, content="")
            return

        # 执行工作流
        if stream:
            yield AgentMessage(
                type=MessageType.THINKING, content=f"正在为产品 {asin} 生成广告方案..."
            )

        # Step 1: 获取产品信息
        if stream:
            yield AgentMessage(type=MessageType.THINKING, content="正在查询产品信息...")

        product_info = await self.query_product(asin)

        if not product_info:
            if stream:
                yield AgentMessage(
                    type=MessageType.TEXT, content=f"⚠️ 数据库中未找到产品 {asin} 的信息"
                )

        # Step 2: 获取 Amazon 详情
        if stream:
            yield AgentMessage(
                type=MessageType.THINKING, content="正在获取 Amazon 详情..."
            )

        amazon_details = await self.query_amazon_details(asin)

        # Step 3: 获取品牌关键词
        brand = product_info.get("brand", "") or amazon_details.get("brand", "")
        keywords = []

        if brand:
            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING,
                    content=f"正在获取 {brand} 的品牌关键词...",
                )

            keywords = await self.query_brand_keywords(brand)

        # Step 4: 生成广告
        if stream:
            yield AgentMessage(type=MessageType.THINKING, content="正在生成广告方案...")

        ads_plan = await self.generate_ads_with_skill(
            product_info, amazon_details, keywords
        )

        # Step 5: 保存方案
        if stream:
            yield AgentMessage(type=MessageType.THINKING, content="正在保存广告方案...")

        saved = await self.save_ads_plan(asin, ads_plan)

        # 返回结果
        self.state = AgentState.COMPLETED

        if stream:
            yield AgentMessage(type=MessageType.TEXT, content="## 广告方案生成完成\n")

            # 产品信息
            yield AgentMessage(
                type=MessageType.TEXT,
                content=f"\n### 产品信息\n"
                f"- **ASIN:** {asin}\n"
                f"- **名称:** {product_info.get('product_name') or amazon_details.get('title', 'N/A')}\n"
                f"- **价格:** ${product_info.get('price') or amazon_details.get('price', 'N/A')}\n"
                f"- **评分:** {product_info.get('rating') or amazon_details.get('rating', 'N/A')} ⭐\n",
            )

            # 广告系列
            campaigns = ads_plan.get("campaigns", [])
            yield AgentMessage(
                type=MessageType.TEXT, content=f"\n### 广告系列 ({len(campaigns)} 个)\n"
            )

            for i, campaign in enumerate(campaigns, 1):
                yield AgentMessage(
                    type=MessageType.TEXT,
                    content=f"\n**{i}. {campaign.get('name', '未命名')}**\n"
                    f"- 类型: {campaign.get('type', 'Search')}\n"
                    f"- 预算: ${campaign.get('budget', 0)}/天\n",
                )

                for ad_group in campaign.get("ad_groups", []):
                    yield AgentMessage(
                        type=MessageType.TEXT,
                        content=f"\n  广告组: {ad_group.get('name', '未命名')}\n",
                    )

                    for ad in ad_group.get("ads", []):
                        yield AgentMessage(
                            type=MessageType.TEXT,
                            content=f"  - 标题1: {ad.get('headline1', '')}\n"
                            f"  - 标题2: {ad.get('headline2', '')}\n"
                            f"  - 描述: {ad.get('description', '')}\n",
                        )

            # QA 报告
            qa = ads_plan.get("qa_report", {})
            if qa.get("passed"):
                yield AgentMessage(
                    type=MessageType.TEXT, content="\n### ✅ QA 检查通过\n"
                )
            else:
                yield AgentMessage(
                    type=MessageType.TEXT, content="\n### ⚠️ QA 检查存在问题\n"
                )

            if saved:
                yield AgentMessage(
                    type=MessageType.TEXT, content="\n广告方案已保存到数据库。\n"
                )

            yield AgentMessage(type=MessageType.DONE, content="")

    async def generate_for_product(self, asin: str) -> Dict[str, Any]:
        """
        为指定产品生成广告（便捷方法）

        Args:
            asin: Amazon ASIN

        Returns:
            广告方案
        """
        result = await self.execute(
            task=f"为产品 {asin} 生成广告", context={"asin": asin}, stream=False
        )
        return result
