"""
YP Affiliate 统一管理台
========================
Flask 应用入口 - Blueprint 架构

模块结构：
  config.py           - 路径常量、DB配置、全局状态
  db.py               - 数据库连接池、缓存、工具函数
  templates_shared.py - 共享CSS/导航/JS组件
  routes_products.py  - 商品列表、广告方案、广告生成API
  routes_merchants.py - Amazon采集、商户管理、商户商品
  routes_collect.py   - YP采集、作战室、下载方案
  routes_analytics.py - 投放优化、质量评分、竞品分析、YP同步

运行: python -X utf8 ads_manager.py
访问: http://localhost:5055
"""

import os
import sys


# 加载 .env 文件中的环境变量
def load_env_file():
    """手动加载 .env 文件到环境变量"""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                # 解析 KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key and value:
                        os.environ[key] = value


load_env_file()

from flask import Flask, request, jsonify, redirect, send_file

# 导入配置和数据库模块
from app_config import BASE_DIR, OUTPUT_DIR
from db import get_db, check_cache_table

# 导入 Blueprint 模块
from routes_products import bp as products_bp
from routes_merchants import bp as merchants_bp
from routes_collect import bp as collect_bp
from routes_analytics import bp as analytics_bp
from routes_agent_chat import bp as agent_chat_bp
from routes_agent_sop import bp as agent_sop_bp

app = Flask(__name__)

# 注册 Blueprint
app.register_blueprint(products_bp)
app.register_blueprint(merchants_bp)
app.register_blueprint(collect_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(agent_chat_bp)
app.register_blueprint(agent_sop_bp)


# ─── 启动控制台 ─────────────────────────────────────────────────────────────
@app.route("/launcher")
def launcher():
    """图形化启动控制台"""
    launcher_path = os.path.join(os.path.dirname(__file__), "launcher.html")
    return send_file(launcher_path, mimetype="text/html")


# ─── 服务控制 API ───────────────────────────────────────────────────────────
@app.route("/api/server/stop", methods=["POST"])
def stop_server():
    """停止服务器"""
    import threading
    import time

    def shutdown():
        time.sleep(1)  # 等待响应发送完成
        print("\n[INFO] Server stopped via /api/server/stop")
        os._exit(0)

    # 在后台线程中延迟关闭
    threading.Thread(target=shutdown, daemon=True).start()

    return jsonify({"ok": True, "message": "Server shutting down..."})


@app.route("/api/server/status")
def server_status():
    """服务器状态检查"""
    return jsonify(
        {"ok": True, "status": "running", "port": int(os.environ.get("ADS_PORT", 5055))}
    )


@app.route("/api/server/start", methods=["POST"])
def server_start():
    """
    服务器启动端点

    如果服务正在运行，返回成功。
    如果服务未运行，此端点无法访问。
    """
    return jsonify(
        {
            "ok": True,
            "status": "running",
            "message": "Service is already running",
            "port": int(os.environ.get("ADS_PORT", 5055)),
        }
    )


# ─── 全局错误处理器 ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify(
            {
                "ok": False,
                "error": "Not Found",
                "msg": f"API 接口不存在: {request.path}",
            }
        ), 404
    return redirect("/")


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify(
            {"ok": False, "error": "Internal Server Error", "msg": str(error)}
        ), 500
    return str(error), 500


@app.errorhandler(Exception)
def handle_exception(e):
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "Server Error", "msg": str(e)}), 500
    raise e


if __name__ == "__main__":
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("YP Affiliate 管理台 (Blueprint)")
    print("URL: http://localhost:5055")
    print("=" * 50)

    # 启动时检查物化缓存表
    check_cache_table()

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("ADS_PORT", 5055)),
        debug=False,
    )
