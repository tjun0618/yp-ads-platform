# -*- coding: utf-8 -*-
"""
tools/browser.py
================
浏览器工具

功能:
- browser_navigate: 打开网页
- browser_click: 点击元素
- browser_extract: 提取数据
- browser_screenshot: 截图
- 连接调试模式 Chrome (CDP)
"""

import logging
import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from .base_tool import (
    BaseTool, ToolConfig, ToolResult, ToolError,
    ValidationError, ExecutionError
)


logger = logging.getLogger(__name__)


# 默认 Chrome 调试端口
DEFAULT_CDP_URL = "http://localhost:9222"


class BrowserManager:
    """
    浏览器管理器
    
    管理与调试 Chrome 的连接
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self._initialized = True
    
    async def connect(self, cdp_url: str = DEFAULT_CDP_URL) -> Browser:
        """
        连接到调试 Chrome
        
        Args:
            cdp_url: Chrome DevTools Protocol URL
        
        Returns:
            Browser 实例
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("playwright is required for browser operations. Run: pip install playwright && playwright install chromium")
        
        if self._browser is not None:
            return self._browser
        
        self._playwright = await async_playwright().start()
        
        try:
            # 连接到现有 Chrome 实例
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            logger.info(f"Connected to Chrome at {cdp_url}")
            
            # 获取或创建上下文
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = await self._browser.new_context()
            
            # 获取或创建页面
            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()
            
            return self._browser
        
        except Exception as e:
            logger.error(f"Failed to connect to Chrome: {e}")
            raise ExecutionError(
                "browser",
                f"Failed to connect to Chrome at {cdp_url}. Make sure Chrome is running with --remote-debugging-port=9222",
                e
            )
    
    async def get_page(self) -> Page:
        """获取当前页面"""
        if self._page is None:
            await self.connect()
        return self._page
    
    async def new_page(self) -> Page:
        """创建新页面"""
        if self._context is None:
            await self.connect()
        self._page = await self._context.new_page()
        return self._page
    
    async def close(self):
        """关闭连接"""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None


# 全局浏览器管理器
_browser_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """获取浏览器管理器"""
    global _browser_manager
    if _browser_manager is None:
        _browser_manager = BrowserManager()
    return _browser_manager


def run_async(coro):
    """运行异步函数"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果在异步环境中，使用 nest_asyncio
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class BrowserNavigateTool(BaseTool):
    """
    浏览器导航工具
    
    打开指定 URL
    """
    
    def __init__(self, config: ToolConfig = None, cdp_url: str = DEFAULT_CDP_URL):
        if config is None:
            config = ToolConfig(
                id="browser_navigate",
                name="打开网页",
                type="browser",
                description="使用浏览器打开指定 URL",
                parameters={
                    "url": {
                        "type": "string",
                        "description": "目标 URL",
                        "required": True
                    },
                    "wait_until": {
                        "type": "string",
                        "description": "等待条件",
                        "enum": ["load", "domcontentloaded", "networkidle"],
                        "default": "domcontentloaded"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "超时时间(秒)",
                        "default": 30
                    }
                },
                returns={
                    "type": "object",
                    "description": "页面信息，包含 url, title"
                },
                timeout=60,
                safe=True
            )
        
        super().__init__(config)
        self.cdp_url = cdp_url
        self._manager = get_browser_manager()
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行导航
        
        Args:
            params: {
                "url": "https://example.com",
                "wait_until": "domcontentloaded",
                "timeout": 30
            }
        
        Returns:
            {"url": "...", "title": "..."}
        """
        return run_async(self._execute_async(params))
    
    async def _execute_async(self, params: Dict[str, Any]) -> Dict[str, Any]:
        url = params.get("url")
        wait_until = params.get("wait_until", "domcontentloaded")
        timeout = params.get("timeout", 30) * 1000  # 转为毫秒
        
        if not url:
            raise ValidationError(self.config.id, "URL is required")
        
        try:
            await self._manager.connect(self.cdp_url)
            page = await self._manager.get_page()
            
            response = await page.goto(url, wait_until=wait_until, timeout=timeout)
            
            return {
                "url": page.url,
                "title": await page.title(),
                "status": response.status if response else None
            }
        
        except Exception as e:
            raise ExecutionError(
                self.config.id,
                f"Navigation failed: {e}",
                e
            )


class BrowserClickTool(BaseTool):
    """
    浏览器点击工具
    
    点击页面元素
    """
    
    def __init__(self, config: ToolConfig = None, cdp_url: str = DEFAULT_CDP_URL):
        if config is None:
            config = ToolConfig(
                id="browser_click",
                name="点击元素",
                type="browser",
                description="点击页面上的元素",
                parameters={
                    "selector": {
                        "type": "string",
                        "description": "CSS 选择器",
                        "required": True
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "等待元素超时(毫秒)",
                        "default": 5000
                    }
                },
                returns={
                    "type": "boolean",
                    "description": "是否点击成功"
                },
                timeout=10,
                safe=True
            )
        
        super().__init__(config)
        self.cdp_url = cdp_url
        self._manager = get_browser_manager()
    
    def execute(self, params: Dict[str, Any]) -> bool:
        return run_async(self._execute_async(params))
    
    async def _execute_async(self, params: Dict[str, Any]) -> bool:
        selector = params.get("selector")
        timeout = params.get("timeout", 5000)
        
        if not selector:
            raise ValidationError(self.config.id, "Selector is required")
        
        try:
            page = await self._manager.get_page()
            
            # 等待元素出现
            await page.wait_for_selector(selector, timeout=timeout)
            
            # 点击
            await page.click(selector)
            
            return True
        
        except Exception as e:
            logger.warning(f"Click failed: {e}")
            return False


class BrowserExtractTool(BaseTool):
    """
    浏览器数据提取工具
    
    从页面提取数据
    """
    
    def __init__(self, config: ToolConfig = None, cdp_url: str = DEFAULT_CDP_URL):
        if config is None:
            config = ToolConfig(
                id="browser_extract",
                name="提取数据",
                type="browser",
                description="从页面提取数据",
                parameters={
                    "selectors": {
                        "type": "object",
                        "description": "字段名 -> CSS选择器映射",
                        "required": True
                    },
                    "multiple": {
                        "type": "boolean",
                        "description": "是否提取多个元素",
                        "default": False
                    }
                },
                returns={
                    "type": "object",
                    "description": "提取的数据对象"
                },
                timeout=10,
                safe=True
            )
        
        super().__init__(config)
        self.cdp_url = cdp_url
        self._manager = get_browser_manager()
    
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return run_async(self._execute_async(params))
    
    async def _execute_async(self, params: Dict[str, Any]) -> Dict[str, Any]:
        selectors = params.get("selectors", {})
        multiple = params.get("multiple", False)
        
        if not selectors:
            raise ValidationError(self.config.id, "Selectors are required")
        
        try:
            page = await self._manager.get_page()
            result = {}
            
            for field_name, selector in selectors.items():
                if multiple:
                    elements = await page.query_selector_all(selector)
                    result[field_name] = [
                        await el.inner_text() for el in elements
                    ]
                else:
                    element = await page.query_selector(selector)
                    if element:
                        result[field_name] = await element.inner_text()
                    else:
                        result[field_name] = None
            
            return result
        
        except Exception as e:
            raise ExecutionError(
                self.config.id,
                f"Extraction failed: {e}",
                e
            )


class BrowserScreenshotTool(BaseTool):
    """
    浏览器截图工具
    
    对当前页面截图
    """
    
    def __init__(self, config: ToolConfig = None, cdp_url: str = DEFAULT_CDP_URL):
        if config is None:
            config = ToolConfig(
                id="browser_screenshot",
                name="截图",
                type="browser",
                description="对当前页面截图",
                parameters={
                    "selector": {
                        "type": "string",
                        "description": "要截图的元素选择器 (可选，默认全页)"
                    },
                    "path": {
                        "type": "string",
                        "description": "截图保存路径",
                        "required": True
                    }
                },
                returns={
                    "type": "string",
                    "description": "截图文件路径"
                },
                timeout=10,
                safe=True
            )
        
        super().__init__(config)
        self.cdp_url = cdp_url
        self._manager = get_browser_manager()
    
    def execute(self, params: Dict[str, Any]) -> str:
        return run_async(self._execute_async(params))
    
    async def _execute_async(self, params: Dict[str, Any]) -> str:
        selector = params.get("selector")
        path = params.get("path")
        
        if not path:
            raise ValidationError(self.config.id, "Path is required")
        
        try:
            page = await self._manager.get_page()
            
            # 确保目录存在
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            
            if selector:
                element = await page.query_selector(selector)
                if element:
                    await element.screenshot(path=path)
                else:
                    raise ExecutionError(
                        self.config.id,
                        f"Element not found: {selector}"
                    )
            else:
                await page.screenshot(path=path, full_page=True)
            
            return path
        
        except Exception as e:
            raise ExecutionError(
                self.config.id,
                f"Screenshot failed: {e}",
                e
            )


# 便捷函数
def browser_navigate(url: str, wait_until: str = "domcontentloaded", timeout: int = 30) -> Dict[str, Any]:
    """
    快捷导航函数
    
    Args:
        url: 目标 URL
        wait_until: 等待条件
        timeout: 超时时间(秒)
    
    Returns:
        页面信息
    """
    tool = BrowserNavigateTool()
    result = tool.run({"url": url, "wait_until": wait_until, "timeout": timeout})
    if not result.success:
        raise result.error if result.error else ExecutionError("browser_navigate", "Unknown error")
    return result.data


def browser_click(selector: str, timeout: int = 5000) -> bool:
    """
    快捷点击函数
    
    Args:
        selector: CSS 选择器
        timeout: 超时时间(毫秒)
    
    Returns:
        是否成功
    """
    tool = BrowserClickTool()
    result = tool.run({"selector": selector, "timeout": timeout})
    return result.success and result.data


def browser_extract(selectors: Dict[str, str], multiple: bool = False) -> Dict[str, Any]:
    """
    快捷提取函数
    
    Args:
        selectors: 字段名 -> 选择器映射
        multiple: 是否提取多个
    
    Returns:
        提取的数据
    """
    tool = BrowserExtractTool()
    result = tool.run({"selectors": selectors, "multiple": multiple})
    if not result.success:
        raise result.error if result.error else ExecutionError("browser_extract", "Unknown error")
    return result.data


def browser_screenshot(path: str, selector: str = None) -> str:
    """
    快捷截图函数
    
    Args:
        path: 保存路径
        selector: 元素选择器(可选)
    
    Returns:
        文件路径
    """
    tool = BrowserScreenshotTool()
    params = {"path": path}
    if selector:
        params["selector"] = selector
    result = tool.run(params)
    if not result.success:
        raise result.error if result.error else ExecutionError("browser_screenshot", "Unknown error")
    return result.data
