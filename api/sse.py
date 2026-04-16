# -*- coding: utf-8 -*-
"""
sse.py
======

Server-Sent Events (SSE) 工具函数，用于流式返回。

使用方式:
    from api.sse import sse_response, sse_progress, sse_error

    def generate():
        yield sse_progress("正在处理...")
        yield sse_progress("完成")
        yield sse_done({"result": "success"})

    return Response(generate(), mimetype="text/event-stream")
"""

import json
import time
from typing import Any, Dict, Generator, Optional, Union


def sse_format(data: Dict[str, Any]) -> str:
    """
    格式化 SSE 数据

    Args:
        data: 要发送的数据字典

    Returns:
        格式化的 SSE 字符串
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def sse_progress(
    text: str,
    step: Optional[int] = None,
    total: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    发送进度消息

    Args:
        text: 进度文本
        step: 当前步骤
        total: 总步骤数
        extra: 额外数据

    Returns:
        SSE 格式的进度消息
    """
    data = {
        "type": "progress",
        "text": text,
        "timestamp": time.time(),
    }
    if step is not None:
        data["step"] = step
    if total is not None:
        data["total"] = total
    if extra:
        data.update(extra)
    return sse_format(data)


def sse_thinking(text: str) -> str:
    """
    发送思考过程消息

    Args:
        text: 思考内容片段

    Returns:
        SSE 格式的思考消息
    """
    return sse_format(
        {
            "type": "thinking",
            "text": text,
            "timestamp": time.time(),
        }
    )


def sse_error(message: str, code: Optional[str] = None) -> str:
    """
    发送错误消息

    Args:
        message: 错误信息
        code: 错误代码

    Returns:
        SSE 格式的错误消息
    """
    data = {
        "type": "error",
        "message": message,
        "timestamp": time.time(),
    }
    if code:
        data["code"] = code
    return sse_format(data)


def sse_done(result: Optional[Dict[str, Any]] = None) -> str:
    """
    发送完成消息

    Args:
        result: 结果数据

    Returns:
        SSE 格式的完成消息
    """
    data = {
        "type": "done",
        "timestamp": time.time(),
    }
    if result:
        data["result"] = result
    return sse_format(data)


def sse_heartbeat() -> str:
    """
    发送心跳消息

    Returns:
        SSE 格式的心跳消息
    """
    return sse_format({"type": "heartbeat", "timestamp": time.time()})


class SSEResponse:
    """
    SSE 响应构建器

    用于链式构建 SSE 响应流。

    Example:
        sse = SSEResponse()
        sse.progress("开始处理")
        sse.progress("步骤 1/3", step=1, total=3)
        sse.thinking("正在思考...")
        sse.done({"result": "success"})

        return Response(sse.build(), mimetype="text/event-stream")
    """

    def __init__(self):
        self._messages: list = []

    def progress(
        self,
        text: str,
        step: Optional[int] = None,
        total: Optional[int] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> "SSEResponse":
        """添加进度消息"""
        self._messages.append(sse_progress(text, step, total, extra))
        return self

    def thinking(self, text: str) -> "SSEResponse":
        """添加思考消息"""
        self._messages.append(sse_thinking(text))
        return self

    def error(self, message: str, code: Optional[str] = None) -> "SSEResponse":
        """添加错误消息"""
        self._messages.append(sse_error(message, code))
        return self

    def done(self, result: Optional[Dict[str, Any]] = None) -> "SSEResponse":
        """添加完成消息"""
        self._messages.append(sse_done(result))
        return self

    def heartbeat(self) -> "SSEResponse":
        """添加心跳消息"""
        self._messages.append(sse_heartbeat())
        return self

    def build(self) -> Generator[str, None, None]:
        """构建生成器"""
        for msg in self._messages:
            yield msg

    def __iter__(self):
        return self.build()


def sse_response(messages: list) -> Generator[str, None, None]:
    """
    从消息列表构建 SSE 响应

    Args:
        messages: 消息列表，每个元素是 (type, data) 元组

    Returns:
        SSE 响应生成器

    Example:
        messages = [
            ("progress", {"text": "开始"}),
            ("thinking", {"text": "思考中..."}),
            ("done", {"result": {"count": 3}}),
        ]
        return Response(sse_response(messages), mimetype="text/event-stream")
    """
    for msg_type, data in messages:
        if msg_type == "progress":
            yield sse_progress(**data)
        elif msg_type == "thinking":
            yield sse_thinking(**data)
        elif msg_type == "error":
            yield sse_error(**data)
        elif msg_type == "done":
            yield sse_done(data.get("result"))
        elif msg_type == "heartbeat":
            yield sse_heartbeat()
        else:
            yield sse_format({"type": msg_type, **data})


# Flask 响应辅助函数
def create_sse_response(generator: Generator[str, None, None]):
    """
    创建 Flask SSE Response 对象

    Args:
        generator: SSE 消息生成器

    Returns:
        Flask Response 对象

    Example:
        from flask import Response
        from api.sse import create_sse_response, SSEResponse

        @app.route("/api/stream")
        def stream():
            sse = SSEResponse()
            sse.progress("开始")
            sse.done({"result": "ok"})
            return create_sse_response(sse.build())
    """
    from flask import Response

    return Response(
        generator,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )
