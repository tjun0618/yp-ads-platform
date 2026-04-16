# -*- coding: utf-8 -*-
"""
API 模块
========

Flask 路由和工具函数，用于集成 Agent 系统。

端点:
    - POST /api/agent/chat         - 与 Agent 对话
    - GET  /api/agent/generate_ads/<asin> - SSE 生成广告
    - GET  /api/agent/status       - 查询任务状态

使用方式:
    from api import register_routes
    register_routes(app)
"""

from .routes import register_routes, bp
from .sse import sse_response, sse_progress, sse_error, sse_done
from .executor import AgentExecutor, execute_agent_task

__all__ = [
    "register_routes",
    "bp",
    "sse_response",
    "sse_progress",
    "sse_error",
    "sse_done",
    "AgentExecutor",
    "execute_agent_task",
]
