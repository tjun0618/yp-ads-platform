# -*- coding: utf-8 -*-
"""
tools/base_tool.py
==================
工具基类

功能:
- 定义工具接口
- 参数验证
- 错误处理
- 超时控制
- 执行日志
"""

import time
import functools
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class ToolError(Exception):
    """工具执行错误"""

    def __init__(self, tool_id: str, message: str, cause: Exception = None):
        self.tool_id = tool_id
        self.message = message
        self.cause = cause
        super().__init__(f"[{tool_id}] {message}")

    def __str__(self) -> str:
        if self.cause:
            return f"[{self.tool_id}] {self.message}: {self.cause}"
        return f"[{self.tool_id}] {self.message}"


class ValidationError(ToolError):
    """参数验证错误"""

    pass


class TimeoutError(ToolError):
    """超时错误"""

    pass


class ExecutionError(ToolError):
    """执行错误"""

    pass


class ErrorHandling(Enum):
    """错误处理策略"""

    RAISE = "raise"  # 抛出异常
    RETURN = "return"  # 返回错误信息
    IGNORE = "ignore"  # 忽略错误


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class ToolConfig:
    """工具配置"""

    id: str
    name: str
    type: str
    description: str
    parameters: Dict[str, Any]
    returns: Dict[str, Any]
    timeout: int = 30
    safe: bool = True
    error_handling: ErrorHandling = ErrorHandling.RAISE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolConfig":
        """从字典创建配置"""
        error_handling = data.get("error_handling", "raise")
        if isinstance(error_handling, str):
            error_handling = ErrorHandling(error_handling)

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters", {}),
            returns=data.get("returns", {}),
            timeout=data.get("timeout", 30),
            safe=data.get("safe", True),
            error_handling=error_handling,
        )


class BaseTool(ABC):
    """
    工具基类

    所有工具必须继承此类并实现 execute 方法
    """

    def __init__(self, config: ToolConfig):
        self.config = config
        self.logger = logging.getLogger(f"tool.{config.id}")
        self._validate_config()

    def _validate_config(self):
        """验证配置"""
        if not self.config.id:
            raise ValueError("Tool ID is required")
        if not self.config.name:
            raise ValueError("Tool name is required")

    def validate_parameters(self, params: Dict[str, Any]) -> None:
        """
        验证参数

        Args:
            params: 参数字典

        Raises:
            ValidationError: 参数验证失败
        """
        param_schema = self.config.parameters

        for param_name, schema in param_schema.items():
            if schema.get("required", False) and param_name not in params:
                raise ValidationError(
                    self.config.id, f"Required parameter missing: {param_name}"
                )

            if param_name in params:
                value = params[param_name]
                expected_type = schema.get("type")

                if expected_type and not self._check_type(value, expected_type):
                    raise ValidationError(
                        self.config.id,
                        f"Parameter '{param_name}' expected type '{expected_type}', got '{type(value).__name__}'",
                    )

                # 检查 enum
                enum_values = schema.get("enum")
                if enum_values and value not in enum_values:
                    raise ValidationError(
                        self.config.id,
                        f"Parameter '{param_name}' must be one of {enum_values}, got '{value}'",
                    )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型"""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_mapping.get(expected_type)
        if expected is None:
            return True  # 未知类型，跳过检查

        return isinstance(value, expected)

    def run(self, params: Dict[str, Any]) -> ToolResult:
        """
        运行工具

        包含完整的参数验证、超时控制、错误处理

        Args:
            params: 参数字典

        Returns:
            ToolResult 执行结果
        """
        start_time = time.time()

        try:
            # 参数验证
            self.validate_parameters(params)

            # 应用默认值
            params = self._apply_defaults(params)

            # 执行
            result = self.execute(params)

            execution_time = time.time() - start_time

            return ToolResult(
                success=True,
                data=result,
                execution_time=execution_time,
                metadata={"tool_id": self.config.id},
            )

        except ValidationError as e:
            return self._handle_error(e, start_time)

        except Exception as e:
            return self._handle_error(e, start_time)

    def _apply_defaults(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """应用默认参数值"""
        result = params.copy()

        for param_name, schema in self.config.parameters.items():
            if param_name not in result and "default" in schema:
                result[param_name] = schema["default"]

        return result

    def _handle_error(self, error: Exception, start_time: float) -> ToolResult:
        """处理错误"""
        execution_time = time.time() - start_time

        self.logger.error(f"Tool {self.config.id} failed: {error}")

        if self.config.error_handling == ErrorHandling.RAISE:
            if isinstance(error, ToolError):
                raise error
            raise ExecutionError(self.config.id, str(error), error)

        return ToolResult(
            success=False,
            error=str(error),
            execution_time=execution_time,
            metadata={"tool_id": self.config.id, "error_type": type(error).__name__},
        )

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行工具逻辑

        子类必须实现此方法

        Args:
            params: 参数字典

        Returns:
            执行结果
        """
        pass

    def __repr__(self) -> str:
        return f"<Tool:{self.config.id} name='{self.config.name}'>"


def timeout(seconds: int):
    """
    超时装饰器

    Usage:
        @timeout(30)
        def my_function():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError(
                    "unknown", f"Execution timed out after {seconds} seconds"
                )

            # Windows 不支持 SIGALRM，使用简单实现
            import platform

            if platform.system() == "Windows":
                return func(*args, **kwargs)

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)

            try:
                result = func(*args, **kwargs)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        return wrapper

    return decorator


def tool_registry():
    """
    工具注册表装饰器

    Usage:
        @tool_registry()
        class MyTool(BaseTool):
            ...
    """
    _registry: Dict[str, type] = {}

    def decorator(cls):
        _registry[cls.__name__] = cls
        return cls

    decorator._registry = _registry

    return decorator
