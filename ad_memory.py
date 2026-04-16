# -*- coding: utf-8 -*-
"""
ad_memory.py — 广告生成记忆引擎

用文件系统模拟 Agent 记忆：
- 每次成功生成广告 → 记录摘要（ASIN、品牌、类目、关键词风格、结果摘要）
- 下次生成时 → 读取历史经验，注入 system prompt
- 自动维护：超过 100 条历史时，压缩旧记录为统计摘要

无需任何外部服务（CoPaw/OpenClaw），直接在 KIMI API 基础上加记忆层。
"""

import os
import json
import time
from collections import Counter

# 记忆文件路径
_MEMORY_DIR = os.path.join(os.path.dirname(__file__), "ad_memory_data")
_HISTORY_FILE = os.path.join(_MEMORY_DIR, "history.json")
_SUMMARY_FILE = os.path.join(_MEMORY_DIR, "summary.json")

MAX_HISTORY = 100  # 超过此数量时压缩


def _ensure_dir():
    os.makedirs(_MEMORY_DIR, exist_ok=True)


def _load_history():
    """加载历史记录"""
    _ensure_dir()
    if os.path.exists(_HISTORY_FILE):
        try:
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_history(records):
    """保存历史记录"""
    _ensure_dir()
    with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def record_generation(asin, brand, category, campaigns_count, keywords_sample,
                      headlines_sample, success=True, error=None):
    """
    记录一次广告生成

    Args:
        asin: 商品 ASIN
        brand: 品牌名
        category: 商品类目
        campaigns_count: 生成的广告系列数
        keywords_sample: 采样几个关键词（列表）
        headlines_sample: 采样几个标题（列表）
        success: 是否成功
        error: 错误信息（如果失败）
    """
    records = _load_history()
    records.append({
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "asin": asin,
        "brand": brand,
        "category": category,
        "campaigns_count": campaigns_count,
        "keywords_sample": keywords_sample[:5],
        "headlines_sample": headlines_sample[:5],
        "success": success,
        "error": error,
    })

    # 自动压缩
    if len(records) > MAX_HISTORY + 20:
        records = _compact_history(records)

    _save_history(records)


def get_memory_context(current_asin=None, current_brand=None, current_category=None):
    """
    获取记忆上下文，用于注入 system prompt

    Returns:
        str: 格式化的经验总结文本，可直接放入 prompt
    """
    records = _load_history()
    if not records:
        return ""

    # 统计经验
    total = len(records)
    successes = [r for r in records if r.get("success")]
    failures = [r for r in records if not r.get("success")]
    success_rate = len(successes) / total * 100 if total > 0 else 0

    # 品牌分布
    brand_counter = Counter(r.get("brand", "Unknown") for r in successes)
    top_brands = brand_counter.most_common(5)

    # 类目分布
    cat_counter = Counter(r.get("category", "Unknown") for r in successes)
    top_cats = cat_counter.most_common(5)

    # 关键词风格（收集所有成功案例的关键词）
    all_keywords = []
    for r in successes:
        all_keywords.extend(r.get("keywords_sample", []))

    # 标题风格（收集所有成功案例的标题）
    all_headlines = []
    for r in successes:
        all_headlines.extend(r.get("headlines_sample", []))

    # 相同品牌的历史经验
    brand_experience = ""
    if current_brand:
        same_brand = [r for r in successes if r.get("brand") == current_brand]
        if same_brand:
            brand_keywords = []
            brand_headlines = []
            for r in same_brand:
                brand_keywords.extend(r.get("keywords_sample", []))
                brand_headlines.extend(r.get("headlines_sample", []))
            brand_experience = f"""
### 品牌 "{current_brand}" 历史经验 ({len(same_brand)} 次成功生成)
- 使用过的关键词样例: {", ".join(brand_keywords[:8])}
- 使用过的标题样例: {", ".join(brand_headlines[:5])}
- 建议：避免重复使用相同关键词和标题，尝试新的角度。
"""

    # 相同类目的经验
    cat_experience = ""
    if current_category and current_category != "Unknown":
        same_cat = [r for r in successes if r.get("category") == current_category]
        if same_cat:
            cat_headlines = []
            for r in same_cat:
                cat_headlines.extend(r.get("headlines_sample", []))
            cat_experience = f"""
### 类目 "{current_category}" 经验 ({len(same_cat)} 次)
- 表现好的标题风格: {", ".join(cat_headlines[:8])}
"""

    # 失败教训
    failure_lessons = ""
    if failures:
        error_counter = Counter(
            (r.get("error") or "Unknown error")[:50]
            for r in failures[-10:]  # 最近10次失败
        )
        top_errors = error_counter.most_common(3)
        failure_lessons = "\n### 常见失败原因（避免重复）\n"
        for err, count in top_errors:
            failure_lessons += f"- [{count}次] {err}\n"

    # 组装上下文
    context = f"""
## 广告生成经验记忆 (共 {total} 次生成, 成功率 {success_rate:.0f}%)

### 经验概况
- 最常生成的品牌: {", ".join(f"{b}({c})" for b, c in top_brands)}
- 最常见的类目: {", ".join(f"{c}({n})" for c, n in top_cats)}
- 关键词风格参考: {", ".join(all_keywords[-15:])}
- 标题风格参考: {", ".join(all_headlines[-10:])}
{brand_experience}{cat_experience}{failure_lessons}
### 改进要求
- 不要重复使用上述已有的关键词和标题，要有创新
- 标题必须 < 30 字符，描述必须 < 90 字符（严格遵守！）
- 参考成功案例的风格，但内容必须不同
"""
    return context


def get_stats():
    """获取记忆统计信息"""
    records = _load_history()
    total = len(records)
    successes = sum(1 for r in records if r.get("success"))
    return {
        "total": total,
        "successes": successes,
        "failures": total - successes,
        "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
    }


def _compact_history(records):
    """压缩历史：保留最近 50 条完整记录，旧的转为统计"""
    if len(records) <= MAX_HISTORY:
        return records

    # 保留最近的
    recent = records[-50:]

    # 旧记录生成摘要
    old = records[:-50]
    summary = {
        "compact_from": len(records),
        "kept_recent": 50,
        "old_total": len(old),
        "old_successes": sum(1 for r in old if r.get("success")),
        "top_brands": list(Counter(r.get("brand", "?") for r in old if r.get("success")).most_common(10)),
        "top_categories": list(Counter(r.get("category", "?") for r in old if r.get("success")).most_common(10)),
    }

    _ensure_dir()
    with open(_SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return recent
