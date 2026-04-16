# -*- coding: utf-8 -*-
"""
agents/orchestrator.py
======================
主调度 Agent

功能:
- 意图识别
- 任务分解
- 子Agent调度
- 结果汇总
"""

import json
import logging
import asyncio
from dataclasses import dataclass
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
    create_agent,
)


class Intent(Enum):
    """用户意图"""

    AD_CREATION = "ad_creation"  # 广告创作
    KEYWORD_SCRAPING = "keyword_scraping"  # 关键词采集
    DATA_COLLECTION = "data_collection"  # 数据采集
    DATA_ANALYSIS = "data_analysis"  # 数据分析
    AMAZON_SCRAPE = "amazon_scrape"  # Amazon 采集
    MERCHANT_SYNC = "merchant_sync"  # 商户同步
    UNKNOWN = "unknown"  # 未知意图


@dataclass
class SubTask:
    """子任务"""

    id: str
    agent_id: str
    task: str
    context: Dict[str, Any]
    status: str = "pending"
    result: Optional[Any] = None


class OrchestratorAgent(BaseAgent):
    """
    主调度 Agent

    职责:
    1. 理解用户意图
    2. 将复杂任务分解为子任务
    3. 调度合适的子 Agent 执行
    4. 汇总结果返回给用户
    """

    def __init__(self, **kwargs):
        """初始化主调度 Agent"""
        super().__init__(agent_id="orchestrator", **kwargs)

        # 子 Agent 实例缓存
        self._sub_agents: Dict[str, BaseAgent] = {}

        # 任务队列
        self._task_queue: List[SubTask] = []

        # 意图- Agent 映射
        self._intent_agent_map = {
            Intent.AD_CREATION: "ad_creator",
            Intent.KEYWORD_SCRAPING: "scraper",
            Intent.DATA_COLLECTION: "scraper",
            Intent.DATA_ANALYSIS: "analyst",
            Intent.AMAZON_SCRAPE: "scraper",
            Intent.MERCHANT_SYNC: "scraper",
        }

        # 意图关键词映射
        self._intent_keywords = {
            Intent.AD_CREATION: [
                "广告",
                "ads",
                "投放",
                "创意",
                "文案",
                "生成广告",
                "创建广告",
                "广告方案",
            ],
            Intent.KEYWORD_SCRAPING: [
                "关键词",
                "keyword",
                "采集关键词",
                "品牌词",
                "搜索词",
                "suggest",
            ],
            Intent.DATA_COLLECTION: [
                "采集",
                "scrape",
                "爬取",
                "抓取",
                "同步",
                "下载",
                "collect",
            ],
            Intent.DATA_ANALYSIS: [
                "分析",
                "analyze",
                "报告",
                "report",
                "统计",
                "洞察",
                "数据报告",
            ],
            Intent.AMAZON_SCRAPE: ["amazon", "亚马逊", "商品详情", "asin", "产品信息"],
            Intent.MERCHANT_SYNC: ["商户", "merchant", "商家", "同步商户", "更新商户"],
        }

        self.logger.info("OrchestratorAgent initialized")

    def recognize_intent(self, user_input: str) -> Intent:
        """
        识别用户意图

        Args:
            user_input: 用户输入

        Returns:
            识别出的意图
        """
        user_input_lower = user_input.lower()

        # 计算每个意图的匹配分数
        scores: Dict[Intent, int] = {}

        for intent, keywords in self._intent_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in user_input_lower:
                    score += 1
            if score > 0:
                scores[intent] = score

        if not scores:
            return Intent.UNKNOWN

        # 返回得分最高的意图
        best_intent = max(scores, key=scores.get)
        return best_intent

    def decompose_task(
        self, intent: Intent, user_input: str, context: Optional[Dict[str, Any]] = None
    ) -> List[SubTask]:
        """
        将任务分解为子任务

        Args:
            intent: 用户意图
            user_input: 用户输入
            context: 上下文

        Returns:
            子任务列表
        """
        sub_tasks = []
        ctx = context or {}

        if intent == Intent.AD_CREATION:
            # 广告创作任务分解
            sub_tasks = [
                SubTask(
                    id="query_product",
                    agent_id="ad_creator",
                    task="查询产品信息",
                    context={"input": user_input, **ctx},
                ),
                SubTask(
                    id="generate_ads",
                    agent_id="ad_creator",
                    task="生成广告方案",
                    context={"input": user_input, **ctx},
                    status="waiting",  # 等待前置任务完成
                ),
            ]

        elif intent == Intent.KEYWORD_SCRAPING:
            sub_tasks = [
                SubTask(
                    id="scrape_keywords",
                    agent_id="scraper",
                    task="采集关键词",
                    context={"input": user_input, **ctx},
                )
            ]

        elif intent == Intent.DATA_COLLECTION:
            sub_tasks = [
                SubTask(
                    id="collect_data",
                    agent_id="scraper",
                    task="采集数据",
                    context={"input": user_input, **ctx},
                )
            ]

        elif intent == Intent.DATA_ANALYSIS:
            sub_tasks = [
                SubTask(
                    id="analyze_data",
                    agent_id="analyst",
                    task="分析数据",
                    context={"input": user_input, **ctx},
                )
            ]

        elif intent == Intent.AMAZON_SCRAPE:
            sub_tasks = [
                SubTask(
                    id="scrape_amazon",
                    agent_id="scraper",
                    task="采集 Amazon 商品",
                    context={"input": user_input, **ctx},
                )
            ]

        elif intent == Intent.MERCHANT_SYNC:
            sub_tasks = [
                SubTask(
                    id="sync_merchants",
                    agent_id="scraper",
                    task="同步商户",
                    context={"input": user_input, **ctx},
                )
            ]

        else:
            # 未知意图，返回空列表
            self.logger.warning(f"Unknown intent for: {user_input}")

        return sub_tasks

    def get_sub_agent(self, agent_id: str) -> BaseAgent:
        """
        获取子 Agent 实例

        Args:
            agent_id: Agent ID

        Returns:
            Agent 实例
        """
        if agent_id not in self._sub_agents:
            self._sub_agents[agent_id] = create_agent(agent_id)

        return self._sub_agents[agent_id]

    async def execute_sub_task(self, sub_task: SubTask) -> Any:
        """
        执行子任务

        Args:
            sub_task: 子任务

        Returns:
            执行结果
        """
        self.logger.info(f"Executing sub-task: {sub_task.id}")

        try:
            agent = self.get_sub_agent(sub_task.agent_id)
            result = await agent.execute(
                task=sub_task.task, context=sub_task.context, stream=False
            )

            sub_task.result = result
            sub_task.status = "completed"
            return result

        except Exception as e:
            self.logger.error(f"Sub-task failed: {sub_task.id} - {e}")
            sub_task.status = "failed"
            raise

    async def execute(
        self, task: str, context: Optional[Dict[str, Any]] = None, stream: bool = True
    ) -> Union[str, Generator[AgentMessage, None, None]]:
        """
        执行任务

        Args:
            task: 任务描述
            context: 执行上下文
            stream: 是否流式输出

        Returns:
            执行结果或消息流
        """
        self.state = AgentState.RUNNING
        self.logger.info(f"Executing task: {task}")

        # 1. 识别意图
        intent = self.recognize_intent(task)
        self.logger.info(f"Recognized intent: {intent.value}")

        if stream:
            yield AgentMessage(
                type=MessageType.THINKING,
                content=f"正在分析您的需求，识别到意图: {intent.value}",
            )

        if intent == Intent.UNKNOWN:
            self.state = AgentState.FAILED
            if stream:
                yield AgentMessage(
                    type=MessageType.ERROR,
                    content="抱歉，我无法理解您的需求。请尝试更具体地描述您想要做什么。",
                )
                yield AgentMessage(type=MessageType.DONE, content="")
            return

        # 2. 分解任务
        sub_tasks = self.decompose_task(intent, task, context)

        if stream:
            yield AgentMessage(
                type=MessageType.THINKING,
                content=f"任务已分解为 {len(sub_tasks)} 个子任务",
            )

        # 3. 执行子任务
        results = []
        for sub_task in sub_tasks:
            if sub_task.status == "waiting":
                # 检查前置任务是否完成
                # 简化处理：跳过等待状态的任务
                continue

            if stream:
                yield AgentMessage(
                    type=MessageType.THINKING, content=f"正在执行: {sub_task.task}"
                )

            try:
                result = await self.execute_sub_task(sub_task)
                results.append(result)

                if stream:
                    yield AgentMessage(
                        type=MessageType.TEXT, content=f"✓ {sub_task.task} 完成"
                    )
            except Exception as e:
                if stream:
                    yield AgentMessage(
                        type=MessageType.ERROR,
                        content=f"✗ {sub_task.task} 失败: {str(e)}",
                    )

        # 4. 汇总结果
        self.state = AgentState.COMPLETED

        if stream:
            yield AgentMessage(type=MessageType.TEXT, content="\n### 执行结果\n")

            for i, result in enumerate(results):
                yield AgentMessage(
                    type=MessageType.TEXT,
                    content=f"\n**子任务 {i + 1}:**\n{self._format_result(result)}",
                )

            yield AgentMessage(type=MessageType.DONE, content="")

    def _format_result(self, result: Any) -> str:
        """格式化结果"""
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2)
        elif isinstance(result, list):
            if len(result) > 5:
                return (
                    f"[{len(result)} 项数据]\n"
                    + json.dumps(result[:3], ensure_ascii=False, indent=2)
                    + "\n..."
                )
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return str(result)

    async def chat(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Generator[AgentMessage, None, None]:
        """
        聊天接口（流式）

        Args:
            message: 用户消息
            context: 上下文

        Yields:
            Agent 消息
        """
        async for msg in self.execute(message, context, stream=True):
            yield msg
