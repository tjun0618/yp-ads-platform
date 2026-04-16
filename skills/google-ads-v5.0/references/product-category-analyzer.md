# 产品品类智能分析器 (Product Category Analyzer)

> 版本: v1.0 | 2026-03-29
> 用途: 在生成广告之前，先理解产品是什么、卖给谁、靠什么驱动购买

---

## 一、分析流程

当收到一个产品的广告需求时，**必须先执行以下分析**，再进入广告生成阶段。

### 输入数据

从用户提供的信息中提取：

```
必需字段:
- 商品名称 (Amazon标题)
- 商品价格 ($)
- 佣金率 (%)
- ASIN (如有)

可选字段（极大提升质量）:
- Amazon评分 + 评价数量
- 产品卖点/特性列表
- 目标受众
- 竞品信息
- 产品图片/A+页面描述
```

### 分析步骤

#### Step 1.1: 提取产品核心关键词（NLP）

从Amazon标题中提取有搜索价值的词，按优先级排列：

```
提取规则:
1. 删除品牌名（通常在标题最前面）
2. 删除无搜索价值的修饰词（Trending, Premium, Quality等）
3. 保留产品核心品类词（如 travel jewelry case）
4. 保留使用场景词（如 for travel, graduation gifts）
5. 保留产品特性词（如 compact, personalized, portable）

示例:
输入: "Nayno Travel Jewelry Case Graduation Gifts for Women Travel Jewelry Organizer Travel Jewelry Box Personalized Gifts Portable Trendy Stuff Birthday Gifts for Women"
→ 品类词: travel jewelry case, travel jewelry organizer, travel jewelry box, jewelry case
→ 场景词: graduation gifts for women, birthday gifts for women, for travel
→ 特性词: personalized, portable, compact (隐含), travel
→ 受众词: for women
```

#### Step 1.2: 判定产品类型

```
判断维度:
                    痛点驱动型          礼品驱动型          效果驱动型
核心购买动因         解决具体问题        送礼/仪式感         追求特定效果
用户搜索特征         "how to fix X"     "gifts for her"    "best X for Y"
典型品类            清洁剂、喂食器      首饰盒、杯子        保健品、护肤品
广告文案重点         痛点+解决方案       场合+价格+颜值      数据+证言+效果
用户旅程阶段数       4-5个              2-3个              4-5个

判断方法:
- 看Amazon标题是否包含 gift/gifts/birthday/graduation/holiday/present → 礼品驱动型
- 看Amazon标题是否包含具体功能描述（如stain remover, WiFi, automatic）→ 痛点驱动型
- 看Amazon标题是否包含效果词（如probiotic, whitening, anti-aging）→ 效果驱动型
- 混合型：同时出现多类信号，取主信号
```

#### Step 1.3: 判定客单价策略

```
佣金分析:
- 单次佣金 < $1.5: 低利润产品 → 必须极简结构（1-2个Campaign），严控CPC
- 单次佣金 $1.5-$5: 中等利润 → 标准3-4个Campaign
- 单次佣金 > $5: 高利润产品 → 可用完整5阶段结构

目标CPA设定:
- 目标CPA = 单次佣金 × 0.6~0.7（确保30-40%毛利空间）
- 但必须对比市场CPC均值，如果目标CPA < 行业最低CPC → 需要发出可行性警告
```

#### Step 1.4: 判定用户搜索画像

```
对每个产品类型，定义用户真实搜索行为:

【礼品驱动型 - 如首饰盒】
真实搜索词:
  - "graduation gifts for her" ✓（高价值）
  - "travel jewelry case" ✓（品类核心词）
  - "small jewelry box for travel" ✓（具体需求）
  - "gifts under $10" ✓（价格敏感礼品搜索）
  - "nayno travel jewelry that works" ✗（不存在这种搜索）
  - "fix nayno jewelry problem" ✗（荒谬）

【痛点驱动型 - 如清洁剂】
真实搜索词:
  - "pet urine odor remover" ✓
  - "best carpet cleaner for dog pee" ✓
  - "how to get dog smell out of couch" ✓
  - "pet stain remover that actually works" ✗（过于口语化，但可接受）
  - "buy pet stain remover solution" ✗（不自然）

【效果驱动型 - 如保健品】
真实搜索词:
  - "best probiotic for dogs" ✓
  - "dog joint supplement reviews" ✓
  - "probiotic for sensitive stomach" ✓
```

---

## 二、输出结果

分析完成后，必须输出以下结构化信息：

```yaml
产品分析报告:
  基础信息:
    品类: [travel jewelry case]
    类型: [礼品驱动型]
    核心购买驱动力: [送礼场景 > 旅行收纳需求]
    价格带: [$9.00 / 低客单价]

  盈利可行性:
    单次佣金: [$1.215]
    目标CPA: [$0.85]
    盈利难度: [高 / 中 / 低]
    可行性警告: [需要严控CPC在$0.2-0.3以内，或建议改用社媒营销]

  推荐账户结构:
    Campaign数: [2-3个]
    Campaign列表:
      - [礼品场景] 预算占比 60%
      - [品牌防守] 预算占比 25%
      - [品类功能] 预算占比 15%

  关键词方向:
    品类核心词: [travel jewelry case, jewelry organizer, portable jewelry box]
    场景词: [graduation gifts for her, birthday gifts under $10]
    品牌词: [nayno travel jewelry case, nayno jewelry organizer]
    禁止使用的词型: [fix X problem, X that works, need a X]

  文案方向:
    标题重点: [Graduation Gift, Under $10, Compact, Portable]
    描述重点: [价格低、适合送礼、Prime配送、小巧便携]
    社会证明: [仅使用Amazon实际数据，无数据则不写]
```

---

## 三、特殊产品处理规则

### 3.1 低客单价产品（佣金 < $1.5）

```
强制规则:
1. 最多2-3个Campaign（品牌 + 核心场景 + 可选测试）
2. 日预算建议不超过$10
3. CPC上限设为: 目标CPA / 预估转化次数
   - 假设预估转化率5%，则需要20次点击出1单
   - CPC上限 = $1.2 / 20 = $0.06 → 现实中很难做到
   - 实际建议: 只投品牌词（CPC可能$0.1-0.3）
4. 必须输出可行性警告
5. 建议: 如果品牌不知名，考虑放弃搜索广告，改用社媒
```

### 3.2 未知品牌（搜索量极低）

```
判断标准:
- 品牌词在关键词规划师中日搜索量 < 100
- 亚马逊排名在品类500名以外

处理规则:
1. 品牌Campaign预算降至10-15%
2. 不要在非品牌广告组中嵌入品牌名
3. 核心词聚焦品类通用词
4. 标题描述中品牌名出现不超过2次
```

### 3.3 季节性产品

```
判断标准:
- 产品标题/描述中包含特定节日/季节词（Christmas, Halloween, Summer等）
- 产品功能与特定季节强相关（如旅行用品→暑假、取暖器→冬季）

处理规则:
1. 标注适用季节
2. 建议分时段预算调整
3. 非季节时段建议暂停或降至最低预算
```

---

## 四、品类关键词模板库

> 以下为各品类的真实搜索词方向，供关键词生成阶段使用

### 礼品类（首饰盒、杯子、装饰品）

```
核心品类词: jewelry case, jewelry box, jewelry organizer, jewelry holder, travel jewelry case
场景词: graduation gifts for her, birthday gifts under $10, stocking stuffers, bridesmaid gifts, gifts for bestie
特性词: compact, portable, personalized, small, cute, velvet, trendy
受众词: for women, for her, for girls, for mom, for girlfriend
```

### 宠物用品类（喂食器、清洁剂、牵引绳）

```
核心品类词: automatic pet feeder, dog stain remover, cat litter, pet water fountain
痛点词: cat not eating while away, dog peeing on carpet, smelly cat litter
场景词: for travel, for multi-cat, for large dogs, for puppies
特性词: automatic, WiFi, app control, large capacity, quiet, waterproof
```

### 电子产品类（耳机、充电器、智能家居）

```
核心品类词: wireless earbuds, phone charger, smart speaker, portable power bank
痛点词: earbuds falling out, phone dying fast, slow charging, Bluetooth disconnecting
对比词: AirPods alternative, Samsung vs Apple, best wireless earbuds under $50
特性词: noise cancelling, waterproof, long battery, fast charging, compact
```

### 健康护理类（保健品、护肤品）

```
核心品类词: probiotic for dogs, joint supplement, face moisturizer, vitamin D drops
效果词: best probiotic for sensitive stomach, top rated joint supplement for dogs
证言方向: vet recommended, clinically proven, 4.5 stars, 10K+ reviews
警示词: (此类产品必须避免医疗声明 - cures, treats, prevents)
```
