# -*- coding: utf-8 -*-
"""
main.py
=======
AI 原生系统主入口

运行: python -X utf8 main.py
访问: http://localhost:5055
"""

import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from flask import Flask, jsonify
from flask_cors import CORS

# 导入配置
from config import config

# 导入工具注册
from tools import ToolRegistry

# 导入 Agent
from agents import create_agent, OrchestratorAgent

# 导入 API 路由
from api import register_routes

# 导入 LLM 客户端
from qianfan_client import QianfanClient


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    CORS(app)

    # 加载配置
    settings = config.load_settings()
    app.config["SETTINGS"] = settings

    # 注册 API 路由
    register_routes(app)

    # 健康检查
    @app.route("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "version": settings.get("system", {}).get("version", "1.0.0"),
                "agents": list(config.load_agents().keys()),
                "tools": list(config.load_tools().keys()),
            }
        )

    # 首页
    @app.route("/")
    def index():
        return """
        <h1>YP AI System</h1>
        <p>AI 原生广告系统已启动</p>
        <h2>API 端点</h2>
        <ul>
            <li>POST /api/agent/chat - 与 Agent 对话</li>
            <li>GET /api/agent/generate_ads/&lt;asin&gt; - SSE 生成广告</li>
            <li>GET /api/agent/status - 查询任务状态</li>
            <li>GET /health - 健康检查</li>
        </ul>
        """

    return app


def init_system():
    """初始化系统"""
    print("=" * 60)
    print("YP AI System - AI 原生广告系统")
    print("=" * 60)

    # 检查配置
    settings = config.load_settings()
    print(f"[配置] 系统版本: {settings.get('system', {}).get('version')}")

    # 检查 LLM 配置
    llm_config = config.get_llm_config()
    provider = llm_config.get("default_provider")
    model = llm_config.get("default_model")
    print(f"[LLM] 默认模型: {provider}/{model}")

    # 检查数据库连接
    try:
        from tools import db_query

        result = db_query("SELECT 1 as test")
        print(f"[数据库] 连接成功")
    except Exception as e:
        print(f"[数据库] 连接失败: {e}")

    # 检查技能
    skills = config.load_skills()
    print(f"[技能] 已注册 {len(skills)} 个技能: {list(skills.keys())}")

    # 检查工具
    tools = config.load_tools()
    print(f"[工具] 已注册 {len(tools)} 个工具: {list(tools.keys())}")

    # 检查 Agent
    agents = config.load_agents()
    print(f"[Agent] 已定义 {len(agents)} 个 Agent: {list(agents.keys())}")

    print("=" * 60)


if __name__ == "__main__":
    # 初始化系统
    init_system()

    # 创建应用
    app = create_app()

    # 获取端口
    settings = config.load_settings()
    port = settings.get("api", {}).get("port", 5055)
    host = settings.get("api", {}).get("host", "0.0.0.0")

    print(f"\n[启动] 服务地址: http://localhost:{port}")
    print("[提示] 按 Ctrl+C 停止服务\n")

    # 启动服务
    app.run(host=host, port=port, debug=True, threaded=True)
