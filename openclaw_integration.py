# -*- coding: utf-8 -*-
"""
openclaw_integration.py
=======================

OpenClaw 集成模块 - 使用 sessions_spawn 创建子 Agent

这个模块提供了与 OpenClaw 框架的集成，允许 Python 代码通过
sessions_spawn 机制创建和管理子 Agent。

使用方式:
    from openclaw_integration import OpenClawOrchestrator

    orchestrator = OpenClawOrchestrator()

    # 生成广告
    result = await orchestrator.spawn_ad_creator(
        task="为 ASIN B08XYZ123 生成 Google Ads 广告方案"
    )

    # 采集数据
    result = await orchestrator.spawn_scraper(
        task="采集 Amazon 产品 B08XYZ123 的详情",
        sub_type="amazon"
    )

    # 分析数据
    result = await orchestrator.spawn_analyst(
        task="分析商户 M123 的广告效果"
    )
"""

import asyncio
import json
import subprocess
import os
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SpawnResult:
    """子 Agent 执行结果"""

    success: bool
    run_id: str
    session_key: str
    status: str
    result: Optional[str] = None
    error: Optional[str] = None
    runtime_seconds: Optional[float] = None
    tokens_used: Optional[int] = None


class OpenClawClient:
    """OpenClaw Gateway API 客户端"""
    
    def __init__(
        self,
        gateway_url: str = "http://127.0.0.1:18789",
        token: Optional[str] = None
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.token = token or self._load_token()
        self.client = httpx.AsyncClient(timeout=300.0)
        
    def _load_token(self) -> str:
        """从 OpenClaw 配置加载 token"""
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("gateway", {}).get("auth", {}).get("token", "")
        return ""
    
    async def health_check(self) -> bool:
        """检查 Gateway 是否运行"""
        try:
            response = await self.client.get(f"{self.gateway_url}/health")
            return response.status_code == 200
        except Exception:
            return False

    async def spawn_subagent(
        self,
        agent_id: str,
        task: str,
        model: Optional[str] = None,
        timeout_seconds: int = 300,
        label: Optional[str] = None
    ) -> SpawnResult:
        """
        使用 sessions_spawn 创建子 Agent
        
        Args:
            agent_id: 目标 Agent ID (ad_creator, scraper, analyst)
            task: 任务描述
            model: 覆盖默认模型
            timeout_seconds: 超时时间
            label: 任务标签
            
        Returns:
            SpawnResult: 执行结果
        """
        # 使用 CLI 方式调用 OpenClaw
        cli_result = OpenClawCLI.spawn_subagent(
            agent_id=agent_id,
            task=task,
            model=model,
            timeout=timeout_seconds
        )
        
        if cli_result.get("success"):
            return SpawnResult(
                success=True,
                run_id=cli_result.get("run_id", ""),
                session_key=f"agent:{agent_id}:spawned",
                status="completed",
                result=cli_result.get("output")
            )
        else:
            return SpawnResult(
                success=False,
                run_id="",
                session_key="",
                status="error",
                error=cli_result.get("error")
            )

    async def _wait_for_result(self, run_id: str, timeout: int = 300) -> Dict[str, Any]:
        """等待子 Agent 完成并返回结果"""
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                return {"status": "timeout", "error": "Timeout waiting for result"}

            try:
                response = await self.client.get(
                    f"{self.gateway_url}/api/tasks/{run_id}", headers=headers
                )
                response.raise_for_status()
                task_info = response.json()

                status = task_info.get("status", "running")

                if status in ["completed", "failed", "timeout"]:
                    return {
                        "status": status,
                        "result": task_info.get("result"),
                        "error": task_info.get("error"),
                        "runtimeSeconds": task_info.get("runtimeSeconds"),
                        "tokensUsed": task_info.get("tokensUsed"),
                    }

                # 等待一段时间后重试
                await asyncio.sleep(2)

            except httpx.HTTPError as e:
                logger.warning(f"Error checking task status: {e}")
                await asyncio.sleep(5)

    async def list_agents(self) -> List[Dict[str, Any]]:
        """列出所有可用的 Agent"""
        try:
            response = await self.client.get(
                f"{self.gateway_url}/api/agents",
                headers={"Authorization": f"Bearer {self.token}"},
            )
            response.raise_for_status()
            return response.json().get("agents", [])
        except httpx.HTTPError as e:
            logger.error(f"Error listing agents: {e}")
            return []

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()


class OpenClawOrchestrator:
    """
    OpenClaw 编排器

    封装了子 Agent 的创建和管理，提供简洁的接口供业务代码调用。
    """

    # Agent 配置
    AGENTS = {
        "ad_creator": {
            "name": "广告创作专家",
            "model": "ernie-4.0-8k",
            "default_timeout": 180,
        },
        "scraper": {
            "name": "数据采集员",
            "model": "ernie-3.5-8k",
            "default_timeout": 120,
        },
        "analyst": {
            "name": "数据分析师",
            "model": "ernie-4.0-8k",
            "default_timeout": 60,
        },
    }

    def __init__(self, gateway_url: str = "http://127.0.0.1:18789"):
        self.client = OpenClawClient(gateway_url=gateway_url)

    async def spawn_ad_creator(
        self, task: str, asin: Optional[str] = None, timeout: int = 180
    ) -> SpawnResult:
        """
        创建广告创作子 Agent

        Args:
            task: 任务描述
            asin: 产品 ASIN (可选)
            timeout: 超时时间

        Returns:
            SpawnResult: 执行结果
        """
        if asin:
            task = f"{task}\n\n目标 ASIN: {asin}"

        return await self.client.spawn_subagent(
            agent_id="ad_creator",
            task=task,
            model=self.AGENTS["ad_creator"]["model"],
            timeout_seconds=timeout,
            label="广告创作",
        )

    async def spawn_scraper(
        self, task: str, sub_type: str = "amazon", timeout: int = 120
    ) -> SpawnResult:
        """
        创建数据采集子 Agent

        Args:
            task: 任务描述
            sub_type: 采集类型 (amazon, yp, keyword)
            timeout: 超时时间

        Returns:
            SpawnResult: 执行结果
        """
        task_with_type = f"[{sub_type.upper()}采集] {task}"

        return await self.client.spawn_subagent(
            agent_id="scraper",
            task=task_with_type,
            model=self.AGENTS["scraper"]["model"],
            timeout_seconds=timeout,
            label=f"{sub_type}采集",
        )

    async def spawn_analyst(
        self, task: str, analysis_type: str = "general", timeout: int = 60
    ) -> SpawnResult:
        """
        创建数据分析子 Agent

        Args:
            task: 任务描述
            analysis_type: 分析类型 (ad_performance, product_performance, etc.)
            timeout: 超时时间

        Returns:
            SpawnResult: 执行结果
        """
        task_with_type = f"[{analysis_type}分析] {task}"

        return await self.client.spawn_subagent(
            agent_id="analyst",
            task=task_with_type,
            model=self.AGENTS["analyst"]["model"],
            timeout_seconds=timeout,
            label=analysis_type,
        )

    async def spawn_multiple(self, tasks: List[Dict[str, Any]]) -> List[SpawnResult]:
        """
        并行创建多个子 Agent

        Args:
            tasks: 任务列表，每个任务包含:
                - agent_id: Agent ID
                - task: 任务描述
                - timeout: 超时时间 (可选)

        Returns:
            List[SpawnResult]: 结果列表
        """
        coroutines = []

        for t in tasks:
            agent_id = t.get("agent_id")
            task = t.get("task")
            timeout = t.get("timeout", 120)
            model = self.AGENTS.get(agent_id, {}).get("model")

            coroutines.append(
                self.client.spawn_subagent(
                    agent_id=agent_id, task=task, model=model, timeout_seconds=timeout
                )
            )

        return await asyncio.gather(*coroutines)

    async def close(self):
        """关闭客户端"""
        await self.client.close()


class OpenClawCLI:
    """
    OpenClaw CLI 封装

    提供通过命令行调用 OpenClaw 的方式，作为 HTTP API 的备选方案。
    """

    @staticmethod
    def spawn_subagent(
        agent_id: str, task: str, model: Optional[str] = None, timeout: int = 300
    ) -> Dict[str, Any]:
        """
        通过 CLI 创建子 Agent

        使用 openclaw agent 命令执行任务
        """
        import shutil, os
        openclaw_cmd = shutil.which("openclaw")
        if not openclaw_cmd:
            for c in [os.path.expanduser("~\\AppData\\Roaming\\npm\\openclaw.cmd"),
                       os.path.expanduser("~\\AppData\\Roaming\\npm\\openclaw")]:
                if os.path.isfile(c):
                    openclaw_cmd = c
                    break
        if not openclaw_cmd:
            return {"success": False, "error": "openclaw command not found", "status": "error"}

        cmd = [
            openclaw_cmd,
            "agent",
            "--agent",
            agent_id,
            "--message",
            task,
            "--timeout",
            str(timeout),
            "--json",
        ]

        if model:
            cmd.extend(["--model", model])

        logger.info(f"Running OpenClaw CLI: {openclaw_cmd} agent --agent {agent_id}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 30,
                encoding="utf-8",
                shell=True,
            )

            if result.returncode == 0:
                return {"success": True, "output": result.stdout, "status": "completed"}
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"OpenClaw CLI error: {error_msg}")
                return {"success": False, "error": error_msg, "status": "failed"}

        except subprocess.TimeoutExpired:
            logger.error("OpenClaw CLI command timed out")
            return {"success": False, "error": "Command timed out", "status": "timeout"}
        except Exception as e:
            logger.error(f"OpenClaw CLI exception: {e}")
            return {"success": False, "error": str(e), "status": "error"}

    @staticmethod
    def list_agents() -> List[Dict[str, Any]]:
        """列出所有 Agent"""
        try:
            import shutil, os
            oc = shutil.which("openclaw") or os.path.expanduser("~\\AppData\\Roaming\\npm\\openclaw.cmd")
            if not oc:
                return []
            result = subprocess.run(
                [oc, "agents", "list", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            if result.returncode == 0:
                return json.loads(result.stdout).get("agents", [])
            return []
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            return []


# 便捷函数
async def create_ad(asin: str, task: str = None) -> SpawnResult:
    """快速创建广告"""
    orchestrator = OpenClawOrchestrator()
    try:
        task = task or f"为产品 {asin} 生成 Google Ads 广告方案"
        return await orchestrator.spawn_ad_creator(task=task, asin=asin)
    finally:
        await orchestrator.close()


async def scrape_amazon(asin: str) -> SpawnResult:
    """快速采集 Amazon 数据"""
    orchestrator = OpenClawOrchestrator()
    try:
        return await orchestrator.spawn_scraper(
            task=f"采集 Amazon 产品 {asin} 的详细信息", sub_type="amazon"
        )
    finally:
        await orchestrator.close()


async def analyze_data(task: str) -> SpawnResult:
    """快速分析数据"""
    orchestrator = OpenClawOrchestrator()
    try:
        return await orchestrator.spawn_analyst(task=task)
    finally:
        await orchestrator.close()


# 测试代码
if __name__ == "__main__":

    async def test():
        print("测试 OpenClaw 集成...")

        # 测试 CLI
        print("\n[CLI] 列出 Agent:")
        agents = OpenClawCLI.list_agents()
        for agent in agents:
            print(f"  - {agent.get('id')}: {agent.get('name')}")

        # 测试 HTTP API (需要 Gateway 运行)
        print("\n[HTTP] 测试 Gateway 连接...")
        orchestrator = OpenClawOrchestrator()
        try:
            agents = await orchestrator.client.list_agents()
            print(f"  连接成功，找到 {len(agents)} 个 Agent")
        except Exception as e:
            print(f"  连接失败: {e}")
            print("  请确保 OpenClaw Gateway 正在运行: openclaw gateway start")
        finally:
            await orchestrator.close()

    asyncio.run(test())
