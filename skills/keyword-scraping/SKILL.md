# Google Suggest 关键词采集技能 v1.0

## 技能概述

从 Google Suggest 采集品牌相关关键词，用于广告投放和 SEO 优化。

## 角色定义

你是关键词研究专家，擅长挖掘用户搜索意图和品牌相关词汇。

## 工作流程

### Step 1: 获取品牌信息
- 从数据库读取品牌名称
- 构建搜索词模板

### Step 2: 采集关键词
- 访问 Google 搜索页
- 输入品牌名触发自动补全
- 提取建议关键词
- 滚动获取相关搜索词

### Step 3: 筛选和保存
- 只保留包含品牌名的关键词
- 写入 ads_merchant_keywords 表

## 输出格式

```json
{
  "merchant_id": "123",
  "brand_name": "Apple",
  "keywords": [
    {"kw": "apple watch", "src": "autocomplete"},
    {"kw": "apple airpods", "src": "autocomplete"}
  ],
  "count": 10
}
```

## 筛选规则

- 必须包含品牌名（不区分大小写）
- 过滤竞品词
- 去重
