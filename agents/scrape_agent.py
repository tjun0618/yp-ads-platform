# -*- coding: utf-8 -*-
"""
agents/scrape_agent.py
======================
采集 Agent

功能:
- 数据采集工作流
- 支持 Amazon、YP、关键词采集
- 浏览器自动化
"""

import json
import logging
import re
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


class ScrapeType(Enum):
    """采集类型"""

    AMAZON = "amazon"
    YP = "yp"
    KEYWORD = "keyword"
    SEMRUSH = "semrush"


class ScrapeAgent(BaseAgent):
    """
    采集 Agent

    采集各类平台数据:
    - Amazon 商品详情
    - YP 商户/产品
    - Google Suggest 关键词
    - SEMrush 竞品数据
    """

    def __init__(self, **kwargs):
        """初始化采集 Agent"""
        super().__init__(agent_id="scraper", **kwargs)

        # 采集子类型配置
        self._sub_types = self._config.get("sub_types", {})

        self.logger.info("ScrapeAgent initialized")

    def detect_scrape_type(self, task: str) -> ScrapeType:
        """
        检测采集类型

        Args:
            task: 任务描述

        Returns:
            采集类型
        """
        task_lower = task.lower()

        if "amazon" in task_lower or "asin" in task_lower:
            return ScrapeType.AMAZON
        elif (
            "keyword" in task_lower or "关键词" in task_lower or "suggest" in task_lower
        ):
            return ScrapeType.KEYWORD
        elif "semrush" in task_lower or "竞品" in task_lower:
            return ScrapeType.SEMRUSH
        else:
            return ScrapeType.YP

    async def scrape_amazon(self, asin: str) -> Dict[str, Any]:
        """
        采集 Amazon 商品详情

        Args:
            asin: Amazon ASIN

        Returns:
            商品详情
        """
        self.logger.info(f"Scraping Amazon product: {asin}")

        # 使用技能加载采集规则
        skill_content = ""
        try:
            skill_content = self.load_skill("amazon-scraping")
        except Exception as e:
            self.logger.warning(f"Could not load amazon-scraping skill: {e}")

        # 构建采集 URL
        url = f"https://www.amazon.com/dp/{asin}"

        # 执行浏览器采集
        result = await self.execute_tool(
            "browser_navigate", url=url, wait_until="domcontentloaded"
        )

        if not result.success:
            return {"error": result.error, "asin": asin}

        # 提取数据
        extract_result = await self.execute_tool(
            "browser_extract",
            selectors={
                "title": "#productTitle",
                "price": ".a-price .a-offscreen",
                "rating": "span.a-icon-alt",
                "review_count": "#acrCustomerReviewText",
                "availability": "#availability span",
            },
        )

        data = extract_result.data if extract_result.success else {}

        # 处理数据
        product_data = {
            "asin": asin,
            "url": url,
            "title": data.get("title", "").strip() if data.get("title") else "",
            "price": self._parse_price(data.get("price", "")),
            "rating": self._parse_rating(data.get("rating", "")),
            "review_count": self._parse_review_count(data.get("review_count", "")),
            "availability": data.get("availability", "").strip()
            if data.get("availability")
            else "",
        }

        # 保存到数据库
        if product_data.get("title"):
            await self.execute_tool(
                "db_write",
                table="amazon_product_details",
                data=product_data,
                mode="upsert",
            )

        return product_data

    def _parse_price(self, price_str: str) -> Optional[float]:
        """解析价格字符串"""
        if not price_str:
            return None

        # 提取数字
        match = re.search(r"[\d,]+\.?\d*", price_str.replace(",", ""))
        if match:
            return float(match.group())
        return None

    def _parse_rating(self, rating_str: str) -> Optional[float]:
        """解析评分字符串"""
        if not rating_str:
            return None

        match = re.search(r"(\d+\.?\d*)", rating_str)
        if match:
            return float(match.group())
        return None

    def _parse_review_count(self, count_str: str) -> Optional[int]:
        """解析评论数"""
        if not count_str:
            return None

        # 移除逗号
        count_str = count_str.replace(",", "")
        match = re.search(r"(\d+)", count_str)
        if match:
            return int(match.group())
        return None

    async def scrape_yp_merchants(
        self, page: int = 1, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        采集 YP 商户列表

        Args:
            page: 页码
            limit: 每页数量

        Returns:
            商户列表
        """
        self.logger.info(f"Scraping YP merchants: page={page}, limit={limit}")

        # 使用技能
        skill_content = ""
        try:
            skill_content = self.load_skill("yp-scraping")
        except Exception as e:
            self.logger.warning(f"Could not load yp-scraping skill: {e}")

        # 这里是占位实现，实际需要调用 YP API 或浏览器采集
        # 从数据库获取商户数据
        result = await self.execute_tool(
            "db_query",
            sql=f"""
                SELECT 
                    merchant_id,
                    merchant_name,
                    status,
                    commission_rate,
                    created_at
                FROM yp_merchants
                WHERE status = 'approved'
                ORDER BY created_at DESC
                LIMIT {limit}
                OFFSET {(page - 1) * limit}
            """,
        )

        if result.success:
            return result.data

        return []

    async def scrape_keywords(
        self, brand_name: str, merchant_id: Optional[str] = None
    ) -> List[str]:
        """
        采集 Google Suggest 关键词

        Args:
            brand_name: 品牌名称
            merchant_id: 商户 ID (可选)

        Returns:
            关键词列表
        """
        self.logger.info(f"Scraping keywords for brand: {brand_name}")

        # 使用技能
        skill_content = ""
        try:
            skill_content = self.load_skill("keyword-scraping")
        except Exception as e:
            self.logger.warning(f"Could not load keyword-scraping skill: {e}")

        # 构建搜索 URL
        url = f"https://www.google.com/search?q={brand_name}"

        # 导航到 Google
        await self.execute_tool(
            "browser_navigate",
            url="https://www.google.com",
            wait_until="domcontentloaded",
        )

        # 提取建议词
        # 这里是占位实现，实际需要处理搜索建议
        keywords = [
            f"{brand_name} review",
            f"{brand_name} official",
            f"{brand_name} store",
        ]

        # 保存到数据库
        if keywords:
            for keyword in keywords:
                await self.execute_tool(
                    "db_write",
                    table="brand_keywords",
                    data={
                        "brand_name": brand_name,
                        "keyword": keyword,
                        "source": "google_suggest",
                    },
                    mode="upsert",
                )

        return keywords

    async def scrape_semrush(self, domain: str) -> Dict[str, Any]:
        """
        采集 SEMrush 竞品数据

        Args:
            domain: 竞品域名

        Returns:
            竞品数据
        """
        self.logger.info(f"Scraping SEMrush data for: {domain}")

        # 这里是占位实现
        # 实际需要登录 SEMrush 并执行采集

        return {
            "domain": domain,
            "organic_keywords": 0,
            "organic_traffic": 0,
            "ad_keywords": 0,
            "ad_traffic": 0,
        }

    async def execute(
        self, task: str, context: Optional[Dict[str, Any]] = None, stream: bool = True
    ) -> Union[str, Generator[AgentMessage, None, None]]:
        """
        执行采集任务

        Args:
            task: 任务描述
            context: 执行上下文
            stream: 是否流式输出

        Returns:
            执行结果或消息流
        """
        self.state = AgentState.RUNNING
        ctx = context or {}

        self.logger.info(f"Executing scrape task: {task}")

        # 检测采集类型
        scrape_type = self.detect_scrape_type(task)

        if stream:
            yield AgentMessage(
                type=MessageType.THINKING,
                content=f"检测到采集类型: {scrape_type.value}",
            )

        result = None

        if scrape_type == ScrapeType.AMAZON:
            # 提取 ASIN
            asin = ctx.get("asin")
            if not asin:
                match = re.search(r"[A-Z0-9]{10}", task)
                asin = match.group() if match else None

            if not asin:
                self.state = AgentState.FAILED
                error_msg = "无法识别 ASIN"
                if stream:
                    yield AgentMessage(type=MessageType.ERROR, content=error_msg)
                    yield AgentMessage(type=MessageType.DONE, content="")
                return

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content=f"正在采集 Amazon 商品 {asin}..."
                )

            result = await self.scrape_amazon(asin)

            if stream:
                yield AgentMessage(
                    type=MessageType.TEXT,
                    content=f"\n### 采集结果\n"
                    f"- **ASIN:** {result.get('asin', '')}\n"
                    f"- **标题:** {result.get('title', 'N/A')}\n"
                    f"- **价格:** ${result.get('price', 'N/A')}\n"
                    f"- **评分:** {result.get('rating', 'N/A')} ⭐\n"
                    f"- **评论数:** {result.get('review_count', 'N/A')}\n",
                )

        elif scrape_type == ScrapeType.KEYWORD:
            # 提取品牌名
            brand_name = ctx.get("brand_name")
            if not brand_name:
                # 尝试从任务中提取
                match = re.search(r"品牌[：:]\s*(\S+)", task)
                if match:
                    brand_name = match.group(1)

            if not brand_name:
                self.state = AgentState.FAILED
                error_msg = "无法识别品牌名称"
                if stream:
                    yield AgentMessage(type=MessageType.ERROR, content=error_msg)
                    yield AgentMessage(type=MessageType.DONE, content="")
                return

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING,
                    content=f"正在采集 {brand_name} 的关键词...",
                )

            keywords = await self.scrape_keywords(brand_name, ctx.get("merchant_id"))
            result = {"brand": brand_name, "keywords": keywords, "count": len(keywords)}

            if stream:
                yield AgentMessage(
                    type=MessageType.TEXT,
                    content=f"\n### 关键词采集结果\n"
                    f"- **品牌:** {brand_name}\n"
                    f"- **关键词数量:** {len(keywords)}\n"
                    f"- **关键词:**\n",
                )
                for kw in keywords[:10]:
                    yield AgentMessage(type=MessageType.TEXT, content=f"  - {kw}\n")

        elif scrape_type == ScrapeType.YP:
            page = ctx.get("page", 1)
            limit = ctx.get("limit", 100)

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING,
                    content=f"正在采集 YP 商户数据 (第 {page} 页)...",
                )

            merchants = await self.scrape_yp_merchants(page, limit)
            result = {"page": page, "merchants": merchants, "count": len(merchants)}

            if stream:
                yield AgentMessage(
                    type=MessageType.TEXT,
                    content=f"\n### YP 商户采集结果\n"
                    f"- **页码:** {page}\n"
                    f"- **商户数量:** {len(merchants)}\n",
                )

        else:
            self.state = AgentState.FAILED
            error_msg = f"不支持的采集类型: {scrape_type.value}"
            if stream:
                yield AgentMessage(type=MessageType.ERROR, content=error_msg)
                yield AgentMessage(type=MessageType.DONE, content="")
            return

        self.state = AgentState.COMPLETED

        if stream:
            yield AgentMessage(type=MessageType.TEXT, content="\n采集任务完成\n")
            yield AgentMessage(type=MessageType.DONE, content="")

    async def batch_scrape_amazon(self, asins: List[str]) -> List[Dict[str, Any]]:
        """
        批量采集 Amazon 商品

        Args:
            asins: ASIN 列表

        Returns:
            采集结果列表
        """
        results = []

        for asin in asins:
            try:
                result = await self.scrape_amazon(asin)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Failed to scrape {asin}: {e}")
                results.append({"asin": asin, "error": str(e)})

        return results
