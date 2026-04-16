# -*- coding: utf-8 -*-
"""
tools/http_tool.py
==================
HTTP 工具

功能:
- http_request: 发送 HTTP 请求
- 支持 GET/POST/PUT/DELETE/PATCH
- 超时控制
- 重试机制
"""

import logging
import json
import time
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base_tool import (
    BaseTool,
    ToolConfig,
    ToolResult,
    ToolError,
    ValidationError,
    ExecutionError,
)


logger = logging.getLogger(__name__)


@dataclass
class HttpResponse:
    """HTTP 响应"""

    status: int
    headers: Dict[str, str]
    body: Any
    elapsed: float  # 响应时间(秒)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "headers": dict(self.headers),
            "body": self.body,
            "elapsed": self.elapsed,
        }

    @property
    def ok(self) -> bool:
        """是否成功 (2xx 状态码)"""
        return 200 <= self.status < 300

    def json(self) -> Any:
        """获取 JSON 响应体"""
        if isinstance(self.body, (dict, list)):
            return self.body
        return json.loads(self.body)


class HttpSession:
    """
    HTTP 会话

    支持连接池、重试、Cookie 管理
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required for HTTP operations. Run: pip install requests"
            )

        self._session = requests.Session()

        # 配置重试
        retry = Retry(
            total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        self._initialized = True

    def request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str] = None,
        params: Dict[str, Any] = None,
        body: Any = None,
        timeout: int = 30,
        **kwargs,
    ) -> HttpResponse:
        """
        发送请求

        Args:
            method: HTTP 方法
            url: URL
            headers: 请求头
            params: URL 参数
            body: 请求体
            timeout: 超时时间(秒)

        Returns:
            HttpResponse
        """
        start_time = time.time()

        try:
            # 准备请求体
            json_body = None
            data_body = None

            if body is not None:
                if isinstance(body, (dict, list)):
                    json_body = body
                else:
                    data_body = body

            response = self._session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                data=data_body,
                timeout=timeout,
                **kwargs,
            )

            elapsed = time.time() - start_time

            # 解析响应体
            try:
                response_body = response.json()
            except (json.JSONDecodeError, ValueError):
                response_body = response.text

            return HttpResponse(
                status=response.status_code,
                headers=dict(response.headers),
                body=response_body,
                elapsed=elapsed,
            )

        except requests.Timeout:
            raise ExecutionError(
                "http_request", f"Request timed out after {timeout} seconds"
            )

        except requests.RequestException as e:
            raise ExecutionError("http_request", f"Request failed: {e}", e)

    def get(self, url: str, **kwargs) -> HttpResponse:
        """GET 请求"""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> HttpResponse:
        """POST 请求"""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> HttpResponse:
        """PUT 请求"""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> HttpResponse:
        """DELETE 请求"""
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs) -> HttpResponse:
        """PATCH 请求"""
        return self.request("PATCH", url, **kwargs)

    def set_default_headers(self, headers: Dict[str, str]):
        """设置默认请求头"""
        self._session.headers.update(headers)

    def set_auth(self, auth: tuple):
        """设置认证信息"""
        self._session.auth = auth

    def close(self):
        """关闭会话"""
        self._session.close()


# 全局会话
_http_session: Optional[HttpSession] = None


def get_http_session() -> HttpSession:
    """获取 HTTP 会话"""
    global _http_session
    if _http_session is None:
        _http_session = HttpSession()
    return _http_session


class HttpRequestTool(BaseTool):
    """
    HTTP 请求工具

    发送 HTTP 请求
    """

    def __init__(self, config: ToolConfig = None):
        if config is None:
            config = ToolConfig(
                id="http_request",
                name="HTTP 请求",
                type="http",
                description="发送 HTTP 请求",
                parameters={
                    "method": {
                        "type": "string",
                        "description": "请求方法",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                        "default": "GET",
                    },
                    "url": {
                        "type": "string",
                        "description": "目标 URL",
                        "required": True,
                    },
                    "headers": {
                        "type": "object",
                        "description": "请求头",
                        "default": {},
                    },
                    "body": {"type": "object", "description": "请求体 (JSON)"},
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间(秒)",
                        "default": 30,
                    },
                },
                returns={
                    "type": "object",
                    "description": "响应对象，包含 status, headers, body",
                },
                timeout=60,
                error_handling="raise",
            )

        super().__init__(config)
        self._session = get_http_session()

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 HTTP 请求

        Args:
            params: {
                "method": "GET",
                "url": "https://api.example.com/data",
                "headers": {"Authorization": "Bearer token"},
                "body": {"key": "value"},
                "timeout": 30
            }

        Returns:
            {"status": 200, "headers": {...}, "body": {...}, "elapsed": 0.5}
        """
        method = params.get("method", "GET").upper()
        url = params.get("url")
        headers = params.get("headers", {})
        body = params.get("body")
        timeout = params.get("timeout", 30)

        if not url:
            raise ValidationError(self.config.id, "URL is required")

        # URL 格式验证
        if not url.startswith(("http://", "https://")):
            raise ValidationError(
                self.config.id, "URL must start with http:// or https://"
            )

        response = self._session.request(
            method=method, url=url, headers=headers, body=body, timeout=timeout
        )

        return response.to_dict()


# 便捷函数
def http_get(
    url: str, headers: Dict[str, str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    快捷 GET 请求

    Args:
        url: 目标 URL
        headers: 请求头
        timeout: 超时时间

    Returns:
        响应字典
    """
    tool = HttpRequestTool()
    result = tool.run(
        {"method": "GET", "url": url, "headers": headers or {}, "timeout": timeout}
    )
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("http_get", "Unknown error")
        )
    return result.data


def http_post(
    url: str, body: Any = None, headers: Dict[str, str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    快捷 POST 请求

    Args:
        url: 目标 URL
        body: 请求体
        headers: 请求头
        timeout: 超时时间

    Returns:
        响应字典
    """
    tool = HttpRequestTool()
    result = tool.run(
        {
            "method": "POST",
            "url": url,
            "headers": headers or {},
            "body": body,
            "timeout": timeout,
        }
    )
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("http_post", "Unknown error")
        )
    return result.data


def http_put(
    url: str, body: Any = None, headers: Dict[str, str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    快捷 PUT 请求
    """
    tool = HttpRequestTool()
    result = tool.run(
        {
            "method": "PUT",
            "url": url,
            "headers": headers or {},
            "body": body,
            "timeout": timeout,
        }
    )
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("http_put", "Unknown error")
        )
    return result.data


def http_delete(
    url: str, headers: Dict[str, str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    快捷 DELETE 请求
    """
    tool = HttpRequestTool()
    result = tool.run(
        {"method": "DELETE", "url": url, "headers": headers or {}, "timeout": timeout}
    )
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("http_delete", "Unknown error")
        )
    return result.data


def http_patch(
    url: str, body: Any = None, headers: Dict[str, str] = None, timeout: int = 30
) -> Dict[str, Any]:
    """
    快捷 PATCH 请求
    """
    tool = HttpRequestTool()
    result = tool.run(
        {
            "method": "PATCH",
            "url": url,
            "headers": headers or {},
            "body": body,
            "timeout": timeout,
        }
    )
    if not result.success:
        raise (
            result.error
            if result.error
            else ExecutionError("http_patch", "Unknown error")
        )
    return result.data
