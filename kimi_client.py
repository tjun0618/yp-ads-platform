# -*- coding: utf-8 -*-
"""
kimi_client.py
==============
KIMI (Moonshot AI) API 客户端，OpenAI 兼容格式
用于调用 KIMI LLM 执行 Google Ads 技能

使用方式:
    client = KimiClient()
    result = client.chat("你好")

配置:
    在环境变量中设置:
    - KIMI_API_KEY: KIMI API Key

    或在 .env 文件中设置
"""

import os
import json
import requests
from typing import Optional, Generator

# KIMI API 配置
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_BASE_URL = os.environ.get("KIMI_BASE_URL", "https://api.moonshot.cn/v1")

# 模型配置
KIMI_MODELS = {
    "moonshot-v1-8k": {"max_tokens": 4096, "context_window": 8192},
    "moonshot-v1-32k": {"max_tokens": 4096, "context_window": 32768},
    "moonshot-v1-128k": {"max_tokens": 4096, "context_window": 131072},
    "kimi-k2.5": {"max_tokens": 8192, "context_window": 131072},
}


class KimiClient:
    """KIMI (Moonshot AI) API 客户端 — OpenAI 兼容格式"""

    def __init__(
        self,
        model: str = "kimi-k2.5",
        api_key: str = None,
        base_url: str = None,
    ):
        """
        初始化客户端

        Args:
            model: 模型名称，默认 kimi-k2.5
                   可选: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k, kimi-k2.5
            api_key: API Key (可选，默认从环境变量读取)
            base_url: API Base URL (可选，默认 https://api.moonshot.cn/v1)
        """
        self.model = model
        self.api_key = api_key or KIMI_API_KEY
        self.base_url = (base_url or KIMI_BASE_URL).rstrip("/")

        model_info = KIMI_MODELS.get(model, KIMI_MODELS["kimi-k2.5"])
        self.max_output_tokens = model_info["max_tokens"]

        if not self.api_key:
            print("[WARN] 未配置 KIMI_API_KEY")

    def chat(
        self,
        message: str,
        system: str = None,
        stream: bool = False,
        temperature: float = 1,
        max_output_tokens: int = None,
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
        if max_output_tokens is None:
            max_output_tokens = self.max_output_tokens

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stream": stream,
        }

        if stream:
            return self._chat_stream(url, payload, headers)
        else:
            resp = requests.post(url, json=payload, headers=headers, timeout=300)
            data = resp.json()

            if "error" in data:
                raise ValueError(f"KIMI API 错误: {data.get('error', {}).get('message', data)}")

            return data["choices"][0]["message"]["content"]

    def _chat_stream(
        self, url: str, payload: dict, headers: dict
    ) -> Generator[str, None, None]:
        """流式返回"""
        resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=300)

        if resp.status_code != 200:
            body = resp.text[:500]
            print(f"[ERROR] KIMI stream HTTP {resp.status_code}: {body}")
            raise ValueError(f"KIMI API HTTP 错误 {resp.status_code}: {body}")

        total_chunks = 0
        for line in resp.iter_lines():
            if line:
                decoded = line.decode("utf-8")
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            total_chunks += 1
                            yield content
                    except json.JSONDecodeError:
                        continue

        if total_chunks == 0:
            print("[ERROR] KIMI stream 0 chunks yielded!")

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
        system_prompt = f"""You are a professional Google Ads advertising strategist specializing in Amazon affiliate products.

Follow the 10-step workflow in the skill file below strictly to generate a complete advertising plan.

# Skill File

{skill_content[:10000]}

# Core Requirements

1. Product analysis must be specific, not generic
2. Keywords must be realistic search terms
3. Ad copy must include specific product info, no vague statements
4. Negative keywords must be tailored to the product category
5. Output the final advertising plan in JSON format

Please analyze the product and generate the Google Ads plan."""

        user_message = f"""# Product Information

- **ASIN**: {product_info.get("asin", "Unknown")}
- **Product Name**: {product_info.get("amz_title") or product_info.get("product_name", "Unknown")}
- **Brand**: {product_info.get("brand") or "Unknown"}
- **Price**: ${product_info.get("price") or "0"}
- **Commission Rate**: {product_info.get("commission") or "0%"}
- **Rating**: {product_info.get("rating") or "N/A"} ({product_info.get("review_count") or 0} reviews)
- **Category**: {product_info.get("category_path") or "Unknown"}
- **Brand Keywords**: {", ".join(product_info.get("brand_keywords", [])[:10]) or "None"}

### Product Bullet Points
{product_info.get("bullet_points") or "N/A"}

### Product Description
{(product_info.get("description") or "N/A")[:500]}

---

Follow the skill file workflow to generate a Google Ads advertising plan for this product.

Output the final result in JSON format, including:
- product_analysis
- profitability
- campaigns (each campaign contains ad_groups, each ad_group contains keywords, headlines, descriptions)
- account_negative_keywords
- sitelinks
- callouts
- qa_report"""

        if stream:
            result = ""
            for chunk in self.chat(
                user_message,
                system=system_prompt,
                stream=True,
                max_output_tokens=self.max_output_tokens,
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
                max_output_tokens=self.max_output_tokens,
            )


# 便捷函数
_client = None


def get_client(model: str = "kimi-k2.5") -> KimiClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = KimiClient(model=model)
    return _client


def chat(message: str, system: str = None, **kwargs) -> str:
    """便捷聊天函数"""
    return get_client().chat(message, system=system, **kwargs)


if __name__ == "__main__":
    # 测试
    print("测试 KIMI API...")
    if not KIMI_API_KEY:
        print("请设置环境变量 KIMI_API_KEY")
    else:
        client = KimiClient()
        result = client.chat("你好，请简单介绍一下自己")
        print(result)
