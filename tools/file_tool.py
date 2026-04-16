# -*- coding: utf-8 -*-
"""
tools/file_tool.py
==================
文件工具

功能:
- file_read: 读取文件
- file_write: 写入文件
- 文件操作安全检查
- 编码处理
"""

import logging
import os
import json
import shutil
from typing import Dict, Any, Optional, Union
from pathlib import Path

from .base_tool import (
    BaseTool,
    ToolConfig,
    ToolResult,
    ToolError,
    ValidationError,
    ExecutionError,
)


logger = logging.getLogger(__name__)


# 允许的基础路径（安全限制）
ALLOWED_BASE_PATHS = [
    os.getcwd(),  # 当前工作目录
    os.path.expanduser("~"),  # 用户目录
    os.environ.get("TEMP", "/tmp"),  # 临时目录
]


def is_path_allowed(path: str) -> bool:
    """
    检查路径是否被允许访问

    Args:
        path: 要检查的路径

    Returns:
        是否允许
    """
    abs_path = os.path.abspath(path)

    for base_path in ALLOWED_BASE_PATHS:
        if abs_path.startswith(os.path.abspath(base_path)):
            return True

    return False


def validate_path(
    path: str, must_exist: bool = False, allow_create: bool = False
) -> Path:
    """
    验证路径

    Args:
        path: 文件路径
        must_exist: 是否必须存在
        allow_create: 是否允许创建

    Returns:
        Path 对象

    Raises:
        ValidationError: 路径验证失败
    """
    if not path:
        raise ValidationError("file", "Path is required")

    path_obj = Path(path)

    # 安全检查
    if not is_path_allowed(path):
        raise ValidationError(
            "file", f"Access denied: path '{path}' is not in allowed directories"
        )

    # 存在性检查
    if must_exist and not path_obj.exists():
        raise ValidationError("file", f"File not found: {path}")

    # 父目录检查
    if allow_create and not path_obj.parent.exists():
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    return path_obj


class FileReadTool(BaseTool):
    """
    文件读取工具

    读取文件内容
    """

    def __init__(self, config: ToolConfig = None):
        if config is None:
            config = ToolConfig(
                id="file_read",
                name="读取文件",
                type="file",
                description="读取文件内容",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                        "required": True,
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码",
                        "default": "utf-8",
                    },
                    "mode": {
                        "type": "string",
                        "description": "读取模式",
                        "enum": ["text", "json", "lines", "binary"],
                        "default": "text",
                    },
                },
                returns={"type": "string", "description": "文件内容"},
                timeout=10,
                safe=True,
            )

        super().__init__(config)

    def execute(self, params: Dict[str, Any]) -> Union[str, bytes, list, dict]:
        """
        执行文件读取

        Args:
            params: {
                "path": "/path/to/file.txt",
                "encoding": "utf-8",
                "mode": "text" | "json" | "lines" | "binary"
            }

        Returns:
            文件内容
        """
        path = params.get("path")
        encoding = params.get("encoding", "utf-8")
        mode = params.get("mode", "text")

        path_obj = validate_path(path, must_exist=True)

        try:
            if mode == "binary":
                return path_obj.read_bytes()

            if mode == "json":
                content = path_obj.read_text(encoding=encoding)
                return json.loads(content)

            if mode == "lines":
                return path_obj.read_text(encoding=encoding).splitlines()

            # 默认文本模式
            return path_obj.read_text(encoding=encoding)

        except UnicodeDecodeError as e:
            raise ExecutionError(
                self.config.id,
                f"Failed to decode file with encoding '{encoding}': {e}",
                e,
            )

        except json.JSONDecodeError as e:
            raise ExecutionError(self.config.id, f"Failed to parse JSON: {e}", e)

        except IOError as e:
            raise ExecutionError(self.config.id, f"Failed to read file: {e}", e)


class FileWriteTool(BaseTool):
    """
    文件写入工具

    写入内容到文件
    """

    def __init__(self, config: ToolConfig = None):
        if config is None:
            config = ToolConfig(
                id="file_write",
                name="写入文件",
                type="file",
                description="写入内容到文件",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "文件路径",
                        "required": True,
                    },
                    "content": {
                        "type": "string",
                        "description": "文件内容",
                        "required": True,
                    },
                    "mode": {
                        "type": "string",
                        "description": "写入模式",
                        "enum": ["write", "append"],
                        "default": "write",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码",
                        "default": "utf-8",
                    },
                    "format": {
                        "type": "string",
                        "description": "内容格式",
                        "enum": ["text", "json"],
                        "default": "text",
                    },
                },
                returns={"type": "boolean", "description": "是否成功"},
                timeout=10,
                safe=False,
            )

        super().__init__(config)

    def execute(self, params: Dict[str, Any]) -> bool:
        """
        执行文件写入

        Args:
            params: {
                "path": "/path/to/file.txt",
                "content": "Hello, World!",
                "mode": "write" | "append",
                "encoding": "utf-8",
                "format": "text" | "json"
            }

        Returns:
            是否成功
        """
        path = params.get("path")
        content = params.get("content")
        mode = params.get("mode", "write")
        encoding = params.get("encoding", "utf-8")
        format_type = params.get("format", "text")

        if content is None:
            raise ValidationError(self.config.id, "Content is required")

        path_obj = validate_path(path, allow_create=True)

        try:
            # 处理 JSON 格式
            if format_type == "json" and isinstance(content, (dict, list)):
                content = json.dumps(content, ensure_ascii=False, indent=2)

            # 处理列表格式（多行）
            if isinstance(content, list):
                content = "\n".join(str(item) for item in content)

            # 确保内容是字符串
            if not isinstance(content, str):
                content = str(content)

            # 写入模式
            write_mode = "a" if mode == "append" else "w"

            with open(path_obj, write_mode, encoding=encoding) as f:
                f.write(content)

                # 确保以换行结尾
                if not content.endswith("\n"):
                    f.write("\n")

            return True

        except IOError as e:
            raise ExecutionError(self.config.id, f"Failed to write file: {e}", e)


class FileDeleteTool(BaseTool):
    """
    文件删除工具

    删除文件或目录
    """

    def __init__(self, config: ToolConfig = None):
        if config is None:
            config = ToolConfig(
                id="file_delete",
                name="删除文件",
                type="file",
                description="删除文件或目录",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "文件或目录路径",
                        "required": True,
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归删除目录",
                        "default": False,
                    },
                },
                returns={"type": "boolean", "description": "是否成功"},
                timeout=10,
                safe=False,
            )

        super().__init__(config)

    def execute(self, params: Dict[str, Any]) -> bool:
        path = params.get("path")
        recursive = params.get("recursive", False)

        path_obj = validate_path(path, must_exist=True)

        try:
            if path_obj.is_file():
                path_obj.unlink()
            elif path_obj.is_dir():
                if recursive:
                    shutil.rmtree(path_obj)
                else:
                    path_obj.rmdir()  # 只能删除空目录

            return True

        except IOError as e:
            raise ExecutionError(self.config.id, f"Failed to delete: {e}", e)


class FileListTool(BaseTool):
    """
    文件列表工具

    列出目录内容
    """

    def __init__(self, config: ToolConfig = None):
        if config is None:
            config = ToolConfig(
                id="file_list",
                name="列出文件",
                type="file",
                description="列出目录内容",
                parameters={
                    "path": {
                        "type": "string",
                        "description": "目录路径",
                        "required": True,
                    },
                    "pattern": {
                        "type": "string",
                        "description": "文件匹配模式 (glob)",
                        "default": "*",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "是否递归列出",
                        "default": False,
                    },
                },
                returns={"type": "array", "description": "文件列表"},
                timeout=10,
                safe=True,
            )

        super().__init__(config)

    def execute(self, params: Dict[str, Any]) -> list:
        path = params.get("path")
        pattern = params.get("pattern", "*")
        recursive = params.get("recursive", False)

        path_obj = validate_path(path, must_exist=True)

        if not path_obj.is_dir():
            raise ValidationError(self.config.id, f"Path is not a directory: {path}")

        try:
            if recursive:
                items = list(path_obj.rglob(pattern))
            else:
                items = list(path_obj.glob(pattern))

            result = []
            for item in items:
                result.append(
                    {
                        "name": item.name,
                        "path": str(item),
                        "is_file": item.is_file(),
                        "is_dir": item.is_dir(),
                        "size": item.stat().st_size if item.is_file() else None,
                    }
                )

            return result

        except IOError as e:
            raise ExecutionError(self.config.id, f"Failed to list directory: {e}", e)


# 便捷函数
def file_read(
    path: str, encoding: str = "utf-8", mode: str = "text"
) -> Union[str, bytes, list, dict]:
    """
    快捷文件读取

    Args:
        path: 文件路径
        encoding: 文件编码
        mode: 读取模式

    Returns:
        文件内容
    """
    tool = FileReadTool()
    result = tool.run({"path": path, "encoding": encoding, "mode": mode})
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("file_read", "Unknown error")
        )
    return result.data


def file_write(
    path: str,
    content: Union[str, dict, list],
    mode: str = "write",
    encoding: str = "utf-8",
    format_type: str = "text",
) -> bool:
    """
    快捷文件写入

    Args:
        path: 文件路径
        content: 内容
        mode: 写入模式
        encoding: 编码
        format_type: 格式

    Returns:
        是否成功
    """
    tool = FileWriteTool()
    result = tool.run(
        {
            "path": path,
            "content": content,
            "mode": mode,
            "encoding": encoding,
            "format": format_type,
        }
    )
    return result.success


def file_delete(path: str, recursive: bool = False) -> bool:
    """
    快捷文件删除

    Args:
        path: 文件路径
        recursive: 是否递归删除

    Returns:
        是否成功
    """
    tool = FileDeleteTool()
    result = tool.run({"path": path, "recursive": recursive})
    return result.success


def file_list(path: str, pattern: str = "*", recursive: bool = False) -> list:
    """
    快捷文件列表

    Args:
        path: 目录路径
        pattern: 匹配模式
        recursive: 是否递归

    Returns:
        文件列表
    """
    tool = FileListTool()
    result = tool.run({"path": path, "pattern": pattern, "recursive": recursive})
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("file_list", "Unknown error")
        )
    return result.data
