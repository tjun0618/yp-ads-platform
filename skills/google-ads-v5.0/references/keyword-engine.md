# 关键词生成引擎 v2.0

> 版本: v2.0 | 2026-03-29
> 用途: 替代旧版模板拼接逻辑，基于品类分析和产品理解生成真实可搜索的关键词

---

## 一、核心原则

### ❌ 禁止的关键词生成方式

```
1. 禁止模板拼接法:
   f"{brand} {product} that works"        → 没人这么搜
   f"fix {brand} {product} problem"       → 荒谬
   f"need a {brand} {product}"            → 不自然
   f"{brand} {product} features"          → 只有iPhone才有搜索量

2. 禁止情绪词当关键词:
   "worried about pet while at work"      → 用户搜场景，不搜情绪
   "embarrassed by pet odors"             → 过于戏剧化
   "struggling with tangled necklaces"    → 可能有人搜，但优先用场景词替代

3. 禁止虚构搜索量:
   如果一个词你不确定有没有人搜，就不要放进去
   原则: 宁可少放5个精准词，不要放10个无效词
```

### ✅ 正确的关键词生成方式

```
1. 品类核心词 + 修饰语组合:
   "travel jewelry case" + for women → "travel jewelry case for women"
   "pet stain remover" + carpet → "pet stain remover for carpet"

2. 场景化表达（用户真实搜索方式）:
   不是 "solutions for tangled necklaces"
   而是 "travel jewelry case no tangle" 或 "tangle free jewelry holder"

3. 购买意图词组合:
   "buy" + {品类核心词} → "buy travel jewelry case"
   {品类核心词} + "under $10" → "travel jewelry case under $10"
   {品类核心词} + "on amazon" → "travel jewelry case on amazon"
```

---

## 二、关键词生成流程

### Step 2.1: 从产品分析结果获取输入

```yaml
输入（来自产品品类分析器）:
  品类核心词: [travel jewelry case, jewelry organizer, jewelry box]
  场景词: [graduation gifts, birthday gifts, travel]
  特性词: [compact, portable, personalized, small]
  受众词: [for women, for her, for girls]
  产品类型: [礼品驱动型]
  品牌名: [nayno]
  品牌知名程度: [低/未知]
```

### Step 2.2: 按广告组主题生成关键词

每个广告组的关键词必须遵循以下规则:

```
规则1: 每组 5-10 个关键词（不超过12个）
规则2: 关键词之间主题一致性 ≥ 90%
规则3: 至少50%的词必须能一眼看出"真实用户会搜"
规则4: 匹配类型分布: 2个[E] + 3-5个[P] + 1-2个[B]或BMM
规则5: 不要在一个组里混入不同意图的词
```

### Step 2.3: 各类广告组的关键词策略

#### A. 品牌组关键词（仅品牌+产品词）

```
规则:
- 只放含品牌名的词
- 不放纯品牌词（如只有"nayno"），除非品牌有搜索量
- 低知名度品牌: 只用 [E] 精确匹配
- 高知名度品牌: 可混用 [E] + [P]

低知名度品牌示例:
  [E] nayno travel jewelry case
  [E] nayno jewelry organizer
  [P] "nayno travel case"
  [P] "nayno jewelry box"

高知名度品牌示例:
  [E] brand product name
  [P] "brand product"
  [P] "buy brand product"
  [B] brand + product + category
```

#### B. 品类核心组关键词（最重要的组）

```
规则:
- 全是品类通用词，不含品牌名
- 以 [P] 词组匹配为主，覆盖核心搜索
- 选择月搜索量 > 1000 的品类词（用关键词规划师验证）

示例（旅行首饰盒）:
  [E] travel jewelry case          ← 最核心品类词
  [E] travel jewelry organizer     ← 核心同义词
  [P] "small jewelry box for travel"  ← 具体需求
  [P] "compact jewelry case"       ← 特性修饰
  [P] "jewelry roll for travel"    ← 品类变体
  [P] "portable jewelry box"       ← 同义词变体
  [P] "travel necklace case"       ← 子品类
  [B] travel + jewelry + holder    ← 广泛匹配修饰
```

#### C. 礼品场景组关键词（礼品驱动型产品核心）

```
规则:
- 聚焦送礼场合 + 价格敏感度
- 不放"for women"这种太泛的词（CPC高、转化低）
- 优先放具体场合词

示例:
  [P] "graduation gifts for her"        ← 毕业季核心词
  [P] "birthday gifts for women under $10" ← 生日+价格
  [P] "stocking stuffers for women"     ← 圣诞季
  [P] "bridesmaid gift ideas"           ← 婚礼季
  [P] "gift for bestie under $10"       ← 好友送礼
  [P] "travel jewelry case gift"        ← 品类+礼物
  [P] "small gift for girlfriend"       ← 恋爱场景
  [P] "personalized jewelry travel case" ← 个性化
```

#### D. 痛点/功能组关键词（功能驱动型产品核心）

```
规则:
- 用"用户的问题场景"而非"情绪表达"
- 不写 "that works"、"solution" 等废话后缀

正确示例（清洁剂）:
  [P] "pet urine odor remover"          ✓ 用户真实搜索
  [P] "dog pee smell removal"           ✓ 直白场景
  [P] "carpet cleaner for pet stains"   ✓ 具体场景

错误示例:
  [P] "pet odor solution that works"    ✗ 废话后缀
  [P] "fix pet smell problem"           ✗ 不自然
  [B] "need pet odor remover"           ✗ 不自然
```

#### E. 购买决策组关键词

```
规则:
- 买意图词 + 品类词组合
- 价格词 + 品类词组合

示例:
  [E] buy travel jewelry case           ← 直接购买
  [P] "travel jewelry case on amazon"   ← 平台指定
  [P] "travel jewelry case free shipping" ← 物流关注
  [P] "travel jewelry case under $10"   ← 价格筛选
  [P] "best travel jewelry case cheap"  ← 性价比
  [P] "shop travel jewelry organizer"   ← 购买意图
```

---

## 三、关键词质量自检清单

生成关键词后，对每个词执行以下检查:

```
□ 真实性检查: "如果我在Google搜这个词，会看到相关广告吗？"
  - 如果不确定 → 删除

□ 自然度检查: "读起来像人打的搜索词吗？"
  - "travel jewelry case" ✓
  - "nayno travel jewelry that works" ✗
  - "need a travel jewelry case" ✗

□ 长度检查: 关键词不超过6个词
  - "best compact travel jewelry case for women" (7词) → 拆分或删除

□ 品牌词检查: 非品牌组中不应出现品牌名
  - 品类组中出现"nayno" → 删除或移到品牌组

□ 重复检查: 不同广告组之间不应有相同或高度相似的关键词
  - 组A和组B都有"travel jewelry case" → 保留在更匹配的组
```

---

## 四、匹配类型使用规范

```
[E] 精确匹配 (Exact):
  用途: 最高价值关键词，CPC最高但转化最精准
  每组2-3个，放在品类核心词和品牌词上
  格式: [keyword]（无引号）

[P] 词组匹配 (Phrase):
  用途: 主力关键词类型，覆盖核心搜索变体
  每组3-5个，放在品类词+修饰语组合上
  格式: "keyword phrase"

[B] 广泛匹配修饰符 (BMM):
  用途: 扩展覆盖，但严格控制
  每组0-2个，放在探索性关键词上
  格式: +word1 +word2 +word3
  ⚠️ 严禁使用纯广泛匹配（无+号）

[BMM] (已淘汰，勿用):
  旧版格式 +word1 +word2 已被Google淘汰，不要使用
```
