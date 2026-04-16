# 广告文案生成器 v2.0

> 版本: v2.0 | 2026-03-29
> 用途: 生成与产品高度相关、有具体卖点、无空话套话的广告文案

---

## 一、核心原则

```
文案铁律:
1. 每条标题/描述都必须包含具体产品信息 → 用户读完后知道"你卖什么"
2. 禁止空泛套话 → "Premium quality", "Trusted by thousands", "Works. Proven." 全部禁止
3. 社会证明必须来自真实数据 → 没有数据就不写，绝不虚构
4. 广告组之间文案差异度 ≥ 60% → 禁止复制粘贴
5. 价格信息必须与输入一致 → 杜绝$0.00或$99错误
```

---

## 二、标题生成规则（15个，≤30字符）

### 2.1 标题结构分配

根据产品类型动态调整，不再用固定模板:

```
【礼品驱动型产品】
- 品类+场景标题: 4个 (Graduation Gift for Her, Travel Jewelry Case $9)
- 价格+价值标题: 3个 (Under $10 Gift, $9.00 Perfect Gift)
- 特性标题: 3个 (Compact Jewelry Box, Portable Case)
- 信任+配送标题: 3个 (Free Prime Shipping, 30-Day Returns)
- 行动号召标题: 2个 (Shop on Amazon, Buy Now)

【痛点驱动型产品】
- 痛点+解决方案标题: 4个 (No More Pet Stains, Eliminate Odors Fast)
- 品类+效果标题: 4个 (Pet Stain Remover $19, Best Carpet Cleaner)
- 社会证明标题: 2个 (4.5★ Vet Recommended, 10K+ Happy Pet Owners) ← 需真实数据
- 信任+配送标题: 3个 (Free Shipping, Money-Back Guarantee)
- 行动号召标题: 2个 (Try It Risk-Free, Shop Now on Amazon)

【效果驱动型产品】
- 效果+数据标题: 4个 (6 Billion CFU Probiotic, Visible Results in 14 Days)
- 成分+认证标题: 3个 (Vet-Formulated, Natural Ingredients)
- 品类标题: 3个 (Dog Joint Supplement, Probiotic for Dogs)
- 信任+配送标题: 3个 (Made in USA, Subscribe & Save 15%)
- 行动号召标题: 2个 (Try 30-Day Supply, Shop Now)
```

### 2.2 标题质量规则

```
✅ 好标题:
  "Graduation Gift for Her"     ← 明确场景+受众
  "Travel Jewelry Case $9"      ← 品类+价格
  "No More Tangled Necklaces"   ← 具体痛点
  "Fits Rings + 4 Necklaces"    ← 具体功能
  "Compact 4x4" – Velvet Lining" ← 具体参数

❌ 坏标题:
  "Nayno Nayno Travel Jewelry"   ← 品牌重复，信息量零
  "Premium Quality Gear"        ← 空泛，什么产品都能用
  "Works. Proven. Delivered."   ← 废话三连
  "Built for Performance"       ← 空泛，对首饰盒不适用
  "#1 Choice"                   ← 无法验证，违规风险
  "Amazon's Top Pick"           ← 如果不是Amazon官方标注，违规
```

### 2.3 字符数标注（强制）

```
每个标题必须标注字符数:
  1. Graduation Gift for Her (24)    ✓
  2. Travel Jewelry Case $9 (23)     ✓
  3. Compact 4x4" – Velvet Lining (29) ✓
```

---

## 三、描述生成规则（5个，≤90字符）

### 3.1 描述结构分配

```
5个描述必须覆盖以下维度（顺序不限）:

描述1 - 核心价值: 产品是什么 + 核心功能 + 价格 + CTA
描述2 - 场景/痛点: 用户问题 + 产品解决方案（仅功能型/痛点型产品需要）
描述3 - 具体卖点: 2-3个具体参数/功能（有数字的优先）
描述4 - 信任保障: 配送方式 + 退换政策 + (可选)社会证明
描述5 - 紧迫/行动: 限时/库存/配送速度 + CTA
```

### 3.2 描述质量规则

```
✅ 好描述:
  "Travel jewelry case with velvet lining. Fits rings, necklaces, earrings. $9. Free Prime." (89)
  → 有材质(velvet)、有功能(rings/necklaces/earrings)、有价格、有配送

  "Tired of tangled chains? Compact 4x4" organizer for purse. 100+ reviews. Buy on Amazon." (87)
  → 有痛点、有尺寸、有社会证明(真实)、有CTA

  "Perfect graduation gift for her. Portable jewelry case, gift box included. Ships free." (86)
  → 有场景、有功能、有附加价值(gift box)、有配送

❌ 坏描述:
  "Shop official Nayno products on Amazon. premium quality product. $9.00. Free Prime" (86)
  → "premium quality product"是空话，没有具体产品信息

  "Tired of the same problem? solves your problem. Try Nayno – rated 4.5/5 by real customers." (89)
  → "solves your problem" 连产品名都没填，模板残留

  "Nayno: premium feature. advanced design. See all features on Amazon. $9.00." (73)
  → "premium feature"是空占位符，完全没有产品信息
```

### 3.3 社会证明使用规则

```
严格分级:
- 有Amazon评分+评价数: "4.5★ with 100+ reviews"
- 有Amazon评分但无评价数: "4.5-star rated on Amazon"
- 有评价数但无具体评分: "100+ verified reviews"
- 什么都没有: 不写社会证明，用其他卖点替代

绝对禁止:
- 虚构评价数（产品只有5个评价，写100+）
- 虚构评分（产品只有3.8星，写4.5）
- "Trusted by 10K+ Buyers"（无法验证）
- "Amazon's Top Pick"（非Amazon官方标注）
- "#1 Choice" / "#1 Best Seller"（除非确实是Amazon标注）
```

### 3.4 价格信息规则

```
1. 所有价格引用必须来自输入数据，禁止猜测
2. 低价产品($0-15)强调价格: "Only $9.00", "Under $10"
3. 中价产品($15-50)可强调价值: "$29.99 for 30-day supply", "$0.97/day"
4. 高价产品($50+)强调投资回报: "One-time investment", "Pays for itself"
5. 绝对禁止: 写$0.00或任何与输入不一致的价格
```

---

## 四、广告组间去重规则

```
1. 任何两个广告组之间的标题重复率不得超过 2/15 (13%)
2. 任何两个广告组之间的描述重复率不得超过 1/5 (20%)
3. 如果检测到重复:
   - 保留在主题更匹配的广告组
   - 另一个广告组替换为新的差异化文案
4. 品牌广告组的标题/描述必须与非品牌组完全不同
```

---

## 五、广告扩展（Ad Extensions）

### 5.1 Sitelink 扩展（4-6条）

```
规则:
- 每条链接文字 ≤25字符
- 每条描述1 + 描述2 各 ≤35字符
- 必须与产品具体相关

示例（旅行首饰盒）:
  View Product Details | Compact velvet case | Fits rings & necklaces
  Customer Reviews | Verified Amazon reviews | See real customer photos
  Gift Ready Info | Comes in gift box | Perfect for any occasion
  Free Shipping | Amazon Prime eligible | Fast delivery to your door
```

### 5.2 Callout 扩展（4-6条）

```
规则: 每条 ≤25字符，必须陈述事实

示例:
  Velvet Lining – No Scratches    ← 具体材质功能
  Compact 4x4" – Fits Any Purse   ← 具体尺寸
  Gift Box Included               ← 具体附加价值
  100+ 5-Star Reviews             ← 真实数据(如有)
  Free Prime Shipping             ← 配送优势
  30-Day Easy Returns             ← 保障
```

### 5.3 Structured Snippet 扩展

```
规则: 标题 + 值(每个值≤25字符，最多10个)

示例:
  标题: Features
  值: Velvet Lining | Compact 4x4" | Lightweight | Gift Box | Portable

  标题: Perfect For
  值: Travel | Graduation Gifts | Birthday Gifts | Daily Use | Purse Storage
```
