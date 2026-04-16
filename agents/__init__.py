# -*- coding: utf-8 -*-
"""
agents/__init__.py
==================
Agent 模块

提供完整的 Agent 框架:

- BaseAgent: Agent 基类
- OrchestratorAgent: 主调度 Agent
- AdAgent: 广告创作 Agent
- ScrapeAgent: 采集 Agent
- AnalysisAgent: 分析 Agent

使用方式:
    from agents import create_agent, OrchestratorAgent

    # 方式1: 使用工厂函数
    agent = create_agent("ad_creator")

    # 方式2: 直接实例化
    orchestrator = OrchestratorAgent()

    # 执行任务
    result = await agent.execute("为产品 B09XYZ123 生成广告")
"""

from .base_agent import (
    AgentMessage,
    AgentState,
    BaseAgent,
    MessageType,
    ToolResult,
    create_agent,
)
from .orchestrator import (
    Intent,
    OrchestratorAgent,
    SubTask,
)
from .ad_agent import AdAgent
from .scrape_agent import (
    ScrapeAgent,
    ScrapeType,
)
from .analysis_agent import (
    AnalysisAgent,
    AnalysisType,
)

__all__ = [
    # 基类
    "BaseAgent",
    "AgentMessage",
    "AgentState",
    "MessageType",
    "ToolResult",
    "create_agent",
    # 主调度 Agent
    "OrchestratorAgent",
    "Intent",
    "SubTask",
    # 广告 Agent
    "AdAgent",
    # 采集 Agent
    "ScrapeAgent",
    "ScrapeType",
    # 分析 Agent
    "AnalysisAgent",
    "AnalysisType",
]

# Agent 版本
__version__ = "1.0.0"
