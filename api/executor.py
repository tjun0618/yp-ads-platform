# -*- coding: utf-8 -*-
"""
executor.py
===========

Agent 执行器，负责从配置创建 Agent 并执行任务。

使用方式:
    from api.executor import AgentExecutor, execute_agent_task

    # 方式 1: 类实例
    executor = AgentExecutor(config)
    result = await executor.execute(task)

    # 方式 2: 便捷函数
    result = execute_agent_task("generate_ads", product_info)
"""

import json
import os
import sys
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Optional
from dataclasses import dataclass, field

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "admin",
    "database": "affiliate_marketing",
    "charset": "utf8mb4",
}

# 默认技能路径
DEFAULT_SKILL_PATH = Path(r"D:\workspace\claws\google-ads-skill\SKILL-Google-Ads.md")
DEFAULT_REFS_DIR = Path(r"D:\workspace\claws\google-ads-skill\references")


@dataclass
class AgentConfig:
    """Agent 配置"""

    name: str = "default"
    model: str = "ernie-4.0-8k"
    skill_path: Optional[Path] = None
    refs_dir: Optional[Path] = None
    max_retries: int = 3
    timeout: int = 300  # 秒
    temperature: float = 0.7
    max_output_tokens: int = 16000


@dataclass
class TaskResult:
    """任务执行结果"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration: float = 0.0
    steps: list = field(default_factory=list)


class AgentExecutor:
    """
    Agent 执行器

    负责：
    - 从配置创建 Agent 客户端
    - 执行任务并处理结果
    - 支持流式输出和回调
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        初始化执行器

        Args:
            config: Agent 配置，为空时使用默认配置
        """
        self.config = config or AgentConfig()
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        """获取或创建百度千帆客户端"""
        if self._client is None:
            try:
                import os
                from qianfan_client import QianfanClient

                # 优先从环境变量读取，其次使用配置
                bearer_token = os.environ.get("QIANFAN_BEARER_TOKEN", "")
                if not bearer_token:
                    # 临时硬编码测试用
                    bearer_token = "bce-v3/ALTAK-Q4oPQbtg0DGqhhKZbeWgK/24f121628d6064d35bac5676023f7b580e05b463"

                self._client = QianfanClient(
                    model=self.config.model,
                    bearer_token=bearer_token,
                )
            except ImportError:
                raise ImportError("无法导入 qianfan_client，请确保文件存在")
        return self._client

    def _get_db(self):
        """获取数据库连接"""
        import mysql.connector

        return mysql.connector.connect(**DB_CONFIG)

    def get_product_info(self, asin: str) -> Optional[Dict[str, Any]]:
        """
        从数据库获取产品信息

        Args:
            asin: 产品 ASIN

        Returns:
            产品信息字典，不存在时返回 None
        """
        conn = self._get_db()
        cur = conn.cursor(dictionary=True)

        try:
            # 获取商品基本信息
            cur.execute(
                """
                SELECT p.asin, p.product_name, p.price, p.commission, p.tracking_url,
                       p.merchant_name, p.yp_merchant_id,
                       a.title as amz_title, a.brand, a.rating, a.review_count,
                       a.bullet_points, a.description, a.availability, a.category_path,
                       a.main_image_url
                FROM yp_us_products p
                LEFT JOIN amazon_product_details a ON p.asin = a.asin
                WHERE p.asin = %s LIMIT 1
            """,
                (asin,),
            )
            product = cur.fetchone()

            if not product:
                return None

            # 获取商户关键词
            merchant_id = str(product.get("yp_merchant_id") or "")
            if merchant_id:
                cur.execute(
                    "SELECT keyword FROM ads_merchant_keywords WHERE merchant_id = %s",
                    (merchant_id,),
                )
                product["brand_keywords"] = [r["keyword"] for r in cur.fetchall()]
            else:
                product["brand_keywords"] = []

            return product

        finally:
            cur.close()
            conn.close()

    def load_skill(self) -> tuple:
        """
        加载技能文件内容

        Returns:
            (skill_content, refs_content) 元组
        """
        skill_path = self.config.skill_path or DEFAULT_SKILL_PATH
        refs_dir = self.config.refs_dir or DEFAULT_REFS_DIR

        skill_content = ""
        if skill_path.exists():
            with open(skill_path, "r", encoding="utf-8") as f:
                skill_content = f.read()

        refs_content = ""
        ref_files = [
            "product-category-analyzer.md",
            "keyword-engine.md",
            "negative-keywords.md",
            "copy-generator.md",
            "qa-checker.md",
        ]

        for ref_file in ref_files:
            ref_path = refs_dir / ref_file
            if ref_path.exists():
                with open(ref_path, "r", encoding="utf-8") as f:
                    refs_content += f"\n\n---\n\n## {ref_file}\n\n{f.read()}"

        return skill_content, refs_content

    def execute(
        self,
        task: str,
        params: Dict[str, Any],
        on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> TaskResult:
        """
        执行任务

        Args:
            task: 任务类型 (如 "generate_ads", "chat")
            params: 任务参数
            on_progress: 进度回调函数

        Returns:
            TaskResult 对象
        """
        start_time = time.time()
        result = TaskResult(success=False, steps=[])

        try:
            if task == "generate_ads":
                return self._execute_generate_ads(params, on_progress, start_time)
            elif task == "chat":
                return self._execute_chat(params, on_progress, start_time)
            else:
                result.error = f"未知任务类型: {task}"
                result.duration = time.time() - start_time
                return result

        except Exception as e:
            result.error = str(e)
            result.duration = time.time() - start_time
            return result

    def _execute_generate_ads(
        self,
        params: Dict[str, Any],
        on_progress: Optional[Callable],
        start_time: float,
    ) -> TaskResult:
        """执行广告生成任务"""
        result = TaskResult(success=False, steps=[])
        asin = params.get("asin")

        if not asin:
            result.error = "缺少 asin 参数"
            result.duration = time.time() - start_time
            return result

        def report(text: str, extra: Optional[Dict] = None):
            result.steps.append(text)
            if on_progress:
                on_progress("progress", {"text": text, **(extra or {})})

        try:
            # Step 1: 获取产品信息
            report(f"📊 正在获取产品信息: {asin}")
            product = self.get_product_info(asin)

            if not product:
                result.error = f"找不到 ASIN {asin} 的商品信息"
                result.duration = time.time() - start_time
                return result

            report(
                f"✅ 产品: {product.get('amz_title') or product.get('product_name', '')[:50]}"
            )

            # Step 2: 加载技能
            report("📝 加载 Google Ads 技能...")
            skill_content, refs_content = self.load_skill()

            # Step 3: 调用 AI
            report("🤖 启动 AI 广告策略师...")

            client = self._get_client()

            accumulated_text = ""

            def on_chunk(chunk: str):
                nonlocal accumulated_text
                accumulated_text += chunk
                if on_progress:
                    on_progress("thinking", {"text": chunk})

            ai_result = client.chat_with_skill(
                product_info=product,
                skill_content=skill_content,
                refs_content=refs_content,
                stream=True,
                on_progress=on_chunk,
            )

            report("✅ AI 生成完成，正在解析结果...")

            # Step 4: 解析 JSON
            json_result = self._extract_json(ai_result)

            if not json_result:
                result.error = "无法从 AI 输出中提取 JSON 结果"
                result.duration = time.time() - start_time
                return result

            # Step 5: 保存到数据库
            report("💾 保存广告方案到数据库...")
            save_result = self._save_to_db(
                asin, json_result, product, params.get("force", False)
            )

            if not save_result["success"]:
                result.error = save_result.get("error", "保存失败")
                result.duration = time.time() - start_time
                return result

            result.success = True
            result.data = {
                "asin": asin,
                "campaign_count": save_result.get("campaign_count", 0),
                "ad_group_count": save_result.get("ad_group_count", 0),
                "ad_count": save_result.get("ad_count", 0),
                "target_cpa": json_result.get("product_analysis", {}).get(
                    "target_cpa", 0
                ),
            }
            result.duration = time.time() - start_time

            report("🎉 广告方案生成完成！")

            return result

        except Exception as e:
            result.error = str(e)
            result.duration = time.time() - start_time
            return result

    def _execute_chat(
        self,
        params: Dict[str, Any],
        on_progress: Optional[Callable],
        start_time: float,
    ) -> TaskResult:
        """执行对话任务"""
        result = TaskResult(success=False, steps=[])

        message = params.get("message")
        system = params.get("system")
        stream = params.get("stream", True)

        if not message:
            result.error = "缺少 message 参数"
            result.duration = time.time() - start_time
            return result

        try:
            client = self._get_client()

            if stream and on_progress:

                def on_chunk(chunk: str):
                    on_progress("thinking", {"text": chunk})

                response = client.chat(message, system=system, stream=True)
                full_response = ""
                for chunk in response:
                    full_response += chunk
                    on_chunk(chunk)
            else:
                full_response = client.chat(message, system=system, stream=False)

            result.success = True
            result.data = {"response": full_response}
            result.duration = time.time() - start_time

            return result

        except Exception as e:
            result.error = str(e)
            result.duration = time.time() - start_time
            return result

    def _extract_json(self, text: str) -> Optional[Dict]:
        """从文本中提取 JSON"""
        json_str = None

        # 尝试提取 ```json ... ```
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                json_str = text[start:end].strip()

        # 尝试提取 ``` ... ```
        if not json_str and "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                json_str = text[start:end].strip()

        # 尝试直接解析
        if not json_str:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = text[start:end]

        if not json_str:
            return None

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return None

    def _save_to_db(
        self,
        asin: str,
        json_result: Dict,
        product: Dict,
        force: bool = False,
    ) -> Dict:
        """保存广告方案到数据库"""
        import mysql.connector

        conn = self._get_db()
        cur = conn.cursor(dictionary=True)

        try:
            campaigns = json_result.get("campaigns", [])
            campaign_count = len(campaigns)
            ad_group_count = sum(len(c.get("ad_groups", [])) for c in campaigns)
            ad_count = ad_group_count * 3

            product_analysis = json_result.get("product_analysis", {})
            target_cpa = float(product_analysis.get("target_cpa", 0) or 0)

            merchant_name = product.get("merchant_name") or ""
            merchant_id = str(product.get("yp_merchant_id") or "")

            # 检查是否已存在
            cur.execute("SELECT id FROM ads_plans WHERE asin=%s", (asin,))
            exists = cur.fetchone()

            if exists and not force:
                conn.close()
                return {"success": False, "error": "方案已存在，使用 force=true 覆盖"}

            if exists:
                # 删除旧数据
                cur.execute(
                    "DELETE FROM ads_ads WHERE ad_group_id IN "
                    "(SELECT id FROM ads_ad_groups WHERE campaign_id IN "
                    "(SELECT id FROM ads_campaigns WHERE asin=%s))",
                    (asin,),
                )
                cur.execute(
                    "DELETE FROM ads_ad_groups WHERE campaign_id IN "
                    "(SELECT id FROM ads_campaigns WHERE asin=%s)",
                    (asin,),
                )
                cur.execute("DELETE FROM ads_campaigns WHERE asin=%s", (asin,))

                # 更新
                cur.execute(
                    """
                    UPDATE ads_plans SET
                        merchant_id = %s,
                        merchant_name = %s,
                        plan_status = 'completed',
                        campaign_count = %s,
                        ad_group_count = %s,
                        ad_count = %s,
                        target_cpa = %s,
                        ai_strategy_notes = %s,
                        updated_at = NOW()
                    WHERE asin = %s
                """,
                    (
                        merchant_id,
                        merchant_name,
                        campaign_count,
                        ad_group_count,
                        ad_count,
                        target_cpa,
                        json.dumps(product_analysis, ensure_ascii=False),
                        asin,
                    ),
                )
            else:
                # 插入
                cur.execute(
                    """
                    INSERT INTO ads_plans (
                        asin, merchant_id, merchant_name, plan_status,
                        campaign_count, ad_group_count, ad_count, target_cpa,
                        ai_strategy_notes, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, 'completed',
                        %s, %s, %s, %s,
                        %s, NOW(), NOW()
                    )
                """,
                    (
                        asin,
                        merchant_id,
                        merchant_name,
                        campaign_count,
                        ad_group_count,
                        ad_count,
                        target_cpa,
                        json.dumps(product_analysis, ensure_ascii=False),
                    ),
                )

            # 插入 campaigns
            for camp in campaigns:
                cur.execute(
                    """
                    INSERT INTO ads_campaigns (asin, name, budget_daily, bid_strategy, negative_keywords)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        asin,
                        camp.get("name", ""),
                        camp.get("budget_daily", 10),
                        camp.get("bid_strategy", "Manual CPC"),
                        json.dumps(
                            camp.get("campaign_negative_keywords", []),
                            ensure_ascii=False,
                        ),
                    ),
                )
                camp_id = cur.lastrowid

                # 插入 ad_groups
                for ag in camp.get("ad_groups", []):
                    cur.execute(
                        """
                        INSERT INTO ads_ad_groups (campaign_id, name, keywords, negative_keywords)
                        VALUES (%s, %s, %s, %s)
                    """,
                        (
                            camp_id,
                            ag.get("name", ""),
                            json.dumps(ag.get("keywords", []), ensure_ascii=False),
                            json.dumps(
                                ag.get("negative_keywords", []), ensure_ascii=False
                            ),
                        ),
                    )
                    ag_id = cur.lastrowid

                    # 插入 ads (3 个变体)
                    headlines = ag.get("headlines", [])
                    descriptions = ag.get("descriptions", [])

                    for variant in range(3):
                        hl = headlines[variant % len(headlines)] if headlines else {}
                        desc = (
                            descriptions[variant % len(descriptions)]
                            if descriptions
                            else {}
                        )

                        cur.execute(
                            """
                            INSERT INTO ads_ads (ad_group_id, variant, headlines, descriptions, all_chars_valid)
                            VALUES (%s, %s, %s, %s, 1)
                        """,
                            (
                                ag_id,
                                variant + 1,
                                json.dumps([hl], ensure_ascii=False),
                                json.dumps([desc], ensure_ascii=False),
                            ),
                        )

            conn.commit()

            return {
                "success": True,
                "campaign_count": campaign_count,
                "ad_group_count": ad_group_count,
                "ad_count": ad_count,
            }

        except Exception as e:
            conn.rollback()
            return {"success": False, "error": str(e)}

        finally:
            cur.close()
            conn.close()


# 便捷函数
def execute_agent_task(
    task: str,
    params: Dict[str, Any],
    config: Optional[AgentConfig] = None,
    on_progress: Optional[Callable] = None,
) -> TaskResult:
    """
    便捷函数：执行 Agent 任务

    Args:
        task: 任务类型
        params: 任务参数
        config: Agent 配置
        on_progress: 进度回调

    Returns:
        TaskResult 对象

    Example:
        result = execute_agent_task(
            "generate_ads",
            {"asin": "B0XXXXX"},
            on_progress=lambda type, data: print(data)
        )
    """
    executor = AgentExecutor(config)
    return executor.execute(task, params, on_progress)


# 任务状态管理
_task_status: Dict[str, Dict[str, Any]] = {}
_status_lock = threading.Lock()


def set_task_status(
    task_id: str,
    status: str,
    result: Optional[Dict] = None,
    error: Optional[str] = None,
):
    """设置任务状态"""
    with _status_lock:
        _task_status[task_id] = {
            "status": status,
            "result": result,
            "error": error,
            "updated_at": time.time(),
        }


def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """获取任务状态"""
    with _status_lock:
        return _task_status.get(task_id)


def clear_task_status(task_id: str):
    """清除任务状态"""
    with _status_lock:
        _task_status.pop(task_id, None)
