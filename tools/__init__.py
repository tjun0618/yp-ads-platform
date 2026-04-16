# -*- coding: utf-8 -*-
"""
tools/__init__.py
================
工具模块

导出所有工具类和便捷函数

使用方式:
    from tools import ToolRegistry, db_query, browser_navigate

    # 使用工具类
    result = ToolRegistry.get("db_query").run({"sql": "SELECT * FROM table"})

    # 使用便捷函数
    data = db_query("SELECT * FROM table")
"""

from typing import Dict, Any, Type, Optional
import logging

from .base_tool import (
    BaseTool,
    ToolConfig,
    ToolResult,
    ToolError,
    ValidationError,
    ExecutionError,
    TimeoutError,
    ErrorHandling,
    tool_registry,
)

from .database import (
    DBQueryTool,
    DBWriteTool,
    ConnectionPool,
    get_db_pool,
    init_db_pool,
    db_query,
    db_insert,
    db_update,
    db_upsert,
)

from .browser import (
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserExtractTool,
    BrowserScreenshotTool,
    BrowserManager,
    get_browser_manager,
    browser_navigate,
    browser_click,
    browser_extract,
    browser_screenshot,
)

from .http_tool import (
    HttpRequestTool,
    HttpSession,
    HttpResponse,
    get_http_session,
    http_get,
    http_post,
    http_put,
    http_delete,
    http_patch,
)

from .file_tool import (
    FileReadTool,
    FileWriteTool,
    FileDeleteTool,
    FileListTool,
    file_read,
    file_write,
    file_delete,
    file_list,
)


logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表

    管理所有可用工具
    """

    _tools: Dict[str, Type[BaseTool]] = {}
    _instances: Dict[str, BaseTool] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool], tool_id: str = None):
        """
        注册工具

        Args:
            tool_class: 工具类
            tool_id: 工具 ID（可选，默认使用类的 config.id）
        """
        # 创建实例以获取 ID
        instance = tool_class()
        tool_id = tool_id or instance.config.id

        cls._tools[tool_id] = tool_class
        cls._instances[tool_id] = instance

        logger.debug(f"Registered tool: {tool_id}")

    @classmethod
    def get(cls, tool_id: str) -> Optional[BaseTool]:
        """
        获取工具实例

        Args:
            tool_id: 工具 ID

        Returns:
            工具实例
        """
        if tool_id in cls._instances:
            return cls._instances[tool_id]

        return None

    @classmethod
    def get_all(cls) -> Dict[str, BaseTool]:
        """获取所有工具实例"""
        return cls._instances.copy()

    @classmethod
    def list_tools(cls) -> Dict[str, Dict[str, Any]]:
        """
        列出所有工具信息

        Returns:
            工具信息字典
        """
        result = {}
        for tool_id, instance in cls._instances.items():
            result[tool_id] = {
                "id": instance.config.id,
                "name": instance.config.name,
                "type": instance.config.type,
                "description": instance.config.description,
                "parameters": instance.config.parameters,
                "returns": instance.config.returns,
                "timeout": instance.config.timeout,
                "safe": instance.config.safe,
            }
        return result

    @classmethod
    def execute(cls, tool_id: str, params: Dict[str, Any]) -> ToolResult:
        """
        执行工具

        Args:
            tool_id: 工具 ID
            params: 参数

        Returns:
            执行结果
        """
        tool = cls.get(tool_id)
        if tool is None:
            return ToolResult(success=False, error=f"Tool not found: {tool_id}")

        return tool.run(params)

    @classmethod
    def clear(cls):
        """清空注册表"""
        cls._tools.clear()
        cls._instances.clear()


def init_tools(db_config: Dict[str, Any] = None, cdp_url: str = None):
    """
    初始化所有工具

    Args:
        db_config: 数据库配置
        cdp_url: Chrome 调试 URL
    """
    # 注册数据库工具
    ToolRegistry.register(DBQueryTool)
    ToolRegistry.register(DBWriteTool)

    # 注册浏览器工具
    ToolRegistry.register(BrowserNavigateTool)
    ToolRegistry.register(BrowserClickTool)
    ToolRegistry.register(BrowserExtractTool)
    ToolRegistry.register(BrowserScreenshotTool)

    # 注册 HTTP 工具
    ToolRegistry.register(HttpRequestTool)

    # 注册文件工具
    ToolRegistry.register(FileReadTool)
    ToolRegistry.register(FileWriteTool)
    ToolRegistry.register(FileDeleteTool)
    ToolRegistry.register(FileListTool)

    # 初始化数据库连接池
    if db_config:
        init_db_pool(db_config)

    logger.info(f"Initialized {len(ToolRegistry._tools)} tools")


def get_tool(tool_id: str) -> Optional[BaseTool]:
    """
    获取工具实例

    Args:
        tool_id: 工具 ID

    Returns:
        工具实例
    """
    return ToolRegistry.get(tool_id)


def run_tool(tool_id: str, params: Dict[str, Any]) -> ToolResult:
    """
    运行工具

    Args:
        tool_id: 工具 ID
        params: 参数

    Returns:
        执行结果
    """
    return ToolRegistry.execute(tool_id, params)


# 自动初始化
init_tools()


__all__ = [
    # 基类
    "BaseTool",
    "ToolConfig",
    "ToolResult",
    "ToolError",
    "ValidationError",
    "ExecutionError",
    "TimeoutError",
    "ErrorHandling",
    # 工具注册表
    "ToolRegistry",
    "init_tools",
    "get_tool",
    "run_tool",
    # 数据库工具
    "DBQueryTool",
    "DBWriteTool",
    "ConnectionPool",
    "get_db_pool",
    "init_db_pool",
    "db_query",
    "db_insert",
    "db_update",
    "db_upsert",
    # 浏览器工具
    "BrowserNavigateTool",
    "BrowserClickTool",
    "BrowserExtractTool",
    "BrowserScreenshotTool",
    "BrowserManager",
    "get_browser_manager",
    "browser_navigate",
    "browser_click",
    "browser_extract",
    "browser_screenshot",
    # HTTP 工具
    "HttpRequestTool",
    "HttpSession",
    "HttpResponse",
    "get_http_session",
    "http_get",
    "http_post",
    "http_put",
    "http_delete",
    "http_patch",
    # 文件工具
    "FileReadTool",
    "FileWriteTool",
    "FileDeleteTool",
    "FileListTool",
    "file_read",
    "file_write",
    "file_delete",
    "file_list",
]
