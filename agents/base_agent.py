# -*- coding: utf-8 -*-
"""
agents/base_agent.py
====================
Agent 基类

功能:
- 从配置创建 Agent 实例
- 加载技能文件
- 注册工具
- 执行任务
- 流式输出支持
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Union,
)

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import config


class AgentState(Enum):
    """Agent 状态"""

    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageType(Enum):
    """消息类型"""

    TEXT = "text"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    DONE = "done"


@dataclass
class AgentMessage:
    """Agent 消息"""

    type: MessageType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
        }


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    data: Any
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "data": self.data, "error": self.error}


class BaseAgent(ABC):
    """
    Agent 基类

    所有具体 Agent 的父类，提供:
    - 配置加载
    - 技能加载
    - 工具注册
    - 任务执行
    - 流式输出
    """

    def __init__(self, agent_id: str, agent_config: Optional[Dict[str, Any]] = None):
        """
        初始化 Agent

        Args:
            agent_id: Agent ID (如 "ad_creator")
            agent_config: 手动传入的配置，为空则从文件加载
        """
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"agent.{agent_id}")

        # 加载配置
        if agent_config:
            self._config = agent_config
        else:
            self._config = config.load_agent(agent_id)
            if not self._config:
                raise ValueError(f"Agent config not found: {agent_id}")

        # Agent 属性
        self.name = self._config.get("name", agent_id)
        self.description = self._config.get("description", "")
        self.model = self._config.get("model", "ernie-4.0-8k")
        self.role = self._config.get("role", "")
        self.timeout = self._config.get("timeout", 60)

        # 状态
        self.state = AgentState.IDLE
        self._context: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []

        # 工具注册表
        self._tools: Dict[str, Callable] = {}
        self._tool_configs: Dict[str, Dict[str, Any]] = {}

        # 加载工具配置
        self._load_tool_configs()

        # 注册内置工具
        self._register_builtin_tools()

        self.logger.info(f"Agent initialized: {self.name} ({agent_id})")

    def _load_tool_configs(self) -> None:
        """加载工具配置"""
        tool_ids = self._config.get("tools", [])
        all_tools = config.load_tools()

        for tool_id in tool_ids:
            if tool_id in all_tools:
                self._tool_configs[tool_id] = all_tools[tool_id]
            else:
                self.logger.warning(f"Tool config not found: {tool_id}")

    def _register_builtin_tools(self) -> None:
        """注册内置工具"""
        # 注册数据库查询工具
        self.register_tool("db_query", self._tool_db_query)
        self.register_tool("db_write", self._tool_db_write)

        # 注册文件工具
        self.register_tool("file_read", self._tool_file_read)
        self.register_tool("file_write", self._tool_file_write)

        # 注册浏览器工具
        self.register_tool("browser_navigate", self._tool_browser_navigate)
        self.register_tool("browser_click", self._tool_browser_click)
        self.register_tool("browser_extract", self._tool_browser_extract)

    def register_tool(
        self, name: str, func: Callable, description: Optional[str] = None
    ) -> None:
        """
        注册工具

        Args:
            name: 工具名称
            func: 工具函数
            description: 工具描述
        """
        self._tools[name] = func
        self.logger.debug(f"Tool registered: {name}")

    def get_tool_schema(self) -> List[Dict[str, Any]]:
        """
        获取工具的 JSON Schema（用于 LLM function calling）

        Returns:
            工具 schema 列表
        """
        schemas = []
        for tool_id in self._config.get("tools", []):
            tool_config = self._tool_configs.get(tool_id, {})
            params = tool_config.get("parameters", {})

            schema = {
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": tool_config.get("description", ""),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }

            # 构建参数 schema
            for param_name, param_config in params.items():
                if isinstance(param_config, dict):
                    prop = {
                        "type": param_config.get("type", "string"),
                        "description": param_config.get("description", ""),
                    }
                    schema["function"]["parameters"]["properties"][param_name] = prop

                    if param_config.get("required"):
                        schema["function"]["parameters"]["required"].append(param_name)

            schemas.append(schema)

        return schemas

    def load_skill(self, skill_id: str) -> str:
        """
        加载技能文件内容

        Args:
            skill_id: 技能 ID

        Returns:
            技能文件内容
        """
        try:
            return config.load_skill_content(skill_id)
        except Exception as e:
            self.logger.error(f"Failed to load skill {skill_id}: {e}")
            raise

    def get_system_prompt(self) -> str:
        """
        获取系统提示词

        Returns:
            系统提示词
        """
        prompt_parts = [f"# 角色定义\n\n{self.role}", f"\n# 可用工具\n"]

        # 添加工具说明
        for tool_id in self._config.get("tools", []):
            tool_config = self._tool_configs.get(tool_id, {})
            prompt_parts.append(f"\n## {tool_id}\n{tool_config.get('description', '')}")

            params = tool_config.get("parameters", {})
            if params:
                prompt_parts.append("\n参数:")
                for param_name, param_config in params.items():
                    if isinstance(param_config, dict):
                        desc = param_config.get("description", "")
                        prompt_parts.append(f"  - {param_name}: {desc}")

        # 加载技能
        for skill_id in self._config.get("skills", []):
            try:
                skill_content = self.load_skill(skill_id)
                prompt_parts.append(f"\n\n# 技能: {skill_id}\n\n{skill_content}")
            except Exception as e:
                self.logger.warning(f"Could not load skill {skill_id}: {e}")

        return "\n".join(prompt_parts)

    def set_context(self, key: str, value: Any) -> None:
        """设置上下文"""
        self._context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self._context.get(key, default)

    def add_to_history(self, role: str, content: str) -> None:
        """添加到历史记录"""
        self._history.append({"role": role, "content": content})

    def clear_history(self) -> None:
        """清空历史记录"""
        self._history.clear()

    async def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            tool_name: 工具名称
            **kwargs: 工具参数

        Returns:
            工具执行结果
        """
        if tool_name not in self._tools:
            return ToolResult(
                success=False, data=None, error=f"Tool not found: {tool_name}"
            )

        try:
            self.logger.info(f"Executing tool: {tool_name} with args: {kwargs}")
            result = await self._tools[tool_name](**kwargs)

            if isinstance(result, ToolResult):
                return result

            return ToolResult(success=True, data=result)

        except Exception as e:
            self.logger.error(f"Tool execution failed: {tool_name} - {e}")
            return ToolResult(success=False, data=None, error=str(e))

    @abstractmethod
    async def execute(
        self, task: str, context: Optional[Dict[str, Any]] = None, stream: bool = True
    ) -> Union[str, Generator[AgentMessage, None, None]]:
        """
        执行任务（抽象方法，由子类实现）

        Args:
            task: 任务描述
            context: 执行上下文
            stream: 是否流式输出

        Returns:
            执行结果或消息流
        """
        pass

    # ========== 内置工具实现 ==========

    async def _tool_db_query(self, sql: str) -> ToolResult:
        """数据库查询工具"""
        import pymysql

        db_config = config.get_database_config()

        try:
            conn = pymysql.connect(
                host=db_config["host"],
                port=db_config["port"],
                user=db_config["user"],
                password=db_config["password"],
                database=db_config["database"],
                charset="utf8mb4",
            )

            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()

            conn.close()
            return ToolResult(success=True, data=list(results))

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    async def _tool_db_write(
        self,
        table: str,
        data: Dict[str, Any],
        mode: str = "insert",
        where: Optional[str] = None,
    ) -> ToolResult:
        """数据库写入工具"""
        import pymysql

        db_config = config.get_database_config()

        try:
            conn = pymysql.connect(
                host=db_config["host"],
                port=db_config["port"],
                user=db_config["user"],
                password=db_config["password"],
                database=db_config["database"],
                charset="utf8mb4",
            )

            with conn.cursor() as cursor:
                if mode == "insert":
                    columns = ", ".join(data.keys())
                    placeholders = ", ".join(["%s"] * len(data))
                    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
                    cursor.execute(sql, list(data.values()))

                elif mode == "update" and where:
                    set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
                    sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
                    cursor.execute(sql, list(data.values()))

                elif mode == "upsert":
                    columns = ", ".join(data.keys())
                    placeholders = ", ".join(["%s"] * len(data))
                    update_clause = ", ".join([f"{k}=VALUES({k})" for k in data.keys()])
                    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
                    cursor.execute(sql, list(data.values()))

                conn.commit()
                affected = cursor.rowcount
                insert_id = cursor.lastrowid

            conn.close()
            return ToolResult(
                success=True, data={"affected_rows": affected, "insert_id": insert_id}
            )

        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    async def _tool_file_read(self, path: str, encoding: str = "utf-8") -> ToolResult:
        """读取文件工具"""
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return ToolResult(success=True, data=content)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    async def _tool_file_write(
        self, path: str, content: str, mode: str = "write", encoding: str = "utf-8"
    ) -> ToolResult:
        """写入文件工具"""
        try:
            write_mode = "w" if mode == "write" else "a"
            with open(path, write_mode, encoding=encoding) as f:
                f.write(content)
            return ToolResult(success=True, data=True)
        except Exception as e:
            return ToolResult(success=False, data=None, error=str(e))

    async def _tool_browser_navigate(
        self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30
    ) -> ToolResult:
        """浏览器导航工具（占位实现）"""
        # 实际实现需要 Playwright 或 Selenium
        self.logger.info(f"Browser navigate to: {url}")
        return ToolResult(success=True, data={"url": url, "status": "navigated"})

    async def _tool_browser_click(
        self, selector: str, timeout: int = 5000
    ) -> ToolResult:
        """浏览器点击工具（占位实现）"""
        self.logger.info(f"Browser click: {selector}")
        return ToolResult(success=True, data=True)

    async def _tool_browser_extract(
        self, selectors: Dict[str, str], multiple: bool = False
    ) -> ToolResult:
        """浏览器数据提取工具（占位实现）"""
        self.logger.info(f"Browser extract: {selectors}")
        return ToolResult(success=True, data={})

    def __repr__(self) -> str:
        return f"Agent({self.agent_id}, name={self.name}, state={self.state.value})"


def create_agent(agent_id: str, **kwargs) -> BaseAgent:
    """
    工厂函数：创建 Agent 实例

    Args:
        agent_id: Agent ID
        **kwargs: 额外参数

    Returns:
        Agent 实例
    """
    from .orchestrator import OrchestratorAgent
    from .ad_agent import AdAgent
    from .scrape_agent import ScrapeAgent
    from .analysis_agent import AnalysisAgent

    agent_classes = {
        "orchestrator": OrchestratorAgent,
        "ad_creator": AdAgent,
        "scraper": ScrapeAgent,
        "analyst": AnalysisAgent,
    }

    agent_class = agent_classes.get(agent_id)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_id}")

    return agent_class(agent_id=agent_id, **kwargs)
