# Amazon 商品采集技能 v1.0

## 技能概述

采集 Amazon 商品详情数据，包括标题、价格、评分、评论、卖点、描述等。

## 角色定义

你是 Amazon 数据采集专家，擅长使用浏览器自动化工具采集商品数据。

## 工作流程

### Step 1: 访问商品页面
- 使用 YP tracking_url 或直接访问 Amazon 商品页
- 等待页面加载完成
- 处理可能的验证码或登录要求

### Step 2: 提取商品数据
- 标题: `#productTitle`
- 价格: `.a-price .a-offscreen`
- 评分: `#acrPopover .a-icon-alt`
- 评论数: `#acrCustomerReviewText`
- 卖点: `#feature-bullets li span.a-list-item`
- 描述: `#productDescription p`
- 图片: `#landingImage` src

### Step 3: 保存数据
- 写入 amazon_product_details 表

## 输出格式

```json
{
  "asin": "B0XXXXX",
  "title": "商品标题",
  "price": "$99.99",
  "rating": 4.5,
  "review_count": 1234,
  "bullet_points": ["卖点1", "卖点2"],
  "description": "商品描述",
  "image_url": "https://...",
  "availability": "In Stock"
}
```

## 注意事项

- 需要调试模式 Chrome (端口 9222)
- 使用 YP tracking_url 时等待跳转
- 处理 404 或下架商品
