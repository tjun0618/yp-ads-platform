# -*- coding: utf-8 -*-
"""
routes.py
=========

Flask 路由定义，提供 API 端点。

端点:
    - POST /api/agent/chat              - 与 Agent 对话
    - GET  /api/agent/generate_ads/<asin> - SSE 生成广告
    - GET  /api/agent/status/<task_id>  - 查询任务状态

OpenClaw 端点 (使用 sessions_spawn):
    - POST /api/openclaw/spawn          - 创建子 Agent
    - POST /api/openclaw/ad             - 生成广告
    - POST /api/openclaw/scrape         - 采集数据
    - POST /api/openclaw/analyze        - 分析数据
"""

import json
import uuid
import threading
import time
import asyncio
from typing import Generator

from flask import Blueprint, request, Response, jsonify, stream_with_context

from .sse import (
    sse_progress,
    sse_thinking,
    sse_error,
    sse_done,
    sse_heartbeat,
    create_sse_response,
)
from .executor import (
    AgentExecutor,
    AgentConfig,
    TaskResult,
    execute_agent_task,
    set_task_status,
    get_task_status,
)

# 创建 Blueprint
bp = Blueprint("agent_api", __name__, url_prefix="/api/agent")

# 正在生成的 ASIN 集合（防止重复提交）
_generating = set()
_gen_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════
# POST /api/agent/chat - 与 Agent 对话
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/chat", methods=["POST"])
def chat():
    """
    与 Agent 对话

    请求体:
        {
            "message": "你好",
            "system": "可选的系统提示词",
            "stream": true,
            "model": "ernie-4.0-8k"
        }

    响应:
        - stream=true: SSE 流式返回
        - stream=false: JSON 结果
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求体"}), 400

        message = data.get("message")
        if not message:
            return jsonify({"ok": False, "error": "缺少 message 参数"}), 400

        system = data.get("system")
        stream = data.get("stream", True)
        model = data.get("model", "ernie-4.0-8k")

        config = AgentConfig(model=model)
        executor = AgentExecutor(config)

        if stream:
            return create_sse_response(_chat_stream(executor, message, system))

        # 非流式
        result = executor.execute(
            "chat", {"message": message, "system": system, "stream": False}
        )

        if result.success:
            return jsonify({"ok": True, "response": result.data.get("response", "")})
        else:
            return jsonify({"ok": False, "error": result.error}), 500

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _chat_stream(
    executor: AgentExecutor, message: str, system: str = None
) -> Generator[str, None, None]:
    """对话流式响应生成器"""

    def on_progress(msg_type: str, data: dict):
        pass  # 在 chat 中不需要进度回调

    try:
        yield sse_progress("🤖 AI 正在思考...")

        result = executor.execute(
            "chat",
            {"message": message, "system": system, "stream": True},
            on_progress=lambda t, d: None,
        )

        if result.success:
            yield sse_done({"response": result.data.get("response", "")})
        else:
            yield sse_error(result.error or "对话失败")

    except Exception as e:
        yield sse_error(str(e))


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/agent/generate_ads/<asin> - SSE 生成广告
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/generate_ads/<asin>", methods=["GET"])
def generate_ads(asin: str):
    """
    SSE 流式生成广告方案

    参数:
        asin: 产品 ASIN
        force: 是否强制覆盖 (query param, 默认 false)
        model: 模型名称 (query param, 默认 ernie-4.0-8k)

    SSE 消息类型:
        - progress: 进度消息
        - thinking: AI 思考过程
        - done: 完成消息
        - error: 错误消息
    """
    force = request.args.get("force", "0") == "1"
    model = request.args.get("model", "ernie-4.0-8k")

    # 检查是否正在生成
    with _gen_lock:
        if asin in _generating:
            return jsonify({"ok": False, "error": "正在生成中，请稍候"}), 429
        _generating.add(asin)

    # 创建任务 ID
    task_id = str(uuid.uuid4())[:8]
    set_task_status(task_id, "running")

    try:
        config = AgentConfig(model=model)
        executor = AgentExecutor(config)

        return create_sse_response(_generate_ads_stream(executor, asin, force, task_id))

    except Exception as e:
        with _gen_lock:
            _generating.discard(asin)
        set_task_status(task_id, "failed", error=str(e))
        return jsonify({"ok": False, "error": str(e)}), 500


def _generate_ads_stream(
    executor: AgentExecutor,
    asin: str,
    force: bool,
    task_id: str,
) -> Generator[str, None, None]:
    """广告生成流式响应生成器"""

    # 进度消息队列
    messages = []
    messages_lock = threading.Lock()

    def on_progress(msg_type: str, data: dict):
        with messages_lock:
            messages.append((msg_type, data))

    def run_task():
        try:
            result = executor.execute(
                "generate_ads",
                {"asin": asin, "force": force},
                on_progress=on_progress,
            )

            if result.success:
                set_task_status(task_id, "completed", result=result.data)
            else:
                set_task_status(task_id, "failed", error=result.error)

        except Exception as e:
            set_task_status(task_id, "failed", error=str(e))

        finally:
            with _gen_lock:
                _generating.discard(asin)

    # 启动后台任务
    thread = threading.Thread(target=run_task, daemon=True)
    thread.start()

    # 流式输出
    last_idx = 0
    heartbeat_counter = 0

    while thread.is_alive() or last_idx < len(messages):
        # 发送新消息
        with messages_lock:
            new_messages = messages[last_idx:]
            last_idx = len(messages)

        for msg_type, data in new_messages:
            if msg_type == "progress":
                yield sse_progress(data.get("text", ""), extra=data)
            elif msg_type == "thinking":
                yield sse_thinking(data.get("text", ""))

        # 检查任务状态
        status = get_task_status(task_id)
        if status and status["status"] in ("completed", "failed"):
            break

        # 心跳
        heartbeat_counter += 1
        if heartbeat_counter % 10 == 0:
            yield sse_heartbeat()

        time.sleep(0.1)

    # 发送最终结果
    status = get_task_status(task_id)

    if status and status["status"] == "completed":
        yield sse_done(status.get("result"))
    elif status and status["status"] == "failed":
        yield sse_error(status.get("error", "生成失败"))


# ═══════════════════════════════════════════════════════════════════════════
# GET /api/agent/status/<task_id> - 查询任务状态
# ═══════════════════════════════════════════════════════════════════════════


@bp.route("/status/<task_id>", methods=["GET"])
def get_status(task_id: str):
    """
    查询任务状态

    参数:
        task_id: 任务 ID

    响应:
        {
            "ok": true,
            "status": "running|completed|failed",
            "result": {...},  // 仅 completed 时有
            "error": "...",   // 仅 failed 时有
            "updated_at": 1234567890.0
        }
    """
    status = get_task_status(task_id)

    if not status:
        return jsonify({"ok": False, "error": "任务不存在"}), 404

    response = {
        "ok": True,
        "status": status["status"],
        "updated_at": status["updated_at"],
    }

    if status["status"] == "completed":
        response["result"] = status.get("result")
    elif status["status"] == "failed":
        response["error"] = status.get("error")

    return jsonify(response)


@bp.route("/status", methods=["GET"])
def list_status():
    """
    列出所有正在进行的任务

    响应:
        {
            "ok": true,
            "tasks": [
                {"task_id": "...", "asin": "...", "status": "running"}
            ]
        }
    """
    from .executor import _task_status, _status_lock

    tasks = []
    with _status_lock:
        for task_id, status in _task_status.items():
            if status["status"] == "running":
                tasks.append(
                    {
                        "task_id": task_id,
                        "status": status["status"],
                        "updated_at": status["updated_at"],
                    }
                )

    return jsonify({"ok": True, "tasks": tasks})


# ═══════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════


def register_routes(app, url_prefix="/api/agent"):
    """
    注册路由到 Flask 应用

    Args:
        app: Flask 应用实例
        url_prefix: URL 前缀，默认 /api/agent

    Example:
        from api import register_routes
        app = Flask(__name__)
        register_routes(app)
    """
    app.register_blueprint(bp, url_prefix=url_prefix)


# 错误处理
@bp.errorhandler(400)
def bad_request(error):
    return jsonify({"ok": False, "error": "Bad Request"}), 400


@bp.errorhandler(404)
def not_found(error):
    return jsonify({"ok": False, "error": "Not Found"}), 404


@bp.errorhandler(500)
def internal_error(error):
    return jsonify({"ok": False, "error": "Internal Server Error"}), 500


@bp.errorhandler(429)
def too_many_requests(error):
    return jsonify({"ok": False, "error": "Too Many Requests"}), 429


# ═══════════════════════════════════════════════════════════════════════════
# OpenClaw sessions_spawn 端点
# ═══════════════════════════════════════════════════════════════════════════

from openclaw_integration import OpenClawOrchestrator


def run_async(coro):
    """在同步环境中运行异步函数"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@bp.route("/openclaw/spawn", methods=["POST"])
def openclaw_spawn():
    """
    使用 sessions_spawn 创建子 Agent

    请求体:
        {
            "agent_id": "ad_creator",  // 必填
            "task": "任务描述",        // 必填
            "timeout": 180,            // 可选
            "model": "ernie-4.0-8k"   // 可选
        }

    响应:
        {
            "ok": true,
            "run_id": "xxx",
            "session_key": "agent:ad_creator:subagent:xxx",
            "status": "accepted"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求体"}), 400

        agent_id = data.get("agent_id")
        task = data.get("task")

        if not agent_id:
            return jsonify({"ok": False, "error": "缺少 agent_id"}), 400
        if not task:
            return jsonify({"ok": False, "error": "缺少 task"}), 400

        timeout = data.get("timeout", 120)
        model = data.get("model")

        # 由于 Flask 是同步的，我们需要在线程中运行异步代码
        def spawn_task():
            return run_async(_spawn_async(agent_id, task, timeout, model))

        result = spawn_task()

        return jsonify(
            {
                "ok": True,
                "run_id": result.get("run_id", ""),
                "session_key": result.get("session_key", ""),
                "status": result.get("status", "accepted"),
            }
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


async def _spawn_async(agent_id: str, task: str, timeout: int, model: str = None):
    """异步创建子 Agent"""
    orchestrator = OpenClawOrchestrator()
    try:
        result = await orchestrator.client.spawn_subagent(
            agent_id=agent_id, task=task, timeout_seconds=timeout, model=model
        )
        return {
            "success": result.success,
            "run_id": result.run_id,
            "session_key": result.session_key,
            "status": "accepted" if result.run_id else "error",
        }
    finally:
        await orchestrator.close()


@bp.route("/openclaw/ad", methods=["POST"])
def openclaw_generate_ad():
    """
    使用 OpenClaw 子 Agent 生成广告

    请求体:
        {
            "asin": "B08XYZ123",      // 必填
            "task": "额外任务描述",     // 可选
            "timeout": 180             // 可选
        }

    响应: SSE 流式
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求体"}), 400

        asin = data.get("asin")
        if not asin:
            return jsonify({"ok": False, "error": "缺少 asin"}), 400

        task = data.get("task", f"为产品 {asin} 生成 Google Ads 广告方案")
        timeout = data.get("timeout", 180)

        return create_sse_response(_openclaw_ad_stream(asin, task, timeout))

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _openclaw_ad_stream(asin: str, task: str, timeout: int):
    """OpenClaw 广告生成流"""
    yield sse_progress("🎯 正在启动广告创作子 Agent...")

    def run_spawn():
        return run_async(_spawn_async("ad_creator", task, timeout))

    result = run_spawn()

    if result.get("success"):
        yield sse_progress(f"✅ 子 Agent 已启动 (run_id: {result.get('run_id')})")
        yield sse_progress("⏳ 等待广告方案生成...")
        yield sse_done(
            {
                "asin": asin,
                "run_id": result.get("run_id"),
                "session_key": result.get("session_key"),
                "message": "广告方案生成任务已提交，请通过 run_id 查询结果",
            }
        )
    else:
        yield sse_error(f"启动子 Agent 失败: {result.get('error')}")


@bp.route("/openclaw/scrape", methods=["POST"])
def openclaw_scrape():
    """
    使用 OpenClaw 子 Agent 采集数据

    请求体:
        {
            "target": "B08XYZ123",     // 采集目标
            "type": "amazon",          // 采集类型 (amazon, yp, keyword)
            "task": "额外任务描述",     // 可选
            "timeout": 120             // 可选
        }

    响应: SSE 流式
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求体"}), 400

        target = data.get("target")
        scrape_type = data.get("type", "amazon")

        if not target:
            return jsonify({"ok": False, "error": "缺少 target"}), 400

        task = data.get("task", f"采集 {target} 的数据")
        timeout = data.get("timeout", 120)

        return create_sse_response(
            _openclaw_scrape_stream(target, scrape_type, task, timeout)
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _openclaw_scrape_stream(target: str, scrape_type: str, task: str, timeout: int):
    """OpenClaw 采集流"""
    yield sse_progress(f"🔍 正在启动 {scrape_type} 采集子 Agent...")

    def run_spawn():
        return run_async(
            _spawn_async("scraper", f"[{scrape_type.upper()}采集] {task}", timeout)
        )

    result = run_spawn()

    if result.get("success"):
        yield sse_progress(f"✅ 采集子 Agent 已启动 (run_id: {result.get('run_id')})")
        yield sse_progress("⏳ 正在采集数据...")
        yield sse_done(
            {
                "target": target,
                "type": scrape_type,
                "run_id": result.get("run_id"),
                "session_key": result.get("session_key"),
                "message": f"{scrape_type} 数据采集任务已提交",
            }
        )
    else:
        yield sse_error(f"启动采集子 Agent 失败: {result.get('error')}")


@bp.route("/openclaw/analyze", methods=["POST"])
def openclaw_analyze():
    """
    使用 OpenClaw 子 Agent 分析数据

    请求体:
        {
            "task": "分析任务描述",     // 必填
            "type": "ad_performance",  // 可选
            "timeout": 60              // 可选
        }

    响应: SSE 流式
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"ok": False, "error": "缺少请求体"}), 400

        task = data.get("task")
        if not task:
            return jsonify({"ok": False, "error": "缺少 task"}), 400

        analysis_type = data.get("type", "general")
        timeout = data.get("timeout", 60)

        return create_sse_response(
            _openclaw_analyze_stream(task, analysis_type, timeout)
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _openclaw_analyze_stream(task: str, analysis_type: str, timeout: int):
    """OpenClaw 分析流"""
    yield sse_progress("📊 正在启动数据分析子 Agent...")

    def run_spawn():
        return run_async(
            _spawn_async("analyst", f"[{analysis_type}分析] {task}", timeout)
        )

    result = run_spawn()

    if result.get("success"):
        yield sse_progress(f"✅ 分析子 Agent 已启动 (run_id: {result.get('run_id')})")
        yield sse_progress("⏳ 正在分析数据...")
        yield sse_done(
            {
                "type": analysis_type,
                "run_id": result.get("run_id"),
                "session_key": result.get("session_key"),
                "message": "数据分析任务已提交",
            }
        )
    else:
        yield sse_error(f"启动分析子 Agent 失败: {result.get('error')}")
