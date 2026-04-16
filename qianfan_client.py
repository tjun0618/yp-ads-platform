# -*- coding: utf-8 -*-
"""
qianfan_client.py
=================
百度千帆 API 客户端，用于调用 LLM 执行 Google Ads 技能

使用方式:
    client = QianfanClient()
    result = client.chat("你好")

配置:
    在环境变量中设置:
    - QIANFAN_AK: 百度千帆 API Key
    - QIANFAN_SK: 百度千帆 Secret Key

    或在 .env 文件中设置
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Optional, Generator

# 百度千帆 API 配置
QIANFAN_AK = os.environ.get("QIANFAN_AK", "")
QIANFAN_SK = os.environ.get("QIANFAN_SK", "")
QIANFAN_ACCESS_TOKEN = os.environ.get("QIANFAN_ACCESS_TOKEN", "")
# Bearer Token (可选，支持 "bce-v3/ALTAK-..." 格式)
QIANFAN_BEARER_TOKEN = os.environ.get("QIANFAN_BEARER_TOKEN", "")

# API 端点
TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
CHAT_URL = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat"


class QianfanClient:
    """百度千帆 API 客户端"""

    def __init__(
        self,
        model: str = "ernie-4.0-8k",
        ak: str = None,
        sk: str = None,
        bearer_token: str = None,
    ):
        """
        初始化客户端

        Args:
            model: 模型名称，默认 ernie-4.0-8k
                   可选: ernie-4.0-8k, ernie-3.5-8k, ernie-speed-8k 等
            ak: API Key (可选，默认从环境变量读取)
            sk: Secret Key (可选，默认从环境变量读取)
            bearer_token: Bearer Token (可选，支持 "bce-v3/ALTAK-..." 格式)
        """
        self.model = model
        self.ak = ak or QIANFAN_AK
        self.sk = sk or QIANFAN_SK
        self.access_token = QIANFAN_ACCESS_TOKEN
        self.bearer_token = bearer_token or QIANFAN_BEARER_TOKEN
        self.token_expires = 0

        if not self.ak and not self.access_token and not self.bearer_token:
            print("[WARN] 未配置 QIANFAN_AK/QIANFAN_SK 或 QIANFAN_BEARER_TOKEN")

    def _get_access_token(self) -> str:
        """获取 access_token"""
        # 如果有 Bearer token，直接返回
        print(
            f"[DEBUG] _get_access_token called, bearer_token: {self.bearer_token[:20] if self.bearer_token else 'None'}..."
        )
        if self.bearer_token:
            return self.bearer_token

        if self.access_token and time.time() < self.token_expires:
            return self.access_token

        if not self.ak or not self.sk:
            raise ValueError("缺少 QIANFAN_AK 或 QIANFAN_SK")

        url = f"{TOKEN_URL}?grant_type=client_credentials&client_id={self.ak}&client_secret={self.sk}"
        resp = requests.post(url, timeout=30)
        data = resp.json()

        if "error" in data:
            raise ValueError(f"获取 token 失败: {data}")

        self.access_token = data["access_token"]
        self.token_expires = time.time() + data.get("expires_in", 86400) - 300
        return self.access_token

    def chat(
        self,
        message: str,
        system: str = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
    ) -> str:
        """
        发送对话请求

        Args:
            message: 用户消息
            system: 系统提示词
            stream: 是否流式返回
            temperature: 温度参数 (0-1)
            max_output_tokens: 最大输出 token 数

        Returns:
            模型回复内容
        """
        token = self._get_access_token()

        # 模型映射
        model_endpoint = {
            "ernie-4.0-8k": "completions_pro",
            "ernie-4.0": "completions_pro",
            "ernie-3.5-8k": "completions",
            "ernie-3.5": "completions",
            "ernie-speed-8k": "ernie_speed",
            "ernie-speed": "ernie_speed",
            "ernie-lite-8k": "ernie_lite",
        }.get(self.model, "completions_pro")

        # 使用 Bearer Token 或 query parameter
        if self.bearer_token:
            url = f"{CHAT_URL}/{model_endpoint}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        else:
            url = f"{CHAT_URL}/{model_endpoint}?access_token={token}"
            headers = {"Content-Type": "application/json"}

        messages = []
        if system:
            messages.append({"role": "user", "content": system})
            messages.append(
                {"role": "assistant", "content": "好的，我会按照要求执行。"}
            )
        messages.append({"role": "user", "content": message})

        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "stream": stream,
        }

        if stream:
            print(f"[DEBUG] chat() stream mode, bearer_token={bool(self.bearer_token)}, model_endpoint={model_endpoint}")
            return self._chat_stream(url, payload, headers if self.bearer_token else {"Content-Type": "application/json"})
        else:
            resp = requests.post(url, json=payload, headers=headers, timeout=300)
            data = resp.json()

            if "error_code" in data:
                raise ValueError(f"API 错误: {data.get('error_msg', data)}")

            return data.get("result", "")

    def _chat_stream(
        self, url: str, payload: dict, headers: dict = None
    ) -> Generator[str, None, None]:
        """流式返回 — 先读取完整响应再逐行解析，避免 stream consumed 问题"""
        # 确保至少有 Content-Type
        if headers is None:
            headers = {}
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        print(f"[DEBUG] _chat_stream url: {url}")
        print(f"[DEBUG] _chat_stream headers: {headers}")

        resp = requests.post(
            url, json=payload, headers=headers, stream=True, timeout=300
        )

        print(f"[DEBUG] _chat_stream status_code: {resp.status_code}")
        print(f"[DEBUG] _chat_stream response headers: {dict(resp.headers)}")

        # 检查 HTTP 错误
        if resp.status_code != 200:
            body = resp.text[:500]
            print(f"[ERROR] _chat_stream HTTP {resp.status_code}: {body}")
            raise ValueError(f"API HTTP 错误 {resp.status_code}: {body}")

        # 先把完整响应读入内存，避免 iter_lines 后再访问 resp 内容报错
        raw_lines = []
        for line in resp.iter_lines():
            if line:
                raw_lines.append(line.decode("utf-8"))
        # 现在 resp 已经完全消费，不再需要它

        total_chunks = 0
        for line in raw_lines:
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError as e:
                    print(f"[WARN] 解析SSE行失败: {e}, line: {line[:200]}")
                    continue
                if "result" in data:
                    total_chunks += 1
                    yield data["result"]
                else:
                    print(f"[WARN] SSE行无result字段: {line[:200]}")
            elif line.startswith("data:"):
                raw = line[5:]
                if raw.strip() == "[DONE]":
                    print(f"[DEBUG] _chat_stream [DONE], total_chunks={total_chunks}")
                else:
                    print(f"[WARN] 非标准SSE行: {line[:200]}")

        if total_chunks == 0:
            print(f"[ERROR] _chat_stream 0 chunks yielded! total_lines={len(raw_lines)}")
            if raw_lines:
                print(f"[ERROR] first lines: {raw_lines[:5]}")

    def chat_with_skill(
        self,
        product_info: dict,
        skill_content: str,
        refs_content: str = "",
        stream: bool = True,
        on_progress: callable = None,
    ) -> str:
        """
        使用技能生成广告方案

        Args:
            product_info: 产品信息字典
            skill_content: 技能文件内容
            refs_content: 参考文件内容
            stream: 是否流式返回
            on_progress: 进度回调函数

        Returns:
            生成的广告方案 (JSON 字符串)
        """
        # 构建系统提示词
        system_prompt = f"""你是一位专业的 Google Ads 广告策划专家，专门为亚马逊联盟商品制作广告方案。

请严格按照以下技能文件的 10 步工作流程执行，生成完整的广告方案。

# 技能文件

{skill_content[:10000]}

# 核心要求

1. 产品分析要具体，不要泛泛而谈
2. 关键词要真实，必须是用户真正会搜索的词
3. 文案要包含具体产品信息，禁止空话套话
4. 否定关键词要按产品品类定制
5. 最后输出 JSON 格式的广告方案

请开始分析产品并生成广告方案。"""

        # 构建用户消息
        user_message = f"""# 产品信息

- **ASIN**: {product_info.get("asin", "未知")}
- **商品名称**: {product_info.get("amz_title") or product_info.get("product_name", "未知")}
- **品牌**: {product_info.get("brand") or "未知"}
- **价格**: ${product_info.get("price") or "0"}
- **佣金率**: {product_info.get("commission") or "0%"}
- **评分**: {product_info.get("rating") or "无"} ({product_info.get("review_count") or 0} 评价)
- **类目**: {product_info.get("category_path") or "未知"}
- **品牌关键词**: {", ".join(product_info.get("brand_keywords", [])[:10]) or "无"}

### 产品卖点
{product_info.get("bullet_points") or "暂无"}

### 产品描述
{(product_info.get("description") or "暂无")[:500]}

---

请按照技能文件的工作流程，为这个产品生成 Google Ads 广告方案。

最后请输出 JSON 格式的结果，包含:
- product_analysis
- profitability  
- campaigns (每个 campaign 包含 ad_groups，每个 ad_group 包含 keywords, headlines, descriptions)
- account_negative_keywords
- sitelinks
- callouts
- qa_report"""

        if stream:
            result = ""
            for chunk in self.chat(
                user_message, system=system_prompt, stream=True, max_output_tokens=2048
            ):
                result += chunk
                if on_progress:
                    on_progress(chunk)
            return result
        else:
            return self.chat(
                user_message,
                system=system_prompt,
                stream=False,
                max_output_tokens=2048,
            )


# 便捷函数
_client = None


def get_client(model: str = "ernie-4.0-8k") -> QianfanClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = QianfanClient(model=model)
    return _client


def chat(message: str, system: str = None, **kwargs) -> str:
    """便捷聊天函数"""
    return get_client().chat(message, system=system, **kwargs)


if __name__ == "__main__":
    # 测试
    print("测试百度千帆 API...")

    if not QIANFAN_AK:
        print("请设置环境变量 QIANFAN_AK 和 QIANFAN_SK")
    else:
        client = QianfanClient()
        result = client.chat("你好，请简单介绍一下自己")
        print(result)
